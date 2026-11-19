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
        super().__init__(); from app.version import display_version; self.setWindowTitle('GDS VTS ' + display_version()); self.resize(1200,800); self.setStyleSheet(STYLESHEET); self.app_state=AppState(); self.state=TelemetryStateService(); self.squall_event_service=SquallEventService(); self.usb=UsbTransport(); self.ble=BleTransport(); TransportManager(self.usb,self.ble,self.state.ingest)
        self.maritime_runtime=MaritimeRuntime(self)
        self.maritime_service=self.maritime_runtime.service
        root=QWidget(); root.setObjectName('appRoot'); self.setCentralWidget(root)
        shell=QHBoxLayout(root);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        self.tabs=TopTabs(self.navigate);shell.addWidget(self.tabs)
        workspace=QWidget();c=QVBoxLayout(workspace);c.setContentsMargins(0,0,0,0);c.setSpacing(0);shell.addWidget(workspace,1)
        self.header=TopHeader();c.addWidget(self.header)
        self.stack=QStackedWidget(); self.configure=ConfigurePage(self.usb,self.ble,self.state); self.nav=NavPage(self.state,self.squall_event_service,self.maritime_runtime); self.vdr=vdr_page.page(); self.vjr=vjr_page.page(); self.stack.addWidget(self.configure); self.stack.addWidget(self.vdr); self.stack.addWidget(self.vjr); self.stack.addWidget(self.nav); c.addWidget(self.stack)
        identity_panel=getattr(self.configure,'identity',None)
        if identity_panel is not None: identity_panel.identityChanged.connect(self._identity_changed)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
        self.event_timer=QTimer(self); self.event_timer.timeout.connect(self.squall_event_service.evaluate_time); self.event_timer.timeout.connect(lambda:self.nav._update_events(self.nav.bridge.getEventState())); self.event_timer.start(1000)
    def _identity_changed(self,_identity):
        # VDR/VJR read Configure on every refresh; repaint them so no stale identity is shown.
        for page,method in ((self.vdr,'refresh_values'),(self.vjr,'refresh')):
            refresh=getattr(page,method,None)
            if callable(refresh): refresh()
    def navigate(self,name):
        # VDR, VJR and NAV carry their own title bars; the global header is shown on Configure only.
        self.header.setVisible(name=='Configure')
        self.stack.setCurrentIndex({'Configure':0,'VDR':1,'VJR':2,'Nav':3}[name])
    def closeEvent(self,event):
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
        self.state.tick(); self.configure.refresh(); self.nav.refresh(); status=self.state.telemetry_status; self.header.status.setText(f'●  {status.value}' + (f' · {self.state.active_source.value}' if self.state.active_source else '')); self.app_state.observe_status(status); self.tabs.set_locked(self.app_state.modules_unlocked)
