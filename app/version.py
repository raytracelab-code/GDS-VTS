"""Single source of the GDS VTS version.

No formal release scheme existed (builds were stamped 0.0.0.0). 0.9.0 is a
clearly-marked *development* version: below 1.0 because the application has not
yet passed hardware and cross-OS acceptance. Bump MAJOR.MINOR.PATCH here only;
the PyInstaller specs read this file for the Windows file-version resource.
"""
__version__ = '0.9.0'
STAGE = 'development'


def edition():
    """'Modern' (PySide6, Windows 10/11) or 'Legacy Compatibility' (PySide2, Windows 7/8)."""
    from app.qt import LEGACY
    return 'Legacy Compatibility' if LEGACY else 'Modern'


def display_version():
    return f'{__version__} ({STAGE}) · {edition()}'
