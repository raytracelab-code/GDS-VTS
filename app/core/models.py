from dataclasses import dataclass
from enum import Enum


class Source(str, Enum):
    USB = "USB"
    BLE = "BLE"


class ConnectionMode(str, Enum):
    AUTO = "AUTO"
    USB_ONLY = "USB ONLY"
    BLE_ONLY = "BLE ONLY"


class TelemetryStatus(str, Enum):
    NO_SOURCE = "NO SOURCE"
    CONNECTED_WAITING = "WAITING"
    LIVE = "LIVE"
    STALE = "STALE"
    LOST = "LOST"


@dataclass(frozen=True)
class UsbDevice:
    port: str
    description: str = ""
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    product: str | None = None

    @property
    def label(self) -> str:
        identity = f"{self.vid:04X}:{self.pid:04X}" if self.vid is not None and self.pid is not None else "unknown"
        return f"{self.port} — {self.description or self.product or 'Serial device'} — {identity}"


@dataclass(frozen=True)
class BleDevice:
    name: str | None
    address: str
    rssi: int | None = None

    @property
    def label(self) -> str:
        suffix = f" — {self.rssi} dBm" if self.rssi is not None else ""
        return f"{self.name or 'Unnamed BLE device'} — {self.address}{suffix}"
