"""Lightweight first-run setup (three steps). Shown only when vessel identity is missing and the
setup was never completed; completion is stored as QSettings 'app/first_run_complete'."""
from app.qt.QtCore import QSettings
from app.qt.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget
from app.core.vessel_identity import load_identity
from app.ui import dialogs

DONE_KEY = 'app/first_run_complete'


def needs_first_run(settings=None):
    settings = settings if settings is not None else QSettings('GDS', 'VTS')
    if str(settings.value(DONE_KEY, 'false')).lower() in ('true', '1'):
        return False
    identity = load_identity(settings)
    return not (identity['vessel'] and identity['hireDate'])


def mark_done(settings=None):
    settings = settings if settings is not None else QSettings('GDS', 'VTS')
    settings.setValue(DONE_KEY, True); settings.sync()


class FirstRunDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent); self.settings = settings
        self.setObjectName('gdsDialog'); self.setStyleSheet(dialogs.STYLE); self.setWindowTitle('Set up GDS VTS')
        root = QVBoxLayout(self); root.setContentsMargins(22, 18, 22, 16); root.setSpacing(10)
        self.step_label = QLabel(''); self.step_label.setObjectName('dialogIntro'); root.addWidget(self.step_label)
        self.pages = QStackedWidget(); root.addWidget(self.pages, 1)
        from app.ui.pages.configure.identity_panel import IdentityPanel
        self.identity = IdentityPanel(settings)
        step1 = self._page('Vessel & client', 'These details appear on every VDR and VJR report and export. '
                           'Vessel Name and Date of Hire are needed before a report can be finalized. You can change them later in Configure.')
        step1.layout().addWidget(self.identity)
        step2 = self._page('Connect the sensor (optional)', 'GDS VTS receives live telemetry from the Patroller-I unit by USB cable or Bluetooth LE.\n\n'
                           '• USB: plug in the cable, then Configure → SCAN USB → choose the port → CONNECT.\n'
                           '• Bluetooth LE: Configure → SCAN BLE → choose the device → CONNECT (Windows 10 1709 or later).\n\n'
                           'Reports (VDR, VJR) can be completed without a connection. You can do this later.')
        step3 = self._page('Ready', 'Setup is complete. Use the navigation rail on the left:\n\n'
                           '• SETUP (Configure) — vessel & client details, sensor connection, support & backups\n'
                           '• VDR — Vessel Daily Report\n• VJR — Vessel Journey Report\n• NAV — navigation map')
        for page in (step1, step2, step3):
            self.pages.addWidget(page)
        footer = QHBoxLayout()
        self.skip_button = QPushButton('Skip setup'); self.skip_button.clicked.connect(self.finish)
        self.back_button = QPushButton('Back'); self.back_button.clicked.connect(lambda: self.go(self.pages.currentIndex() - 1))
        self.next_button = QPushButton('Next'); self.next_button.setProperty('primary', True); self.next_button.clicked.connect(self.next)
        footer.addWidget(self.skip_button); footer.addStretch(); footer.addWidget(self.back_button); footer.addWidget(self.next_button)
        root.addLayout(footer); self.resize(860, 600); self.go(0)

    @staticmethod
    def _page(title, text):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)
        heading = QLabel(title); heading.setObjectName('dialogTitle'); layout.addWidget(heading)
        body = QLabel(text); body.setWordWrap(True); layout.addWidget(body)
        return page

    def go(self, index):
        index = max(0, min(2, index)); self.pages.setCurrentIndex(index)
        self.step_label.setText(f'Step {index + 1} of 3')
        self.back_button.setEnabled(index > 0); self.next_button.setText('Finish' if index == 2 else 'Next')
        self.pages.widget(index).layout().addStretch() if index and self.pages.widget(index).layout().count() == 2 else None

    def next(self):
        index = self.pages.currentIndex()
        if index == 0 and self.identity.save_button.isEnabled() and not self.identity.save():
            return  # invalid entries stay on step 1 with inline errors
        if index == 2:
            return self.finish()
        self.go(index + 1)

    def finish(self):
        mark_done(self.settings); self.accept()
