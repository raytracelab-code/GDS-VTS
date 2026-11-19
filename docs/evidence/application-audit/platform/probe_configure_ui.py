import os, sys, time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
from datetime import datetime, timezone, timedelta
from app.qt.QtWidgets import QApplication, QPushButton
app = QApplication([])
from app.ui.pages.configure.configure_page import ConfigurePage
from app.telemetry.telemetry_state import TelemetryStateService
from app.transports import UsbTransport, BleTransport, TransportManager
from app.core.models import Source, UsbDevice

state = TelemetryStateService(); usb = UsbTransport(); ble = BleTransport(); TransportManager(usb, ble, state.ingest)
page = ConfigurePage(usb, ble, state)
print('buttons:', sorted({b.text() for b in page.findChildren(QPushButton)}))
# two ports; select the second; check details
usb.scan = lambda: [UsbDevice('COM3', 'USB Serial Port', 0x0403, 0x6001, 'FT1'), UsbDevice('COM7', 'USB Serial Device', 0x2341, 0x0043, 'CDC9')]
page.connection.scan_usb(); page.connection.usb_select.setCurrentIndex(1)
print('selected:', page.connection.usb_select.currentText(), '| details Port shown:', page.connection.usb_detail['Port'].text())
# connect failure: what does the user see?
usb.connect = lambda d: (usb._emit_error('Unable to open selected serial device: PermissionError(13, Access is denied.)'), False)[1]
page.connection.connect_usb(); print('after failed connect, USB status label:', page.connection.usb_info.text(), '| any visible error label? on_error wired:', usb.on_error)
# frame arrives
state.ingest(Source.USB, b'{"PID":"P1","Latitude":"0312.5","Longitude":"10130.0","Heading":"12","Roll":"1","Voltage":"12.5"}\n')
page.refresh(); print('LIVE TELEMETRY latitude label:', page.telemetry.labels['latitude'].text(), '| heading:', page.telemetry.labels['heading'].text())
print('health GPS:', page.diagnostics.health['GPS'].text(), '| Telemetry:', page.diagnostics.health['Telemetry'].text())
# source goes silent 15s
past = datetime.now(timezone.utc) - timedelta(seconds=15); state.last_valid_frame_time = past; state.source_last_valid[Source.USB] = past
state.tick(); page.refresh()
print('after 15s silence: summary TELEMETRY:', page.connection.summary_values['TELEMETRY'].text(), '| health GPS:', page.diagnostics.health['GPS'].text(), '| health Heading:', page.diagnostics.health['Heading'].text(), '| USB tile:', page.diagnostics.health['USB'].text())
