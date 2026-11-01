import asyncio
import threading
from app.core.models import BleDevice
from .base_transport import BaseTransport

NUS_SERVICE = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
NUS_NOTIFY = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'


class BleTransport(BaseTransport):
    """Bleak runs on a private event loop so Qt's GUI loop remains responsive."""
    def __init__(self) -> None:
        super().__init__(); self._client = None; self._loop = None; self._thread = None

    def scan(self) -> list[BleDevice]:
        try: return self._run(asyncio.run(self._scan_async()))
        except Exception as exc: self._emit_error(f"BLE scan failed: {exc}"); return []

    async def _scan_async(self):
        from bleak import BleakScanner
        devices = await BleakScanner.discover(timeout=4.0)
        return [BleDevice(d.name, d.address, getattr(d, 'rssi', None)) for d in devices]

    def _run(self, coro):
        result = [] ; error = []
        def runner():
            try: result.append(asyncio.run(coro))
            except Exception as exc: error.append(exc)
        t = threading.Thread(target=runner, daemon=True); t.start(); t.join()
        if error: raise error[0]
        return result[0]

    def connect(self, device: BleDevice) -> bool:
        try:
            from bleak import BleakClient
            self._client = BleakClient(device.address)
            self._run(self._connect_async())
            if self.on_state: self.on_state(True)
            return True
        except Exception as exc: self._emit_error(f"BLE connection failed: {exc}"); return False

    async def _connect_async(self):
        await self._client.connect()
        await self._client.start_notify(NUS_NOTIFY, lambda _, data: self.on_data(bytes(data)) if self.on_data else None)

    def disconnect(self) -> None:
        if self._client:
            try: self._run(self._client.disconnect())
            except Exception: pass
        self._client = None
        if self.on_state: self.on_state(False)
    def is_connected(self) -> bool: return bool(self._client and self._client.is_connected)
