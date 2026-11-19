"""Runtime check of the real MainWindow for issues 005, 019, 021 (and 009 via a real PDF download).

Isolation: QStandardPaths test mode (temporary stores) and an INI file for vessel identity
(app.core.vessel_identity is pointed at it) - the Windows registry and real reports are untouched.
Squall data comes only from a clearly-labelled test fixture through MainWindow's ingest API.
Run: .venv\\Scripts\\python.exe docs\\evidence\\remaining-p1-fixes\\runtime\\runtime_check.py
"""
import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]; OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests'))
os.environ['GDS_OVERPASS_ENABLED'] = 'false'
from app.nav.web_scheme import register_gds_scheme  # noqa: E402
register_gds_scheme()
from app.qt import API  # noqa: E402
from app.qt.QtCore import QSettings, QStandardPaths, QUrl  # noqa: E402
from app.qt.QtWidgets import QApplication, QDialog  # noqa: E402
app = QApplication(sys.argv[:1]); QStandardPaths.setTestModeEnabled(True)
data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
for name in ('vdr/reports.json', 'vjr/report.json'):
    if (data/name).exists(): (data/name).unlink()   # test-mode folder only
import shutil  # noqa: E402
shutil.rmtree(data/'vjr'/'archive', ignore_errors=True)
import app.core.vessel_identity as vessel_identity  # noqa: E402
ini = QSettings(str(Path(tempfile.mkdtemp())/'identity.ini'), QSettings.Format.IniFormat)
vessel_identity._settings = lambda settings=None: settings if settings is not None else ini
vessel_identity.save_identity(dict(vessel='MV RUNTIME CHECK', client='RUNTIME CLIENT', hireDate='2026-01-01', imo='9074729', capacity='850'))
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.pages.vdr import workspace as vdr_ws  # noqa: E402
from test_vdr import fixture_report  # noqa: E402
from vjr_fixture import full_report  # noqa: E402

log = []
def note(text): log.append(text); print(text.encode('ascii', 'replace').decode(), flush=True)
def pump(seconds, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)
        if until and until(): return True
def shot(widget, name): widget.grab().save(str(OUT/name)); note('screenshot ' + name)

window = MainWindow(); window.resize(1366, 768); window.show(); pump(1.5)
today = date.today()

# ---- VDR history / reopen (005)
vdr = window.vdr
for back in (3, 2, 1):
    day = (today - timedelta(days=back)).isoformat(); vdr.store.import_report(fixture_report(day))
vdr.store.select((today - timedelta(days=3)).isoformat()); assert vdr.store.finalize(identity=vessel_identity.load_identity()) == []
vdr.store.reopen(); assert vdr.store.finalize(identity=vessel_identity.load_identity()) == []
vdr.store.select((today - timedelta(days=1)).isoformat()); vdr.store.finalize(identity=vessel_identity.load_identity()); vdr.store.reopen()
vdr.store.select(today.isoformat()); vdr._rebuild(); window.tabs.buttons['VDR'].click(); pump(0.5)
captured = {}
def history_exec(dialog):
    dialog.show(); pump(0.5); t = time.perf_counter(); dialog.apply_filter(); captured['filter_ms'] = (time.perf_counter()-t)*1000
    dialog.grab().save(str(OUT/'01_vdr_previous_reports.png')); note('screenshot 01_vdr_previous_reports.png')
    dialog.search.setText((today - timedelta(days=3)).strftime('%d %b')); pump(0.2)
    dialog.grab().save(str(OUT/'02_vdr_previous_reports_search.png')); note('screenshot 02_vdr_previous_reports_search.png')
    dialog.table.selectRow(0); dialog.open_selected(); return QDialog.DialogCode.Accepted
vdr_ws.exec_qt = history_exec
t = time.perf_counter(); opened = vdr.show_history()
note(f'VDR history rows={[(r["day"], r["status"]) for r in vdr.store.history(vessel_identity.load_identity())]}')
note(f'VDR history open+render {(time.perf_counter()-t)*1000:.0f} ms (filter {captured["filter_ms"]:.1f} ms); opened {opened}; '
     f'finalized={vdr.report["finalized"]} read-only={vdr.editors[("meta","captain")].isReadOnly()} button={vdr.finalize_button.text()!r}')
pump(0.3); shot(window, '03_vdr_opened_old_finalized_readonly.png')

# ---- VJR voyage history (005)
vjr = window.vjr
vjr.store.mutate(lambda r: (r.clear(), r.update(full_report()))); vjr.store.archive()
vjr.store.mutate(lambda r: (r['departure'].update(departure_location='Kemaman Base', destination='Platform Bravo', departure_date=today.isoformat()), r['arrival'].update(arrival_date='', report_date='')))
vjr.rebuild(); window.tabs.buttons['VJR'].click(); pump(0.5)
import app.qt as qt  # noqa: E402
def voyage_exec(dialog):
    dialog.show(); pump(0.5); dialog.grab().save(str(OUT/'04_vjr_voyage_history.png')); note('screenshot 04_vjr_voyage_history.png'); return 0
