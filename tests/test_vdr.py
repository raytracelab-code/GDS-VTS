"""VDR domain, native workflow, compatibility and export regression coverage."""
import base64
from copy import deepcopy
import json
import zlib
import pytest
from app.qt.QtCore import Qt
from app.qt.QtGui import QFontInfo
from app.qt.QtWidgets import QLabel
from app.vdr.model import new_report, blank_row, calculate, normalize, minutes, rollover, validate
from app.vdr.store import ReportStore
from app.vdr.pdf import export_pdf, import_pdf
from app.ui.pages.vdr.workspace import VdrPage
from app.ui.theme import FONT_DISPLAY, FONT_BODY, FONT_DATA


def fixture_report(day='2026-11-18'):
    r = new_report(day, dict(vessel='TEST VESSEL', client='TEST CLIENT', hireDate='2026-01-01'))
    r['meta'].update(captain='Test Captain', loc24='LABUAN', fwd='2.5', aft='2.7')
    for wx in r['wx']:
        wx.update(wind='12', swell='1.2', sea='SLIGHT', sky='CLEAR', vis='10', temp='30')
    r['acts'][0].update(to='2400', act='Alongside berth', cat='Alongside berth at Supply Base', loc='LABUAN', dp='N', lifts='0', pob='5')
    r['eq'][0].update(total='1000', daily='12', fm0='100', fm24='350')
    for row in r['bulk']: row['open'] = '5000'
    r['bulk'][0].update(rcvQty='1000', rcvFrom='TEST BUNKER', rcvB='100', rcvA='1100', rcvTicket='T-001')
    r['bulk'][0]['tr'] = [dict(to='TEST PARTY', qty='100', mb='0', ma='100', tk='TR-1')]
    r['crew'][0].update(name='Test Crew', rank='Master', nat='my', age='40', ic='TEST-ID', signon='2026-11-01')
    r['ctr'][0].update(name='Test Contractor', vendor='TEST VENDOR', nat='bd', age='35', ic='TEST-PASS')
    return r


@pytest.fixture
def page(qtbot, tmp_path):
    store = ReportStore(tmp_path/'reports.json', today='2026-11-18')
    store.reports[store.current] = fixture_report()
    p = VdrPage(store)
    qtbot.addWidget(p); p.resize(1440, 800); p.show(); qtbot.wait(30)
    yield p
    p.save_timer.stop()


@pytest.mark.parametrize('value,expected', [('2400', 1440), ('0000', 0), ('630', 390), ('2460', None), ('2401', None), ('6', None), ('1261', None)])
def test_time_parse(value, expected):
    assert minutes(value) == expected


def test_calculations_and_rollover():
    r = fixture_report(); c = calculate(r)
    assert c['totalCons'] == 250 and c['bulkClose'][0] == 5650
    assert c['coverage'] == 1440 and c['actD'][0]['fromM'] == 0
    next_day = rollover(r, '2026-11-19')
    assert next_day['eq'][0]['total'] == '1012.0'
    assert next_day['eq'][0]['fm0'] == '350' and next_day['eq'][0]['fm24'] == ''
    assert next_day['bulk'][0]['open'] == '5650.0' and next_day['bulk'][0]['tr'] == []
    assert next_day['crew'] == r['crew'] and next_day['acts'] == [blank_row('acts')]
    assert not next_day['finalized']


def test_required_validation_and_invalid_values():
    assert not validate(fixture_report())
    assert {e['s'] for e in validate(new_report())} == {0, 1, 2, 5}
    r = fixture_report(); r['eq'][0]['fm24'] = '50'; r['bulk'][0]['open'] = '-2000'; r['crew'][0]['signon'] = '2025-01-01'
    assert {3, 4, 5} <= {e['s'] for e in validate(r)}


def test_store_history_across_dates_and_restart(tmp_path):
    p = tmp_path/'vdr.json'; store = ReportStore(p, today='2026-11-18')
    store.mutate(lambda r: r['meta'].update(captain='First'))
    store.select('2026-11-17'); store.mutate(lambda r: r['meta'].update(captain='Second'))
    store.select('2026-11-18'); store.undo()
    assert store.current == '2026-11-17' and store.report['meta']['captain'] == ''
    store.redo(); assert store.report['meta']['captain'] == 'Second'
    store.save(); reopened = ReportStore(p, today='2026-11-18')
    assert reopened.reports == store.reports


def test_store_does_not_overwrite_corruption(tmp_path):
    path = tmp_path/'broken.json'; path.write_text('broken')
    store = ReportStore(path, today='2026-11-18')
    with pytest.raises(OSError): store.save()
    assert path.read_text() == 'broken'


def test_finalization_edit_undo_compatibility(tmp_path):
    s = ReportStore(tmp_path/'vdr.json', today='2026-11-18'); s.reports[s.current] = fixture_report()
    assert s.finalize() == [] and s.report['finalized']
    original = deepcopy(s.report); s.save()
    assert ReportStore(s.path, today=s.today).report == original
    s.mutate(lambda r: r['meta'].update(captain='Changed'))
    assert not s.report['finalized']; s.undo(); assert s.report == original
    legacy = deepcopy(original); legacy.pop('identity')
    assert normalize(legacy)['finalized'] and normalize(legacy)['meta'] == legacy['meta']


