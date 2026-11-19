"""Connection diagnostics without touching transport code.

LinkMonitor wraps the existing ``ingest(source, data)`` callback: it records when bytes arrived,
how many packets/bytes were received and keeps a bounded raw-data history for the diagnostic
monitor. Transports may call ``on_data`` from worker threads, so recording is lock-protected and
O(1). Nothing here changes what is ingested.
"""
from collections import deque
from datetime import datetime, timezone
import threading

RAW_HISTORY = 400          # lines kept for the raw monitor
RAW_LINE_LIMIT = 300       # characters shown per line


class LinkMonitor:
    def __init__(self, clock=lambda: datetime.now(timezone.utc)):
        self.clock = clock
        self._lock = threading.Lock()
        self.raw = deque(maxlen=RAW_HISTORY)
        self.sequence = 0                     # increases with every raw entry (UI polls this)
        self.packets, self.bytes, self.last_packet_at = {}, {}, {}
        self.connects, self.connected_since, self.devices = {}, {}, {}

    def wrap(self, ingest):
        def recording(source, data):
            self.record(source, data)
            return ingest(source, data)
        return recording

    def record(self, source, data):
        now = self.clock(); key = getattr(source, 'value', str(source))
        text = bytes(data).decode('utf-8', errors='replace').replace('\r', '')
        with self._lock:
            self.packets[key] = self.packets.get(key, 0) + 1
            self.bytes[key] = self.bytes.get(key, 0) + len(data)
            self.last_packet_at[key] = now
            for line in text.split('\n'):
                if line:
                    self.raw.append((now, key, line[:RAW_LINE_LIMIT] + ('…' if len(line) > RAW_LINE_LIMIT else '')))
            self.sequence += 1

    def connection_changed(self, kind, connected, device=''):
        with self._lock:
            if connected:
                self.connects[kind] = self.connects.get(kind, 0) + 1
                self.connected_since[kind] = self.clock(); self.devices[kind] = device
            else:
                self.connected_since.pop(kind, None)

    def reconnects(self, kind):
        return max(0, self.connects.get(kind, 0) - 1)

    def snapshot(self):
        with self._lock:
            return dict(packets=dict(self.packets), bytes=dict(self.bytes),
                        last_packet_at={k: v.isoformat() for k, v in self.last_packet_at.items()},
                        connects=dict(self.connects), devices=dict(self.devices),
                        connected_since={k: v.isoformat() for k, v in self.connected_since.items()})

    def raw_lines(self):
        with self._lock:
            return list(self.raw), self.sequence

    def clear(self):
        with self._lock:
            self.raw.clear(); self.sequence += 1


def link_state(status, packets, valid, invalid, age):
    """Plain-language link state from existing counters (no fabricated metrics).
    ``status`` is TelemetryStatus.value; returns (label, tone, explanation)."""
    if status == 'NO SOURCE':
        return 'NOT CONNECTED', 'neutral', 'No device is connected.'
    if not packets:
        return 'NO DATA YET', 'warning', 'Connected, but no bytes have been received yet. Check that the device is powered and sending.'
    if not valid and invalid:
        return 'INVALID DATA', 'error', f'Data is arriving but none of it is valid telemetry JSON ({invalid} invalid line(s)). Check the device output format.'
    if status == 'LIVE':
        return 'LIVE', 'success', 'Valid telemetry is arriving.'
    if status in ('STALE', 'LOST'):
        return status, 'warning' if status == 'STALE' else 'error', f'Valid data stopped {age:.0f} s ago.' if age is not None else 'Valid data stopped.'
    return 'WAITING', 'warning', 'Connected — waiting for the first valid frame.'
