from .models import TelemetryStatus


class AppState:
    """Session-only module gate. A temporary outage never re-locks modules."""
    def __init__(self) -> None:
        self.modules_unlocked = False

    def observe_status(self, status: TelemetryStatus) -> None:
        if status is TelemetryStatus.LIVE:
            self.modules_unlocked = True
