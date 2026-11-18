from pathlib import Path
from app.qt.QtSvgWidgets import QSvgWidget
from app.qt.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
class Sidebar(QWidget):
    def __init__(self, navigate):
        super().__init__(); self.setObjectName('sidebar'); self.setFixedWidth(220); layout=QVBoxLayout(self); layout.setContentsMargins(14,20,14,20); layout.setSpacing(8)
        logo=QSvgWidget(str(Path(__file__).resolve().parents[2] / 'resources' / 'theme' / 'deep-current' / 'logos' / 'logo-small.svg')); logo.setFixedSize(44,44); layout.addWidget(logo)
        brand=QLabel('GDS VTS'); brand.setObjectName('brand'); layout.addWidget(brand)
        sub=QLabel('VESSEL TELEMETRY SYSTEM'); sub.setObjectName('productSubtle'); layout.addWidget(sub); layout.addSpacing(18)
        self.buttons={}
        for name in ('Configure','VDR','VJR','Nav'):
            b=QPushButton(name); b.setObjectName('nav'); b.setCheckable(True); b.clicked.connect(lambda _=False, n=name: self._select(navigate,n)); layout.addWidget(b); self.buttons[name]=b
        self.buttons['Configure'].setChecked(True)
        layout.addStretch(); self.set_locked(False)
    def set_locked(self, unlocked):
        for name in ('VDR','VJR','Nav'):
            self.buttons[name].setEnabled(unlocked); self.buttons[name].setText(name if unlocked else f'🔒  {name}')
    def _select(self,navigate,name):
        for button in self.buttons.values(): button.setChecked(False)
        self.buttons[name].setChecked(True); navigate(name)
