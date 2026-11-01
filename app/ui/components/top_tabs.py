from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

class TopTabs(QWidget):
    def __init__(self, navigate):
        super().__init__(); self.setObjectName('topTabs'); layout=QHBoxLayout(self); layout.setContentsMargins(24,0,24,0); layout.setSpacing(8); self.buttons={}
        for name in ('Configure','VDR','VJR','Nav'):
            button=QPushButton(name.upper()); button.setObjectName('moduleTab'); button.setCheckable(True); button.clicked.connect(lambda _, n=name: self._select(navigate,n)); layout.addWidget(button); self.buttons[name]=button
        self.buttons['Configure'].setChecked(True); layout.addStretch(); self.set_locked(False)
    def set_locked(self, unlocked):
        for name in ('VDR','VJR','Nav'):
            self.buttons[name].setEnabled(unlocked); self.buttons[name].setText(name.upper() if unlocked else f'{name.upper()}  ·  LOCKED')
    def _select(self,navigate,name):
        for button in self.buttons.values(): button.setChecked(False)
        self.buttons[name].setChecked(True); navigate(name)
