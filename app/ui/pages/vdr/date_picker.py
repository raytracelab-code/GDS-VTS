"""Application-owned VDR date input/popover. Empty dates have no sentinel value."""
import re
import weakref
from app.qt.QtCore import QDate, QEvent, QLocale, QPoint, QRectF, Qt, Signal
from app.qt.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from app.qt.QtWidgets import QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from app.ui.theme import COLORS
from app.qt import isValid, LEGACY
from .style import themed
from .widgets import load_fonts

ENGLISH = QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
CALENDAR_STYLE = themed("""
QFrame#gdsVdrCalendar {background:$surface;border:1px solid $border;border-radius:12px;}
#gdsVdrCalendar QWidget {font-family:'Inter';font-size:13px;color:$navy;background:transparent;}
#gdsVdrCalendar QLabel#calendarTitle {font-size:14px;font-weight:600;}
#gdsVdrCalendar QLabel#weekday {font-size:11px;color:$muted;}
#gdsVdrCalendar QPushButton {min-height:0;padding:0;border:1px solid transparent;border-radius:6px;background:transparent;color:$navy;font-family:'Inter';font-size:13px;font-weight:400;}
#gdsVdrCalendar QPushButton:hover {background:$workspace;}
#gdsVdrCalendar QPushButton[outsideMonth="true"] {color:$muted;}
#gdsVdrCalendar QPushButton[today="true"] {border:1px solid $accent;}
#gdsVdrCalendar QPushButton[focused="true"] {border:1px solid $navy;}
#gdsVdrCalendar QPushButton[selected="true"] {background:$navy;color:$surface;border-color:$navy;font-weight:600;}
#gdsVdrCalendar QPushButton:disabled {color:$border;background:transparent;border-color:transparent;}
#gdsVdrCalendar QPushButton#monthArrow {font-size:20px;border:1px solid $border;}
#gdsVdrCalendar QPushButton#calendarAction {padding:4px 8px;font-size:12px;font-weight:600;}
""")


def parse_date(value):
    if isinstance(value, QDate):
        return value if value.isValid() and value.year() >= 1 else QDate()
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return QDate.fromString(value, 'yyyy-MM-dd')
    return QDate()


class VdrDatePicker(QLineEdit):
    """Selection-only date field. valueChanged emits ISO text or an empty string."""
    valueChanged = Signal(str)
    dateChanged = Signal(QDate)

    def __init__(self, value='', *, report_date=None, today=None, minimum=None, maximum=None, clearable=True, parent=None):
        super().__init__(parent)
        load_fonts()
        self.setObjectName('vdrDateInput')
        self.setProperty('data', True)
        self.setPlaceholderText('Select date')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Manual parsing is deliberately avoided: only valid grid selections commit.
        QLineEdit.setReadOnly(self, True)
        self._locked = False
        self._date = QDate()
        self.report_date = report_date
        self.today_provider = today or QDate.currentDate
        self.minimum = parse_date(minimum)
        self.maximum = parse_date(maximum)
        self.clearable = clearable
        self.popover = None
        self.set_value(value, emit=False)
        icon = QPixmap(16, 16); icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon); painter.setPen(QPen(QColor(COLORS['muted']), 1))
        painter.drawRoundedRect(2, 3, 12, 11, 2, 2); painter.drawLine(2, 7, 14, 7)
        painter.drawLine(5, 1, 5, 5); painter.drawLine(11, 1, 11, 5); painter.end()
        action = self.addAction(QIcon(icon), QLineEdit.ActionPosition.TrailingPosition)
        action.setToolTip('Choose date'); action.triggered.connect(self.open_calendar)

    def today(self):
        value = self.today_provider() if callable(self.today_provider) else self.today_provider
        return parse_date(value) if parse_date(value).isValid() else QDate.currentDate()

    def date(self): return QDate(self._date)
    def iso_value(self): return self._date.toString('yyyy-MM-dd') if self._date.isValid() else ''
    def isReadOnly(self): return self._locked

    def setReadOnly(self, locked):
        self._locked = bool(locked)
        self.setProperty('dateLocked', self._locked)
        if self.popover and isValid(self.popover) and self._locked:
            self.popover.hide()
        self.style().unpolish(self); self.style().polish(self)

    def allowed(self, day):
        return (day.isValid() and day.year() >= 1 and
                (not self.minimum.isValid() or day >= self.minimum) and
                (not self.maximum.isValid() or day <= self.maximum))

    def set_value(self, value, *, emit=True):
        day = parse_date(value)
        empty = value == '' or isinstance(value, QDate) and not value.isValid()
        if not day.isValid() and not empty:
            return False
        if emit and (self._locked or not self.isEnabled() or (day.isValid() and not self.allowed(day)) or (empty and not self.clearable)):
            return False
        changed = self._date != day
        self._date = day
        QLineEdit.setText(self, ENGLISH.toString(day, 'dd MMM yyyy') if day.isValid() else '')
        if changed and emit:
            # Emit legacy QDate first: the ISO subscriber may rebuild/delete this input.
            self.dateChanged.emit(QDate(day))
            self.valueChanged.emit(self.iso_value())
        return True

    def setDate(self, day): return self.set_value(day)
    def clear(self): return self.set_value('')

    def initial_date(self):
        if self._date.isValid():
            return self.date()
        report = self.report_date() if callable(self.report_date) else self.report_date
        day = parse_date(report)
        if not day.isValid():
            day = self.today()
        if self.minimum.isValid() and day < self.minimum:
            day = self.minimum
        if self.maximum.isValid() and day > self.maximum:
            day = self.maximum
        return day

    def open_calendar(self):
        if self._locked or not self.isEnabled() or QApplication.activeModalWidget() is not None:
            return None
        if self.popover is None or not isValid(self.popover):
            self.popover = CalendarPopover(self)
        if self.popover.isVisible():
            self.popover.hide()
            return None
        self.popover.open()
        return self.popover

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(); self.open_calendar(); event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            self.open_calendar(); event.accept()
        else:
            super().keyPressEvent(event)


