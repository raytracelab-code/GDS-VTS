"""Small reference form primitives and local font registration."""
from pathlib import Path
from app.qt.QtCore import QPoint, QPointF, QRect, QSize, Qt
from app.qt.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen
from app.qt.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLayout
from app.vdr.model import number
from app.ui.theme import COLORS, FONT_BODY

ASSETS = Path(__file__).resolve().parents[3] / 'resources/vdr'


def load_fonts():
    if not getattr(load_fonts, 'loaded', False):
        for stem in ('manrope', 'inter', 'jetbrains-mono'):
            if QFontDatabase.addApplicationFont(str(ASSETS/f'{stem}.ttf')) < 0:
                raise RuntimeError('Could not load bundled VDR font: '+stem)
        load_fonts.loaded = True


def box(horizontal=False, margins=(0, 0, 0, 0), gap=0):
    widget = QWidget()
    layout = QHBoxLayout(widget) if horizontal else QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(gap)
    return widget, layout


def label(text, name=''):
    widget = QLabel(text)
    widget.setObjectName(name)
    return widget


def button(text, callback, name='', check=False):
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setCheckable(check)
    widget.clicked.connect(callback)
    return widget


class FlowLayout(QLayout):
    """Reference flex-wrap equivalent for the weather selector groups."""
    def __init__(self, parent=None, spacing=20):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item): self.items.append(item)
    def count(self): return len(self.items)
    def itemAt(self, index): return self.items[index] if 0 <= index < len(self.items) else None
    def takeAt(self, index): return self.items.pop(index) if 0 <= index < len(self.items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._arrange(QRect(0, 0, width, 0), True)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        result = QSize()
        for item in self.items: result = result.expandedTo(item.minimumSize())
        return result
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, False)
    def _arrange(self, rect, measure):
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            size = item.sizeHint()
            if x > rect.x() and x+size.width() > rect.right()+1:
                x, y, height = rect.x(), y+height+self.spacing(), 0
            if not measure: item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width()+self.spacing()
            height = max(height, size.height())
        return y+height-rect.y()


class DraftProfile(QWidget):
    def __init__(self, report):
        super().__init__()
        self.report = report
        self.setMinimumHeight(125)
        self.setMaximumHeight(150)
        self.setAccessibleName('Draft profile: forward and aft vessel trim')

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width()/560, self.height()/158)
        p.translate((self.width()-560*scale)/2, 14*scale)
        p.scale(scale, scale)
        fwd, aft = number(self.report()['meta']['fwd']), number(self.report()['meta']['aft'])
        f, a = [min(max(v if v is not None else 2.5, 0), 6) for v in (fwd, aft)]
        p.save()
        p.translate(313, 55+9*((f+a)/2-2.5))
        p.rotate(math.degrees(math.atan2(9*(f-a), 340)))
        p.translate(-313, -55)
        p.setPen(QPen(QColor(COLORS['navy']), 1.5)); p.setBrush(QColor(COLORS['workspace']))
        p.drawRect(398, 15, 92, 16); p.drawRect(408, 4, 60, 11)
        for x in (404, 418, 432):
            p.drawRect(x, 18, 7, 5)
        hull = QPainterPath(QPointF(96, 42))
        hull.lineTo(382, 42); hull.lineTo(382, 31); hull.lineTo(505, 29)
        hull.quadTo(523, 28, 531, 37); hull.lineTo(536, 55); hull.lineTo(524, 77.5)
        hull.quadTo(330, 82.5, 118, 77.5); hull.quadTo(96, 68.25, 93, 55); hull.closeSubpath()
        p.setBrush(QColor(COLORS['border'])); p.drawPath(hull); p.restore()
        water = QColor(COLORS['workspace']); water.setAlpha(145)
        p.fillRect(0, 55, 560, 75, water)
        p.setPen(QPen(QColor(COLORS['muted']), 1, Qt.PenStyle.DashLine)); p.drawLine(0, 55, 560, 55)
        p.setPen(QPen(QColor(COLORS['navy']), 1.5)); p.setFont(QFont(FONT_BODY, 9))
        for x, value, text in ((120, a, 'AFT'), (460, f, 'FWD')):
            y = max(55+9*value, 59)
            p.drawLine(QPointF(x, 55), QPointF(x, y)); p.drawLine(QPointF(x-8, y), QPointF(x+8, y))
            p.drawText(QPointF(x+12 if x == 120 else x-40, (55+y)/2+4), text)
        p.end()
