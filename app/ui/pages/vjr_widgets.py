"""Presentation-only VJR primitives using the accepted VDR design system."""
from app.qt.QtCore import QRect, Qt
from app.qt.QtGui import QColor, QFont, QPainter, QPen
from app.qt.QtWidgets import (QGridLayout, QHeaderView, QLabel, QTableWidget,
                              QVBoxLayout, QWidget)
from app.ui.theme import COLORS, FONT_DISPLAY
from .vdr.style import STYLE as VDR_STYLE, themed


STYLE = VDR_STYLE.replace('vdrPage', 'vjrPage') + themed("""
#vjrPage QFrame#topbar {border-bottom:1px solid $border;}
#vjrPage QLabel#pageTitle {font-size:20px;}
#vjrPage QLabel#vesselContext {font-family:'$data';font-size:12px;color:$navy;}
#vjrPage QLabel#journeyStatus {font-size:10px;color:#087D70;background:#E6F8F4;border:1px solid #C4E9E0;border-radius:7px;padding:4px 8px;}
#vjrPage QLabel#sectionHeading {font-size:16px;}
#vjrPage QLabel#blockTitle {font-size:11px;letter-spacing:.5px;}
#vjrPage QFrame#formBlock {border-radius:10px;}
#vjrPage #sidebar QPushButton#sectionNav {padding:10px 8px;font-size:12px;}
#vjrPage QLabel#navCaption {font-size:10px;letter-spacing:1px;color:$muted;}
#vjrPage QLabel#navSummary {font-size:11px;color:$muted;}
#vjrPage QLineEdit {min-height:18px;padding:7px 9px;}
#vjrPage QLineEdit:read-only {background:#F0F5F7;color:$navy;border-color:#DFE7ED;}
#vjrPage QLineEdit#vdrDateInput {background:$surface;border-color:$border;}
#vjrPage QLineEdit[invalid="true"], #vjrPage QTimeEdit[invalid="true"] {border:1px solid #D97770;}
#vjrPage QLabel#inlineError {color:#B42318;font-size:10px;}
#vjrPage QLabel#storageNotice {color:#5C3A00;background:#FFF7E6;border:1px solid #F0C36D;border-radius:8px;padding:8px 12px;font-size:12px;font-weight:600;}
#vjrPage QLabel#validationNotice {color:#9F342B;background:#FFF5F3;border:1px solid #F4D1CC;border-radius:8px;padding:8px 12px;font-size:11px;}
#vjrPage QTimeEdit {min-height:18px;padding:7px 8px;background:$surface;color:$navy;border:1px solid $border;border-radius:6px;font-family:'$data';font-size:13px;}
#vjrPage QTimeEdit::up-button, #vjrPage QTimeEdit::down-button {width:0;height:0;border:0;}
#vjrPage QTimeEdit QLineEdit {padding:0;border:0;min-height:0;background:transparent;}
#vjrPage QCheckBox {font-size:11px;color:$muted;spacing:6px;}
#vjrPage QPushButton#download {background:$navy;color:$surface;border:1px solid $navy;}
#vjrPage QPushButton#download:hover {background:$light;}
#vjrPage QPushButton#download:disabled {background:$workspace;color:$muted;border-color:$border;}
#vjrPage QPushButton#deleteRow {color:#A93D35;background:transparent;border-color:transparent;}
#vjrPage QPushButton#deleteRow:hover {background:#FFF0EE;border-color:#F3CECA;}
#vjrPage QTableWidget {alternate-background-color:#F8FAFC;selection-background-color:#E3EFEE;selection-color:$navy;}
#vjrPage QTableWidget::item {padding:4px 8px;border:0;}
#vjrPage QTableWidget::item:selected {background:#E3EFEE;color:$navy;}
#vjrPage QTableWidget QLineEdit, #vjrPage QTableWidget QComboBox {min-height:0;padding:4px 6px;}
#vjrPage QLabel#rowNumberCorner {background:$workspace;color:$navy;border-right:1px solid $border;border-bottom:1px solid $border;font-size:9px;font-weight:600;}
#vjrPage QFrame#photoReserved {background:#F5F8FA;border:1px dashed #CDD9E2;border-radius:10px;}
#vjrPage QFrame#photoCard {background:$surface;border:1px solid $border;border-radius:10px;}
#vjrPage QLabel#photoPreview {background:#F0F5F7;border:1px solid $border;border-radius:8px;}
#vjrPage QLabel#photoQr {background:white;border:1px solid $border;border-radius:8px;}
#vjrPage QLabel#reservedGlyph {font-size:24px;color:#8B9EAF;}
#vjrPage QLabel#reservedBadge {font-size:9px;font-weight:600;letter-spacing:.7px;color:$muted;}
#vjrPage QLabel#emptyState {color:$muted;font-size:12px;padding:20px 8px;}
#vjrPage QLabel#tableHint {color:$muted;font-size:10px;}
""")


