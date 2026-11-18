from __future__ import annotations
import threading
from typing import Iterable
from app.core.models import UsbDevice
from .base_transport import BaseTransport


class UsbTransport(BaseTransport):
    BAUDRATE = 115200
    def __init__(self) -> None:
        super().__init__(); self._serial = None; self._thread = None; self._running = False

    def scan(self) -> list[UsbDevice]:
        try:
            from serial.tools import list_ports
            return [UsbDevice(p.device, p.description or '', p.vid, p.pid, p.serial_number, p.manufacturer, p.product) for p in list_ports.comports()]
        except Exception as exc:
            self._emit_error(f"USB scan failed: {exc}"); return []

    def connect(self, device: UsbDevice) -> bool:
        try:
            import serial
            self._serial = serial.Serial(device.port, self.BAUDRATE, bytesize=8, parity='N', stopbits=1, timeout=0.25)
            self._running = True; self._thread = threading.Thread(target=self._read_loop, daemon=True); self._thread.start()
            if self.on_state: self.on_state(True)
            return True
        except Exception as exc:
            self._emit_error(f"Unable to open selected serial device: {exc}"); return False

    def _read_loop(self) -> None:
        while self._running and self._serial:
            try:
                data = self._serial.read(self._serial.in_waiting or 1)
                if data and self.on_data: self.on_data(data)
            except Exception as exc:
                self._emit_error(f"USB read failed: {exc}"); break
        if self.on_state: self.on_state(False)

    def disconnect(self) -> None:
        self._running = False
        if self._serial:
            try: self._serial.close()
            except Exception: pass
        self._serial = None

    def is_connected(self) -> bool: return bool(self._serial and self._serial.is_open)
