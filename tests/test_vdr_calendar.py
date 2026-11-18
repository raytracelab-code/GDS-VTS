"""GDS date input, popup lifetime/placement, and existing VDR store integration."""
import pytest
from app.qt.QtCore import QDate, QPoint, Qt
from app.qt.QtGui import QFontInfo
from app.qt.QtWidgets import QDateEdit, QDialog, QLineEdit, QVBoxLayout, QWidget
from app.ui.pages.vdr.date_picker import CalendarPopover, VdrDatePicker
from app.ui.pages.vdr.workspace import VdrPage
from app.vdr.store import ReportStore
from test_vdr import fixture_report


@pytest.fixture
def host(qtbot):
    widget = QWidget(); widget.setObjectName('vdrPage'); widget.resize(700, 650)
    qtbot.addWidget(widget); widget.show()
    yield widget
    active = CalendarPopover._active() if CalendarPopover._active else None
    if active:
        active.hide()


def picker(host, value='', **kwargs):
    widget = VdrDatePicker(value, today=lambda: QDate(2026, 11, 19), parent=host, **kwargs)
    widget.setGeometry(40, 40, 220, 36); widget.show()
    return widget


@pytest.mark.parametrize('value,report,expected', [
    ('', '2026-11-19', QDate(2026,11,1)),
    ('2025-03-12', '2026-11-19', QDate(2025,3,1)),
    ('', '2024-06-08', QDate(2024,6,1)),
    ('', None, QDate(2026,11,1)),
    ('invalid', '2026-11-19', QDate(2026,11,1)),
])
def test_initial_month_uses_value_report_then_today(host, value, report, expected):
    field = picker(host, value, report_date=lambda: report)
    popup = field.open_calendar()
    assert popup.month == expected and popup.month.year() != 1752
    if not value or value == 'invalid':
        assert not field.date().isValid() and field.iso_value() == ''


def test_selected_today_and_inter_styles(host):
    field = picker(host, '2026-11-18')
    popup = field.open_calendar()
    selected = next(b for b in popup.day_buttons if b.property('selected'))
    today = next(b for b in popup.day_buttons if b.property('today'))
    assert selected.property('isoDate') == '2026-11-18'
    assert today.property('isoDate') == '2026-11-19'
    assert QFontInfo(selected.font()).family() == 'Inter'
    assert QFontInfo(popup.title.font()).family() == 'Inter'


def test_previous_next_month_and_year_rollover(host):
    popup = picker(host, '2026-12-19').open_calendar()
    popup.next.click(); assert popup.month == QDate(2027,1,1)
    popup.previous.click(); assert popup.month == QDate(2026,12,1)
    popup.change_month(-11); assert popup.month == QDate(2026,1,1)
    popup.previous.click(); assert popup.month == QDate(2025,12,1)


def test_selection_commits_iso_and_closes(host, qtbot):
    field = picker(host, report_date='2026-11-19')
    changes = []; field.valueChanged.connect(changes.append)
    popup = field.open_calendar()
    cell = next(b for b in popup.day_buttons if b.property('isoDate') == '2026-11-12')
    qtbot.mouseClick(cell, Qt.MouseButton.LeftButton)
    assert field.iso_value() == '2026-11-12' and field.text() == '12 Nov 2026'
    assert changes == ['2026-11-12'] and not popup.isVisible()


def test_invalid_values_and_typing_do_not_corrupt_value(host, qtbot):
    field = picker(host, '2026-11-12')
    changes = []; field.valueChanged.connect(changes.append)
    assert not field.set_value('2026-02-31')
    assert not field.set_value('12/11/2026')
    field.setFocus(); qtbot.keyClicks(field, 'bad date')
    assert field.iso_value() == '2026-11-12' and field.text() == '12 Nov 2026' and not changes


def test_outside_click_closes_and_second_field_replaces_popup(host, qtbot):
    first = picker(host); second = picker(host); second.move(380, 40)
    popup = first.open_calendar()
    qtbot.mouseClick(host, Qt.MouseButton.LeftButton, pos=QPoint(650, 550))
    assert not popup.isVisible()
    popup = first.open_calendar(); replacement = second.open_calendar()
    assert not popup.isVisible() and replacement.isVisible()
    assert CalendarPopover._active() is replacement


def test_escape_arrows_enter_and_tab(host, qtbot):
    field = picker(host, report_date='2026-11-19')
    following = QLineEdit(host); following.setGeometry(40, 100, 220, 36); following.show()
    QWidget.setTabOrder(field, following)
    popup = field.open_calendar()
    qtbot.keyClick(popup, Qt.Key.Key_Left)
    qtbot.keyClick(popup, Qt.Key.Key_Up)
    assert popup.focused_date == QDate(2026,11,11)
    qtbot.keyClick(popup, Qt.Key.Key_Return)
    assert field.iso_value() == '2026-11-11' and not popup.isVisible()
    popup = field.open_calendar(); qtbot.keyClick(popup, Qt.Key.Key_Escape)
    assert not popup.isVisible()
    popup = field.open_calendar(); qtbot.keyClick(popup, Qt.Key.Key_Tab)
    assert not popup.isVisible() and following.hasFocus()


