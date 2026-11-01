from typing import Protocol
from app.telemetry.frame import TelemetryFrame
class TelemetryRecorder(Protocol):
    def record(self, frame: TelemetryFrame) -> None: ...
