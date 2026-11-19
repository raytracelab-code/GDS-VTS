"""NAV map renderer health (GDS-AUDIT-019). Pure logic; NavPage feeds it Qt/JS events.

Detected failures:
* page load failed (loadFinished(False))           -> LOAD_FAILED
* WebEngine render process terminated/crashed       -> RENDERER_STOPPED
* WebGL could not start or its context was lost     -> WEBGL_UNAVAILABLE
* page loaded but the map never reported a style    -> NOT_RESPONDING (blank surface watchdog)
"""
OK, LOADING, LOAD_FAILED, RENDERER_STOPPED, WEBGL_UNAVAILABLE, NOT_RESPONDING = (
    'OK', 'LOADING', 'LOAD_FAILED', 'RENDERER_STOPPED', 'WEBGL_UNAVAILABLE', 'NOT_RESPONDING')
FAILED = (LOAD_FAILED, RENDERER_STOPPED, WEBGL_UNAVAILABLE, NOT_RESPONDING)
READY_TIMEOUT_SECONDS = 30.0   # page loaded, but no map style reported within this time

MESSAGES = {
    LOAD_FAILED: ('Map failed to load',
                  'The map page could not be loaded. Vessel data, reports and alerts are not affected. Press Retry map.'),
    RENDERER_STOPPED: ('Map renderer stopped',
                       'The map display process stopped unexpectedly. Your data is safe. Press Retry map to restart the map.'),
    WEBGL_UNAVAILABLE: ('Map unavailable on this display',
                        'This computer could not start 3D map graphics (WebGL). Update the graphics driver or run the '
                        'Legacy Compatibility build, then press Retry map.'),
    NOT_RESPONDING: ('Map not responding',
                     'The map page loaded but did not finish drawing. Press Retry map. If this repeats, restart GDS VTS.'),
}


class RendererHealth:
    def __init__(self):
        self.state = LOADING
        self.detail = ''              # technical detail for the log/tooltip, never the main message
        self.loaded_at = None
        self.retries = 0
        self.failures = 0

    def start_load(self, now):
        self.state, self.detail, self.loaded_at = LOADING, '', None

    def load_finished(self, ok, now):
        if self.state in (RENDERER_STOPPED, WEBGL_UNAVAILABLE):
            return self.state       # a load event after a crash/WebGL failure does not mean recovery
        if ok:
            self.loaded_at = now
            return self.state
        return self._fail(LOAD_FAILED, 'loadFinished(false)')

    def map_ready(self):
        """The map reported a loaded style: the surface is drawing."""
        if self.state in (LOADING, NOT_RESPONDING, LOAD_FAILED):
            self.state, self.detail = OK, ''
        return self.state

    def renderer_terminated(self, status, exit_code):
        return self._fail(RENDERER_STOPPED, f'render process terminated: {status} (exit code {exit_code})')

    def webgl_failed(self, reason=''):
        return self._fail(WEBGL_UNAVAILABLE, reason or 'WebGL unavailable')

    def check(self, now):
        """Watchdog: a loaded page whose map never reports ready is a blank map."""
        if self.state == LOADING and self.loaded_at is not None and now - self.loaded_at >= READY_TIMEOUT_SECONDS:
            return self._fail(NOT_RESPONDING, f'no map style within {READY_TIMEOUT_SECONDS:.0f} s of page load')
        return self.state

    def can_retry(self):
        return self.state in FAILED

    def retry(self, now):
        """Begin a retry; returns False while a retry is already loading (no stacked reloads)."""
        if not self.can_retry():
            return False
        self.retries += 1
        self.start_load(now)
        return True

    def message(self):
        return MESSAGES.get(self.state)

    def _fail(self, state, detail):
        if self.state != state:
            self.failures += 1
        self.state, self.detail = state, detail
        return state
