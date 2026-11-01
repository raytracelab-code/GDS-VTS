from pathlib import Path
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

class TopHeader(QWidget):
    def __init__(self):
        super().__init__(); self.setObjectName('header'); self.setFixedHeight(68); layout=QHBoxLayout(self); layout.setContentsMargins(24,10,24,10); layout.setSpacing(12)
        logo=QSvgWidget(str(Path(__file__).resolve().parents[2] / 'resources' / 'theme' / 'deep-current' / 'logos' / 'logo-small.svg')); logo.setFixedSize(38,38); layout.addWidget(logo)
        text=QVBoxLayout(); text.setSpacing(0); brand=QLabel('GDS VTS'); brand.setObjectName('brandDark'); subtitle=QLabel('VESSEL TELEMETRY SYSTEM'); subtitle.setObjectName('productSubtleDark'); text.addWidget(brand); text.addWidget(subtitle); layout.addLayout(text); layout.addStretch()
        self.status=QLabel('●  NO SOURCE'); self.status.setObjectName('statusNeutral'); layout.addWidget(self.status)
