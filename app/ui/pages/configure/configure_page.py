from PySide6.QtWidgets import QWidget,QVBoxLayout,QScrollArea
from .connection_panel import ConnectionPanel
from .telemetry_panel import TelemetryPanel
from .diagnostics_panel import DiagnosticsPanel
class ConfigurePage(QWidget):
    def __init__(self, usb, ble, state):
        super().__init__(); self.setObjectName('configurePage'); outer=QVBoxLayout(self); outer.setContentsMargins(24,20,24,20); scroll=QScrollArea(); scroll.setWidgetResizable(True); host=QWidget(); l=QVBoxLayout(host); l.setContentsMargins(0,0,4,0); l.setSpacing(16); self.connection=ConnectionPanel(usb,ble,state); self.telemetry=TelemetryPanel(); self.diagnostics=DiagnosticsPanel(state); l.addWidget(self.connection); l.addWidget(self.telemetry); l.addWidget(self.diagnostics); l.addStretch(); scroll.setWidget(host); outer.addWidget(scroll)
    def refresh(self): self.connection.refresh(); self.diagnostics.refresh()
