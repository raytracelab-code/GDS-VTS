from app.qt.QtCore import QTimer
from app.qt.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QStackedWidget
from app.core.app_state import AppState
from app.transports import UsbTransport,BleTransport,TransportManager
from app.telemetry.telemetry_state import TelemetryStateService
from app.nav.events import SquallEventService
from app.nav.maritime.runtime import MaritimeRuntime
from .theme import STYLESHEET
from .components.top_header import TopHeader
from .components.top_tabs import TopTabs
from .pages.configure.configure_page import ConfigurePage
from .pages import vdr_page,vjr_page
from .pages.nav.nav_page import NavPage
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); from app.version import display_version; self.setWindowTitle('GDS VTS ' + display_version()); self.resize(1200,800); self.setStyleSheet(STYLESHEET); self.app_state=AppState(); self.state=TelemetryStateService(); self.squall_event_service=SquallEventService(); self.usb=UsbTransport(); self.ble=BleTransport(); from app.telemetry.link_monitor import LinkMonitor; self.link_monitor=LinkMonitor(); TransportManager(self.usb,self.ble,self.link_monitor.wrap(self.state.ingest))
        self.maritime_runtime=MaritimeRuntime(self)
        self.maritime_service=self.maritime_runtime.service
        root=QWidget(); root.setObjectName('appRoot'); self.setCentralWidget(root)
        shell=QHBoxLayout(root);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        self.tabs=TopTabs(self.navigate);shell.addWidget(self.tabs)
        workspace=QWidget();c=QVBoxLayout(workspace);c.setContentsMargins(0,0,0,0);c.setSpacing(0);shell.addWidget(workspace,1)
        self.header=TopHeader();c.addWidget(self.header)
        self.stack=QStackedWidget(); self.configure=ConfigurePage(self.usb,self.ble,self.state,None,self.link_monitor); self.nav=NavPage(self.state,self.squall_event_service,self.maritime_runtime); self.vdr=vdr_page.page(); self.vjr=vjr_page.page(); self.stack.addWidget(self.configure); self.stack.addWidget(self.vdr); self.stack.addWidget(self.vjr); self.stack.addWidget(self.nav); c.addWidget(self.stack)
        identity_panel=getattr(self.configure,'identity',None)
        if identity_panel is not None: identity_panel.identityChanged.connect(self._identity_changed)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
        self.event_timer=QTimer(self); self.event_timer.timeout.connect(self.squall_event_service.evaluate_time); self.event_timer.timeout.connect(lambda:self.nav._update_events(self.nav.bridge.getEventState())); self.event_timer.timeout.connect(lambda:self.nav.bridge.publishEventState()); self.event_timer.start(1000)
    def _identity_changed(self,_identity):
        # VDR/VJR read Configure on every refresh; repaint them so no stale identity is shown.
        for page,method in ((self.vdr,'refresh_values'),(self.vjr,'refresh')):
            refresh=getattr(page,method,None)
            if callable(refresh): refresh()
    def navigate(self,name):
        # VDR, VJR and NAV carry their own title bars; the global header is shown on Configure only.
        self.header.setVisible(name=='Configure')
        self.stack.setCurrentIndex({'Configure':0,'VDR':1,'VJR':2,'Nav':3}[name])
    def showEvent(self,event):
        super().showEvent(event)
        if not getattr(self,'_placed',False):
            # First show: keep the whole window on a connected screen and inside its usable area (taskbar excluded).
            self._placed=True
            from app.ui.dialogs import ensure_visible_window
            if not self.isMaximized() and not self.isFullScreen(): ensure_visible_window(self)
    def flush_all(self):
        """Save VDR and VJR now; False when either could not be saved (its banner explains why)."""
        ok=True
        for page in (self.vdr,self.vjr):
            flush=getattr(page,'flush_save',None)
            if callable(flush) and flush() is False: ok=False
        return ok
    def lock_after_restore(self):
        """After a backup restore the in-memory stores are stale: stop them saving until restart."""
        message='Data was restored from a backup. Restart GDS VTS to load it; editing is paused until then.'
        for page in (self.vdr,self.vjr):
            store=getattr(page,'store',None)
            if store is not None: store.load_error=message
        if hasattr(self.vdr,'show_banner'): self.vdr.show_banner(message,'error')
        if hasattr(self.vjr,'_storage_error'): self.vjr._storage_error(OSError(message))
    def diagnostics(self):
        """Live, non-sensitive state for the support bundle (counters and states; no positions)."""
        state=self.state; connection=getattr(self.configure,'connection',None)
        from app.core.platform_capabilities import native_ble_available
        return dict(telemetry_status=state.telemetry_status.value,active_source=state.active_source.value if state.active_source else None,
                    valid_frames=state.valid_frame_count,invalid_frames=state.invalid_frame_count,
                    last_valid_frame_time=state.last_valid_frame_time.isoformat() if state.last_valid_frame_time else None,
                    link=self.link_monitor.snapshot(),connected=dict(getattr(connection,'connected',{})),
                    capabilities=dict(native_ble=native_ble_available()),
                    renderer_state=getattr(getattr(self.nav,'renderer_health',None),'state',None),
                    squall_feed=self.squall_event_service.feed_status()['state'] if hasattr(self.squall_event_service,'feed_status') else None)
    def maybe_first_run(self):
        from app.ui.first_run import FirstRunDialog,needs_first_run
        if needs_first_run():
            from app.ui import dialogs
            dialog=FirstRunDialog(self); dialogs.exec_dialog(dialog,self)
            if getattr(self.configure,'identity',None) is not None: self.configure.identity.reload()
            self._identity_changed(None)
    def closeEvent(self,event):
        # Never close silently over changes that could not be saved (normal autosave asks nothing).
        if not getattr(self,'_closing_confirmed',False) and not self.flush_all():
            from app.ui import dialogs
            if not dialogs.confirm(self,'Close without saving?','Your latest VDR/VJR changes could not be saved (see the red message on that page). '
                                   'Closing now loses those changes.\n\nCancel to stay and fix the problem (for example free disk space), or close anyway.',
                                   'Close without saving',destructive=True):
                event.ignore(); return
        self._closing_confirmed=True
        self.timer.stop();self.event_timer.stop()
        # Release COM ports / BLE links so a relaunch never finds the port held by this process.
        connection=getattr(self.configure,'connection',None)
        if connection is not None and hasattr(connection,'disconnect_all'): connection.disconnect_all()
        for page in (self.vdr,self.vjr):
            flush=getattr(page,'flush_save',None)
            if callable(flush): flush()
        self.maritime_runtime.close()
        super().closeEvent(event)
    def ingest_squall_event(self,payload): return self.squall_event_service.ingest_mapping(payload)
    def ingest_squall_json(self,text): return self.squall_event_service.ingest_json(text)
    def refresh(self):
        self.state.tick(); self.configure.refresh(); self.nav.refresh(); status=self.state.telemetry_status; from app.ui.status import set_badge; self.header.status.setObjectName('statusBadge'); set_badge(self.header.status, status.value + (f' · {self.state.active_source.value}' if self.state.active_source else '')); self.app_state.observe_status(status); self.tabs.set_locked(self.app_state.modules_unlocked)
        # GDS-AUDIT-021: a squall alert is visible from every page through the NAV rail button.
        level=getattr(self.nav,'squall_alert_level','')
        if level: self.tabs.buttons['Nav'].setText('NAV ⚠'); self.tabs.buttons['Nav'].setToolTip(f'NAV — squall {level.lower()} alert')
