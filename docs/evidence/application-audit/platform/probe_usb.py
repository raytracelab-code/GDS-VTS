import sys, time, types, threading
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
import serial
from serial.tools import list_ports
from app.transports.usb_transport import UsbTransport
from app.transports.transport_manager import TransportManager
from app.transports.ble_transport import BleTransport
from app.telemetry.telemetry_state import TelemetryStateService
from app.core.models import UsbDevice

print('real ports:', [(p.device, p.description, p.vid, p.pid) for p in list_ports.comports()])
errors, states = [], []
usb = UsbTransport(); usb.on_error = errors.append; usb.on_state = states.append
print('connect missing COM250 ->', usb.connect(UsbDevice('COM250')), errors[-1:])

class FakeSerial:
    script = []
    def __init__(self, *a, **k): self.is_open = True; self.q = list(FakeSerial.script); self.port = a[0]
    @property
    def in_waiting(self): return len(self.q[0]) if self.q else 0
    def read(self, n):
        if not self.q: time.sleep(0.05); return b''
        item = self.q.pop(0)
        if isinstance(item, Exception): raise item
        return item
    def close(self): self.is_open = False
serial.Serial = FakeSerial
state = TelemetryStateService(); usb2 = UsbTransport(); TransportManager(usb2, BleTransport(), state.ingest)
errs2, st2 = [], []; usb2.on_error = errs2.append; usb2.on_state = st2.append
good = b'{"Latitude":"0312.5","Longitude":"10130.0"}\n'
FakeSerial.script = [good, b'[' * 100000 + b'\n', good, good]
usb2.connect(UsbDevice('COMX')); time.sleep(0.5)
print('after poison line: valid', state.valid_frame_count, 'thread alive', usb2._thread.is_alive(), 'is_connected()', usb2.is_connected(), 'errors', [e[:60] for e in errs2], 'states', st2)
# unplug: SerialException mid-stream
state = TelemetryStateService(); usb3 = UsbTransport(); TransportManager(usb3, BleTransport(), state.ingest)
e3, s3 = [], []; usb3.on_error = e3.append; usb3.on_state = s3.append
FakeSerial.script = [good, serial.SerialException('ClearCommError failed (PermissionError(13, The device does not recognize the command.))')]
usb3.connect(UsbDevice('COMY')); time.sleep(0.4)
print('unplug: errors', e3, 'states', s3, 'is_connected()', usb3.is_connected(), 'arbiter active still', state.active_source)
# double connect without disconnect
FakeSerial.script = []
usb4 = UsbTransport(); usb4.connect(UsbDevice('COMA')); t1, s1 = usb4._thread, usb4._serial
usb4.connect(UsbDevice('COMB')); time.sleep(0.2)
print('double connect: old thread alive', t1.is_alive(), 'old serial open', s1.is_open, 'threads', threading.active_count())
usb4.disconnect(); time.sleep(0.5); print('after disconnect old thread alive', t1.is_alive())
