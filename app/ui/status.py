"""One status-badge vocabulary for every module (text is always shown; colour only reinforces it).

Tones: success (healthy), warning (stale / attention), error (failure), neutral (inactive / info).
"""
TONES = ('success', 'warning', 'error', 'neutral')
STATE_TONE = {
    'LIVE': 'success', 'CONNECTED': 'success', 'FINALIZED': 'success', 'SAVED': 'success', 'READY TO FINALIZE': 'success',
    'STALE': 'warning', 'WAITING': 'warning', 'CONNECTING': 'warning', 'NO DATA YET': 'warning', 'SAVING': 'warning',
    'DRAFT': 'neutral', 'REOPENED': 'warning', 'NOT CONNECTED': 'neutral', 'DISCONNECTED': 'neutral', 'NO DEVICE': 'neutral',
    'NO DATA': 'neutral', 'NO SOURCE': 'neutral', 'UNAVAILABLE': 'neutral',
    'LOST': 'error', 'SAVE FAILED': 'error', 'NOT SAVED': 'error', 'INVALID DATA': 'error', 'ERROR': 'error',
}
ICON = {'success': '●', 'warning': '▲', 'error': '■', 'neutral': '○'}

BADGE_QSS = """
QLabel[badgeTone] { border-radius:9px; padding:3px 9px; font-size:11px; font-weight:700; }
QLabel[badgeTone="success"] { color:#087D70; background:#E6F8F4; }
QLabel[badgeTone="warning"] { color:#8A5300; background:#FFF4DC; }
QLabel[badgeTone="error"] { color:#B42318; background:#FDECEC; }
QLabel[badgeTone="neutral"] { color:#59697B; background:#EEF2F6; }
"""


def tone_for(text):
    upper = str(text).upper()
    for state in sorted(STATE_TONE, key=len, reverse=True):
        if state in upper:
            return STATE_TONE[state]
    return 'neutral'


def set_badge(label, text, tone=None, with_icon=True):
    """Show ``text`` as a badge. The shape marker (● ▲ ■ ○) keeps status readable without colour."""
    tone = tone or tone_for(text)
    label.setText(f'{ICON[tone]}  {text}' if with_icon else text)
    if label.property('badgeTone') != tone:
        label.setProperty('badgeTone', tone)
        label.style().unpolish(label); label.style().polish(label)
    # Padding comes from the stylesheet: re-measure so a longer state text is never clipped.
    label.setMinimumWidth(label.sizeHint().width()); label.updateGeometry()
    return tone


WARNING_QSS = "QLabel#plausibilityWarning { color:#8A5300; background:#FFF4DC; border-radius:6px; padding:3px 8px; font-size:11px; }"
WARNING_FIELD_QSS = "border:1px solid #D9A441; background:#FFFBF0;"


def warning_text(message):
    return '▲ ' + message


class busy:
    """Wait cursor while an operation runs (export, bundle, backup, restore) so the app never looks frozen."""
    def __enter__(self):
        from app.qt.QtCore import Qt
        from app.qt.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); return self

    def __exit__(self, *exc):
        from app.qt.QtWidgets import QApplication
        QApplication.restoreOverrideCursor(); return False
