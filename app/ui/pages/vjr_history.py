"""VJR → Voyage history (GDS-AUDIT-005/011). Lists vjr/archive; restoring swaps journeys safely."""
from app.qt.QtCore import QDate, Qt
from app.ui import dialogs
from app.qt.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

COLUMNS = ('Departure\ndate', 'Departure\nlocation', 'Arrival\ndestination', 'Vessel', 'Status', 'Archived')  # two-line headers never clip


def _date(value):
    day = QDate.fromString(value or '', 'yyyy-MM-dd')
    return day.toString('dd MMM yyyy') if day.isValid() else (value or '—')


def values(row):
    return (_date(row['departure_date']), row['departure_location'] or '—', row['destination'] or '—', row['vessel'] or '—',
            row['status'], row['archived'].strftime('%d %b %Y %H:%M'))


def matches(row, text):
    text = text.strip().casefold()
    return not text or any(text in str(v).casefold() for v in values(row) + (row['departure_date'],))


class VoyageHistoryDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent); self.setWindowTitle('Voyage history'); self.resize(860, 520)
        self.setObjectName('gdsDialog'); self.setStyleSheet(dialogs.STYLE)
        self.store, self.rows, self.restored = store, store.archived_journeys(), None
        layout = QVBoxLayout(self); layout.setSpacing(10)
        title = QLabel('Voyage history'); title.setObjectName('dialogTitle'); layout.addWidget(title)
        current = store.report['departure']
        summary = QLabel('Current journey: ' + ' → '.join(v for v in (current.get('departure_location'), current.get('destination')) if v)
                         + (f" · departed {_date(current.get('departure_date'))}" if current.get('departure_date') else '') if any(
                             current.get(k) for k in ('departure_location', 'destination', 'departure_date')) else 'Current journey: not started')
        summary.setWordWrap(True); layout.addWidget(summary)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search by date, location, destination or vessel')
        self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self.apply_filter); layout.addWidget(self.search)
        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS); self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed); layout.addWidget(self.table, 1)
        self.empty = QLabel(''); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty.setWordWrap(True); layout.addWidget(self.empty)
        buttons = QHBoxLayout(); buttons.addStretch()
        self.restore_button = QPushButton('Make this the current journey…'); self.restore_button.clicked.connect(self.restore_selected)
        self.restore_button.setProperty('primary', True)
        close = QPushButton('Close'); close.clicked.connect(self.reject)
        buttons.addWidget(self.restore_button); buttons.addWidget(close); layout.addLayout(buttons)
        self.apply_filter('')

    def visible_rows(self):
        return [row for row in self.rows if matches(row, self.search.text())]

    def apply_filter(self, _text=''):
        rows = self.visible_rows(); self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(values(row)):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, str(row['path']))
                if not row['readable']:
                    item.setToolTip('This archive file could not be read: ' + row.get('error', ''))
                self.table.setItem(i, j, item)
        if not self.rows:
            self.empty.setText('No archived voyages yet. Use “New voyage…” to archive the current journey and start the next one.')
        elif not rows:
            self.empty.setText('No voyages match this search.')
        self.empty.setVisible(not rows); self.table.setVisible(bool(rows)); self._selection_changed()

    def _row(self):
        items = self.table.selectedItems()
        if not items:
            return None
        path = items[0].data(Qt.ItemDataRole.UserRole)
        return next((row for row in self.rows if str(row['path']) == path), None)

    def _selection_changed(self):
        row = self._row(); self.restore_button.setEnabled(bool(row and row['readable']))

    def restore_selected(self):
        row = self._row()
        if not row or not row['readable']:
            return False
        if not dialogs.confirm(self, 'Make this the current journey?',
                '• The current journey is archived first; nothing is deleted.\n'
                f'• {row["departure_location"] or "The selected voyage"} becomes the current journey.\n'
                '• Undo history is cleared for this switch; you can switch back from Voyage history at any time.',
                'Make current'):
            return False
        try:
            self.restored = self.store.restore_archived(row['path'])
        except (OSError, ValueError, TypeError, KeyError) as error:
            dialogs.notify(self, 'Voyage not restored', 'The voyage could not be restored. Nothing was changed.', details=str(error))
            return False
        self.accept(); return True
