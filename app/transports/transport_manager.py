from app.core.models import Source


class TransportManager:
    def __init__(self, usb, ble, ingest) -> None:
        self.usb, self.ble = usb, ble
        usb.on_data = lambda b: ingest(Source.USB, b)
        ble.on_data = lambda b: ingest(Source.BLE, b)
