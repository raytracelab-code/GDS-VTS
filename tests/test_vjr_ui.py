import pytest
from app.qt.QtCore import Qt, QDate
from app.qt.QtWidgets import QLineEdit, QDateEdit, QComboBox
from app.ui.pages.vjr_workspace import VjrPage, FieldDelegate
from app.vjr.store import VjrStore
from app.vjr.schema import TABLES, CAPACITIES
from openpyxl import load_workbook
from vjr_fixture import full_report


@pytest.fixture
def page(qtbot,tmp_path):
    store=VjrStore(tmp_path/'vjr.json')
    widget=VjrPage(store,lambda:{})
    qtbot.addWidget(widget); widget.resize(1200,800); widget.show()
    return widget


def test_sections_photo_reservation_and_scrolling(page,qtbot):
    assert page.tabs.count()==7
    assert all('Guide' not in page.tabs.tabText(i) for i in range(7))
    for index in range(7):
        page.tabs.setCurrentIndex(index); qtbot.wait(10)
        assert page.tabs.currentWidget().isVisible()
    page.tabs.setCurrentIndex(4); qtbot.wait(10)
    scroll=page.tabs.currentWidget()
    assert scroll.verticalScrollBar().maximum()>0
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    assert scroll.verticalScrollBar().value()>0
    from app.qt.QtWidgets import QLabel
    assert len(page.photo_cards)==2
    assert all(card.generate_button.text()=='Generate QR' for card in page.photo_cards.values())
    assert page.excel_button.text()=='Download Excel'


def test_field_autosave_restart_and_history(page,qtbot):
    editor=page.editors[('meta','report_id')]
    qtbot.keyClicks(editor,'REPORT-123')
    assert VjrStore(page.store.path).report['meta']['report_id']=='REPORT-123'
    page.undo(); assert page.store.report['meta']['report_id']=='REPORT-12'
    page.redo(); assert page.store.report['meta']['report_id']=='REPORT-123'
    page.tabs.setCurrentIndex(4)
    page.editors[('departure','report_date')].setDate(QDate(2026,11,18))
    assert page.store.report['departure']['report_date']=='2026-11-18'
    page.flush_save(); assert VjrStore(page.store.path).report==page.store.report


@pytest.mark.parametrize('group',list(TABLES))
def test_tables_add_edit_remove_history(page,group):
    path=(group,)
    page.add_row(path,TABLES[group],CAPACITIES[group])
    table,schema=page.tables[path]
    table.item(0,0).setText('2026-11-18' if group=='progress' else '5' if group=='waypoints' else 'Test Person')
    assert page.store.report[group][0][schema[0][0]]==table.item(0,0).text()
    table.setCurrentCell(0,0); page.remove_row(path)
    assert not page.store.report[group]
    page.undo(); assert len(page.store.report[group])==1
    page.redo(); assert not page.store.report[group]


def test_shared_calculations_and_linked_arrival(page):
    page.store.report=full_report(); page.rebuild()
    crew,_=page.tables[('crew',)]; assert crew.item(0,6).text()=='19'
    departure,_=page.tables[('departure','deck')]; arrival,_=page.tables[('arrival','deck')]
    assert departure.item(0,5).text()=='60' and departure.item(0,6).text()=='6.00%'
    assert arrival.item(0,5).text()=='70'
    assert not departure.item(0,5).flags() & Qt.ItemFlag.ItemIsEditable
    assert page.editors[('arrival','captain')].isReadOnly()
    page.set_field(('departure','captain'),'Updated Captain')
    assert page.editors[('arrival','captain')].text()=='Updated Captain'
    arrival.item(0,2).setText('25')
    assert page.store.report['departure']['deck'][0]['ops']=='10'
    page.undo(); assert page.store.report['arrival']['deck'][0]['ops']=='20'


def test_invalid_values_autosave_and_export_block(page):
    page.add_row(('waypoints',),TABLES['waypoints'],30)
    table,_=page.tables[('waypoints',)]; table.item(0,0).setText('91')
    assert 'out of range' in table.item(0,0).toolTip()
    assert not page.excel_button.isEnabled() and page.errors.text()
    assert VjrStore(page.store.path).report['waypoints'][0]['lat_degree']=='91'


def test_save_dialog_export_cancel_and_filename(page,tmp_path,monkeypatch):
    from app.ui.pages import vjr_workspace as module
    page.store.report=full_report(); page.rebuild()
    captured=[]
    path=tmp_path/'download.xlsx'
    def dialog(*args):
        captured.append(args); return str(path),'Excel'
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',dialog)
    page.download_excel()
    assert path.exists() and captured[0][2]=='VJR_Acceptance_Vessel_2026-11-18.xlsx'
    book=load_workbook(path); assert book['1. Core Crew']['C8'].value=='Captain Example'; book.close()
    before=path.read_bytes()
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a:('',''))
    page.download_excel(); assert path.read_bytes()==before


def test_configured_identity_refresh(page):
    identity=dict(vessel='Configured Vessel',client='Configured Client')
    page.identity_provider=lambda:identity; page.rebuild()
    assert page.editors[('meta','vessel')].isReadOnly()
    assert page.report['meta']['vessel']=='Configured Vessel'
    identity['vessel']='Renamed Vessel'; page.refresh()
    assert page.editors[('meta','vessel')].text()=='Renamed Vessel'
    assert not page.store.report['meta']['vessel']


@pytest.mark.parametrize('group,key',[('departure','captain'),('departure','departure_remarks'),
    ('departure','arrival_remarks'),('arrival','arrival_remarks')])
def test_report_field_history_and_restart(page,qtbot,group,key):
    page.tabs.setCurrentIndex(4 if group=='departure' else 5)
    editor=page.editors[(group,key)]
    qtbot.keyClicks(editor,'X')
    assert page.store.report[group][key]=='X'
    page.undo(); assert page.store.report[group][key]==''
    page.redo(); assert VjrStore(page.store.path).report[group][key]=='X'


def test_keyboard_undo_and_independent_inventory(page,qtbot):
    page.store.report=full_report(); page.rebuild(); page.tabs.setCurrentIndex(5)
    table,_=page.tables[('arrival','inventory')]
    table.item(0,1).setText('999')
    assert page.store.report['departure']['inventory'][0]['quantity']=='100'
    table.setFocus(); qtbot.keyClick(table,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    assert page.store.report['arrival']['inventory'][0]['quantity']=='110'
    page.redo(); assert VjrStore(page.store.path).report['arrival']['inventory'][0]['quantity']=='999'
