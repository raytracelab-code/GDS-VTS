"""Manual-sweep automation: trigger every reachable pop-up in the REAL MainWindow (1366x768 window)
and record how it actually opened - modal, in front, centred on the main window, inside the screen,
action buttons visible. Each dialog is captured, then closed with Esc (or its Close button).

Isolation: QStandardPaths test mode; vessel identity in a temporary INI (registry untouched).
Run: .venv\\Scripts\\python.exe -u docs\\evidence\\dialog-visibility\\app_sweep.py
"""
import json
import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]; OUT = Path(__file__).resolve().parent/'app-sweep'
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests')); OUT.mkdir(exist_ok=True)
os.environ['GDS_OVERPASS_ENABLED'] = 'false'
from app.nav.web_scheme import register_gds_scheme  # noqa: E402
register_gds_scheme()
from app.qt import API  # noqa: E402
from app.qt.QtCore import QPoint, QRect, QSettings, QStandardPaths, QTimer, Qt  # noqa: E402
from app.qt.QtGui import QGuiApplication  # noqa: E402
from app.qt.QtWidgets import QAbstractButton, QApplication  # noqa: E402
app = QApplication(sys.argv[:1]); QStandardPaths.setTestModeEnabled(True)
data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
for name in ('vdr/reports.json', 'vjr/report.json'):
    if (data/name).exists(): (data/name).unlink()
import app.core.vessel_identity as vessel_identity  # noqa: E402
ini = QSettings(str(Path(tempfile.mkdtemp())/'identity.ini'), QSettings.Format.IniFormat)
vessel_identity._settings = lambda settings=None: settings if settings is not None else ini
from app.ui.main_window import MainWindow  # noqa: E402
from test_vdr import fixture_report  # noqa: E402

results = []
def pump(seconds):
    end = time.time() + seconds
    while time.time() < end: app.processEvents(); time.sleep(0.01)

window = MainWindow(); window.resize(1366, 768); window.show(); pump(2)
screen = QGuiApplication.screenAt(window.frameGeometry().center()).availableGeometry()


def sweep(name, trigger, close='esc'):
    """Run ``trigger`` (which opens a modal dialog); inspect the dialog from a timer inside its loop."""
    seen = {}
    def inspect():
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            seen['error'] = 'no modal dialog appeared'; return
        frame, main = dialog.frameGeometry(), window.frameGeometry()
        buttons = [b for b in dialog.findChildren(QAbstractButton) if b.isVisible() and b.text()]
        from app.qt.QtWidgets import QScrollArea
        in_scroll = lambda b: any(sa.isAncestorOf(b) for sa in dialog.findChildren(QScrollArea))
        # Buttons inside a scrolling list are reached by scrolling; footer/dialog buttons must be fully visible.
        clipped = [b.text() for b in buttons if not in_scroll(b) and not dialog.rect().contains(QRect(b.mapTo(dialog, QPoint(0, 0)), b.size()))]
        seen.update(title=dialog.windowTitle(), modal=dialog.isModal(), parent_is_main=dialog.parentWidget() is not None and dialog.parentWidget().window() is window,
                    active=QApplication.activeWindow() is dialog, inside_screen=screen.contains(frame),
                    centre_offset=[frame.center().x() - main.center().x(), frame.center().y() - main.center().y()],
                    size=[frame.width(), frame.height()], buttons=[b.text().replace('&&', '&') for b in buttons], clipped=clipped)
        dialog.grab().save(str(OUT/f'{name}.png'))
        dialog.reject() if hasattr(dialog, 'reject') else dialog.close()
    QTimer.singleShot(700, inspect)
    try:
        trigger()
    except Exception as error:  # record, keep sweeping
        seen['error'] = repr(error)
    pump(0.3); results.append(dict(name=name, **seen)); print(name, seen.get('error') or ('OK' if seen.get('inside_screen') and not seen.get('clipped') else 'PROBLEM'), flush=True)


today = date.today().isoformat()
vdr, vjr, nav = window.vdr, window.vjr, window.nav
window.tabs.buttons['VDR'].click(); pump(0.5)
sweep('01_vdr_finalize_validation', vdr.finalize)
for back in (2, 1):
    vdr.store.import_report(fixture_report((date.today() - timedelta(days=back)).isoformat()))
vdr.store.select(today); vdr._rebuild()
sweep('02_vdr_previous_reports', vdr.show_history)
vessel_identity.save_identity(dict(vessel='MV SWEEP', hireDate='2026-01-01'))
vdr.store.select((date.today() - timedelta(days=1)).isoformat()); vdr.store.finalize(identity=vessel_identity.load_identity()); vdr._rebuild(); pump(0.3)
sweep('03_vdr_reopen_confirmation', vdr.finalize)  # finalized -> Reopen asks first; Esc = Cancel
results[-1]['still_finalized_after_esc'] = vdr.report['finalized']
window.tabs.buttons['VJR'].click(); pump(0.5)
sweep('04_vjr_excel_validation', vjr.download_excel)
sweep('05_vjr_new_voyage', vjr.new_voyage)
vjr.store.archive()
sweep('06_vjr_voyage_history', vjr.show_voyage_history)
card = next(iter(vjr.photo_cards.values()))
help_button = next(b for b in card.findChildren(QAbstractButton) if b.text() == "Can't connect?")
sweep('07_vjr_photo_help', help_button.click)
window.tabs.buttons['Nav'].click(); pump(3)
sweep('08_nav_map_regions', nav._map_regions)
sweep('09_nav_vessel_config', lambda: nav.command('VESSEL CONFIG'))
window.tabs.buttons['Configure'].click(); pump(0.3)

(OUT/f'sweep_{API}.json').write_text(json.dumps(dict(api=API, screen=[screen.width(), screen.height()], dialogs=results), indent=1), encoding='utf-8')
problems = [r for r in results if r.get('error') or r.get('clipped') or not r.get('inside_screen') or not r.get('modal') or not r.get('parent_is_main')]
print(f'{API}: {len(results)} dialogs swept, {len(problems)} problems')
window.close(); window.maritime_runtime.close(wait=True, timeout=2.0); window.nav.shutdown_webengine()
