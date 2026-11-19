"""Shared test safety net.

Offscreen Qt cannot answer a modal QMessageBox, so an unexpected one would hang
the whole suite. Fail fast instead; tests that expect a dialog monkeypatch it.
"""
import pytest


@pytest.fixture(autouse=True)
def _no_unexpected_modal_dialogs(monkeypatch):
    try:
        from app.qt.QtWidgets import QMessageBox
    except Exception:  # pragma: no cover - Qt unavailable
        yield
        return

    def unexpected(*args, **kwargs):
        raise AssertionError('Unexpected modal QMessageBox in test: %r' % (args[1:3],))

    for name in ('question', 'warning', 'information', 'critical'):
        monkeypatch.setattr(QMessageBox, name, unexpected)
    # Every application dialog goes through app.ui.dialogs; an unexpected one fails instead of hanging.
    from app.ui import dialogs
    for name in ('exec_dialog', 'notify', 'confirm'):
        monkeypatch.setattr(dialogs, name, unexpected)
    yield
