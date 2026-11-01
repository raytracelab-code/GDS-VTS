from app.core.models import Source,ConnectionMode,UsbDevice,BleDevice,TelemetryStatus
from app.core.app_state import AppState
from app.telemetry.stream_assembler import StreamAssembler
from app.telemetry.parser import TelemetryParser
from app.telemetry.normalizer import TelemetryNormalizer
from app.telemetry.frame import TelemetryFrame
from app.telemetry.telemetry_state import TelemetryStateService
from app.telemetry.diagnostics import derive_diagnostics

def payload(): return '{"PID":"P1","Latitude":"2230.0","Longitude":"09030.0","Temperature_C":"N/A","Heading":"12"}'
def test_usb_device_discovery_model(): assert 'COM5' in UsbDevice('COM5','FTDI',0x403,0x6001).label
def test_ble_device_discovery_model(): assert 'Patroller' in BleDevice('Patroller','AA',-60).label
def test_stream_partial_multiple_crlf_and_empty():
    s=StreamAssembler(); assert s.feed(b'{"a":1}')==[]; assert s.feed(b'\r\n\n{"b":2}\n')==['{"a":1}','{"b":2}']
def test_stream_invalid_bytes_never_crash(): assert StreamAssembler().feed(b'\xff\n')==['�']
def test_json_parser(): assert TelemetryParser().parse('{"PID":"x"}') == {'PID':'x'}; assert TelemetryParser().parse('{bad}') is None
def test_na_and_coordinate_normalization_once():
    frame=TelemetryNormalizer().normalize({'Latitude':'2230.0','Longitude':'09030.0','Temperature_C':'N/A'},Source.USB,True)
    assert frame.latitude == 22.5 and frame.longitude == 90.5 and frame.temperature_c is None
def test_canonical_frame(): assert TelemetryFrame(pid='x',valid=True).pid == 'x'
def test_source_priority_and_exactly_once():
    s=TelemetryStateService(); assert len(s.ingest(Source.BLE,payload().encode()+b'\n'))==1
    assert len(s.ingest(Source.USB,payload().encode()+b'\n'))==1
    assert s.active_source is Source.USB
    assert s.ingest(Source.BLE,payload().encode()+b'\n')==[]
def test_usb_failover_to_ble():
    s=TelemetryStateService(); s.ingest(Source.BLE,payload().encode()+b'\n'); s.ingest(Source.USB,payload().encode()+b'\n'); s.mark_disconnected(Source.USB); assert s.active_source is Source.BLE
def test_connection_modes():
    u=TelemetryStateService(ConnectionMode.USB_ONLY); assert u.ingest(Source.BLE,payload().encode()+b'\n')==[]; assert len(u.ingest(Source.USB,payload().encode()+b'\n'))==1
    b=TelemetryStateService(ConnectionMode.BLE_ONLY); assert b.ingest(Source.USB,payload().encode()+b'\n')==[]; assert len(b.ingest(Source.BLE,payload().encode()+b'\n'))==1
def test_module_unlock_persists():
    app=AppState(); app.observe_status(TelemetryStatus.LIVE); app.observe_status(TelemetryStatus.LOST); assert app.modules_unlocked
def test_diagnostics_derivation():
    d=derive_diagnostics(TelemetryStatus.LIVE,TelemetryFrame(latitude=1,heading=2,valid=True)); assert d['GPS']=='LIVE' and d['Weather']=='UNAVAILABLE'
