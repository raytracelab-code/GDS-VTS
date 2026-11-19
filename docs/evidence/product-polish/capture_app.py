"""Runtime check + screenshots of the real MainWindow for the reliability/diagnostics/polish phase.

Isolation: QStandardPaths test mode; vessel identity and first-run state in a temporary INI;
software telemetry fixture frames through the normal ingest path (no hardware). The registry is only read.
Run: .venv\\Scripts\\python.exe -u docs\\evidence\\product-polish\\capture_app.py [scale]
     (set QT_SCALE_FACTOR=1.25 for the 125 % set)
"""
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests'))
SCALE = os.environ.get('QT_SCALE_FACTOR', '1')
os.environ['GDS_OVERPASS_ENABLED'] = 'false'
from app.nav.web_scheme import register_gds_scheme  # noqa: E402
register_gds_scheme()
from app.qt import API  # noqa: E402
from app.qt.QtCore import QSettings, QStandardPaths  # noqa: E402
from app.qt.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv[:1]); QStandardPaths.setTestModeEnabled(True)
OUT = Path(__file__).resolve().parent/f'1366x768@{int(float(SCALE)*100)}%-{API}'; OUT.mkdir(parents=True, exist_ok=True)
data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
for name in ('vdr/reports.json', 'vjr/report.json'):
    if (data/name).exists(): (data/name).unlink()
import app.core.vessel_identity as vessel_identity  # noqa: E402
ini = QSettings(str(Path(tempfile.mkdtemp())/'identity.ini'), QSettings.Format.IniFormat)
vessel_identity._settings = lambda settings=None: settings if settings is not None else ini
from app.ui import dialogs  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.core.models import Source  # noqa: E402
from test_vdr import fixture_report  # noqa: E402
from vjr_fixture import full_report  # noqa: E402

log = []
def note(text): log.append(text); print(str(text).encode('ascii', 'replace').decode(), flush=True)
def pump(seconds):
    end = time.time() + seconds
    while time.time() < end: app.processEvents(); time.sleep(0.01)
def shot(widget, name): widget.grab().save(str(OUT/f'{name}.png')); note('screenshot ' + name)

# First run (isolated settings): shown because identity is empty.
from app.ui.first_run import FirstRunDialog, needs_first_run  # noqa: E402
note(f'first run needed on empty profile: {needs_first_run(ini)}')
first = FirstRunDialog(None, ini); dialogs.fit_to_screen(first); first.show(); pump(0.5); shot(first, '00_first_run_step1')
first.identity.inputs['vessel'].setText('MV POLISH CHECK'); first.identity.inputs['hireDate'].set_value('2026-01-01'); first.identity._edited()
first.next(); pump(0.2); shot(first, '00_first_run_step2'); first.next(); first.next(); pump(0.2)
note(f'first run after Finish: needed={needs_first_run(ini)} vessel={ini.value("vessel/name")}')

window = MainWindow(); window.resize(1366, 768); window.show(); pump(1.5)
# Software telemetry fixture through the real ingest path (includes one invalid line and a 55 kn speed).
conn = window.configure.connection
conn.usb_devices = [type('D', (), dict(port='COM7', description='USB Serial (fixture)', product='', vid=0x0403, pid=0x6001, serial_number='FX1', label='COM7 — fixture'))()]
conn.usb_select.clear(); conn.usb_select.addItems(['COM7 — fixture']); conn._set_connected('USB', True)
ingest = window.link_monitor.wrap(window.state.ingest)
frame = '{"PID":"FIXTURE","Latitude":"0518.0","Longitude":"10313.0","Speed_Knots":"55","COG":"90","Temperature_C":"31","Humidity":"78","Pressure_Kpa":"101.2"}\n'
ingest(Source.USB, b'not json at all\n'); ingest(Source.USB, frame.encode()); pump(1.2)
shot(window, '01_configure_top')
page = window.configure; scroll = page.findChild(__import__('app.qt.QtWidgets', fromlist=['QScrollArea']).QScrollArea)
scroll.ensureWidgetVisible(page.connection.usb_link); pump(0.3); shot(window, '02_configure_connection_link_state')
note(f'USB link: {conn.usb_link.text()!r}')
scroll.ensureWidgetVisible(page.telemetry.labels['speed_knots']); pump(0.3); shot(window, '03_configure_telemetry_plausibility')
note(f'telemetry speed label: {page.telemetry.labels["speed_knots"].text()!r} tip={page.telemetry.labels["speed_knots"].toolTip()!r}')
scroll.ensureWidgetVisible(page.support); pump(0.3); shot(window, '04_configure_support_card')