@pytest.mark.parametrize('position', [QPoint(40,40), QPoint(470,580)])
def test_popup_placement_stays_in_viewport_and_flips_above(host, position):
    field = picker(host); field.move(position)
    popup = field.open_calendar()
    assert popup.viewport_bounds().contains(popup.frameGeometry())
    if position.y() > 400:
        assert popup.geometry().bottom() < field.mapToGlobal(QPoint(0,0)).y()
    else:
        assert popup.geometry().top() > field.mapToGlobal(QPoint(0,field.height())).y()
    assert popup.width() == 300


def test_min_max_disable_dates_without_historical_sentinel(host):
    field = picker(host, report_date='2026-11-19', minimum='2026-11-10', maximum='2026-11-19')
    popup = field.open_calendar()
    assert not popup.previous.isEnabled() and not popup.next.isEnabled()
    assert not next(b for b in popup.day_buttons if b.property('isoDate') == '2026-11-20').isEnabled()
    assert not field.setDate(QDate(2026,11,20)) and field.iso_value() == ''


def test_readonly_disabled_and_modal_lock(host, qtbot):
    field = picker(host)
    field.setReadOnly(True); assert field.open_calendar() is None
    field.setReadOnly(False); field.setEnabled(False); assert field.open_calendar() is None
    field.setEnabled(True); popup = field.open_calendar(); field.setReadOnly(True)
    assert not popup.isVisible()
    field.setReadOnly(False); popup = field.open_calendar()
    dialog = QDialog(host); qtbot.addWidget(dialog); dialog.setModal(True); dialog.show()
    assert not popup.isVisible() and field.open_calendar() is None
    dialog.hide()


@pytest.fixture
def page(qtbot, tmp_path):
    store = ReportStore(tmp_path/'reports.json', today='2026-11-19')
    store.reports[store.current] = fixture_report('2026-11-19')
    page = VdrPage(store); qtbot.addWidget(page); page.resize(1440, 820); page.show(); qtbot.wait(30)
    yield page
    page.save_timer.stop()


def test_date_selection_undo_redo_autosave_and_persistence(page, qtbot):
    editor = page.editors[('hse','lti')]
    popup = editor.open_calendar(); popup.select('2026-11-12')
    assert page.report['hse']['lti'] == '2026-11-12'
    page.undo(); assert page.report['hse']['lti'] == ''
    page.redo(); assert page.report['hse']['lti'] == '2026-11-12'
    qtbot.waitUntil(lambda: page.saved.text().startswith('Saved '), timeout=2000)
    assert ReportStore(page.store.path, today=page.store.today).report['hse']['lti'] == '2026-11-12'


def test_report_date_selection_routes_without_duplicate_report_state(page):
    popup = page.report_date.open_calendar()
    assert popup.month == QDate(2026,11,1)
    assert next(b for b in popup.day_buttons if b.property('selected')).property('isoDate') == '2026-11-19'
    popup.select('2026-11-18')
    assert page.store.current == '2026-11-18' and page.report_date.iso_value() == '2026-11-18'


def test_finalized_dates_lock_and_draft_edit_restores_existing_workflow(page):
    assert page.finalize()
    assert page.editors[('hse','lti')].open_calendar() is None
    assert page.editors[('crew',0,'signon')].open_calendar() is None
    # Report-date navigation remains available even on a finalized report.
    popup = page.report_date.open_calendar(); assert popup is not None; popup.hide()
    page.edit(('meta','captain'), 'Changed')
    assert not page.report['finalized'] and page.editors[('hse','lti')].open_calendar() is not None


@pytest.mark.parametrize('mode,section,path', [('scroll',0,('hse','inj')), ('steps',5,('crew',0,'signon'))])
def test_picker_in_scroll_steps_and_all_date_controls_share_component(page, qtbot, mode, section, path):
    assert not page.findChildren(QDateEdit)
    assert isinstance(page.report_date, VdrDatePicker)
    assert all(isinstance(w, VdrDatePicker) for p,w in page.editors.items() if p[0] == 'hse' and p[1] != 'inc24' or p[-1] == 'signon')
    page.set_mode(mode); page.go_section(section); qtbot.wait(250)
    editor = page.editors[path]
    page.scroll.ensureWidgetVisible(editor); qtbot.wait(30)
    popup = editor.open_calendar()
    assert popup.isVisible() and popup.viewport_bounds().contains(popup.frameGeometry())
