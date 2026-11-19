"""Shared pop-up behaviour for GDS VTS (dialog visibility audit).

* fit_to_screen()  - a dialog never exceeds the available area of its parent's screen and
                     opens centred on the main window (follows it across monitors).
* exec_dialog()    - fit, then run modally. Every application-created dialog uses it.
* notify()/confirm() - GDS-styled message boxes: wrapped text, technical detail behind
                     "Show Details...", clearly named buttons, safe default for destructive actions.
* IssuesDialog     - header / scrolling grouped issue list / fixed footer.

Works with PySide2 (Qt5) and PySide6 (Qt6) through app.qt. Native file dialogs are untouched.
"""
import re

from app.qt import exec_qt
from app.qt.QtCore import QPoint, QRect, Qt
from app.qt.QtGui import QGuiApplication
from app.qt.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)
from app.ui.theme import COLORS, FONT_BODY, FONT_DISPLAY

MAX_SCREEN_FRACTION = 0.92
TEXT_WIDTH = 520          # readable line length for message text (px at 100 %)

STYLE = f"""
QDialog#gdsDialog, QMessageBox#gdsMessage {{ background:{COLORS['workspace']}; }}
QDialog#gdsDialog QLabel, QMessageBox#gdsMessage QLabel {{ color:{COLORS['text']}; font-family:'{FONT_BODY}'; font-size:13px; background:transparent; }}
QDialog#gdsDialog QLabel#dialogTitle {{ color:{COLORS['navy']}; font-family:'{FONT_DISPLAY}'; font-size:17px; font-weight:700; }}
QDialog#gdsDialog QLabel#dialogIntro {{ color:{COLORS['muted']}; }}
QDialog#gdsDialog QFrame#issueGroup {{ background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-radius:10px; }}
QDialog#gdsDialog QLabel#groupTitle {{ color:{COLORS['dark']}; font-family:'{FONT_DISPLAY}'; font-size:14px; font-weight:700; }}
QDialog#gdsDialog QScrollArea {{ background:transparent; border:0; }}
QDialog#gdsDialog QWidget#issueBody {{ background:{COLORS['workspace']}; }}
QDialog#gdsDialog QTableWidget, QDialog#gdsDialog QTreeWidget {{ background:{COLORS['surface']}; alternate-background-color:#F4F7FA; color:{COLORS['text']};
    gridline-color:{COLORS['border']}; border:1px solid {COLORS['border']}; border-radius:8px; selection-background-color:#D8EAE4; selection-color:{COLORS['dark']}; }}
QDialog#gdsDialog QHeaderView::section {{ background:{COLORS['workspace']}; color:{COLORS['navy']}; border:0; border-bottom:1px solid {COLORS['border']};
    padding:6px; font-weight:600; }}
QDialog#gdsDialog QLineEdit, QDialog#gdsDialog QDoubleSpinBox, QDialog#gdsDialog QComboBox {{ background:{COLORS['surface']}; color:{COLORS['text']};
    border:1px solid #C7D2DD; border-radius:8px; min-height:32px; padding:0 10px; }}
QDialog#gdsDialog QLineEdit:focus, QDialog#gdsDialog QDoubleSpinBox:focus, QDialog#gdsDialog QComboBox:focus {{ border:1px solid {COLORS['navy']}; }}
QDialog#gdsDialog QPushButton, QMessageBox#gdsMessage QPushButton {{ min-height:34px; min-width:88px; padding:0 16px; border-radius:8px;
    background:{COLORS['surface']}; color:{COLORS['navy']}; border:1px solid #C7D2DD; font-weight:600; }}
QDialog#gdsDialog QPushButton:hover, QMessageBox#gdsMessage QPushButton:hover {{ border-color:{COLORS['navy']}; }}
QDialog#gdsDialog QPushButton:focus, QMessageBox#gdsMessage QPushButton:focus {{ border:2px solid {COLORS['accent']}; }}
QDialog#gdsDialog QPushButton[primary="true"], QMessageBox#gdsMessage QPushButton[primary="true"] {{ background:{COLORS['navy']}; color:#FFF; border-color:{COLORS['navy']}; }}
QDialog#gdsDialog QPushButton[destructive="true"], QMessageBox#gdsMessage QPushButton[destructive="true"] {{ background:#B42318; color:#FFF; border-color:#B42318; }}
"""


