"""Configure → Vessel & Client: the single editable source of vessel identity."""
from app.qt.QtCore import QDate, Signal
from app.qt.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from app.core.vessel_identity import FIELDS, IdentityError, load_identity, normalize_identity, save_identity
from app.ui.pages.vdr.date_picker import VdrDatePicker

HINTS = {
    'vessel': 'Shown on every VDR and VJR report and export.',
    'imo': '7 digits, e.g. 9074729. Optional.',
    'client': 'Charterer / client shown on reports.',
    'client_id': 'Client reference used in VJR exports. Optional.',
    'hireDate': 'Day 1 of the charter. VDR Report No. counts from this date.',
    'capacity': 'Used by VJR deck utilisation. Optional.',
}


class IdentityPanel(QFrame):
    identityChanged = Signal(dict)

    def __init__(self, settings=None):
        super().__init__(); self.setObjectName('card'); self.settings = settings
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 20, 22, 20); layout.setSpacing(14)
        head = QHBoxLayout(); titles = QVBoxLayout(); titles.setSpacing(3)
        title = QLabel('VESSEL & CLIENT'); title.setObjectName('sectionTitle')
        subtitle = QLabel('Enter once. VDR, VJR, PDF and Excel exports all use these values.'); subtitle.setObjectName('sectionSubtitle')
        titles.addWidget(title); titles.addWidget(subtitle); head.addLayout(titles); head.addStretch()
        self.status = QLabel(''); self.status.setObjectName('identityStatus'); self.status.setWordWrap(True); head.addWidget(self.status)
        layout.addLayout(head)
        grid = QGridLayout(); grid.setHorizontalSpacing(20); grid.setVerticalSpacing(6)
        self.inputs, self.errors = {}, {}
        for index, (key, _setting, label_text, limit) in enumerate(FIELDS):
            cell = QWidget(); cl = QVBoxLayout(cell); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(4)
            caption = QLabel(label_text.upper() + (' *' if key in ('vessel', 'hireDate') else '')); caption.setObjectName('fieldLabelDark')
            if key == 'hireDate':
                editor = VdrDatePicker('', maximum=QDate.currentDate().toString('yyyy-MM-dd'), clearable=True)
                editor.valueChanged.connect(lambda _value: self._edited())
            else:
                editor = QLineEdit(); editor.setMaxLength(max(limit, 20) if key != 'imo' else 11)
                editor.textEdited.connect(lambda _text: self._edited())
            editor.setMinimumHeight(36); editor.setAccessibleName(label_text); editor.setToolTip(HINTS[key])
            editor.setObjectName('identityInput')
            error = QLabel(''); error.setObjectName('fieldError'); error.setWordWrap(True); error.hide()
            hint = QLabel(HINTS[key]); hint.setObjectName('sectionSubtitle'); hint.setWordWrap(True)
            cl.addWidget(caption); cl.addWidget(editor); cl.addWidget(error); cl.addWidget(hint)
            grid.addWidget(cell, index // 3, index % 3); self.inputs[key] = editor; self.errors[key] = error
        for column in range(3): grid.setColumnStretch(column, 1)
        layout.addLayout(grid)
        actions = QHBoxLayout(); actions.addStretch()
        self.revert_button = QPushButton('REVERT'); self.revert_button.setObjectName('secondaryButton'); self.revert_button.clicked.connect(self.reload)
        self.save_button = QPushButton('SAVE VESSEL DETAILS'); self.save_button.clicked.connect(self.save)
        actions.addWidget(self.revert_button); actions.addWidget(self.save_button); layout.addLayout(actions)
        self.reload()

    def values(self):
        return {key: (editor.iso_value() if isinstance(editor, VdrDatePicker) else editor.text())
                for key, editor in self.inputs.items()}

    def reload(self):
        identity = load_identity(self.settings)
        for key, editor in self.inputs.items():
            if isinstance(editor, VdrDatePicker): editor.set_value(identity[key], emit=False)
            else: editor.setText(identity[key])
        self._show_errors({}); self._dirty(False)
        missing = [label for key, _s, label, _l in FIELDS if key in ('vessel', 'hireDate') and not identity[key]]
        self._status('Required before finalizing reports: ' + ', '.join(missing) if missing else 'Saved', bool(missing))

    def _edited(self):
        self._dirty(normalize_identity(self.values()) != load_identity(self.settings))
        if self.save_button.isEnabled(): self._status('Unsaved changes', True)

    def _dirty(self, dirty):
        self.save_button.setEnabled(dirty); self.revert_button.setEnabled(dirty)

    def _status(self, text, attention):
        self.status.setText(text); self.status.setProperty('attention', attention)
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)

    def _show_errors(self, errors):
        for key, label in self.errors.items():
            label.setText(errors.get(key, '')); label.setVisible(key in errors)

    def save(self):
        try:
            stored = save_identity(self.values(), self.settings)
        except IdentityError as error:
            self._show_errors(error.errors); self._status('Not saved — correct the highlighted fields', True)
            return False
        except OSError as error:
            self._status(f'Not saved — {error} Close other GDS VTS windows and try again.', True)
            return False
        self.reload(); self.identityChanged.emit(stored)
        return True
