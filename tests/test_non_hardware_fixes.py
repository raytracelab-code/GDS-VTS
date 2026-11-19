"""Regression coverage for the non-hardware audit fixes (docs/GDS-VTS-NON-HARDWARE-FIX-REPORT.md).

Identity authority, VDR carry-forward, store resilience, finalize/export contract,
Configure telemetry/connection wiring. No real hardware, registry or network is used.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.qt.QtCore import QSettings
from app.core.models import TelemetryStatus
from app.core.vessel_identity import IdentityError, load_identity, report_identity_issues, save_identity, validate_identity
from app.vdr.model import calculate, number, report_number, rollover
from app.vdr.store import ReportStore, StoreError
from app.vdr.validation import final_issues
from app.vdr.excel import VdrExcelExporter
from app.vdr.pdf import export_pdf, import_pdf
from app.ui.pages.vdr.workspace import VdrPage
from test_vdr import fixture_report
from test_vdr_excel_export import full_excel_report

IDENTITY = dict(vessel='MV CONFIGURED', imo='9074729', client='CONFIGURED CLIENT', client_id='C-9',
                hireDate='2026-01-01', capacity='850')


@pytest.fixture
def settings(tmp_path):
    store = QSettings(str(tmp_path/'identity.ini'), QSettings.Format.IniFormat)
    yield store
    store.sync()


# --------------------------------------------------------------- identity authority
def test_identity_persists_and_validates(settings):
    assert load_identity(settings)['vessel'] == ''
    saved = save_identity(dict(IDENTITY, imo='IMO 9074729', vessel='  MV   CONFIGURED '), settings)
    assert saved['imo'] == '9074729' and saved['vessel'] == 'MV CONFIGURED'
    reread = QSettings(settings.fileName(), QSettings.Format.IniFormat)
    assert load_identity(reread) == saved
    errors = validate_identity(dict(imo='1234568', hireDate='2999-01-01', capacity='-5'))
    assert set(errors) == {'imo', 'hireDate', 'capacity'}
    with pytest.raises(IdentityError):
        save_identity(dict(IDENTITY, imo='123'), settings)
    assert load_identity(settings)['imo'] == '9074729'  # rejected save changes nothing


def test_configure_identity_panel_saves_and_notifies(qtbot, settings):
    from app.ui.pages.configure.identity_panel import IdentityPanel
    panel = IdentityPanel(settings); qtbot.addWidget(panel)
    assert not panel.save_button.isEnabled()
    panel.inputs['vessel'].setText('MV PANEL'); panel._edited()
    panel.inputs['hireDate'].set_value('2026-02-01')
    panel.inputs['imo'].setText('999'); panel._edited()
    assert not panel.save() and panel.errors['imo'].isVisibleTo(panel)
    panel.inputs['imo'].setText('9074729')
    received = []; panel.identityChanged.connect(received.append)
    assert panel.save()
    assert load_identity(settings)['vessel'] == 'MV PANEL' and received[0]['hireDate'] == '2026-02-01'


def test_vdr_screen_pdf_and_excel_share_configure_identity(qtbot, tmp_path, settings):
    save_identity(IDENTITY, settings)
    store = ReportStore(tmp_path/'reports.json', today='2026-11-19')
    report = full_excel_report(); report.update(finalized=False, identity=dict(vessel='STALE COPY', hireDate='2025-06-01'))
    store.reports[store.current] = report
    page = VdrPage(store, identity_provider=lambda: load_identity(settings)); qtbot.addWidget(page)
    assert 'MV CONFIGURED' in page.subtitle.text() and page.hire_value.text() == '01 Jan 2026'
    expected_no = report_number(page.report, load_identity(settings))
    assert expected_no == 323 and page.report_no.text() == '323'
    assert page.finalize(), 'final validation should pass'
    assert page.report['identity']['vessel'] == 'MV CONFIGURED'  # snapshot recorded at finalize
    xlsx = tmp_path/'out.xlsx'; VdrExcelExporter().export(page.report, xlsx, identity=load_identity(settings))
    sheet = load_workbook(xlsx, data_only=True)['VDR']
    assert sheet['E12'].value == 'MV CONFIGURED' and sheet['C12'].value == expected_no
    assert sheet['I12'].value.date().isoformat() == '2026-01-01'
    pdf = tmp_path/'out.pdf'; export_pdf(page._export_report(), pdf)
    from pypdf import PdfReader
    text = ''.join(p.extract_text() for p in PdfReader(str(pdf)).pages)
    assert 'MV CONFIGURED' in text and '323' in text and 'STALE COPY' not in text
    assert import_pdf(pdf)['identity']['vessel'] == 'MV CONFIGURED'


def test_finalize_blocked_without_identity_with_actionable_message(tmp_path):
    store = ReportStore(tmp_path/'reports.json', today='2026-11-18')
    store.reports[store.current] = fixture_report()
    issues = store.finalize(identity={})
    assert any('Date of Hire is not set' in i['msg'] for i in issues) and not store.report['finalized']
    assert report_identity_issues(dict(vessel='X', hireDate='2026-12-01'), '2026-11-18')  # hire after report date
    assert store.finalize(identity=IDENTITY) == [] and store.report['finalized']


def test_vjr_reads_configure_identity_on_screen_and_in_excel(qtbot, tmp_path, settings):
    from app.ui.pages.vjr_workspace import VjrPage
    from app.vjr.store import VjrStore
    from app.vjr.excel import VjrExcelExporter
    from vjr_fixture import full_report
    save_identity(IDENTITY, settings)
    store = VjrStore(tmp_path/'vjr.json'); store.report = full_report()
    provider = lambda: {k: load_identity(settings)[k] for k in ('vessel', 'imo', 'client', 'client_id', 'capacity')}
    page = VjrPage(store, identity_provider=provider); qtbot.addWidget(page)
    assert page.report['meta']['vessel'] == 'MV CONFIGURED' and page.report['meta']['imo'] == '9074729'
    assert page.editors[('meta', 'vessel')].isReadOnly()
    out = tmp_path/'vjr.xlsx'
    VjrExcelExporter(photo_root=tmp_path/'photos').export(page.report, out)
    book = load_workbook(out, data_only=True)
    assert book['4. Departure Report']['D6'].value == 'MV CONFIGURED'
    assert book['GDS Meta']['D11'].value == 'MV CONFIGURED'


def test_no_independent_identity_writer_remains():
    """Only app/core/vessel_identity.py writes vessel/* settings."""
    root = Path(__file__).resolve().parents[1]/'app'
    writers = [p for p in root.rglob('*.py') if "setValue('vessel/" in p.read_text(encoding='utf-8')
               or 'setValue("vessel/' in p.read_text(encoding='utf-8')]
    assert writers == []
    readers = [p.name for p in root.rglob('*.py') if "'vessel/name'" in p.read_text(encoding='utf-8')]
    assert readers == ['vessel_identity.py']


# ------------------------------------------------------------------ carry-forward
def _store(tmp_path, today):
    return ReportStore(tmp_path/'reports.json', today=today)


def test_carry_forward_follows_correction_of_previous_day(tmp_path):
    s = _store(tmp_path, '2026-11-17'); s.reports['2026-11-17'] = fixture_report('2026-11-17'); s.save()
    s = _store(tmp_path, '2026-11-18')
    fw = s.report['bulk'][1]
    assert fw['open'] == '5000' and s.report['eq'][0]['fm0'] == '350' and s.report['eq'][0]['total'] == '1012'
    s.mutate(lambda r: r['meta'].update(captain='Day 2 captain'))
    s.select('2026-11-17'); s.mutate(lambda r: r['bulk'][1].update(cons='1000'))   # correct day 1 closing → 4000
    s.select('2026-11-18')
    assert s.report['bulk'][1]['open'] == '4000'
    s.save(); assert _store(tmp_path, '2026-11-18').report['bulk'][1]['open'] == '4000'


def test_manual_opening_override_is_kept_and_reported(tmp_path):
    from app.vdr.model import carry_forward_status
    s = _store(tmp_path, '2026-11-17'); s.reports['2026-11-17'] = fixture_report('2026-11-17'); s.save()
    s = _store(tmp_path, '2026-11-18'); s.mutate(lambda r: r['bulk'][2].update(open='1234'))
    s.select('2026-11-17'); s.mutate(lambda r: r['bulk'][2].update(cons='10'))
    s.select('2026-11-18')
    assert s.report['bulk'][2]['open'] == '1234'
    _linked, differing = carry_forward_status(s.report, s.reports['2026-11-17'])
    assert [d[0] for d in differing] == ['LUB. OIL (ltrs) opening @0000H'] and differing[0][2] == '4990'


def test_finalized_day_is_never_rewritten_by_carry_forward(tmp_path):
    s = _store(tmp_path, '2026-11-17'); s.reports['2026-11-17'] = fixture_report('2026-11-17'); s.save()
    s = _store(tmp_path, '2026-11-18')
    s.reports['2026-11-18'] = r = rollover(s.reports['2026-11-17'], '2026-11-18')
    r.update(finalized=True, finalizedAt='x')
    s.select('2026-11-17'); s.mutate(lambda r: r['bulk'][1].update(cons='1000'))
    s.select('2026-11-18'); assert s.report['bulk'][1]['open'] == '5000'


def test_skipped_days_use_most_recent_prior_report(tmp_path):
    s = _store(tmp_path, '2026-11-10'); s.reports['2026-11-10'] = fixture_report('2026-11-10'); s.save()
    s = _store(tmp_path, '2026-11-13')
    assert s.source_day('2026-11-13') == '2026-11-10'
    assert s.report['bulk'][0]['open'] == '5650' and s.report['crew'][0]['name'] == 'Test Crew'
    assert s.report['carry']['source'] == '2026-11-10'
    s.select('2026-11-12'); s.select('2026-11-13')  # browsing creates untouched stubs …
    assert s.source_day('2026-11-13') == '2026-11-10'  # … which are never used as a source
    s.save(); assert sorted(json.loads(s.path.read_text())['reports']) == ['2026-11-10']  # nor persisted


def test_number_formatting_and_strict_decimal_comma():
    assert number('2,5') is None and number('1,250.5') == 1250.5 and number('1.000,5') is None
    assert rollover(fixture_report(), '2026-11-19')['bulk'][0]['open'] == '5650'


# ------------------------------------------------------------- store resilience
def test_overlong_text_is_refused_not_truncated(qtbot, tmp_path):
    s = _store(tmp_path, '2026-11-18'); s.reports[s.current] = fixture_report(); s.save()
    s.reports[s.current]['bulk'][0]['remarks'] = 'x'*20001  # would make the store unreadable on restart
    with pytest.raises(StoreError) as error:
        s.save()
    assert 'could not be read back' in str(error.value) and 'previously saved data is safe' in str(error.value)
    assert ReportStore(s.path, today=s.today).report['bulk'][0]['remarks'] == ''  # file on disk still the last good one
    s.reports[s.current] = fixture_report()
    page = VdrPage(s, identity_provider=lambda: IDENTITY); qtbot.addWidget(page)
    page.edit(('bulk', 0, 'remarks'), 'y'*1001)
    assert page.report['bulk'][0]['remarks'] == '' and 'too long' in page.banner_text.text()
    assert not page.banner.isHidden()


def test_one_malformed_record_is_quarantined_not_fatal(tmp_path):
    path = tmp_path/'reports.json'
    good = fixture_report('2026-11-17'); bad = fixture_report('2026-11-16'); bad['acts'][0]['act'] = 'z'*30000
    path.write_text(json.dumps(dict(schemaVersion=1, reports={'2026-11-17': good, '2026-11-16': bad})), encoding='utf-8')
    s = ReportStore(path, today='2026-11-18')
    assert '2026-11-17' in s.reports and '2026-11-16' not in s.reports and not s.load_error
    assert '2026-11-16' in s.quarantined and 'set aside' in s.notices[0]
    s.mutate(lambda r: r['meta'].update(captain='Edited')); s.save()
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['quarantined']['2026-11-16']['data']['acts'][0]['act'] == 'z'*30000  # kept verbatim


def test_corrupt_file_recovers_from_backup_and_preserves_damaged_copy(tmp_path):
    path = tmp_path/'reports.json'
    s = ReportStore(path, today='2026-11-17'); s.reports[s.current] = fixture_report('2026-11-17'); s.save()
    s = ReportStore(path, today='2026-11-17')  # successful load refreshes the .bak
    assert (tmp_path/'reports.json.bak').exists()
    path.write_text('{"reports": {broken', encoding='utf-8')
    s = ReportStore(path, today='2026-11-18')
    assert '2026-11-17' in s.reports and 'restored from the backup' in s.notices[0]
    assert list(tmp_path.glob('reports.json.damaged-*'))[0].read_text(encoding='utf-8') == '{"reports": {broken'
    s.mutate(lambda r: r['meta'].update(captain='after recovery')); s.save()  # no dead end


def test_corrupt_file_without_backup_starts_fresh_and_keeps_damaged(tmp_path):
    path = tmp_path/'reports.json'; path.write_text('not json', encoding='utf-8')
    s = ReportStore(path, today='2026-11-18')
    assert 'no usable backup' in s.notices[0] and not s.load_error
    assert list(tmp_path.glob('reports.json.damaged-*'))
    s.mutate(lambda r: r['meta'].update(captain='fresh')); s.save()


def test_permission_failure_is_explained(tmp_path, monkeypatch):
    import app.vdr.store as module
    s = _store(tmp_path, '2026-11-18'); s.reports[s.current] = fixture_report()
    def deny(*_args): raise PermissionError(13, 'Access is denied')
    monkeypatch.setattr(module.os, 'replace', deny)
    with pytest.raises(StoreError) as error:
        s.save()
    assert 'Windows denied access' in str(error.value) and 'previously saved data is safe' in str(error.value)


def test_vjr_corrupt_store_recovers_and_keeps_saving(tmp_path):
    from app.vjr.store import VjrStore
    path = tmp_path/'report.json'
    s = VjrStore(path); s.mutate(lambda r: r['meta'].update(report_id='R-1'))
    VjrStore(path)  # good load → backup
    path.write_text('{oops', encoding='utf-8')
    s = VjrStore(path)
    assert s.report['meta']['report_id'] == 'R-1' and 'restored from the backup' in s.notices[0]
    assert list(tmp_path.glob('report.json.damaged-*'))
    s.mutate(lambda r: r['meta'].update(report_id='R-2'))
    assert json.loads(path.read_text(encoding='utf-8'))['meta']['report_id'] == 'R-2'


# --------------------------------------------------------- finalize = export contract
def test_finalize_blocks_export_only_errors_then_export_succeeds(tmp_path):
    s = _store(tmp_path, '2026-11-19')
    report = full_excel_report(); report['finalized'] = False
    report['acts'][0]['lifts'] = 'abc'
    report['bulk'][1]['tr'].append(dict(to='SECOND', qty='1', mb='', ma='', tk=''))
    s.reports[s.current] = report
    issues = s.finalize(identity=IDENTITY)
    messages = ' | '.join(i['msg'] for i in issues)
    assert 'Row 1 lifts' in messages and 'transfers; template capacity = 1' in messages
    assert not s.report['finalized']
    s.mutate(lambda r: (r['acts'][0].update(lifts='1'), r['bulk'][1]['tr'].pop()))
    assert s.finalize(identity=IDENTITY) == []
    VdrExcelExporter().export(s.report, tmp_path/'ok.xlsx', identity=IDENTITY)
    export_pdf(dict(s.report, identity=IDENTITY), tmp_path/'ok.pdf')


def test_excel_lists_every_issue_not_only_the_first():
    from app.vdr.excel import ExcelExportError
    r = full_excel_report(); r['acts'][0]['lifts'] = 'abc'; r['end']['fuel'] = '12 days'
    with pytest.raises(ExcelExportError) as error:
        VdrExcelExporter().export(r, Path(os.devnull).with_suffix('.xlsx'), identity=IDENTITY)
    assert 'Row 1 lifts' in str(error.value) and 'Fuel endurance' in str(error.value)


def test_finalized_report_is_read_only_until_reopened(qtbot, tmp_path, monkeypatch):
    from app.ui.pages.vdr import workspace
    s = _store(tmp_path, '2026-11-18'); s.reports[s.current] = fixture_report()
    page = VdrPage(s, identity_provider=lambda: IDENTITY); qtbot.addWidget(page)
    assert page.finalize() and page.report['finalized']
    assert page.editors[('meta', 'captain')].isReadOnly() and page.finalize_button.text() == 'Reopen report'
    page.edit(('meta', 'captain'), 'typo'); assert page.report['finalized'] and page.report['meta']['captain'] == 'Test Captain'
    monkeypatch.setattr('app.ui.dialogs.confirm', lambda *a, **k: True)
    assert page.finalize()  # Reopen
    assert not page.report['finalized'] and not page.editors[('meta', 'captain')].isReadOnly()


def test_import_of_invalid_finalized_report_becomes_draft(tmp_path):
    s = _store(tmp_path, '2026-11-18')
    report = fixture_report(); report.update(finalized=True, finalizedAt='x'); report['bulk'][0]['tr'][0]['qty'] = 'ten'
    issues = s.import_report(report, identity=IDENTITY)
    assert issues and not s.report['finalized']


def test_time_2400_never_deletes_logged_rows(qtbot, tmp_path):
    s = _store(tmp_path, '2026-11-18'); r = fixture_report()
    r['acts'] = [dict(r['acts'][0], to=t, act=f'A{t}') for t in ('0600', '1200', '1800')]
    s.reports[s.current] = r
    page = VdrPage(s, identity_provider=lambda: IDENTITY); qtbot.addWidget(page)
    editor = page.editors[('acts', 1, 'to')]; editor.setText('2400'); page._finish_time(('acts', 1, 'to'), editor)
    assert len(page.report['acts']) == 3 and 'were kept' in page.banner_text.text()


# ------------------------------------------------------------- Configure wiring
def test_configure_telemetry_panel_shows_zero_and_units():
    from types import SimpleNamespace
    from app.ui.pages.configure.telemetry_panel import TelemetryPanel, format_value
    assert format_value('speed_knots', 0.0) == '0.0 kn' and format_value('heading', 0.0) == '000°'
    assert format_value('heading', None) == '—'
    panel = TelemetryPanel()
    frame = SimpleNamespace(**{name: None for name in panel.labels}); frame.speed_knots = 0.0; frame.heading = 0.0; frame.latitude = 5.5
    panel.update_frame(frame, TelemetryStatus.LIVE)
    assert panel.labels['speed_knots'].text() == '0.0 kn' and panel.labels['heading'].text() == '000°'
    panel.update_frame(frame, TelemetryStatus.STALE)
    assert 'STALE' in panel.subtitle.text() and not panel.labels['heading'].isEnabled()
    panel.update_frame(frame, TelemetryStatus.NO_SOURCE)
    assert panel.labels['speed_knots'].text() == '—'


class FakeTransport:
    def __init__(self, devices, ok=True):
        self.devices, self.ok, self.connected, self.disconnects = devices, ok, False, 0
        self.on_error = self.on_state = self.on_data = None
    def scan(self): return list(self.devices)
    def connect(self, device):
        if not self.ok:
            self.on_error(f'{device.port} is in use by another program.'); return False
        self.connected = True; self.on_state(True); return True
    def disconnect(self): self.disconnects += 1; self.connected = False
    def is_connected(self): return self.connected


def test_connection_panel_reports_errors_unplug_and_disconnect(qtbot):
    from app.core.models import UsbDevice
    from app.telemetry.telemetry_state import TelemetryStateService
    from app.ui.pages.configure.connection_panel import ConnectionPanel
    usb = FakeTransport([UsbDevice('COM3', 'A'), UsbDevice('COM7', 'B')], ok=False); ble = FakeTransport([])
    panel = ConnectionPanel(usb, ble, TelemetryStateService()); qtbot.addWidget(panel)
    panel.scan_usb(); panel.usb_select.setCurrentIndex(1)
    assert panel.usb_detail['Port'].text() == 'COM7'   # details follow the selection
    assert not panel.connect_usb() and 'in use by another program' in panel.usb_message.text()
    usb.ok = True; assert panel.connect_usb() and 'CONNECTED' in panel.usb_info.text() and panel.usb_disconnect.isEnabled()
    usb.on_state(False); panel.refresh()  # cable pulled: read thread reports state False
    assert 'DISCONNECTED' in panel.usb_info.text() and 'Device disconnected' in panel.usb_message.text()
    assert usb.disconnects == 1  # dead handle released via the transport's own disconnect()
    assert panel.connect_usb(); panel.usb_disconnect.click()
    assert usb.disconnects == 2 and not panel.connected['USB']


# ------------------------------------------------------------- VJR new voyage (011)
def test_vjr_new_voyage_archives_and_keeps_crew(qtbot, tmp_path, monkeypatch):
    from app.ui.pages import vjr_workspace
    from app.ui.pages.vjr_workspace import VjrPage
    from app.vjr.store import VjrStore
    from vjr_fixture import full_report
    store = VjrStore(tmp_path/'vjr'/'report.json'); store.mutate(lambda r: (r.clear(), r.update(full_report())))
    page = VjrPage(store, identity_provider=lambda: {}); qtbot.addWidget(page)
    monkeypatch.setattr('app.ui.dialogs.confirm', lambda *a, **k: True)
    assert page.new_voyage()
    archived = list((tmp_path/'vjr'/'archive').glob('journey-*.json'))
    assert len(archived) == 1 and json.loads(archived[0].read_text(encoding='utf-8'))['departure']['departure_location'] == 'Supply Base'
    assert store.report['departure']['departure_location'] == '' and store.report['progress'] == []
    assert [c['name'] for c in store.report['crew']] == ['Captain Example', 'Officer Example']
    page.undo(); assert store.report['departure']['departure_location'] == 'Supply Base'


def test_squall_list_never_reads_as_all_clear_without_feed():
    import inspect
    from app.ui.pages.nav import nav_page
    source = inspect.getsource(nav_page.NavPage._update_events)
    assert 'squall_feed_text' in source  # superseded by feed states (tests/test_remaining_p1.py)


def test_untouched_day_rebuilds_when_an_earlier_report_appears(tmp_path):
    s = _store(tmp_path, '2026-11-19')               # today auto-created blank (no earlier report)
    assert s.report['crew'][0]['name'] == ''
    s.import_report(fixture_report('2026-11-18'))   # earlier report arrives later
    s.select('2026-11-19')
    assert s.report['crew'][0]['name'] == 'Test Crew' and s.report['bulk'][1]['open'] == '5000'
