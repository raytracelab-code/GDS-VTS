from pathlib import Path
from app.qt.QtCore import Qt, QSize
from app.qt.QtSvgWidgets import QSvgWidget
from app.qt.QtWidgets import QWidget, QVBoxLayout, QToolButton
from .nav_icons import nav_icon

# Abbreviations are spelled out on hover (GDS-AUDIT-049).
TOOLTIPS={'Configure':'Configure — vessel & client details and sensor connection','VDR':'VDR — Vessel Daily Report',
          'VJR':'VJR — Vessel Journey Report','Nav':'NAV — Navigation map'}

class TopTabs(QWidget):
    def __init__(self, navigate):
        super().__init__(); self.setObjectName('navigationRail'); self.setFixedWidth(60)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.setStyleSheet('''
          #navigationRail { background:#0a1628; border-right:1px solid #263849; }
          #navigationRail QToolButton { color:#92a8b9; background:transparent; border:0; border-radius:10px; font-size:9px; padding:5px 0; }
          #navigationRail QToolButton:hover { background:#162d43; color:#edf6f5; }
          #navigationRail QToolButton:checked { background:#1e3a5f; color:#9ee4d6; border-left:2px solid #2dd4bf; }
          #navigationRail QToolButton:disabled { color:#4e6277; }
        ''')
        layout=QVBoxLayout(self); layout.setContentsMargins(5,14,5,12); layout.setSpacing(10); self.buttons={}
        logo=QSvgWidget(str(Path(__file__).resolve().parents[2]/'resources/theme/deep-current/logos/logo-small.svg'))
        logo.setFixedSize(34,34);logo.setToolTip('GDS VTS · Deep Current');layout.addWidget(logo,0,Qt.AlignmentFlag.AlignHCenter);layout.addSpacing(22)
        for name in ('Configure','VDR','VJR','Nav'):
            button=QToolButton();button.setText('SETUP' if name=='Configure' else name.upper());button.setIcon(nav_icon(name));button.setIconSize(QSize(22,22));button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon);button.setFixedSize(50,52);button.setToolTip(TOOLTIPS[name]);button.setAccessibleName(name);button.setCheckable(True);button.clicked.connect(lambda _=False, n=name:self._select(navigate,n));layout.addWidget(button);self.buttons[name]=button
        self.buttons['Configure'].setChecked(True); layout.addStretch(); self.set_locked(False)
    def set_locked(self, unlocked):
        # VDR supports manual reports without a live telemetry source.
        for name in ('Configure','VDR','VJR'):
            self.buttons[name].setEnabled(True);self.buttons[name].setToolTip(TOOLTIPS[name])
        # VJR now supports manually maintained journeys without live telemetry.
        self.buttons['Nav'].setEnabled(True); self.buttons['Nav'].setText('NAV'); self.buttons['Nav'].setToolTip(TOOLTIPS['Nav'])
    def _select(self,navigate,name):
        for button in self.buttons.values(): button.setChecked(False)
        self.buttons[name].setChecked(True); navigate(name)
