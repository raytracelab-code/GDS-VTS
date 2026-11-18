"""Actual MainWindow construction/routing with hardware and NAV services isolated.

The real rail, refresh, router, stack, session gate and reference VDR page are
used. Only external services and unrelated page contents are replaced, so these
checks never connect USB/BLE/network or write to the production report store.
Normal unmodified main.py is exercised separately for desktop acceptance.
"""
from types import SimpleNamespace
import pytest
from app.qt.QtCore import Qt
from app.qt.QtWidgets import QWidget
from app.core.models import TelemetryStatus
from app.ui.pages.vdr.workspace import VdrPage
from app.vdr.store import ReportStore
from test_vdr import fixture_report


@pytest.fixture
def shell(qtbot, tmp_path, monkeypatch):
    from app.ui import main_window as module
    state = SimpleNamespace(telemetry_status=TelemetryStatus.NO_SOURCE, active_source=None,
                            ingest=lambda *a: None, tick=lambda: None)

    class UnrelatedPage(QWidget):
        def __init__(self, *args):
            super().__init__()
        def refresh(self):
            pass

    monkeypatch.setattr(module, 'TelemetryStateService', lambda: state)
    monkeypatch.setattr(module, 'UsbTransport', lambda: None)
    monkeypatch.setattr(module, 'BleTransport', lambda: None)
    monkeypatch.setattr(module, 'TransportManager', lambda *args: None)
    monkeypatch.setattr(module, 'MaritimeRuntime', lambda *args: SimpleNamespace(service=None, close=lambda: None))
    monkeypatch.setattr(module, 'ConfigurePage', UnrelatedPage)
    monkeypatch.setattr(module, 'NavPage', UnrelatedPage)
    store = ReportStore(tmp_path/'reports.json', today='2026-11-19')
    vdr = VdrPage(store)
    created = []

    def create_vdr():
        created.append(vdr)
        return vdr

    monkeypatch.setattr(module.vdr_page, 'page', create_vdr)
    window = module.MainWindow()
    window.timer.stop(); window.event_timer.stop()
    qtbot.addWidget(window); window.resize(1200, 800); window.show()
    window.refresh()
    yield window, vdr, state, created
    vdr.save_timer.stop()


@pytest.mark.parametrize('status', list(TelemetryStatus))
def test_vdr_click_routes_existing_page_in_every_telemetry_state(shell, qtbot, status):
    window, vdr, state, created = shell
    state.telemetry_status = status
    window.refresh()
    assert window.tabs.buttons['VDR'].isEnabled()
    assert window.tabs.buttons['VDR'].toolTip() == 'VDR'
    qtbot.mouseClick(window.tabs.buttons['VDR'], Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is vdr
    assert vdr.isVisible() and window.tabs.buttons['VDR'].isChecked()
    assert not window.tabs.buttons['Configure'].isChecked()
    assert created == [vdr] and window.stack.count() == 4
    # The next telemetry refresh must not relock or reroute VDR.
    window.refresh()
    assert window.stack.currentWidget() is vdr and window.tabs.buttons['VDR'].isEnabled()


@pytest.mark.parametrize('name,index', [('Configure', 0), ('Nav', 3)])
def test_always_available_routes_without_source(shell, qtbot, name, index):
    window, vdr, state, _ = shell
    qtbot.mouseClick(window.tabs.buttons['VDR'], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.tabs.buttons[name], Qt.MouseButton.LeftButton)
    assert window.stack.currentIndex() == index and window.tabs.buttons[name].isChecked()
    assert state.telemetry_status is TelemetryStatus.NO_SOURCE


def test_vjr_gate_is_preserved_before_and_after_live(shell, qtbot):
    window, vdr, state, _ = shell
    for status in (TelemetryStatus.NO_SOURCE, TelemetryStatus.CONNECTED_WAITING, TelemetryStatus.STALE, TelemetryStatus.LOST):
        state.telemetry_status = status; window.refresh()
        assert not window.tabs.buttons['VJR'].isEnabled()
        assert 'Locked until telemetry is live' in window.tabs.buttons['VJR'].toolTip()
    state.telemetry_status = TelemetryStatus.LIVE; window.refresh()
    assert window.tabs.buttons['VJR'].isEnabled()
    qtbot.mouseClick(window.tabs.buttons['VJR'], Qt.MouseButton.LeftButton)
    assert window.stack.currentIndex() == 2
    state.telemetry_status = TelemetryStatus.LOST; window.refresh()
    assert window.tabs.buttons['VJR'].isEnabled()  # Existing session unlock remains sticky.


def test_offline_vdr_edit_navigation_autosave_and_history(shell, qtbot):
    window, vdr, state, _ = shell
    qtbot.mouseClick(window.tabs.buttons['VDR'], Qt.MouseButton.LeftButton)
    vdr.navigate_date(-1); assert vdr.store.current == '2026-11-18'
    vdr.navigate_date(1); assert vdr.store.current == '2026-11-19'
    vdr.set_mode('steps'); vdr.go_section(4)
    assert not vdr.sections[4].isHidden() and vdr.sections[0].isHidden()
    vdr.set_mode('scroll'); assert all(not s.isHidden() for s in vdr.sections)
    editor = vdr.editors[('meta', 'captain')]
    editor.setFocus(); qtbot.keyClicks(editor, 'Offline Captain')
    assert vdr.report['meta']['captain'] == 'Offline Captain'
    vdr.undo(); assert vdr.report['meta']['captain'] != 'Offline Captain'
    vdr.redo(); assert vdr.report['meta']['captain'] == 'Offline Captain'
    qtbot.waitUntil(lambda: vdr.saved.text().startswith('Saved '), timeout=2000)
    assert ReportStore(vdr.store.path, today=vdr.store.today).report == vdr.report
    assert state.telemetry_status is TelemetryStatus.NO_SOURCE


def test_offline_vdr_validation_finalize_pdf_export_import(shell, qtbot, tmp_path, monkeypatch):
    from app.ui.pages.vdr import workspace
    window, vdr, state, _ = shell
    qtbot.mouseClick(window.tabs.buttons['VDR'], Qt.MouseButton.LeftButton)
    errors = []; monkeypatch.setattr(vdr, 'show_errors', lambda e: errors.extend(e))
    assert not vdr.finalize() and errors and not vdr.download_button.isEnabled()
    # Deterministic report data lives only in this test's temporary store.
    vdr.store.import_report(fixture_report('2026-11-19')); vdr._rebuild()
    assert vdr.finalize() and vdr.download_button.isEnabled()
    path = tmp_path/'offline-report.pdf'
    monkeypatch.setattr(workspace.QFileDialog, 'getSaveFileName', lambda *a: (str(path), 'PDF'))
    vdr.download(); assert path.exists()
    vdr.edit(('meta', 'captain'), 'Changed')
    monkeypatch.setattr(workspace.QFileDialog, 'getOpenFileName', lambda *a: (str(path), 'PDF'))
    monkeypatch.setattr(workspace.QMessageBox, 'question', lambda *a: workspace.QMessageBox.StandardButton.Yes)
    vdr.import_report()
    assert vdr.report['meta']['captain'] == 'Test Captain' and vdr.report['finalized']
    assert state.telemetry_status is TelemetryStatus.NO_SOURCE
