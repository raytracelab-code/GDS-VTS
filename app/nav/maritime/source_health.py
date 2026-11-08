from dataclasses import dataclass
from enum import StrEnum


class SourceState(StrEnum):
    DISABLED = 'DISABLED'
    DISABLED_LICENSE = 'DISABLED_LICENSE'
    READY = 'READY'
    LOADING = 'LOADING'
    OUT_OF_COVERAGE = 'OUT_OF_COVERAGE'
    NO_STABLE_MACHINE_API = 'NO_STABLE_MACHINE_API'
    NOT_CONFIGURED = 'NOT_CONFIGURED'
    CONNECTING = 'CONNECTING'
    LIVE = 'LIVE'
    DEGRADED = 'DEGRADED'
    STALE = 'STALE'
    ERROR = 'ERROR'


@dataclass
class SourceHealth:
    state: SourceState = SourceState.NOT_CONFIGURED
    last_message_at: object = None
    last_success_at: object = None
    error: str | None = None
    area: dict | None = None
    cached: bool = False
    dynamic: bool = False

    def payload(self, now):
        return dict(state=str(self.state), last_message_at=self.last_message_at.isoformat() if self.last_message_at else None,
                    last_success_at=self.last_success_at.isoformat() if self.last_success_at else None,
                    age_seconds=max(0, (now-self.last_success_at).total_seconds()) if self.last_success_at else None,
                    error=self.error, area=self.area, cached=self.cached)
