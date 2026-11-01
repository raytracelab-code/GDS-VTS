from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QStackedWidget
from app.core.app_state import AppState
from app.transports import UsbTransport,BleTransport,TransportManager
from app.telemetry.telemetry_state import TelemetryStateService
from .theme import STYLESHEET
from .components.top_header import TopHeader
from .components.top_tabs import TopTabs
from .pages.configure.configure_page import ConfigurePage
from .pages import vdr_page,vjr_page
from .pages.nav.nav_page import NavPage
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('GDS VTS'); self.resize(1200,800); self.setStyleSheet(STYLESHEET); self.app_state=AppState(); self.state=TelemetryStateService(); self.usb=UsbTransport(); self.ble=BleTransport(); TransportManager(self.usb,self.ble,self.state.ingest)
        root=QWidget(); root.setObjectName('appRoot'); self.setCentralWidget(root); c=QVBoxLayout(root); c.setContentsMargins(0,0,0,0); c.setSpacing(0); self.header=TopHeader(); c.addWidget(self.header); self.tabs=TopTabs(self.navigate); c.addWidget(self.tabs); self.stack=QStackedWidget(); self.configure=ConfigurePage(self.usb,self.ble,self.state); self.nav=NavPage(self.state); self.stack.addWidget(self.configure); self.stack.addWidget(vdr_page.page()); self.stack.addWidget(vjr_page.page()); self.stack.addWidget(self.nav); c.addWidget(self.stack)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
    def navigate(self,name): self.stack.setCurrentIndex({'Configure':0,'VDR':1,'VJR':2,'Nav':3}[name])
    def refresh(self):
        self.state.tick(); self.configure.refresh(); self.nav.refresh(); status=self.state.telemetry_status; self.header.status.setText(f'●  {status.value}' + (f' · {self.state.active_source.value}' if self.state.active_source else '')); self.app_state.observe_status(status); self.tabs.set_locked(self.app_state.modules_unlocked)
