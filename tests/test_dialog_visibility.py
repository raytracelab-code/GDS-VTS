"""Dialog visibility audit: every application dialog fits the usable screen and keeps its
footer actions visible at 1920x1080, 1600x900, 1366x768 and 1280x720 (taskbar excluded)."""
from types import SimpleNamespace

import pytest

from app.qt.QtCore import QPoint, QRect
from app.qt.QtWidgets import QPushButton, QWidget
from app.ui import dialogs

SCREENS = {'1920x1080': QRect(0, 0, 1920, 1040), '1600x900': QRect(0, 0, 1600, 860),
           '1366x768': QRect(0, 0, 1366, 728), '1280x720': QRect(0, 0, 1280, 680)}
LONG_PATH = 'C:\\Users\\operator\\AppData\\Local\\GDS VTS\\vdr\\' + 'very_long_folder_name_without_spaces_' * 6 + 'reports.json'


@pytest.fixture(params=sorted(SCREENS))
def screen(request, monkeypatch, qtbot):
    rect = SCREENS[request.param]
    monkeypatch.setattr(dialogs, 'available_geometry', lambda widget=None: QRect(rect))
    parent = QWidget(); qtbot.addWidget(parent); parent.setGeometry(rect.adjusted(0, 0, -rect.width()//3, -rect.height()//3))
    return SimpleNamespace(rect=rect, parent=parent, name=request.param)


def place(dialog, screen, qtbot):
    qtbot.addWidget(dialog); dialogs.fit_to_screen(dialog, screen.parent); dialog.show(); qtbot.waitExposed(dialog)
    geometry = dialog.frameGeometry()  # the whole window, title bar included
    assert screen.rect.contains(geometry), f'{type(dialog).__name__} {geometry} outside {screen.rect} ({screen.name})'
    return geometry


def assert_visible(dialog, *buttons):
    inside = dialog.rect()
    for button in buttons:
        assert button.isVisible(), button.text()
        top_left = button.mapTo(dialog, QPoint(0, 0))
        assert inside.contains(QRect(top_left, button.size())), f'{button.text()!r} clipped: {top_left} {button.size()} in {inside}'
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text().replace('&', '')), f'{button.text()!r} text clipped'


def test_finalize_issues_dialog_scrolls_and_keeps_footer(screen, qtbot):
    groups = [dict(title=f'Section {g}', items=[f'Problem {g}.{i}: ' + 'detail ' * 12 for i in range(8)],
                   action=f'Go to Section {g}', callback=lambda: None) for g in range(7)]
    dialog = dialogs.IssuesDialog(screen.parent, 'Complete these items before finalizing', 'The report stays a draft.', groups)
    geometry = place(dialog, screen, qtbot)
    assert geometry.height() <= screen.rect.height()*dialogs.MAX_SCREEN_FRACTION + 1
    assert_visible(dialog, dialog.close_button)
    assert dialog.scroll.verticalScrollBar().maximum() > 0  # 56 issues scroll inside; the footer stays put
    assert dialog.scroll.horizontalScrollBar().maximum() == 0


def test_vdr_finalize_groups_identity_problems_under_one_action(qtbot, tmp_path):
    from app.ui.pages.vdr.workspace import VdrPage
    from app.vdr.store import ReportStore
    from test_vdr import fixture_report
    store = ReportStore(tmp_path/'r.json', today='2026-11-18'); r = fixture_report(); r['meta']['captain'] = ''
    store.reports[store.current] = r
    page = VdrPage(store, identity_provider=lambda: {}); qtbot.addWidget(page)
    groups = page.issue_groups(store.finalize(identity={}))
    assert groups[0]['title'] == 'Vessel & Client (Configure)' and len(groups[0]['items']) == 2
    assert any('Date of Hire is not set' in item for item in groups[0]['items'])
    assert groups[1]['title'] == 'Report & HSE' and groups[1]['action'] == 'Go to Report & HSE'
    assert not any('01 REPORT' in g['title'].upper() for g in groups)


def test_vdr_history_with_many_reports(screen, qtbot):
    from app.ui.pages.vdr.history_dialog import ReportHistoryDialog
    rows = [dict(day=f'2026-{1 + i // 28:02d}-{1 + i % 28:02d}', report_no=str(i), vessel='MV ' + 'LONG VESSEL NAME ' * 3,
                 status='FINALIZED · REV 2', modified='2026-11-19T10:00:00+00:00', openable=True) for i in range(300)]
    dialog = ReportHistoryDialog(rows, '2026-11-18', screen.parent); place(dialog, screen, qtbot)
    assert_visible(dialog, dialog.open_button, *[b for b in dialog.findChildren(QPushButton) if b.text() == 'Close'])
    assert dialog.search.isVisible() and dialog.table.verticalScrollBar().maximum() > 0  # only the list scrolls


def test_reopen_confirmation_states_consequences_and_defaults_to_cancel(screen, qtbot, monkeypatch, tmp_path):
    from app.ui.pages.vdr.workspace import VdrPage
    from app.vdr.store import ReportStore
    from test_vdr import TEST_IDENTITY, fixture_report
    store = ReportStore(tmp_path/'r.json', today='2026-11-18', identity=TEST_IDENTITY); store.reports[store.current] = fixture_report()
    page = VdrPage(store, identity_provider=lambda: dict(TEST_IDENTITY)); qtbot.addWidget(page); assert page.finalize()
    captured = {}
    monkeypatch.setattr(dialogs, 'confirm', lambda parent, title, text, label, **k: captured.update(title=title, text=text, label=label, **k) or False)
    assert not page.reopen() and page.report['finalized']
    assert '18 Nov 2026' in captured['text'] and 'Report No. 322' in captured['text'] and 'REV 2' in captured['text']
    box, yes, no = dialogs.build_confirm(screen.parent, captured['title'], captured['text'], captured['label'], destructive=True)
    place(box, screen, qtbot); assert_visible(box, yes, no)
    assert box.defaultButton() is no and box.escapeButton() is no and yes.text() == 'Reopen report'


def test_long_paths_wrap_inside_message_boxes(screen, qtbot):
    box, ok = dialogs.build_notify(screen.parent, 'Not saved', f'Not saved: Windows denied access to {LONG_PATH}. Your data is safe.',
                                   details=LONG_PATH)
    geometry = place(box, screen, qtbot); assert_visible(box, ok)
    assert geometry.width() <= 760, geometry  # a long path does not make a giant-width dialog
    assert '\u200b' in box.text()  # break opportunities inserted after path separators


def test_new_voyage_and_restore_confirmations(screen, qtbot):
    for title, label in (('Start a new voyage?', 'Start new voyage'), ('Make this the current journey?', 'Make current'),
                         ('Remove this map region?', 'Remove region'), ('Delete this photo?', 'Delete photo')):
        box, yes, no = dialogs.build_confirm(screen.parent, title, '• one\n• two\n• three', label, destructive='Remove' in label or 'Delete' in label)
        place(box, screen, qtbot); assert_visible(box, yes, no); box.close()


def test_vjr_voyage_history(screen, qtbot, tmp_path):
    from app.ui.pages.vjr_history import VoyageHistoryDialog
    from app.vjr.store import VjrStore
    from vjr_fixture import full_report
    store = VjrStore(tmp_path/'vjr'/'report.json'); store.report = full_report()
    for _ in range(40):
        store.archive()
    dialog = VoyageHistoryDialog(store, screen.parent); place(dialog, screen, qtbot)
    assert_visible(dialog, dialog.restore_button, *[b for b in dialog.findChildren(QPushButton) if b.text() == 'Close'])
    assert dialog.table.rowCount() == 40 and dialog.table.horizontalScrollBar().maximum() == 0


def test_export_multi_error_dialog(screen, qtbot):
    lines = [f'• 0{s} Section {s}: problem {i} in {LONG_PATH}' for s in range(1, 6) for i in range(10)]
    dialog = dialogs.IssuesDialog(screen.parent, 'Excel file not created', 'Your data is safe.', dialogs.issues_from_lines(lines))
    place(dialog, screen, qtbot); assert_visible(dialog, dialog.close_button)
    assert len(dialogs.issues_from_lines(lines)) == 5 and dialog.scroll.horizontalScrollBar().maximum() == 0


def test_map_regions_dialog(screen, qtbot, monkeypatch, tmp_path):
    from app.ui.pages.nav import map_regions_dialog as module
    monkeypatch.setattr(module, 'PackageManager', lambda: SimpleNamespace(installed_regions=lambda **k: [], invalid_regions={}))
    monkeypatch.setattr(module, 'cache_root', lambda: tmp_path/'cache')
    (tmp_path/'regions-catalog.json').write_text(__import__('json').dumps(
        [dict(region_id=f'r{i}', display_name=f'Region {i}', group=f'Group {i % 6}', status='AVAILABLE', download_size=10**8) for i in range(120)]))
    dialog = module.MapRegionsDialog(screen.parent); place(dialog, screen, qtbot)
    assert_visible(dialog, dialog.close_button, *dialog.buttons)


def test_vessel_config_dialog(screen, qtbot):
    from app.nav.vessel_config import VesselConfig
    from app.ui.pages.nav.vessel_config_dialog import VesselConfigDialog
    dialog = VesselConfigDialog(VesselConfig(), screen.parent); place(dialog, screen, qtbot)
    assert_visible(dialog, *dialog.findChildren(QPushButton))


def test_photo_card_qr_fits_vjr_content_width(qtbot, tmp_path):
    from app.ui.pages.vjr_workspace import VjrPage
    from app.vjr.store import VjrStore
    page = VjrPage(VjrStore(tmp_path/'vjr.json'), identity_provider=lambda: {}); qtbot.addWidget(page)
    card = next(iter(page.photo_cards.values()))
    # VJR content width at 1366x768: window minus rail (60), sidebar (214) and margins (~80).
    assert card.minimumSizeHint().width() <= 1366 - 60 - 214 - 80


def test_main_window_is_kept_on_a_visible_screen(qtbot, monkeypatch):
    monkeypatch.setattr(dialogs, 'available_geometry', lambda widget=None: QRect(0, 0, 1280, 680))
    window = QWidget(); qtbot.addWidget(window); window.setGeometry(2600, 900, 1200, 800)  # e.g. a disconnected monitor
    dialogs.ensure_visible_window(window)
    assert QRect(0, 0, 1280, 680).contains(window.geometry()), window.geometry()


def test_fit_rect_follows_parent_monitor():
    second = QRect(1920, 0, 1600, 860)
    rect = dialogs.fit_rect(QRect(0, 0, 700, 500).size(), QRect(2000, 100, 1200, 700), second)
    assert second.contains(rect) and abs(rect.center().x() - 2600) <= 3


def test_keyboard_escape_cancels_and_enter_uses_default(qtbot):
    from app.qt.QtCore import Qt, QTimer
    from app.qt.QtWidgets import QApplication
    dialog = dialogs.IssuesDialog(None, 'T', 'intro', [dict(title='A', items=['x'])]); qtbot.addWidget(dialog)
    dialog.show(); qtbot.waitExposed(dialog); qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible() and dialog.result() == 0  # Esc closes without action
    box, yes, no = dialogs.build_confirm(None, 'Delete?', 'text', 'Delete', destructive=True); qtbot.addWidget(box)
    QTimer.singleShot(200, lambda: qtbot.keyClick(QApplication.activeModalWidget() or box, Qt.Key.Key_Return))
    from app.qt import exec_qt
    exec_qt(box)
    assert box.clickedButton() is no  # Enter on a destructive confirmation = Cancel (safe default)
