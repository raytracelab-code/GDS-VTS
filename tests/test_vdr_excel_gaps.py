"""Excel VDR gap fields reuse existing inventory and activity business rules."""
from copy import deepcopy
import json
import pytest
from app.qt.QtCore import Qt
from app.qt.QtWidgets import QAbstractItemView, QComboBox
from app.vdr.model import blank_row, calculate, derive_location_durations, new_report, normalize
from app.vdr.store import ReportStore
from app.vdr.pdf import export_pdf, import_pdf
from app.ui.pages.vdr.sections import BULK
from app.ui.pages.vdr.workspace import VdrPage
from test_vdr import fixture_report, TEST_IDENTITY


def activities(*pairs):
    return [dict(blank_row('acts'), to=to, loc=location) for to, location in pairs]


def values(table):
    return [[table.item(i,j).text() for j in range(4)] for i in range(table.rowCount())]


@pytest.mark.parametrize('pairs,expected', [
    ([('0600','DUYONG')], [('0000','0600','06:00','DUYONG')]),
    ([('0600','DUYONG'),('1200','JAMPUK')], [('0000','0600','06:00','DUYONG'),('0600','1200','06:00','JAMPUK')]),
    ([('0400','DUYONG'),('0800','DUYONG'),('1200','DUYONG'),('1800','JAMPUK'),('2400','JAMPUK')],
     [('0000','1200','12:00','DUYONG'),('1200','2400','12:00','JAMPUK')]),
    ([('0600','DUYONG'),('1200','JAMPUK'),('1800','DUYONG')],
     [('0000','0600','06:00','DUYONG'),('0600','1200','06:00','JAMPUK'),('1200','1800','06:00','DUYONG')]),
    ([('0045','A'),('1315','B')], [('0000','0045','00:45','A'),('0045','1315','12:30','B')]),
    ([('2400','A')], [('0000','2400','24:00','A')]),
    ([('bad','A')], []),
    ([('2460','A')], []),
    ([('0600','')], []),
    ([('0600','   ')], []),
    ([('0600','A'),('0500','A'),('1200','A')], [('0000','0600','06:00','A'),('0600','1200','06:00','A')]),
    ([('0600','A'),('1200',''),('1800','A')], [('0000','0600','06:00','A'),('1200','1800','06:00','A')]),
    ([('0600','A'),('0600','A')], [('0000','0600','06:00','A')]),
    ([], []),
])
def test_location_summary(pairs, expected):
    rows = activities(*pairs); before = deepcopy(rows)
    summary = derive_location_durations(rows)
    assert [tuple(r[k] for k in ('from','to','duration','location')) for r in summary] == expected
    assert all(set(r) == {'from','to','duration','location'} for r in summary)
    assert rows == before


def test_standard_bulk_order_and_default_rows_preserved():
    assert BULK[-5:] == ['SBM (bbls)', 'FOAM', 'BASE OIL (bbls)', 'NABM (bbls)', 'PREMIX (bbls)']
    assert len(BULK) == len(set(BULK))
    assert [r['name'] for r in new_report()['bulk']] == BULK[:5]


@pytest.fixture
def page(qtbot, tmp_path):
    store = ReportStore(tmp_path/'reports.json', today='2026-11-19', identity=TEST_IDENTITY)
    page = VdrPage(store, identity_provider=lambda: dict(TEST_IDENTITY)); page.resize(1440,900); qtbot.addWidget(page); page.show()
    yield page
    page.save_timer.stop()


@pytest.mark.parametrize('name', ['NABM (bbls)','PREMIX (bbls)'])
def test_standard_bulk_details_transfers_calculations_and_pdf(page, qtbot, name, tmp_path):
    page.store.reports[page.store.current] = fixture_report(page.store.current); page._rebuild()
    combo = next(w for w in page.sections[4].findChildren(QComboBox) if w.findData(name) >= 0)
    combo.activated.emit(combo.findData(name))
    index = len(page.report['bulk'])-1
    assert page.report['bulk'][index]['name'] == name
    for key, value in dict(open='100',rcvQty='20',cons='5',remarks='Test stock').items():
        page.edit(('bulk',index,key),value)
    page.toggle_details(index)
    for key, value in dict(rcvFrom='SUPPLY',rcvB='10',rcvA='30',rcvTicket='R-001').items():
        page.editors[('bulk',index,key)].textEdited.emit(value)
    page.add_transfer(index)
    for key, value in dict(to='THIRD PARTY',qty='12',mb='30',ma='42',tk='T-001').items():
        page.editors[('bulk',index,'tr',0,key)].textEdited.emit(value)
    assert calculate(page.report)['bulkClose'][index] == 103
    assert page.computed[('transfer',index)].text() == '12'
    assert page.computed[('closing',index)].text() == '103'
    row = deepcopy(page.report['bulk'][index])
    assert row['rcvFrom'] == 'SUPPLY' and row['tr'][0]['tk'] == 'T-001'
    assert normalize(page.report)['bulk'][index] == row
    page.flush_save(); assert ReportStore(page.store.path,today=page.store.today).report['bulk'][index] == row
    assert page.store.finalize() == []
    path = tmp_path/'report.pdf'; export_pdf(page.report,path)
    assert import_pdf(path)['bulk'][index] == row


@pytest.mark.parametrize('mode',['scroll','steps'])
def test_summary_in_same_activity_section_readonly_and_updates(page, qtbot, mode):
    page.set_mode(mode); page.go_section(2)
    assert len(page.sections) == len(page.nav_buttons) == 7
    assert page.sections[2].isAncestorOf(page.location_durations)
    assert page.location_durations.isVisible()
    assert page.location_durations.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    page.edit(('acts',0,'to'),'0600'); page.edit(('acts',0,'loc'),'DUYONG')
    assert values(page.location_durations) == [['0000','0600','06:00','DUYONG']]
    assert not page.location_durations.item(0,0).flags() & Qt.ItemFlag.ItemIsEditable
    count = len(page.store.undo_stack)
    page.refresh_values(); assert len(page.store.undo_stack) == count
    page.edit(('acts',0,'loc'),'JAMPUK')
    assert values(page.location_durations)[0][-1] == 'JAMPUK'
    page.undo(); assert values(page.location_durations)[0][-1] == 'DUYONG'
    page.redo(); assert values(page.location_durations)[0][-1] == 'JAMPUK'
    page.flush_save()
    saved = json.loads(page.store.path.read_text())['reports'][page.store.current]
    assert set(saved) == set(new_report()) and saved['acts'][0]['loc'] == 'JAMPUK'
    assert derive_location_durations(ReportStore(page.store.path,today=page.store.today).report['acts'])[0]['location'] == 'JAMPUK'


def test_summary_row_content_order_removal_and_validation_unchanged(page):
    rows = activities(('0400','DUYONG'),('0800','DUYONG'),('1200','DUYONG'),('1800','JAMPUK'),('2400','JAMPUK'))
    page.store.mutate(lambda r:r.update(acts=rows)); page._rebuild()
    assert values(page.location_durations) == [['0000','1200','12:00','DUYONG'],['1200','2400','12:00','JAMPUK']]
    page.remove_row('acts',0)
    assert values(page.location_durations)[0] == ['0000','1200','12:00','DUYONG']
    page.undo(); assert values(page.location_durations)[1] == ['1200','2400','12:00','JAMPUK']
    page.edit(('acts',0,'to'),'2500')
    assert values(page.location_durations)[0] == ['0000','1200','12:00','DUYONG']
    assert calculate(page.report)['actD'][0]['ok'] is False
