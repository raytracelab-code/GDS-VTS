"""VDR → Previous reports (GDS-AUDIT-005). Reads the existing report store only."""
from datetime import datetime, timezone
from app.qt.QtCore import QDate, Qt
from app.ui import dialogs
from app.qt.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

COLUMNS = ('Report date', 'Report No.', 'Vessel', 'Status', 'Last modified')


def _date(day):
    value = QDate.fromString(day, 'yyyy-MM-dd')
    return value.toString('dd MMM yyyy') if value.isValid() else day


def _modified(stamp):
    if not stamp:
        return '—'
    try:  # stored as UTC ISO-8601; shown in local time
        value = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime('%d %b %Y %H:%M')


def matches(row, text):
    """Search by report date (ISO or '19 Nov 2026'), Report No., vessel or status."""
    text = text.strip().casefold()
    return not text or any(text in str(value).casefold() for value in
                           (row['day'], _date(row['day']), row['report_no'], row['vessel'], row['status']))


class ReportHistoryDialog(QDialog):
    def __init__(self, rows, current_day, parent=None):
        super().__init__(parent); self.setWindowTitle('Previous reports'); self.resize(760, 520)
        self.setObjectName('gdsDialog'); self.setStyleSheet(dialogs.STYLE)
        self.rows, self.selected_day = rows, None
        layout = QVBoxLayout(self); layout.setSpacing(10)
        title = QLabel('Previous reports'); title.setObjectName('dialogTitle'); layout.addWidget(title)
        hint = QLabel('Newest first. Opening a finalized report shows it read-only; use Reopen report to edit it.')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search by date (2026-11-18 or 18 Nov), Report No., vessel or status')
        self.search.textChanged.connect(self.apply_filter); self.search.setClearButtonEnabled(True); layout.addWidget(self.search)
        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide(); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table, 1)
        self.empty = QLabel(''); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        buttons = QHBoxLayout(); buttons.addStretch()
        self.open_button = QPushButton('Open report'); self.open_button.clicked.connect(self.open_selected); self.open_button.setProperty('primary', True)
        close = QPushButton('Close'); close.clicked.connect(self.reject)
        buttons.addWidget(self.open_button); buttons.addWidget(close); layout.addLayout(buttons)
        self.current_day = current_day
        self.apply_filter('')

    def visible_rows(self):
        return [row for row in self.rows if matches(row, self.search.text())]

    def apply_filter(self, _text=''):
        rows = self.visible_rows()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (_date(row['day']), row['report_no'], row['vessel'], row['status'], _modified(row['modified']))
            for j, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, row['day'])
                if not row['openable']:
                    item.setToolTip('This stored report could not be read and was set aside. ' + row.get('error', ''))
                self.table.setItem(i, j, item)
            if row['day'] == self.current_day:
                self.table.selectRow(i)
        if not self.rows:
            self.empty.setText('No saved reports yet. A report is saved here as soon as you enter data for a day.')
        elif not rows:
            self.empty.setText('No reports match this search.')
        self.empty.setVisible(not rows); self.table.setVisible(bool(rows))
        self._selection_changed()

    def _row(self):
        items = self.table.selectedItems()
        if not items:
            return None
        day = items[0].data(Qt.ItemDataRole.UserRole)
        return next((row for row in self.rows if row['day'] == day), None)

    def _selection_changed(self):
        row = self._row(); self.open_button.setEnabled(bool(row and row['openable']))

    def open_selected(self):
        row = self._row()
        if row and row['openable']:
            self.selected_day = row['day']; self.accept()