# ------------------------------------------------------------------ geometry
def available_geometry(widget=None):
    """Usable area (excludes the taskbar) of the screen showing ``widget``'s window."""
    screen = None
    window = widget.window() if widget is not None else QApplication.activeWindow()
    if window is not None:
        handle = window.windowHandle()
        if handle is not None and handle.screen() is not None:
            screen = handle.screen()
        else:
            screen = QGuiApplication.screenAt(window.frameGeometry().center())
    screen = screen or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 1280, 720)


# Window frame added by Windows around the client area (title bar + borders, logical px).
# Defaults are conservative; fit_to_screen() measures the real frame from a shown parent window.
FRAME_TOP, FRAME_SIDE = 40, 8


def frame_margins(widget):
    """(top, side) frame size measured from a visible top-level window, else the defaults."""
    window = widget.window() if widget is not None else None
    if window is not None and window.isVisible():
        frame, client = window.frameGeometry(), window.geometry()
        top, side = client.top() - frame.top(), client.left() - frame.left()
        if 0 < top < 120:
            return max(top, 30), max(side, 1)
    return FRAME_TOP, FRAME_SIDE


def fit_rect(size, anchor, available, margins=None):
    """Client rectangle for ``size``: clamped so the WHOLE window (frame included) is inside the
    available area, centred on ``anchor``."""
    top, side = margins or (FRAME_TOP, FRAME_SIDE)
    width = min(size.width(), int(available.width()*MAX_SCREEN_FRACTION) - 2*side)
    height = min(size.height(), int(available.height()*MAX_SCREEN_FRACTION) - top - side)
    x = anchor.center().x() - width//2
    y = anchor.center().y() - height//2
    x = max(available.left() + side, min(x, available.right() - side - width + 1))
    y = max(available.top() + top, min(y, available.bottom() - side - height + 1))
    return QRect(x, y, width, height)


def fit_to_screen(widget, parent=None):
    """Size and place a dialog/window so it is entirely inside the usable screen area."""
    parent = parent if parent is not None else widget.parentWidget()
    available = available_geometry(parent if parent is not None else widget)
    margins = frame_margins(parent)
    widget.setMaximumSize(int(available.width()*MAX_SCREEN_FRACTION) - 2*margins[1],
                          int(available.height()*MAX_SCREEN_FRACTION) - margins[0] - margins[1])
    widget.ensurePolished()
    if widget.layout() is not None:
        widget.layout().activate()
    hint = widget.sizeHint().expandedTo(widget.minimumSizeHint())
    # An explicit resize() is the preferred size; otherwise the layout's hint. Either way it is clamped below.
    size = widget.size() if widget.testAttribute(Qt.WidgetAttribute.WA_Resized) else hint
    anchor = parent.window().frameGeometry() if parent is not None else available
    rect = fit_rect(size, anchor, available, margins)
    widget.setGeometry(rect)  # client geometry; the frame fits around it inside the screen
    return rect


def ensure_visible_window(window):
    """Main window: keep it on a connected screen and within its usable area."""
    available = available_geometry(window)
    rect = fit_rect(window.size(), window.frameGeometry() if available.intersects(window.frameGeometry()) else available, available, frame_margins(window))
    window.resize(rect.size()); window.setGeometry(rect)


def exec_dialog(dialog, parent=None):
    """Fit, then run modally (application-modal behind a parent is impossible: the parent is set)."""
    dialog.setWindowModality(Qt.WindowModality.WindowModal if dialog.parentWidget() is not None else Qt.WindowModality.ApplicationModal)
    fit_to_screen(dialog, parent)
    return exec_qt(dialog)


# ------------------------------------------------------------------ message boxes
BREAK = re.compile(r'([\\/_.\-])')


def wrap_long_tokens(text):
    """Allow file paths / long identifiers to wrap (zero-width break after separators)."""
    return ' '.join(BREAK.sub('\\1\u200b', token) if len(token) > 40 else token for token in str(text).split(' '))


def _message(parent, icon, title, text, details=''):
    box = QMessageBox(parent); box.setObjectName('gdsMessage'); box.setStyleSheet(STYLE)
    box.setIcon(icon); box.setWindowTitle(title)
    box.setTextFormat(Qt.TextFormat.PlainText); box.setText(wrap_long_tokens(text))
    if details:
        box.setDetailedText(str(details))
    label = box.findChild(QLabel, 'qt_msgbox_label')
    if label is not None:
        label.setWordWrap(True); label.setMaximumWidth(TEXT_WIDTH)
    return box


