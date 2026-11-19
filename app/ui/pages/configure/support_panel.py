"""Configure → Support & maintenance: About/build info, support bundle, backup/restore, raw data monitor.

One card in the existing Configure card style. All pop-ups use app.ui.dialogs (accepted architecture);
file choice uses the native Windows dialogs.
"""
from pathlib import Path
import sys

from app.qt.QtCore import QSettings, QStandardPaths, Qt, QTimer
from app.qt.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QVBoxLayout)
from app.ui import dialogs


def data_root():
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))


from app.ui.status import busy  # noqa: E402  (shared wait cursor)


def about_text():
    from app.core.support_bundle import runtime_info
    info = runtime_info()
    lines = [('GDS VTS', f"{info['version']} ({info['stage']})"), ('Edition', info['edition']), ('Git commit', info['commit']),
             ('Python', info['python']), ('Qt', f"{info['qt_binding']} / Qt {info['qt_version']}"),
             ('Operating system', info['os']), ('Architecture', info['architecture']),
             ('Packaged build', 'yes' if info['frozen'] else 'no (running from source)')]
    if info['build_info']:
        lines.append(('Build info', info['build_info'].replace('\n', ' · ')))
    return '\n'.join(f'{k}: {v}' for k, v in lines)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('gdsDialog'); self.setStyleSheet(dialogs.STYLE); self.setWindowTitle('About GDS VTS')
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 18, 22, 16); layout.setSpacing(10)
        title = QLabel('About GDS VTS'); title.setObjectName('dialogTitle'); layout.addWidget(title)
        self.text = QPlainTextEdit(about_text()); self.text.setReadOnly(True); self.text.setMinimumHeight(190)
        self.text.setStyleSheet('QPlainTextEdit { background:#FFF; border:1px solid #D8E0E8; border-radius:8px; font-family:"Cascadia Mono","Consolas",monospace; font-size:12px; }')
        layout.addWidget(self.text, 1)
        row = QHBoxLayout(); self.copy_button = QPushButton('Copy build information'); self.copy_button.clicked.connect(self.copy)
        self.copied = QLabel(''); row.addWidget(self.copy_button); row.addWidget(self.copied, 1)
        close = QPushButton('Close'); close.setProperty('primary', True); close.clicked.connect(self.accept); close.setDefault(True); row.addWidget(close)
        layout.addLayout(row); self.resize(560, 330)

    def copy(self):
        QApplication.clipboard().setText(self.text.toPlainText()); self.copied.setText('Copied to clipboard')


class RawMonitorDialog(QDialog):
    """Diagnostic only: last raw lines received from the active connection (bounded, pausable)."""
    def __init__(self, monitor, parent=None):
        super().__init__(parent); self.monitor = monitor; self._sequence = -1; self.paused = False
        self.setObjectName('gdsDialog'); self.setStyleSheet(dialogs.STYLE); self.setWindowTitle('Raw data monitor')
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 18, 22, 16); layout.setSpacing(10)
        title = QLabel('Raw data monitor'); title.setObjectName('dialogTitle'); layout.addWidget(title)
        intro = QLabel(f'Diagnostic view of the last {monitor.raw.maxlen} lines received from the connected device, exactly as received. '
                       'It does not change what the application uses.'); intro.setObjectName('dialogIntro'); intro.setWordWrap(True); layout.addWidget(intro)
        self.view = QPlainTextEdit(); self.view.setReadOnly(True); self.view.setMaximumBlockCount(monitor.raw.maxlen)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setStyleSheet('QPlainTextEdit { background:#0F2440; color:#D9F3EE; border-radius:8px; font-family:"Cascadia Mono","Consolas",monospace; font-size:11px; }')
        self.view.setPlaceholderText('No data received yet. Connect a device in Configure; received lines appear here.')
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.pause_button = QPushButton('Pause'); self.pause_button.setCheckable(True); self.pause_button.toggled.connect(self._pause)
        clear = QPushButton('Clear'); clear.clicked.connect(self.clear)
        copy = QPushButton('Copy'); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.view.toPlainText()))
        close = QPushButton('Close'); close.setProperty('primary', True); close.clicked.connect(self.accept)
        for button in (self.pause_button, clear, copy): row.addWidget(button)
        row.addStretch(); row.addWidget(close); layout.addLayout(row)
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self.refresh); self.timer.start()
        self.resize(760, 460); self.refresh()

    def _pause(self, paused):
        self.paused = paused; self.pause_button.setText('Resume' if paused else 'Pause')

    def clear(self):
        self.monitor.clear(); self.view.clear()

    def refresh(self):
        if self.paused:
            return
        lines, sequence = self.monitor.raw_lines()
        if sequence == self._sequence:
            return
        self._sequence = sequence
        self.view.setPlainText('\n'.join(f'{at:%H:%M:%S} {source:<3} {text}' for at, source, text in lines))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())