class CalendarPopover(QFrame):
    """Single active Qt popup layer, independent of clipping report/card containers."""
    _active = None

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.owner = owner
        self.setObjectName('gdsVdrCalendar')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(CALENDAR_STYLE)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(300)
        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12); root.setSpacing(8)
        header = QHBoxLayout(); header.setSpacing(8)
        self.previous = self._button('‹', lambda: self.change_month(-1), 'monthArrow')
        self.previous.setAccessibleName('Previous month'); self.previous.setFixedSize(30, 32)
        self.title = QLabel(); self.title.setObjectName('calendarTitle'); self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next = self._button('›', lambda: self.change_month(1), 'monthArrow')
        self.next.setAccessibleName('Next month'); self.next.setFixedSize(30, 32)
        header.addWidget(self.previous); header.addWidget(self.title, 1); header.addWidget(self.next); root.addLayout(header)
        grid = QGridLayout(); grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(4); grid.setVerticalSpacing(3)
        for col, text in enumerate(('Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa')):
            day = QLabel(text); day.setObjectName('weekday'); day.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(day, 0, col)
        self.day_buttons = []
        for i in range(42):
            day = self._button('', lambda checked=False, n=i: self.select(self.day_buttons[n].property('isoDate')))
            day.setFixedSize(34, 34)
            self.day_buttons.append(day); grid.addWidget(day, i//7+1, i%7)
        root.addLayout(grid)
        footer = QHBoxLayout()
        self.today_button = self._button('Today', lambda: self.select(self.owner.today()), 'calendarAction')
        self.clear_button = self._button('Clear', self.clear_selection, 'calendarAction')
        self.clear_button.setVisible(owner.clearable)
        footer.addWidget(self.today_button); footer.addStretch(); footer.addWidget(self.clear_button); root.addLayout(footer)

    def paintEvent(self, event):
        # A translucent Windows popup does not reliably paint a QSS frame surface.
        # Paint the rounded panel ourselves so underlying report text cannot bleed through.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        painter.setBrush(QColor(COLORS['surface']))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 12, 12)

    def _button(self, text, callback, name=''):
        button = QPushButton(text); button.setObjectName(name); button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        return button

    def open(self):
        current = self._active() if self._active else None
        if current is not None and isValid(current) and current is not self:
            current.hide()
        CalendarPopover._active = weakref.ref(self)
        self.focused_date = self.owner.initial_date()
        self.month = QDate(self.focused_date.year(), self.focused_date.month(), 1)
        self.render_month()
        self.adjustSize()
        self.position_at_input()
        QApplication.instance().installEventFilter(self)
        self.show(); self.raise_(); self.setFocus(Qt.FocusReason.PopupFocusReason)

    def viewport_bounds(self):
        host = self.owner.window()
        ancestor = self.owner.parentWidget()
        while ancestor:
            if ancestor.objectName() == 'vdrPage':
                host = ancestor; break
            ancestor = ancestor.parentWidget()
        bounds = host.rect().translated(host.mapToGlobal(QPoint(0, 0)))
        screen = self.owner.screen()
        return bounds.intersected(screen.availableGeometry()) if screen else bounds

    def position_at_input(self):
        bounds = self.viewport_bounds().adjusted(4, 4, -4, -4)
        anchor = self.owner.rect().translated(self.owner.mapToGlobal(QPoint(0, 0)))
        x = max(bounds.left(), min(anchor.left(), bounds.right()-self.width()+1))
        below = anchor.bottom()+6
        y = below if below+self.height() <= bounds.bottom()+1 else anchor.top()-self.height()-6
        y = max(bounds.top(), min(y, bounds.bottom()-self.height()+1))
        self.move(x, y)

    def render_month(self):
        self.title.setText(ENGLISH.toString(self.month, 'MMMM yyyy'))
        first = self.month.addDays(-(self.month.dayOfWeek()%7))
        today, selected = self.owner.today(), self.owner.date()
        for i, button in enumerate(self.day_buttons):
            day = first.addDays(i)
            button.setText(str(day.day())); button.setProperty('isoDate', day.toString('yyyy-MM-dd'))
            button.setAccessibleName(ENGLISH.toString(day, 'dd MMM yyyy'))
            button.setEnabled(self.owner.allowed(day))
            for name, value in [('outsideMonth', day.month() != self.month.month()), ('today', day == today),
                                ('selected', day == selected), ('focused', day == self.focused_date)]:
                button.setProperty(name, value)
            button.style().unpolish(button); button.style().polish(button)
        previous_last = self.month.addDays(-1)
        next_first = self.month.addMonths(1)
        self.previous.setEnabled(previous_last.year() >= 1 and (not self.owner.minimum.isValid() or previous_last >= self.owner.minimum))
        self.next.setEnabled(next_first.isValid() and (not self.owner.maximum.isValid() or next_first <= self.owner.maximum))
        self.today_button.setEnabled(self.owner.allowed(today))

    def change_month(self, offset):
        target = self.month.addMonths(offset)
        if target.year() < 1 or not target.isValid():
            return
        if self.owner.maximum.isValid() and target > self.owner.maximum:
            return
        if self.owner.minimum.isValid() and target.addMonths(1).addDays(-1) < self.owner.minimum:
            return
        self.month = target
        self.focused_date = target
        self.render_month()

    def select(self, value):
        day = parse_date(value)
        if not self.owner.allowed(day) or self.owner.isReadOnly() or not self.owner.isEnabled():
            return
        owner = self.owner
        self.hide(); owner.setFocus(Qt.FocusReason.PopupFocusReason)
        owner.set_value(day)

    def clear_selection(self):
        owner = self.owner
        if owner.clearable and not owner.isReadOnly():
            self.hide(); owner.setFocus(Qt.FocusReason.PopupFocusReason); owner.clear()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide(); self.owner.setFocus(); return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.select(self.focused_date); return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.hide()
            # Qt5 popup dismissal does not synchronously reactivate its owner window.
            if LEGACY:
                QApplication.setActiveWindow(self.owner.window())
            self.owner.setFocus(); self.owner.focusNextPrevChild(key == Qt.Key.Key_Tab); return
        offsets = {Qt.Key.Key_Left:-1, Qt.Key.Key_Right:1, Qt.Key.Key_Up:-7, Qt.Key.Key_Down:7}
        if key in offsets:
            day = self.focused_date.addDays(offsets[key])
            if self.owner.allowed(day):
                self.focused_date = day; self.month = QDate(day.year(), day.month(), 1); self.render_month()
            return
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            amount = 12 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.change_month(-amount if key == Qt.Key.Key_PageUp else amount); return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if not self.isVisible():
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            point = event.globalPosition().toPoint()
            inside = self.rect().contains(self.mapFromGlobal(point))
            in_owner = self.owner.rect().contains(self.owner.mapFromGlobal(point))
            if not inside and not in_owner:
                self.hide()
        elif event.type() == QEvent.Type.Show and isinstance(watched, QDialog) and watched.isModal():
            self.hide()
        elif event.type() == QEvent.Type.Wheel and watched is not self and not (isinstance(watched, QWidget) and self.isAncestorOf(watched)):
            self.hide()
        elif isinstance(watched, QWidget) and (watched is self.owner or watched.isAncestorOf(self.owner)):
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                self.position_at_input()
            elif event.type() == QEvent.Type.Hide:
                self.hide()
        return False

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        current = self._active() if self._active else None
        if current is self:
            CalendarPopover._active = None
        super().hideEvent(event)
