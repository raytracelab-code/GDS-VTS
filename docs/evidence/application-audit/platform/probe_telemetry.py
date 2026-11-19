import sys, time, tracemalloc, threading
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
from datetime import datetime, timezone, timedelta
from app.telemetry.stream_assembler import StreamAssembler
from app.telemetry.parser import TelemetryParser
from app.telemetry.validator import TelemetryValidator
from app.telemetry.normalizer import TelemetryNormalizer, _coordinate
from app.telemetry.telemetry_state import TelemetryStateService
from app.core.models import Source, TelemetryStatus

def r(name, fn):
    try: print(name, '->', fn())
    except BaseException as e: print(name, '-> RAISES', type(e).__name__, str(e)[:80])

p = TelemetryParser(); v = TelemetryValidator()
# 1 partial / split frames
a = StreamAssembler()
r('split1', lambda: a.feed(b'{"Latitude":"0312.5",'))
r('split2', lambda: a.feed(b'"Longitude":"10130.0"}\r\n'))
r('crlf+blank', lambda: StreamAssembler().feed(b'\r\n\r\n{"a":1}\r\n'))
r('invalid utf8', lambda: StreamAssembler().feed(b'{"PID":"\xff\xfe"}\n'))
# 2 parser edge cases
r('empty obj valid?', lambda: v.valid(p.parse('{}')))
r('arbitrary obj valid?', lambda: v.valid(p.parse('{"hello":"world"}')))
r('array', lambda: p.parse('[1,2]'))
r('garbage', lambda: p.parse('$GPGGA,123'))
r('NaN lat valid?', lambda: v.valid(p.parse('{"Latitude":NaN,"Longitude":"Infinity"}')))
r('lat 999999 valid?', lambda: v.valid(p.parse('{"Latitude":999999,"Longitude":1}')))
r('deep nesting', lambda: p.parse('['*200000 + ']'*200000))
r('deep nesting obj', lambda: p.parse('{"a":' * 100000 + '1' + '}' * 100000))
# 3 coordinate heuristic
for raw in ['0312.5', '10130.0', '101.5', '3.2', '-101.5', '0030.0', '115.25', '18000.0']:
    r(f'coord {raw}', lambda raw=raw: _coordinate(raw))
# 4 unbounded buffer without newline
tracemalloc.start(); a = StreamAssembler(); chunk = b'x' * 65536
for _ in range(800): a.feed(chunk)
print('no-newline buffer bytes =', len(a.buffer), 'traced peak MB =', round(tracemalloc.get_traced_memory()[1]/1e6, 1)); tracemalloc.stop()
# quadratic cost of buffer += for long line
a = StreamAssembler(); t = time.perf_counter()
for _ in range(3000): a.feed(b'y' * 1024)
print('3000x1KB no-newline feed seconds =', round(time.perf_counter() - t, 3))
# 5 throughput flood
s = TelemetryStateService(); line = b'{"PID":"P1","Latitude":"0312.5","Longitude":"10130.0","Heading":"12","Speed_Knots":"5"}\n'
blob = line * 20000; t = time.perf_counter(); s.ingest(Source.USB, blob); dt = time.perf_counter() - t
print(f'flood 20000 frames in {dt:.3f}s = {20000/dt:.0f} frames/s; valid={s.valid_frame_count}')
# 6 stale / lost reachability with tick()
s = TelemetryStateService(); s.ingest(Source.USB, line)
print('status fresh', s.telemetry_status.value)
past = datetime.now(timezone.utc) - timedelta(seconds=5)
s.last_valid_frame_time = past; s.source_last_valid[Source.USB] = past
print('5s old, before tick', s.telemetry_status.value); s.tick(); print('5s old, after tick', s.telemetry_status.value, 'active', s.active_source)
# 7 unplug: mark_disconnected wired? (ingest after BLE+USB)
s = TelemetryStateService(); s.ingest(Source.USB, line); s.ingest(Source.BLE, line)
print('active', s.active_source, 'standby', s.standby_source)
# 8 listener exception propagates out of ingest (would kill USB reader thread)
s = TelemetryStateService(); s.listeners.append(lambda f: 1/0)
r('listener raises', lambda: s.ingest(Source.USB, line))
# 9 non-dict values
r('Latitude list', lambda: v.valid(p.parse('{"Latitude":[1,2]}')))
r('PID object normalize', lambda: TelemetryNormalizer().normalize(p.parse('{"PID":{"x":1},"Heading":true}'), Source.USB, True).heading)
# 10 RecursionError through ingest
s = TelemetryStateService()
r('ingest deep nesting', lambda: s.ingest(Source.USB, b'[' * 200000 + b'\n'))
