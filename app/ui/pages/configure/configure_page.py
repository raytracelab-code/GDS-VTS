from app.qt.QtWidgets import QWidget,QVBoxLayout,QScrollArea
from .connection_panel import ConnectionPanel
from .telemetry_panel import TelemetryPanel
from .diagnostics_panel import DiagnosticsPanel
from .identity_panel import IdentityPanel
from .support_panel import SupportPanel
class ConfigurePage(QWidget):
    def __init__(self, usb, ble, state, settings=None, monitor=None):
        super().__init__(); self.setObjectName('configurePage'); self.state=state; outer=QVBoxLayout(self); outer.setContentsMargins(24,20,24,20); scroll=QScrollArea(); scroll.setWidgetResizable(True); host=QWidget(); l=QVBoxLayout(host); l.setContentsMargins(0,0,4,0); l.setSpacing(16)
        self.identity=IdentityPanel(settings); self.connection=ConnectionPanel(usb,ble,state,monitor); self.telemetry=TelemetryPanel(); self.diagnostics=DiagnosticsPanel(state,monitor); self.support=SupportPanel(settings=settings,monitor=monitor)
        l.addWidget(self.identity); l.addWidget(self.connection); l.addWidget(self.telemetry); l.addWidget(self.diagnostics); l.addWidget(self.support); l.addStretch(); scroll.setWidget(host); outer.addWidget(scroll)
    def refresh(self):
        self.connection.refresh(); self.diagnostics.refresh(); self.telemetry.update_frame(self.state.latest_frame, self.state.telemetry_status)
