from datetime import datetime, timezone
from app.core.models import ConnectionMode, Source, TelemetryStatus
from .stream_assembler import StreamAssembler
from .parser import TelemetryParser
from .validator import TelemetryValidator
from .normalizer import TelemetryNormalizer

class SourceArbiter:
    def __init__(self, mode=ConnectionMode.AUTO): self.mode=mode; self.active=None; self.healthy=set()
    def choose(self, source, valid):
        if valid: self.healthy.add(source)
        if self.mode is ConnectionMode.USB_ONLY: self.active=Source.USB if Source.USB in self.healthy else None
        elif self.mode is ConnectionMode.BLE_ONLY: self.active=Source.BLE if Source.BLE in self.healthy else None
        else: self.active=Source.USB if Source.USB in self.healthy else (Source.BLE if Source.BLE in self.healthy else None)
        return valid and source is self.active
    def fail(self, source):
        self.healthy.discard(source); self.choose(source, False)
    @property
    def standby(self): return next((s for s in self.healthy if s is not self.active), None)

class TelemetryStateService:
    def __init__(self, mode=ConnectionMode.AUTO):
        self.assemblers={s:StreamAssembler() for s in Source}; self.parser=TelemetryParser(); self.validator=TelemetryValidator(); self.normalizer=TelemetryNormalizer(); self.arbiter=SourceArbiter(mode)
        self.latest_frame=None; self.last_valid_frame_time=None; self.source_last_valid={}; self.valid_frame_count=0; self.invalid_frame_count=0; self.listeners=[]
    @property
    def active_source(self): return self.arbiter.active
    @property
    def standby_source(self): return self.arbiter.standby
    @property
    def telemetry_status(self):
        if not self.active_source: return TelemetryStatus.NO_SOURCE
        if not self.last_valid_frame_time: return TelemetryStatus.CONNECTED_WAITING
        age = (datetime.now(timezone.utc) - self.last_valid_frame_time).total_seconds()
        if age < 3: return TelemetryStatus.LIVE
        if age < 10: return TelemetryStatus.STALE
        return TelemetryStatus.LOST
    @property
    def frame_age(self):
        return None if not self.last_valid_frame_time else (datetime.now(timezone.utc) - self.last_valid_frame_time).total_seconds()
    def tick(self):
        """Expire an unhealthy source; a fresh standby can then become authoritative."""
        now = datetime.now(timezone.utc)
        for source, timestamp in list(self.source_last_valid.items()):
            if (now - timestamp).total_seconds() >= 3:
                self.arbiter.healthy.discard(source)
        self.arbiter.choose(self.arbiter.active, False)
    def ingest(self, source, data):
        published=[]
        for line in self.assemblers[source].feed(data):
            payload=self.parser.parse(line); valid=self.validator.valid(payload) if payload is not None else False
            if not valid: self.invalid_frame_count += 1; continue
            frame=self.normalizer.normalize(payload, source, True)
            self.source_last_valid[source] = frame.received_at
            if self.arbiter.choose(source, True):
                self.latest_frame=frame; self.last_valid_frame_time=frame.received_at; self.valid_frame_count += 1; published.append(frame)
                for listener in self.listeners: listener(frame)
        return published
    def mark_disconnected(self, source): self.arbiter.fail(source)
