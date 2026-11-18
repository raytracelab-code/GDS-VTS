"""One shared minute clock and settled-center debounce for NAV palette."""
from datetime import datetime, timezone
import logging
from app.qt.QtCore import QObject, QTimer, QSettings, Signal
from .palette import PaletteEngine, canonical_utc, position

log = logging.getLogger(__name__)


class PaletteController(QObject):
    changed = Signal(dict)

    def __init__(self, telemetry, parent=None, clock=None, settings=None):
        super().__init__(parent)
        self.telemetry = telemetry
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.settings = settings if settings is not None else QSettings('GDS', 'VTS')
        self.engine = PaletteEngine(self.settings.value('nav/palette', 'AUTO'))
        self.center = None
        self.pending_center = None
        self.follow = False
        self.signature = None
        self.reference = None
        self.log_signature = None
        self.payload = {}
        self.minute = QTimer(self)
        self.minute.setInterval(60000)
        self.minute.timeout.connect(lambda: self.update(force=True))
        self.minute.start()
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(700)
        self.debounce.timeout.connect(self._settled)
        self.update(force=True)

    def map_center(self, latitude, longitude):
        candidate = position((latitude, longitude))
        if candidate:
            self.pending_center = candidate
            self.debounce.start()

    def _settled(self):
        self.center = self.pending_center
        self.update()

    def set_mode(self, mode):
        if mode not in ('AUTO', 'DAY', 'NIGHT'):
            return
        if self.engine.mode != mode:
            self.engine.previous = None
        self.engine.mode = mode
        self.settings.setValue('nav/palette', mode)
        self.update(force=True)

    def update(self, follow=None, force=False):
        if follow is not None:
            self.follow = bool(follow)
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError('Palette clock must provide timezone-aware UTC')
        now = now.astimezone(timezone.utc)
        live = getattr(self.telemetry.telemetry_status, 'value', '') == 'LIVE'
        frame = self.telemetry.latest_frame
        utc, time_source = canonical_utc(frame, now, live)
        own = position((frame.latitude, frame.longitude)) if live and frame and frame.valid else None
        reference = own if self.follow and own else self.center
        ref_type = 'OWN_VESSEL' if self.follow and own else 'MAP_CENTER' if self.center else 'FALLBACK'
        signature = (utc.replace(second=0, microsecond=0), time_source, ref_type, self.engine.mode)
        # Compare to the last calculated position, not rounded grid boundaries:
        # tiny jitter cannot repeatedly cross a bucket and trigger recalculation.
        distance = 0.
        if reference is not None and self.reference is not None:
            distance = max(abs(reference[0] - self.reference[0]),
                           abs((reference[1] - self.reference[1] + 180) % 360 - 180))
        moved = (reference is None) != (self.reference is None) or distance >= .01
        if force or signature != self.signature or moved:
            if self.signature is None or ref_type != self.signature[2] or distance >= 1:
                self.engine.previous = None
            self.signature = signature
            self.reference = reference
            self.payload = self.engine.calculate(utc, own, self.center, self.follow, time_source)
            self.changed.emit(self.payload)
            diagnostic = (self.engine.mode, self.payload['computed_solar_state'], ref_type)
            if diagnostic != self.log_signature:
                log.debug('MAP PALETTE %s %s reference=%s', *diagnostic)
                self.log_signature = diagnostic
