"""Screenshot sweep of every application dialog on a simulated usable screen.

Usage (scaling is real Qt device-pixel scaling via QT_SCALE_FACTOR):
  .venv\\Scripts\\python.exe docs\\evidence\\dialog-visibility\\capture_dialogs.py 1366x768 1.0
  set QT_SCALE_FACTOR=1.25 & .venv\\Scripts\\python.exe ... 1366x768 1.25
The usable area is the display size divided by the scale factor, minus a 40 px taskbar.
Writes PNGs and a checklist (fits screen / footer visible) into <size>@<scale>/.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests'))
size, scale = sys.argv[1], float(sys.argv[2])
width, height = (int(v) for v in size.split('x'))
from app.qt.QtCore import QPoint, QRect, QStandardPaths  # noqa: E402
from app.qt.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402
app = QApplication(sys.argv[:1]); QStandardPaths.setTestModeEnabled(True)
from app.qt import API  # noqa: E402
from app.ui import dialogs  # noqa: E402
SCREEN = QRect(0, 0, int(width/scale), int(height/scale) - 40)
dialogs.available_geometry = lambda widget=None: QRect(SCREEN)
OUT = Path(__file__).resolve().parent/f'{size}@{int(scale*100)}%-{API}'; OUT.mkdir(parents=True, exist_ok=True)
parent = QWidget(); parent.setGeometry(SCREEN); parent.show()
checks = []


def capture(name, dialog, *buttons):
    dialogs.fit_to_screen(dialog, parent); dialog.show()
    for _ in range(20): app.processEvents()
    geometry = dialog.frameGeometry(); inside = dialog.rect()  # whole window incl. title bar
    clipped = [b.text() for b in buttons if not inside.contains(QRect(b.mapTo(dialog, QPoint(0, 0)), b.size())) or not b.isVisible()]
    checks.append(dict(dialog=name, geometry=[geometry.x(), geometry.y(), geometry.width(), geometry.height()],
                       fits_screen=SCREEN.contains(geometry), footer_visible=not clipped, clipped=clipped))
    dialog.grab().save(str(OUT/f'{name}.png')); dialog.close()


from test_vdr import TEST_IDENTITY, fixture_report  # noqa: E402
from app.vdr.store import ReportStore  # noqa: E402
from app.ui.pages.vdr.workspace import VdrPage  # noqa: E402
tmp = Path(tempfile.mkdtemp())
store = ReportStore(tmp/'r.json', today='2026-11-19', identity={}); r = fixture_report('2026-11-19'); r['meta']['captain'] = ''; r['acts'][0]['to'] = '1200'
store.reports[store.current] = r
page = VdrPage(store, identity_provider=lambda: {})
issues = store.finalize(identity={})
d = dialogs.IssuesDialog(parent, 'Complete these items before finalizing', f'The report stays a DRAFT until the {len(issues)} item(s) below are completed.', page.issue_groups(issues))
capture('01_finalize_validation', d, d.close_button, *d.action_buttons[:1])

from app.ui.pages.vdr.history_dialog import ReportHistoryDialog  # noqa: E402
rows = [dict(day=f'2026-11-{d:02d}', report_no=str(300 + d), vessel='MV RUNTIME CHECK', status=['DRAFT', 'FINALIZED', 'FINALIZED · REV 2', 'REOPENED · DRAFT'][d % 4],
             modified='2026-11-19T10:00:00+00:00', openable=True) for d in range(1, 29)]
d = ReportHistoryDialog(rows, '2026-11-18', parent); capture('02_vdr_previous_reports', d, d.open_button)
d = ReportHistoryDialog([], '2026-11-18', parent); capture('03_vdr_previous_reports_empty', d, d.open_button)

box, yes, no = dialogs.build_confirm(parent, 'Reopen finalized report?', 'Report 18 Nov 2026 · Report No. 322 · currently FINALIZED.\n\n'
    'Reopening makes this report an editable DRAFT. Files you already exported or sent are not changed.\n\nWhen you finalize it again it becomes REV 2.',
    'Reopen report', destructive=True)
capture('04_vdr_reopen_confirmation', box, yes, no)
box, yes, no = dialogs.build_confirm(parent, 'Replace existing report?', 'A report for 2026-11-18 already exists. Importing replaces it with the report from the PDF.\n\nUndo (Ctrl+Z) remains available.', 'Replace report', destructive=True)
capture('05_vdr_import_replace', box, yes, no)
long_path = 'C:\\Users\\operator\\Documents\\Vessel reports\\2026\\November\\' + 'a_very_long_folder_name_without_spaces_' * 3 + 'VDR_MV_RUNTIME_CHECK_2026-11-18.pdf'
box, ok = dialogs.build_notify(parent, 'PDF not created', 'The PDF could not be created. Your report data is safe and unchanged.\n\nIf the file is open in a PDF viewer, close it and try again, or choose another folder.',
    details=f"[Errno 13] Permission denied: '{long_path}'\n\nDestination: {long_path}")
capture('06_pdf_export_error_long_path', box, ok)
lines = ['• 02 Weather: Weather 0000H: missing wind, swell, sea, sky', '• 03 Activity log: Row 1 lifts: "abc" is not a valid number',
         '• 05 Bulk inventory: FRESH WATER (ltrs) has 2 transfers; template capacity = 1.', '• 06 Core crew: Crew row 3: name is required (or delete the row)'] * 3
d = dialogs.IssuesDialog(parent, 'Excel file not created', 'Your report data is safe and unchanged. Reopen the report, correct these items, then finalize again.', dialogs.issues_from_lines(lines))
capture('07_vdr_excel_multi_error', d, d.close_button)
box, ok = dialogs.build_notify(parent, 'Not saved', f'Not saved: Windows denied access to {Path(long_path).parent}. Your previously saved data is safe. '
    'Check that the folder is not read-only or locked by another program.', details=long_path)
capture('08_storage_save_failed', box, ok)

from app.vjr.store import VjrStore  # noqa: E402
from app.ui.pages.vjr_history import VoyageHistoryDialog  # noqa: E402
from vjr_fixture import full_report  # noqa: E402
vjr_store = VjrStore(tmp/'vjr'/'report.json'); vjr_store.report = full_report()
for _ in range(12): vjr_store.archive()
d = VoyageHistoryDialog(vjr_store, parent); d.table.selectRow(0); capture('09_vjr_voyage_history', d, d.restore_button)
box, yes, no = dialogs.build_confirm(parent, 'Start a new voyage?', '• Supply Base → Platform Alpha is archived unchanged (open it again from Voyage history).\n'
    '• The crew and contractor lists are kept for the new voyage.\n• A new, empty journey becomes the current journey.\n\nUndo (Ctrl+Z) restores the previous journey.', 'Start new voyage')
capture('10_vjr_new_voyage', box, yes, no)
from app.ui.pages.vjr_workspace import VjrPage  # noqa: E402
vjr_page = VjrPage(VjrStore(tmp/'v2.json'), identity_provider=lambda: {})
from app.vjr.validation import validate  # noqa: E402
issues = validate(vjr_page.report)
captured = {}
dialogs.exec_dialog = lambda dialog, parent_=None: captured.setdefault('d', dialog)
vjr_page.show_issues(issues); d = captured.pop('d')
capture('11_vjr_validation_before_excel', d, d.close_button)
from app.ui.pages.vjr_photos import HELP  # noqa: E402
box, ok = dialogs.build_notify(parent, 'Local network upload', HELP, kind='information'); capture('12_vjr_photo_help', box, ok)
box, yes, no = dialogs.build_confirm(parent, 'Delete this photo?', 'The photo is removed from the current report. Undo (Ctrl+Z) can restore it.', 'Delete photo', destructive=True)
capture('13_vjr_photo_delete', box, yes, no)

import app.ui.pages.nav.map_regions_dialog as regions  # noqa: E402
regions.PackageManager = lambda: SimpleNamespace(installed_regions=lambda **k: [], invalid_regions={})
regions.cache_root = lambda: tmp/'cache'
(tmp/'regions-catalog.json').write_text(json.dumps([dict(region_id=f'r{i}', display_name=f'Malaysia region {i}', group=['Peninsular', 'Sabah', 'Sarawak'][i % 3],
                                                    status='AVAILABLE', download_size=(i+1)*10**8) for i in range(60)]))
d = regions.MapRegionsDialog(parent); capture('14_nav_map_regions', d, d.close_button, *d.buttons)
box, yes, no = dialogs.build_confirm(parent, 'Remove this map region?', 'The installed region and its previous revision are deleted from this computer. You can install it again later.', 'Remove region', destructive=True)
capture('15_nav_remove_region', box, yes, no)
from app.nav.vessel_config import VesselConfig  # noqa: E402
from app.ui.pages.nav.vessel_config_dialog import VesselConfigDialog  # noqa: E402
d = VesselConfigDialog(VesselConfig(), parent); capture('16_nav_vessel_config', d, *d.findChildren(QPushButton))
box, ok = dialogs.build_notify(parent, 'Spatial package not imported', 'The package could not be imported. The active spatial data is unchanged.', details='Invalid signature in ' + long_path)
capture('17_nav_spatial_import_error', box, ok)

(OUT/'checklist.json').write_text(json.dumps(dict(screen=[SCREEN.width(), SCREEN.height()], scale=scale, api=API, dialogs=checks), indent=1), encoding='utf-8')
bad = [c for c in checks if not (c['fits_screen'] and c['footer_visible'])]
print(f'{size}@{scale} {API}: {len(checks)} dialogs, {len(bad)} problems', bad)