original_exec = qt.exec_qt; qt.exec_qt = voyage_exec
dialog = vjr.show_voyage_history(); qt.exec_qt = original_exec
note(f'VJR voyage history rows={[(r["departure_location"], r["status"]) for r in vjr.store.archived_journeys()]}')

# ---- Squall feed states (021)
window.tabs.buttons['Nav'].click(); pump(4)
nav = window.nav
if nav.layers_panel.isHidden(): nav.toggle_layers()
nav.toggle_weather(); pump(1.2)
note(f'squall (no provider): {nav.event_count.text()!r}')
shot(window, '05_nav_squall_provider_unavailable.png')
now = datetime.now(timezone.utc)
window.ingest_squall_event(dict(operation='CREATE', event_type='squall', event_id='SQ-TEST', observed_at=now.isoformat(), latitude=5.3,
    longitude=103.2, direction_deg=90, speed_knots=20, severity='moderate', impact_radius_nm=3, surveillance_radius_nm=8,
    predicted_path=[dict(latitude=5.3, longitude=103.4, eta_seconds=900)], source='TEST FIXTURE - not real weather'))
pump(1.5); note(f'squall (fixture message): {nav.event_count.text()!r}')
shot(window, '06_nav_squall_feed_live.png')
service = window.squall_event_service
service.last_message_at = now - timedelta(seconds=200); pump(1.5)
note(f'squall (no message for 200 s): {nav.event_count.text()!r}')
service.provider_failed('fixture provider disconnected'); pump(1.5)
note(f'squall (provider failed): {nav.event_count.text()!r}; events={[(e["event_id"], e["status"]) for e in nav.bridge.getEventState()["events"]]}')
shot(window, '07_nav_squall_provider_failed_stale.png')
service.provider_recovered(); window.ingest_squall_event(dict(operation='UPDATE', event_type='squall', event_id='SQ-TEST',
    observed_at=datetime.now(timezone.utc).isoformat(), latitude=5.3, longitude=103.25, direction_deg=90, speed_knots=20, severity='moderate',
    impact_radius_nm=3, surveillance_radius_nm=8, predicted_path=[dict(latitude=5.3, longitude=103.4, eta_seconds=600)], source='TEST FIXTURE - not real weather'))
pump(1.5); note(f'squall (recovered): {nav.event_count.text()!r}')
# Own-vessel impact: a software telemetry frame (fixture, no hardware) puts the vessel inside the impact zone.
from app.core.models import Source  # noqa: E402
frame = '{"PID":"FIXTURE","Latitude":"0518.0","Longitude":"10313.0","SOG":"0","COG":"0","Heading":"0"}\n'
window.state.ingest(Source.USB, frame.encode()); pump(2.5)
note(f'vessel {nav.vessel.latitude},{nav.vessel.longitude}; squall alert: {nav.squall_alert.text() if hasattr(nav, "squall_alert") else None!r}; '
     f'rail button: {window.tabs.buttons["Nav"].text()!r}')
shot(window, '07b_nav_squall_impact_alert_own_vessel.png')

# ---- Renderer failure + retry inside the full app (019)
h = nav.renderer_health; nav.web.setUrl(QUrl('chrome://crash')); pump(10, lambda: h.state == 'RENDERER_STOPPED')
note(f'renderer crash in app -> {h.state}; overlay={nav.renderer_overlay.isVisible()}'); shot(window, '08_nav_renderer_stopped_in_app.png')
t = time.perf_counter(); nav.retry_renderer(); pump(30, lambda: h.state == 'OK')
note(f'renderer retry in app -> {h.state} in {time.perf_counter()-t:.2f} s; overlay={nav.renderer_overlay.isVisible()}')

# ---- PDF download of a report with very long rows (009)
from app.vdr.pdf import export_pdf  # noqa: E402
r = fixture_report(); r.update(finalized=True, finalizedAt=datetime.now(timezone.utc).isoformat())
r['acts'][0]['act'] = ' '.join(f'ACT-{i:04d}' for i in range(1, 901)); r['crew'][0]['comments'] = 'Long crew comment ' * 50
t = time.perf_counter(); export_pdf(dict(r, identity=vessel_identity.load_identity()), OUT/'09_runtime_long_rows.pdf')
note(f'PDF with a row longer than a page: {(time.perf_counter()-t)*1000:.0f} ms')

# ---- Shutdown
t = time.perf_counter(); window.close(); window.maritime_runtime.close(wait=True, timeout=2.0); window.nav.shutdown_webengine()
note(f'shutdown {time.perf_counter()-t:.2f} s')
(OUT/f'runtime_check_output_{API}.txt').write_text('\n'.join(log) + '\n', encoding='utf-8')