class SupportPanel(QFrame):
    """Support & maintenance card. ``window`` supplies flush_all()/lock_after_restore()/diagnostics()."""
    def __init__(self, window_provider=None, settings=None, monitor=None):
        super().__init__(); self.setObjectName('card'); self.window_provider = window_provider or (lambda: self.window())
        self.settings, self.monitor = settings, monitor
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 20, 22, 20); layout.setSpacing(12)
        title = QLabel('SUPPORT & MAINTENANCE'); title.setObjectName('sectionTitle')
        subtitle = QLabel('Build information, troubleshooting files for support, and backups of your reports and settings.')
        subtitle.setObjectName('sectionSubtitle'); subtitle.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(subtitle)
        row = QHBoxLayout(); row.setSpacing(10)
        self.buttons = {}
        for key, text, tip in (('about', 'About && build info', 'Version, edition, commit, Python/Qt and OS (copyable)'),
                               ('bundle', 'Export support bundle…', 'Diagnostics ZIP for support. No report contents, photos, credentials or positions.'),
                               ('backup', 'Create backup…', 'One ZIP with VDR/VJR data, photos and vessel/app settings'),
                               ('restore', 'Restore backup…', 'Validates the backup and keeps a safety copy of the current data first'),
                               ('raw', 'Raw data monitor', 'Diagnostic view of the last lines received from the device')):
            button = QPushButton(text); button.setObjectName('secondaryButton'); button.setToolTip(tip)
            button.clicked.connect(getattr(self, key)); row.addWidget(button); self.buttons[key] = button
        row.addStretch(); layout.addLayout(row)
        self.status = QLabel(''); self.status.setObjectName('sectionSubtitle'); self.status.setWordWrap(True); self.status.hide()
        layout.addWidget(self.status)

    def _settings(self):
        return self.settings if self.settings is not None else QSettings('GDS', 'VTS')

    def _say(self, text):
        self.status.setText(dialogs.wrap_long_tokens(text)); self.status.setVisible(bool(text))

    def about(self):
        dialogs.exec_dialog(AboutDialog(self), self)

    def raw(self):
        from app.telemetry.link_monitor import LinkMonitor
        dialogs.exec_dialog(RawMonitorDialog(self.monitor or LinkMonitor(), self), self)

    def bundle(self):
        from app.core.support_bundle import suggested_name, write_bundle
        path, _ = QFileDialog.getSaveFileName(self, 'Export support bundle', suggested_name(), 'ZIP archives (*.zip)')
        if not path:
            return None
        window = self.window_provider()
        diagnostics = window.diagnostics() if hasattr(window, 'diagnostics') else {}
        settings = self._settings(); values = {k: settings.value(k) for k in settings.allKeys()}
        try:
            with busy():
                written, members = write_bundle(path, values, diagnostics)
        except OSError as error:
            dialogs.notify(self, 'Support bundle not created', 'The support bundle could not be written. Choose another folder and try again.',
                           details=str(error)); return None
        self._say(f'Support bundle saved: {written}')
        dialogs.notify(self, 'Support bundle saved', f'{written.name}\nSaved in {written.parent}\n\n{len(members)} files of diagnostics; '
                       'no report contents, photos, credentials or position history.', kind='information')
        return written

    def backup(self):
        from datetime import datetime
        from app.core.backup import create_backup, settings_snapshot
        path, _ = QFileDialog.getSaveFileName(self, 'Create backup', f'GDS-VTS-backup-{datetime.now():%Y%m%d-%H%M}.zip', 'ZIP archives (*.zip)')
        if not path:
            return None
        window = self.window_provider()
        if hasattr(window, 'flush_all') and not window.flush_all():
            if not dialogs.confirm(self, 'Some changes are not saved', 'The latest changes could not be saved, so they will not be in this backup.\n\n'
                                   'Create the backup with the data that is already saved?', 'Create backup anyway'):
                return None
        try:
            with busy():
                manifest = create_backup(path, data_root(), settings_snapshot(self._settings()))
        except OSError as error:
            dialogs.notify(self, 'Backup not created', 'The backup could not be written. Your data is unchanged. Choose another folder and try again.',
                           details=str(error)); return None
        self._say(f'Backup saved: {path}')
        dialogs.notify(self, 'Backup created', f'{Path(path).name}\nSaved in {Path(path).parent}\n\n{len(manifest["files"])} files backed up.', kind='information')
        return manifest

    def restore(self):
        from app.core.backup import BackupError, apply_settings_to, describe, inspect_backup, restore_backup
        path, _ = QFileDialog.getOpenFileName(self, 'Restore backup', '', 'GDS VTS backups (*.zip)')
        if not path:
            return None
        try:
            with busy():
                summary = inspect_backup(path)
        except BackupError as error:
            dialogs.notify(self, 'Backup cannot be restored', f'{error}\n\nYour current data is unchanged.'); return None
        if not dialogs.confirm(self, 'Restore this backup?', describe(summary) + '\n\nYour current reports, journeys, photos and settings are replaced. '
                               'A safety copy of the current data is saved first. GDS VTS then needs a restart.', 'Restore backup', destructive=True):
            return None
        window = self.window_provider()
        if hasattr(window, 'flush_all'):
            window.flush_all()
        safety_dir = data_root()/'backups'
        try:
            with busy():
                summary, safety = restore_backup(path, data_root(), safety_dir, apply_settings_to(self._settings()))
        except BackupError as error:
            dialogs.notify(self, 'Restore failed', f'{error}', details=f'The archive was kept for diagnostics in {safety_dir}.'); return None
        if hasattr(window, 'lock_after_restore'):
            window.lock_after_restore()
        self._say(f'Backup restored. Safety copy of the previous data: {safety}')
        if dialogs.confirm(self, 'Backup restored', 'The backup was restored. GDS VTS must restart to load it; editing is paused until then.\n\n'
                           f'A safety copy of the previous data was saved as {safety.name}.', 'Restart now', 'Later'):
            restart_application()
        return summary


def restart_application():
    from app.qt.QtCore import QProcess
    args = sys.argv[1:] if getattr(sys, 'frozen', False) else sys.argv
    QProcess.startDetached(sys.executable, args)
    QApplication.instance().quit()
