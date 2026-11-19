"""Reliability, diagnostics and UI polish: plausibility, support bundle, backup/restore, first run,
connection diagnostics, status badges, autosave badge and 1366x768 layout checks."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from app.qt.QtCore import QSettings
from app.core import plausibility as P
from app.core.backup import BackupError, apply_settings_to, create_backup, inspect_backup, restore_backup, settings_snapshot
from app.core.support_bundle import redact_text, sanitize_settings, write_bundle
from app.telemetry.link_monitor import LinkMonitor, link_state
from app.ui.status import set_badge, tone_for
from test_vdr import TEST_IDENTITY, fixture_report


# ------------------------------------------------------------------ plausibility
@pytest.mark.parametrize('kind,value,level', [
    ('latitude', 95, 'invalid'), ('latitude', -33.9, None), ('longitude', 181, 'invalid'), ('heading', 360.5, 'invalid'),
    ('heading', 0, None), ('speed_knots', 0, None), ('speed_knots', 48, 'warning'), ('humidity_percent', 101, 'invalid'),
    ('pressure_kpa', 101.3, None), ('pressure_kpa', 85, 'warning'), ('pressure_kpa', 30, 'invalid'), ('temperature_c', 30, None),
    ('temperature_c', 55, 'warning'), ('wind_speed_knots', 120, 'warning'), ('pm25', 800, 'warning'), ('solar_power_w_m2', 1200, None),
    ('rainfall_mm_min', 'abc', None), ('wind_direction_deg', '', None)])
def test_plausibility_levels(kind, value, level):
    result = P.check(kind, value)
    assert (result[0] if result else None) == level


def test_frame_plausibility_never_changes_values():
    frame = SimpleNamespace(latitude=91.0, longitude=103.5, speed_knots=55.0, heading=0.0, cog=None)
    flagged = P.check_frame(frame)
    assert flagged['latitude'][0] == 'invalid' and flagged['speed_knots'][0] == 'warning' and 'heading' not in flagged
    assert frame.latitude == 91.0 and frame.speed_knots == 55.0


def test_vdr_soft_warnings_do_not_block_finalize(tmp_path):
    from app.vdr.store import ReportStore
    r = fixture_report(); r['eq'][0].update(daily='30', total='10'); r['bulk'][0].update(rcvQty='5000', rcvB='100', rcvA='1100')
    messages = ' | '.join(m for _s, _p, m in P.vdr_warnings(r))
    assert 'more than 24 h' in messages and 'less than today' in messages and 'more than the meter difference' in messages
    store = ReportStore(tmp_path/'r.json', today='2026-11-18', identity=TEST_IDENTITY); r2 = fixture_report(); r2['eq'][0]['daily'] = '30'
    store.reports[store.current] = r2
    assert P.vdr_warnings(r2) and store.finalize() == []  # soft: finalize still allowed


def test_vdr_field_gets_amber_flag_and_nav_markers(qtbot, tmp_path):
    from app.ui.pages.vdr.workspace import VdrPage
    from app.vdr.store import ReportStore
    store = ReportStore(tmp_path/'r.json', today='2026-11-18'); r = fixture_report(); r['eq'][0]['daily'] = '30'
    store.reports[store.current] = r
    page = VdrPage(store, identity_provider=lambda: dict(TEST_IDENTITY)); qtbot.addWidget(page)
    editor = page.editors[('eq', 0, 'daily')]
    assert editor.property('plausibility') == 'warning' and 'more than 24 h' in editor.toolTip()
    assert page.nav_buttons[3].text().endswith('▲') and page.nav_buttons[0].text().endswith('✓')


def test_vjr_plausibility_mapping():
    from app.ui.pages.vjr_workspace import PLAUSIBILITY_KIND, REQUIRED_FIELDS
    assert P.check(PLAUSIBILITY_KIND[('progress', 'speed')], '60')[0] == 'warning'
    assert P.check(PLAUSIBILITY_KIND['visibility'], '20') is None and ('departure', 'departure_date') in REQUIRED_FIELDS


# ------------------------------------------------------------------ support bundle
def test_support_bundle_redacts_and_excludes_sensitive_data(tmp_path):
    log = tmp_path/'startup.log'
    log.write_text(f'GET https://api.example/x?key=SECRET123 token=abcdef api_key: XYZ path {Path.home()}\\file\n', encoding='utf-8')
    settings = {'vessel/name': 'MV TEST', 'nav/providers/aisstream_api_key': 'K-1', 'nav/last_latitude': '5.3', 'app/first_run_complete': 'true'}
    diagnostics = {'packets': 3, 'vessel_position': [5.3, 103.2], 'auth_token': 'T'}
    path, members = write_bundle(tmp_path/'bundle.zip', settings, diagnostics, logs=[log])
    with zipfile.ZipFile(path) as z:
        text = '\n'.join(z.read(n).decode('utf-8') for n in z.namelist())
        assert set(z.namelist()) >= {'README.txt', 'build_and_runtime.json', 'settings_sanitized.json', 'diagnostics.json', 'logs/startup.log'}
        cleaned = json.loads(z.read('settings_sanitized.json'))
    assert 'SECRET123' not in text and 'abcdef' not in text and 'XYZ' not in text and 'K-1' not in text and str(Path.home()) not in text
    assert cleaned['nav/providers/aisstream_api_key'] == '[redacted]' and cleaned['nav/last_latitude'] == '[omitted: position]'
    assert '103.2' not in text and 'MV TEST' in text
    assert redact_text('Authorization: Bearer abc.def') .count('abc') == 0


def test_support_panel_exports_bundle(qtbot, tmp_path, monkeypatch):
    from app.ui.pages.configure import support_panel
    settings = QSettings(str(tmp_path/'s.ini'), QSettings.Format.IniFormat); settings.setValue('vessel/name', 'MV X')
    panel = support_panel.SupportPanel(window_provider=lambda: SimpleNamespace(diagnostics=lambda: {'packets': 1}), settings=settings)
    qtbot.addWidget(panel); out = tmp_path/'out'/'b.zip'
    monkeypatch.setattr(support_panel.QFileDialog, 'getSaveFileName', lambda *a: (str(out), ''))
    shown = []; monkeypatch.setattr('app.ui.dialogs.notify', lambda *a, **k: shown.append(a[1]))
    assert panel.bundle() == out and out.exists() and shown == ['Support bundle saved']


def test_about_text_lists_build_information():
    from app.ui.pages.configure.support_panel import about_text
    text = about_text()
    for key in ('GDS VTS: 0.9.0', 'Edition:', 'Git commit:', 'Python:', 'Qt:', 'Operating system:', 'Architecture:'):
        assert key in text


# ------------------------------------------------------------------ backup / restore
def make_data(root):
    from app.vdr.store import ReportStore
    from app.vjr.store import VjrStore
    from vjr_fixture import full_report
    store = ReportStore(root/'vdr'/'reports.json', today='2026-11-18'); store.reports[store.current] = fixture_report(); store.save()
    (root/'vdr'/'reports.json.damaged-20260101').write_text('junk')
    vjr = VjrStore(root/'vjr'/'report.json'); vjr.mutate(lambda r: (r.clear(), r.update(full_report()))); vjr.archive()
    (root/'vjr'/'attachments'/'abc').mkdir(parents=True); (root/'vjr'/'attachments'/'abc'/'photo.jpg').write_bytes(b'\xff\xd8photo')
    (root/'cache').mkdir(); (root/'cache'/'tile.bin').write_bytes(b'x')


def test_backup_contains_user_data_only(tmp_path):
    data = tmp_path/'data'; make_data(data)
    settings = QSettings(str(tmp_path/'s.ini'), QSettings.Format.IniFormat); settings.setValue('vessel/name', 'MV B'); settings.setValue('other/x', 1)
    manifest = create_backup(tmp_path/'b.zip', data, settings_snapshot(settings))
    names = {f['path'] for f in manifest['files']}
    assert {'data/vdr/reports.json', 'data/vjr/report.json', 'data/vjr/attachments/abc/photo.jpg', 'settings.json'} <= names
    assert any(n.startswith('data/vjr/archive/') for n in names)
    assert not any('damaged' in n or 'cache' in n or n.endswith('.bak') for n in names)
    summary = inspect_backup(tmp_path/'b.zip')
    assert summary['vdr_reports'] == 1 and summary['vjr_current'] and summary['vjr_archived'] == 1 and summary['photos'] == 1


def test_restore_replaces_data_and_keeps_a_safety_copy(tmp_path):
    data = tmp_path/'data'; make_data(data)
    settings = QSettings(str(tmp_path/'s.ini'), QSettings.Format.IniFormat); settings.setValue('vessel/name', 'BACKED UP')
    create_backup(tmp_path/'b.zip', data, settings_snapshot(settings))
    report = json.loads((data/'vdr'/'reports.json').read_text()); report['reports']['2026-11-18']['meta']['captain'] = 'CHANGED AFTER BACKUP'
    (data/'vdr'/'reports.json').write_text(json.dumps(report)); settings.setValue('vessel/name', 'CHANGED')
    summary, safety = restore_backup(tmp_path/'b.zip', data, tmp_path/'safety', apply_settings_to(settings))
    assert json.loads((data/'vdr'/'reports.json').read_text())['reports']['2026-11-18']['meta']['captain'] == 'Test Captain'
    assert settings.value('vessel/name') == 'BACKED UP' and safety.exists()
    assert 'CHANGED AFTER BACKUP' in zipfile.ZipFile(safety).read('data/vdr/reports.json').decode()
    assert list(data.glob('.vdr-replaced-*'))  # previous folder kept, never deleted


@pytest.mark.parametrize('damage', ['not_zip', 'no_manifest', 'checksum', 'unsafe_path', 'bad_report'])
def test_invalid_backup_is_rejected_and_data_untouched(tmp_path, damage):
    data = tmp_path/'data'; make_data(data); before = (data/'vdr'/'reports.json').read_bytes()
    good = tmp_path/'good.zip'; create_backup(good, data, {})
    bad = tmp_path/'bad.zip'
    if damage == 'not_zip':
        bad.write_bytes(b'hello')
    else:
        with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, 'w') as target:
            for info in source.infolist():
                content = source.read(info.filename)
                if damage == 'no_manifest' and info.filename == 'manifest.json':
                    continue
                if damage == 'checksum' and info.filename == 'data/vdr/reports.json':
                    content = content.replace(b'Test Captain', b'Evil Captain')
                target.writestr(info, content)
            if damage == 'unsafe_path':
                target.writestr('../escape.txt', 'x')
            if damage == 'bad_report':
                manifest = json.loads(source.read('manifest.json')); payload = b'{"reports": {"2026-11-18": {"meta": 5}}}'
                import hashlib
                for entry in manifest['files']:
                    if entry['path'] == 'data/vdr/reports.json':
                        entry['sha256'] = hashlib.sha256(payload).hexdigest()
        if damage == 'bad_report':
            with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, 'w') as target:
                for info in source.infolist():
                    if info.filename == 'manifest.json':
                        target.writestr(info, json.dumps(manifest))
                    elif info.filename == 'data/vdr/reports.json':
                        target.writestr(info, payload)
                    else:
                        target.writestr(info, source.read(info.filename))
    with pytest.raises(BackupError):
        restore_backup(bad, data, tmp_path/'safety')
    assert (data/'vdr'/'reports.json').read_bytes() == before
    assert list((tmp_path/'safety').glob('failed-restore-*'))  # failed archive kept for diagnostics


def test_restore_failing_midway_rolls_back_everything(tmp_path, monkeypatch):
    import app.core.backup as backup
    data = tmp_path/'data'; make_data(data); create_backup(tmp_path/'b.zip', data, {})
    before = {p: p.read_bytes() for p in (data/'vdr'/'reports.json', data/'vjr'/'report.json')}
    real = backup.os.replace; calls = []
    def flaky(src, dst):
        calls.append(dst)
        if str(dst).endswith('vjr') and 'incoming' in str(src):
            raise OSError('disk full')
        return real(src, dst)
    monkeypatch.setattr(backup.os, 'replace', flaky)
    with pytest.raises(BackupError):
        restore_backup(tmp_path/'b.zip', data, tmp_path/'safety')
    monkeypatch.setattr(backup.os, 'replace', real)
    assert all(p.read_bytes() == content for p, content in before.items())  # VDR rolled back too


def test_lock_after_restore_stops_old_stores_saving(tmp_path):
    from app.vdr.store import ReportStore
    store = ReportStore(tmp_path/'r.json', today='2026-11-18'); store.load_error = 'Data was restored from a backup.'
    with pytest.raises(OSError):
        store.save()


# ------------------------------------------------------------------ first run
def test_first_run_only_when_identity_missing(qtbot, tmp_path):
    from app.core.vessel_identity import save_identity
    from app.ui.first_run import FirstRunDialog, mark_done, needs_first_run
    settings = QSettings(str(tmp_path/'s.ini'), QSettings.Format.IniFormat)
    assert needs_first_run(settings)
    mark_done(settings); assert not needs_first_run(settings)
    other = QSettings(str(tmp_path/'t.ini'), QSettings.Format.IniFormat); save_identity(dict(vessel='MV', hireDate='2026-01-01'), other)
    assert not needs_first_run(other)
    fresh = QSettings(str(tmp_path/'u.ini'), QSettings.Format.IniFormat)
    dialog = FirstRunDialog(None, fresh); qtbot.addWidget(dialog)
    dialog.identity.inputs['imo'].setText('123'); dialog.identity._edited(); dialog.next()
    assert dialog.pages.currentIndex() == 0  # invalid IMO keeps step 1
    dialog.identity.inputs['imo'].setText(''); dialog.identity.inputs['vessel'].setText('MV FIRST'); dialog.identity._edited()
    dialog.next(); dialog.next(); assert dialog.pages.currentIndex() == 2 and dialog.next_button.text() == 'Finish'
    dialog.next(); assert not needs_first_run(fresh) and fresh.value('vessel/name') == 'MV FIRST'


# ------------------------------------------------------------------ diagnostics, badges, autosave
def test_link_monitor_records_without_changing_ingest():
    seen = []; monitor = LinkMonitor(); ingest = monitor.wrap(lambda s, d: seen.append(d) or ['frame'])
    assert ingest(SimpleNamespace(value='USB'), b'{"a":1}\n{"b":2}\n') == ['frame'] and seen == [b'{"a":1}\n{"b":2}\n']
    assert monitor.packets['USB'] == 1 and len(monitor.raw) == 2
    for _ in range(1000):
        ingest(SimpleNamespace(value='USB'), b'x' * 10 + b'\n')
    assert len(monitor.raw) == monitor.raw.maxlen  # bounded history
    monitor.connection_changed('USB', True, 'COM3'); monitor.connection_changed('USB', False); monitor.connection_changed('USB', True, 'COM3')
    assert monitor.reconnects('USB') == 1


@pytest.mark.parametrize('args,label', [(('NO SOURCE', 0, 0, 0, None), 'NOT CONNECTED'), (('WAITING', 0, 0, 0, None), 'NO DATA YET'),
                                        (('WAITING', 5, 0, 7, None), 'INVALID DATA'), (('LIVE', 5, 5, 0, 1.0), 'LIVE'),
                                        (('STALE', 5, 5, 0, 6.0), 'STALE')])
def test_link_state_distinguishes_problems(args, label):
    assert link_state(*args)[0] == label


def test_status_badges_use_text_and_shape(qtbot):
    from app.qt.QtWidgets import QLabel
    assert [tone_for(t) for t in ('LIVE', 'STALE', 'NO DATA', 'NOT CONNECTED', 'DISCONNECTED', 'CONNECTED', 'NOT SAVED', 'FINALIZED')] == \
           ['success', 'warning', 'neutral', 'neutral', 'neutral', 'success', 'error', 'success']
    label = QLabel(); qtbot.addWidget(label); set_badge(label, 'STALE')
    assert label.text() == '▲  STALE' and label.property('badgeTone') == 'warning'


def test_autosave_badge_states(qtbot, tmp_path):
    from app.ui.pages.vdr.workspace import VdrPage
    from app.vdr.store import ReportStore
    store = ReportStore(tmp_path/'r.json', today='2026-11-18'); store.reports[store.current] = fixture_report()
    page = VdrPage(store, identity_provider=lambda: dict(TEST_IDENTITY)); qtbot.addWidget(page)
    page.edit(('meta', 'captain'), 'X'); assert page.saved.text() == 'Saving…' and page.saved.property('badgeTone') == 'neutral'
    assert page.flush_save() and page.saved.text().startswith('Saved ') and page.saved.property('badgeTone') == 'success'
    store.load_error = 'blocked'; assert not page.flush_save() and page.saved.property('badgeTone') == 'error'


# ------------------------------------------------------------------ 1366x768 layout
def _no_horizontal_scroll(widget, qtbot):
    from app.qt.QtWidgets import QScrollArea
    widget.resize(1306, 728); widget.show(); qtbot.waitExposed(widget); qtbot.wait(50)
    page_scrolls = [s for s in widget.findChildren(QScrollArea) if s.horizontalScrollBar().maximum() > 0 and s.width() > 900]
    return page_scrolls


def test_pages_fit_1366x768_without_horizontal_page_scroll(qtbot, tmp_path):
    from app.telemetry.telemetry_state import TelemetryStateService
    from app.ui.pages.configure.configure_page import ConfigurePage
    from app.ui.pages.vdr.workspace import VdrPage
    from app.ui.pages.vjr_workspace import VjrPage
    from app.vdr.store import ReportStore
    from app.vjr.store import VjrStore
    fake = SimpleNamespace(scan=lambda: [], connect=lambda d: False, disconnect=lambda: None, is_connected=lambda: False, on_error=None, on_state=None)
    configure = ConfigurePage(fake, fake, TelemetryStateService(), settings=QSettings(str(tmp_path/'c.ini'), QSettings.Format.IniFormat)); qtbot.addWidget(configure)
    assert _no_horizontal_scroll(configure, qtbot) == []
    store = ReportStore(tmp_path/'r.json', today='2026-11-18'); store.reports[store.current] = fixture_report()
    vdr = VdrPage(store, identity_provider=lambda: dict(TEST_IDENTITY)); qtbot.addWidget(vdr)
    _no_horizontal_scroll(vdr, qtbot); assert vdr.topbar_scroll.horizontalScrollBar().maximum() == 0  # all title-bar actions visible
    vjr = VjrPage(VjrStore(tmp_path/'v.json'), identity_provider=lambda: {}); qtbot.addWidget(vjr)
    assert _no_horizontal_scroll(vjr, qtbot) == []
    for button in (vjr.excel_button, vjr.new_voyage_button, vjr.history_button):
        assert vjr.rect().contains(button.mapTo(vjr, button.rect().bottomRight()))


def test_vjr_suspicious_cell_is_marked(qtbot, tmp_path):
    from app.qt.QtWidgets import QTableWidget
    from app.ui.pages.vjr_workspace import VjrPage
    from app.vjr.schema import PROGRESS
    from app.vjr.store import VjrStore
    from vjr_fixture import full_report
    store = VjrStore(tmp_path/'v.json'); report = full_report()
    report['progress'].append(dict(report['waypoints'][0], date='2026-11-18', hour='10', minute='00', speed='60')); store.report = report
    page = VjrPage(store, identity_provider=lambda: {}); qtbot.addWidget(page); page.refresh()
    table = next(t for t in page.findChildren(QTableWidget) if t.objectName() == 'progress')
    item = table.item(table.rowCount()-1, [k for k, _l, _c, _t in PROGRESS].index('speed'))
    assert item.toolTip().startswith('▲') and 'unusually high' in item.toolTip()