def test_pdf_all_sections_and_round_trip(tmp_path):
    from pypdf import PdfReader
    r = fixture_report(); r.update(finalized=True, finalizedAt='2026-11-18T12:00:00Z')
    path = tmp_path/'report.pdf'; export_pdf(r, path)
    assert import_pdf(path) == r
    text = '\n'.join(p.extract_text() for p in PdfReader(path).pages)
    for title in ('Report & HSE', 'Weather condition', 'Daily operation activity log', 'Running hours', 'Bulk inventory', 'Core crew', 'Contractors'):
        assert title in text
    assert 'TEST VESSEL' in text and 'TR-1' in text and 'AMAN JUARA' not in text
    assert 'Malaysia' in text and 'Bangladesh' in text
    r['finalized'] = False
    with pytest.raises(ValueError): export_pdf(r, path)


def test_reference_pdf_metadata_import(tmp_path):
    # The exact reference serializer: UTF8 JSON -> zlib -> base64 XML.
    report = fixture_report(); report.pop('identity'); report.update(finalized=True, finalizedAt='legacy')
    payload = base64.b64encode(zlib.compress(json.dumps(report).encode()))
    path = tmp_path/'legacy.pdf'; path.write_bytes(b'%PDF-1.3\n<jspdf:metadata>'+payload+b'</jspdf:metadata>\n%%EOF')
    imported = import_pdf(path)
    assert imported['meta'] == report['meta'] and imported['finalizedAt'] == 'legacy'


def test_import_invalid_and_future_records(tmp_path):
    path = tmp_path/'bad.pdf'; path.write_bytes(b'%PDF-1.7\n<jspdf:metadata>bad=</jspdf:metadata>')
    with pytest.raises(ValueError): import_pdf(path)
    s = ReportStore(tmp_path/'reports.json', today='2026-11-18')
    with pytest.raises(ValueError): s.import_report(fixture_report('2026-11-19'))
    assert not s.report['finalized']


def test_all_sections_and_font_assignments(page):
    assert len(page.sections) == 7 and set(page.tables) == {'acts', 'eq', 'bulk', 'crew', 'ctr'}
    assert all(not s.isHidden() for s in page.sections)
    title = page.findChild(QLabel, 'pageTitle')
    assert QFontInfo(title.font()).family() == FONT_DISPLAY
    assert QFontInfo(page.editors[('meta', 'captain')].font()).family() == FONT_BODY
    assert QFontInfo(page.editors[('eq', 0, 'fm0')].font()).family() == FONT_DATA


def test_date_navigation(page):
    assert not page.next_day.isEnabled()
    page.navigate_date(-1); assert page.store.current == '2026-11-17' and page.next_day.isEnabled()
    page.navigate_date(1); assert page.report['meta']['captain'] == 'Test Captain'
    page.select_date('2026-11-19'); assert page.store.current == '2026-11-18'


def test_steps_scroll_and_navigation(page, qtbot):
    qtbot.mouseClick(page.steps_button, Qt.MouseButton.LeftButton)
    page.go_section(4); assert [not s.isHidden() for s in page.sections] == [False]*4+[True, False, False]
    assert page.nav_buttons[4].isChecked() and page.step_footer.isVisible()
    page.go_section(6); assert not page.next_step.isEnabled()
    page.set_mode('scroll'); assert all(not s.isHidden() for s in page.sections)
    page.go_section(2); qtbot.wait(250)
    assert page.scroll.verticalScrollBar().value() > 0


@pytest.mark.parametrize('group,name', [('acts',''), ('eq','GENERATOR 3'), ('bulk','CEMENT (mt)'), ('crew',''), ('ctr','')])
def test_add_remove_rows(page, group, name):
    if group == 'acts': page.edit(('acts', 0, 'to'), '1200')
    before = len(page.report[group]); page.add_row(group, name)
    assert len(page.report[group]) == before+1
    page.remove_row(group, before); assert len(page.report[group]) == before


def test_bulk_detail_and_live_computations(page):
    page.toggle_details(0); page.add_transfer(0)
    assert ('bulk', 0, 'tr', 1, 'qty') in page.editors
    page.edit(('bulk', 0, 'tr', 1, 'qty'), '50')
    assert page.computed[('closing', 0)].text() == '5,600'
    page.edit(('eq', 0, 'fm24'), '400')
    assert page.computed[('fuel', 0)].text() == '300'
    page.remove_transfer(0, 1); assert len(page.report['bulk'][0]['tr']) == 1