def build_notify(parent, title, text, details='', kind='warning'):
    icon = {'information': QMessageBox.Icon.Information, 'warning': QMessageBox.Icon.Warning,
            'error': QMessageBox.Icon.Critical}.get(kind, QMessageBox.Icon.Warning)
    box = _message(parent, icon, title, text, details)
    ok = box.addButton('OK', QMessageBox.ButtonRole.AcceptRole); ok.setProperty('primary', True)
    box.setDefaultButton(ok); box.setEscapeButton(ok)
    return box, ok


def notify(parent, title, text, details='', kind='warning'):
    """Information/warning/error with one OK button. Long technical detail goes in ``details``."""
    box, _ok = build_notify(parent, title, text, details, kind)
    exec_dialog(box, parent)


def build_confirm(parent, title, text, confirm_label, cancel_label='Cancel', destructive=False, details=''):
    box = _message(parent, QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question, title, text, details)
    yes = box.addButton(confirm_label, QMessageBox.ButtonRole.AcceptRole)
    no = box.addButton(cancel_label, QMessageBox.ButtonRole.RejectRole)
    yes.setProperty('destructive' if destructive else 'primary', True)
    box.setDefaultButton(no if destructive else yes); box.setEscapeButton(no)
    return box, yes, no


def confirm(parent, title, text, confirm_label, cancel_label='Cancel', destructive=False, details=''):
    """True only when the user presses ``confirm_label``. Destructive actions default to Cancel;
    Esc always cancels."""
    box, yes, _no = build_confirm(parent, title, text, confirm_label, cancel_label, destructive, details)
    exec_dialog(box, parent)
    return box.clickedButton() is yes


# ------------------------------------------------------------------ issue list dialog
class IssuesDialog(QDialog):
    """Header / scrollable grouped issues / fixed footer. ``groups`` is a list of
    dict(title=str, items=[str], action=str|None, callback=callable|None)."""

    def __init__(self, parent, title, intro, groups, close_label='Close'):
        super().__init__(parent); self.setObjectName('gdsDialog'); self.setStyleSheet(STYLE)
        self.setWindowTitle(title); self.action_buttons = []
        root = QVBoxLayout(self); root.setContentsMargins(22, 18, 22, 16); root.setSpacing(10)
        heading = QLabel(title); heading.setObjectName('dialogTitle'); heading.setWordWrap(True); root.addWidget(heading)
        if intro:
            text = QLabel(intro); text.setObjectName('dialogIntro'); text.setWordWrap(True); root.addWidget(text)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget(); body.setObjectName('issueBody'); body_layout = QVBoxLayout(body); body_layout.setContentsMargins(0, 0, 4, 0); body_layout.setSpacing(10)
        for group in groups:
            frame = QFrame(); frame.setObjectName('issueGroup'); gl = QVBoxLayout(frame); gl.setContentsMargins(16, 12, 16, 12); gl.setSpacing(6)
            name = QLabel(group['title']); name.setObjectName('groupTitle'); name.setWordWrap(True); gl.addWidget(name)
            for item in group['items']:
                line = QLabel('•  ' + wrap_long_tokens(item)); line.setWordWrap(True); gl.addWidget(line)
            if group.get('action') and group.get('callback'):
                button = QPushButton(group['action'].replace('&', '&&')); button.setProperty('primary', True)  # '&' is not a mnemonic
                button.clicked.connect(lambda _=False, cb=group['callback']: (self.accept(), cb()))
                row = QHBoxLayout(); row.addWidget(button); row.addStretch(); gl.addLayout(row); self.action_buttons.append(button)
            body_layout.addWidget(frame)
        body_layout.addStretch(); self.scroll.setWidget(body); root.addWidget(self.scroll, 1)
        footer = QHBoxLayout(); footer.addStretch()
        self.close_button = QPushButton(close_label); self.close_button.clicked.connect(self.reject); self.close_button.setDefault(True)
        footer.addWidget(self.close_button); root.addLayout(footer)
        self.resize(620, min(560, 170 + 70*len(groups) + 24*sum(len(g['items']) for g in groups)))


def issues_from_lines(lines):
    """Group '• SECTION: message' / 'SECTION: message' lines (exporter output) by section."""
    groups = {}
    for line in lines:
        line = line.strip().lstrip('•').strip()
        if not line:
            continue
        section, _, message = line.partition(': ')
        if not message:
            section, message = 'Other', line
        groups.setdefault(section, []).append(message)
    return [dict(title=title, items=items) for title, items in groups.items()]
