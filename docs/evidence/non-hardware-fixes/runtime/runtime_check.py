"""Runtime check of the real MainWindow (source build) for the non-hardware fixes.

Isolation: QStandardPaths test mode (temporary report stores) and an INI file for
vessel identity (app.core.vessel_identity is pointed at it), so the registry and reports are untouched.
Overpass is disabled for this run (GDS_OVERPASS_ENABLED=false); no hardware is used.

Run:  .venv\\Scripts\\python.exe docs\\evidence\\non-hardware-fixes\\runtime\\runtime_check.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests'))
os.environ['GDS_OVERPASS_ENABLED'] = 'false'

from app.qt import exec_qt  # noqa: E402
from app.qt.QtCore import QSettings, QStandardPaths, QTimer  # noqa: E402
from app.qt.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
QStandardPaths.setTestModeEnabled(True)
settings_dir = tempfile.mkdtemp(prefix='gds-runtime-settings-')
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir)
data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
for name in ('vdr/reports.json', 'vjr/report.json'):
    if (data_dir/name).exists():
        (data_dir/name).unlink()  # test-mode folder only (never the real AppData store)

# setDefaultFormat() does not affect QSettings('GDS','VTS'); route identity storage to an INI file explicitly.
import app.core.vessel_identity as vessel_identity  # noqa: E402
_ini = QSettings(str(Path(settings_dir)/'GDS-VTS.ini'), QSettings.Format.IniFormat)
vessel_identity._settings = lambda settings=None: settings if settings is not None else _ini
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.pages.vdr import workspace as vdr_workspace  # noqa: E402
from test_vdr import fixture_report  # noqa: E402

log = []
def note(text):
    log.append(text); print(text, flush=True)

def settle(ms=300):
    end = time.time() + ms/1000
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)

def shot(widget, name):
    widget.grab().save(str(OUT/name)); note(f'screenshot {name}')

window = MainWindow(); window.resize(1366, 768); window.show(); settle(800)
note(f'window title: {window.windowTitle()}')
shot(window, '01_configure_identity_empty_1366x768.png')

panel = window.configure.identity
note(f'identity status before: {panel.status.text()}')
panel.inputs['vessel'].setText('MV RUNTIME CHECK'); panel.inputs['imo'].setText('9074729')
panel.inputs['client'].setText('RUNTIME CLIENT'); panel.inputs['client_id'].setText('RC-1')
panel.inputs['hireDate'].set_value('2026-01-01'); panel.inputs['capacity'].setText('850'); panel._edited()
panel.inputs['imo'].setText('9074720'); assert not panel.save()
note(f'invalid IMO rejected: {panel.errors["imo"].text()}')
panel.inputs['imo'].setText('9074729'); assert panel.save()
note(f'identity saved (isolated INI): {_ini.value("vessel/name")} / hire {_ini.value("vessel/date_of_hire")}')
settle(); shot(window, '02_configure_identity_saved_1366x768.png')

# --- VDR: identity, Report No., carry-forward
window.tabs.buttons['VDR'].click(); settle(500)
vdr = window.vdr
note(f'VDR subtitle={vdr.subtitle.text()!r} hire={vdr.hire_value.text()!r} reportNo={vdr.report_no.text()!r} (today {vdr.store.today})')
yesterday = (__import__('datetime').date.fromisoformat(vdr.store.today) - __import__('datetime').timedelta(days=1)).isoformat()
vdr.store.import_report(fixture_report(yesterday)); vdr.select_date(vdr.store.today); settle()
note(f'today FW opening after rollover from {yesterday}: {vdr.report["bulk"][1]["open"]}')
vdr.select_date(yesterday); settle(); vdr.store.reopen() if vdr.report['finalized'] else None
vdr.edit(('bulk', 1, 'cons'), '1000'); vdr.select_date(vdr.store.today); settle()
note(f'today FW opening after correcting {yesterday}: {vdr.report["bulk"][1]["open"]} (expected 4000)')
vdr.edit(('bulk', 2, 'open'), '1234'); vdr._rebuild(); vdr.go_section(4); settle(500)
note(f'carry notice: {vdr.carry_notices[-1][0].text()}')
shot(vdr, '03_vdr_identity_reportno_carry_notice_1366x768.png')

# --- Finalize blocked: grouped issues dialog
def capture(dialog):
    dialog.show(); settle(300); dialog.grab().save(str(OUT/'04_vdr_finalize_blocked_grouped_issues.png'))
    note('screenshot 04_vdr_finalize_blocked_grouped_issues.png'); dialog.close(); return 0
vdr_workspace.exec_qt = capture
note(f'finalize incomplete report -> {vdr.finalize()}')

# --- Over-long text: refused with banner
vdr.edit(('meta', 'captain'), 'x'*250); settle()
note(f'over-long banner visible={not vdr.banner.isHidden()} text={vdr.banner_text.text()[:90]!r}')
shot(vdr, '05_vdr_overlong_text_refused.png'); vdr.banner.hide()

# --- VJR identity from Configure
window.tabs.buttons['VJR'].click(); settle(600)
vjr = window.vjr
note(f'VJR meta vessel={vjr.report["meta"]["vessel"]!r} imo={vjr.report["meta"]["imo"]!r} read-only={vjr.editors[("meta","vessel")].isReadOnly()}')
shot(window, '06_vjr_identity_from_configure_1366x768.png')

# --- NAV (WebGL rendering itself is not assessed by this script)
window.tabs.buttons['Nav'].click(); settle(2500)
note(f'NAV readout: {getattr(window.nav, "readout", None) and window.nav.readout.text()!r}')
shot(window, '07_nav_no_telemetry_state_1366x768.png')

# --- Close
window.tabs.buttons['Configure'].click(); settle(200)
start = time.perf_counter(); window.close()
window.maritime_runtime.close(wait=True, timeout=2.0)
note(f'window close + bounded maritime close: {time.perf_counter()-start:.2f} s')
(OUT/'runtime_check_output.txt').write_text('\n'.join(log) + '\n', encoding='utf-8')