def test_weather_selection_copy_and_temperature(page):
    page.toggle_weather(0, 'sky', 'CLEAR'); assert page.report['wx'][0]['sky'] == ''
    page.toggle_weather(0, 'sky', 'RAINING'); page.copy_weather(1)
    assert page.report['wx'][1]['sky'] == 'RAINING' and page.report['wx'][1]['t'] == '0600H'
    page.change_temp(1, 1); assert page.report['wx'][1]['temp'] == '31'


def test_ui_undo_redo_save_finalize_download(page, monkeypatch):
    page.edit(('meta', 'captain'), 'Changed'); page.undo(); assert page.report['meta']['captain'] == 'Test Captain'
    page.redo(); assert page.report['meta']['captain'] == 'Changed'
    assert page.flush_save() and page.saved.text().startswith('Saved ')
    assert page.finalize() and page.download_button.isEnabled() and page.finalize_button.text() == 'FINALIZED'
    page.edit(('meta', 'captain'), '')
    errors = []; monkeypatch.setattr(page, 'show_errors', lambda e: errors.extend(e))
    assert not page.finalize() and errors and not page.download_button.isEnabled()


def test_activity_time_normalization_autoadd_and_2400(page):
    page.edit(('acts', 0, 'to'), '6'); e = page.editors[('acts', 0, 'to')]; e.setText('6'); page._finish_time(('acts', 0, 'to'), e)
    assert page.report['acts'][0]['to'] == '0600' and len(page.report['acts']) == 2
    page.edit(('acts', 1, 'to'), '2400'); e = page.editors[('acts', 1, 'to')]; e.setText('2400'); page._finish_time(('acts', 1, 'to'), e)
    assert not page.add_activity.isEnabled() and page.computed[('from', 1)].text() == '0600'


def test_narrow_width_preserves_columns(page, qtbot):
    page.resize(1000, 750); qtbot.wait(30)
    t = page.tables['acts']
    assert t.columnWidth(4) == 225 and t.columnWidth(3) == 240
    assert t.horizontalScrollBar().maximum() > 0


def test_keyboard_undo_redo_from_focused_field(page, qtbot):
    editor = page.editors[('meta', 'captain')]
    editor.setFocus(); editor.selectAll(); qtbot.keyClicks(editor, 'Captain A')
    qtbot.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert page.report['meta']['captain'] != 'Captain A'
    qtbot.keyClick(page.editors[('meta', 'captain')], Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert page.report['meta']['captain'] == 'Captain A'


def test_ui_pdf_download_and_import_actions(page, tmp_path, monkeypatch):
    from app.ui.pages.vdr import workspace
    page.finalize(); path = tmp_path/'download.pdf'
    monkeypatch.setattr(workspace.QFileDialog, 'getSaveFileName', lambda *a: (str(path), 'PDF'))
    page.download(); assert path.exists()
    page.edit(('meta', 'captain'), 'Different')
    monkeypatch.setattr(workspace.QFileDialog, 'getOpenFileName', lambda *a: (str(path), 'PDF'))
    monkeypatch.setattr(workspace.QMessageBox, 'question', lambda *a: workspace.QMessageBox.StandardButton.Yes)
    page.import_report()
    assert page.report['meta']['captain'] == 'Test Captain' and page.report['finalized']
    page.undo(); assert page.report['meta']['captain'] == 'Different'


def test_old_finalized_import_preserved(tmp_path):
    s = ReportStore(tmp_path/'vdr.json', today='2026-11-18')
    report = fixture_report('2024-01-01'); report.update(finalized=True, finalizedAt='2024-01-02T00:00:00Z')
    s.import_report(report); s.save()
    assert s.report == report
    assert ReportStore(s.path, today=s.today).reports['2024-01-01'] == report


def test_country_catalog_and_local_flag_assets(page):
    from app.ui.pages.vdr.sections import CATALOG
    assert len(CATALOG['countryCodes']) >= 190
    assert CATALOG['countryCodes']['Malaysia'] == 'my'
    combo = page.editors[('crew', 0, 'nat')]
    assert combo.currentData() == 'my' and combo.currentText() == 'Malaysia'
    assert not combo.itemIcon(combo.findData('bd')).isNull()


@pytest.mark.parametrize('group', ['acts', 'eq', 'bulk', 'crew', 'ctr'])
def test_wide_grids_fill_available_width_without_compressing_columns(page, qtbot, group):
    page.resize(1680, 800); page.set_mode('steps')
    page.go_section({'acts':2, 'eq':3, 'bulk':4, 'crew':5, 'ctr':6}[group]); qtbot.wait(40)
    table = page.tables[group]
    assert sum(table.columnWidth(i) for i in range(table.columnCount())) == table.viewport().width()
    assert all(table.columnWidth(i) >= v for i,v in enumerate(table.property('baseWidths')))


def test_optional_dates_can_be_cleared_from_calendar(page, qtbot):
    from app.qt.QtCore import QDate
    editor = page.editors[('hse', 'lti')]
    editor.setDate(QDate(2026, 11, 1)); assert page.report['hse']['lti'] == '2026-11-01'
    popup = editor.open_calendar()
    popup.clear_button.click(); assert page.report['hse']['lti'] == ''