# About + raw monitor + support bundle + backup (real code paths, dialogs captured)
about = __import__('app.ui.pages.configure.support_panel', fromlist=['AboutDialog'])
d = about.AboutDialog(window); dialogs.fit_to_screen(d, window); d.show(); pump(0.4); shot(d, '05_about_build_info'); d.close()
d = about.RawMonitorDialog(window.link_monitor, window); dialogs.fit_to_screen(d, window); d.show(); pump(0.8); shot(d, '06_raw_data_monitor'); d.close()
from app.core.support_bundle import write_bundle  # noqa: E402
bundle, members = write_bundle(OUT/'support-bundle-sample.zip', {k: QSettings('GDS', 'VTS').value(k) for k in QSettings('GDS', 'VTS').allKeys()}, window.diagnostics())
with zipfile.ZipFile(bundle) as z:
    text = '\n'.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist())
note(f'support bundle members={members}; contains "Latitude"/position values: {"5.3" in text or "103.2" in text}')
from app.core.backup import create_backup, describe, inspect_backup, settings_snapshot  # noqa: E402
window.vdr.store.import_report(fixture_report()); window.vdr.flush_save()
window.vjr.mutate(lambda r: (r.clear(), r.update(full_report())), structural=True)
t = time.perf_counter(); create_backup(OUT/'backup-sample.zip', data, settings_snapshot(ini)); note(f'backup created in {time.perf_counter()-t:.2f} s')
summary = inspect_backup(OUT/'backup-sample.zip'); note('restore preview: ' + describe(summary).replace('\n', ' | '))
box, yes, no = dialogs.build_confirm(window, 'Restore this backup?', describe(summary) + '\n\nYour current reports, journeys, photos and settings are replaced. '
                                     'A safety copy of the current data is saved first. GDS VTS then needs a restart.', 'Restore backup', destructive=True)
dialogs.fit_to_screen(box, window); box.show(); pump(0.4); shot(box, '07_restore_confirmation'); box.close()

# VDR: plausibility (30 h daily), section markers, autosave badge
window.tabs.buttons['VDR'].click(); pump(0.3); vdr = window.vdr
vdr.edit(('eq', 0, 'daily'), '30'); pump(0.2); note(f'VDR autosave: {vdr.saved.text()!r} tone={vdr.saved.property("badgeTone")}')
vdr.flush_save(); vdr.go_section(3); pump(0.6); shot(window, '08_vdr_plausibility_and_markers')
note(f'VDR nav: {[b.text() for b in vdr.nav_buttons]}')
# VJR: progress speed 60 kn (amber), required markers, section markers
window.tabs.buttons['VJR'].click(); pump(0.3); vjr = window.vjr
vjr.mutate(lambda r: r['progress'].append(dict(r['waypoints'][0], date='2026-11-18', hour='10', minute='00', speed='60', remarks='fixture')), structural=True)
vjr.tabs.setCurrentIndex(6); pump(0.3)
for t in vjr.findChildren(__import__('app.qt.QtWidgets', fromlist=['QTableWidget']).QTableWidget): t.clearSelection()
pump(0.3); shot(window, '09_vjr_progress_plausibility')
vjr.tabs.setCurrentIndex(4); pump(0.4); shot(window, '10_vjr_required_markers')
note(f'VJR nav: {[b.text() for b in vjr.nav_buttons]}; save badge {vjr.saved.text()!r}')
# NAV: readout check values + squall wording
window.tabs.buttons['Nav'].click(); pump(2); ingest(Source.USB, frame.encode()); pump(1)
nav = window.nav
if nav.layers_panel.isHidden(): nav.toggle_layers()
pump(1.2); shot(window, '11_nav_readout_and_squall')
note(f'NAV readout tail: {nav.readout.text().splitlines()[-2:]!r}; squall: {nav.event_count.text()!r}')
window.tabs.buttons['Configure'].click(); pump(0.2)
(OUT/'runtime_output.txt').write_text('\n'.join(map(str, log)) + '\n', encoding='utf-8')
window._closing_confirmed = True; window.close(); window.maritime_runtime.close(wait=True, timeout=2.0); window.nav.shutdown_webengine()