class FieldGrid(QWidget):
    """Reflow existing field widgets on width changes; never recreate editors."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(12)
        self.fields = []
        self.columns = 0

    def add_field(self, widget, wide=False):
        self.fields.append((widget, wide))
        self.reflow(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self, force=False):
        columns = 3 if self.width() >= 780 else 2 if self.width() >= 490 else 1
        if columns == self.columns and not force:
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        row, col = 0, 0
        for widget, wide in self.fields:
            span = columns if wide else 1
            if col+span > columns:
                row, col = row+1, 0
            self.grid.addWidget(widget, row, col, 1, span)
            col += span
            if col == columns:
                row, col = row+1, 0
        for index in range(3):
            self.grid.setColumnStretch(index, 1 if index < columns else 0)


class GroupedHeader(QHeaderView):
    """Compact, word-wrapped column labels with optional shared headings."""
    def __init__(self, groups, parent):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.groups = groups
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSectionsClickable(False)
        self.setFixedHeight(64 if groups else 44)
        self.group_height = 24 if groups else 0
        self.setMinimumSectionSize(46)

    def paintSection(self, painter, rect, logical):
        if not rect.isValid():
            return
        painter.save()
        cell = rect.adjusted(0, self.group_height, 0, 0)
        painter.fillRect(cell, QColor(COLORS['workspace']))
        painter.setPen(QColor(COLORS['border']))
        painter.drawLine(cell.bottomLeft(), cell.bottomRight())
        painter.drawLine(cell.topRight(), cell.bottomRight())
        font = QFont(FONT_DISPLAY); font.setPixelSize(10); font.setBold(True)
        painter.setFont(font); painter.setPen(QColor(COLORS['navy']))
        text = str(self.model().headerData(logical, Qt.Orientation.Horizontal) or '')
        painter.drawText(cell.adjusted(5, 2, -5, -2),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.groups:
            return
        painter = QPainter(self.viewport())
        font = QFont(FONT_DISPLAY); font.setPixelSize(9); font.setBold(True)
        painter.setFont(font)
        for start, end, title in self.groups:
            left = self.sectionViewportPosition(start)
            width = sum(self.sectionSize(i) for i in range(start, end+1))
            rect = QRect(left, 0, width, self.group_height)
            painter.fillRect(rect, QColor('#E4ECF1'))
            painter.setPen(QColor(COLORS['border'])); painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setPen(QColor(COLORS['navy']))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, title)
        painter.end()


class ReportTable(QTableWidget):
    """Let page scrolling continue when a table has no vertical work to do."""
    def __init__(self, rows, columns, groups, parent=None):
        super().__init__(rows, columns, parent)
        self.setHorizontalHeader(GroupedHeader(groups, self))
        self.verticalHeader().setFixedWidth(42)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setCornerButtonEnabled(False)
        self.corner = QLabel('NO.', self)
        self.corner.setObjectName('rowNumberCorner')
        self.corner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.corner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.horizontalHeader().geometriesChanged.connect(self.position_corner)

    def position_corner(self):
        if hasattr(self, 'corner'):
            self.corner.setGeometry(1, 1, self.verticalHeader().width(), self.horizontalHeader().height())
            self.corner.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_corner()

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        delta = event.angleDelta()
        if not delta.x() and (bar.maximum() == 0 or
                (delta.y() > 0 and bar.value() == bar.minimum()) or
                (delta.y() < 0 and bar.value() == bar.maximum())):
            event.ignore()
            return
        super().wheelEvent(event)
