"""NAV truthfulness, offline recovery, provider privacy and bounded shutdown.

GDS-AUDIT-016/017/018/020/022/023/057. No public network, no WebEngine:
the NAV page uses a recording web surface, providers use a local stalled socket.
"""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.qt.QtCore import Qt, QSettings
from app.qt.QtWidgets import QWidget, QVBoxLayout, QLabel
from app.nav import VesselConfig, VesselState, TrackManager
from app.nav.track_manager import TrackPoint, haversine_nm
from app.nav.map_controls import FollowController
from app.nav.presentation import (format_speed, format_angle, telemetry_freshness, marker_payload,
                                  readout_text, track_metrics, freshness_banner, LIVE, STALE, NO_DATA)
from app.ui.pages.nav.nav_page import NavPage

NOW = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)


def frame(age=0.5, speed=0.0, heading=0.0, cog=0.0, lat=5.25, lon=103.5, valid=True):
    return SimpleNamespace(received_at=NOW - timedelta(seconds=age), latitude=lat, longitude=lon, speed_knots=speed,
                           heading=heading, cog=cog, source='USB', valid=valid)


def vessel_for(f):
    vessel = VesselState(); vessel.update(f, VesselConfig()); return vessel


# ---- GDS-AUDIT-016: valid zeros and unknown heading -------------------------------------------

def test_zero_speed_and_heading_are_values_not_missing():
    assert format_speed(0) == '0.0 kn' and format_speed(0.0) == '0.0 kn'
    assert format_angle(0) == '000.0°' and format_angle(359.96) == '000.0°' and format_angle(5) == '005.0°'
    assert format_speed(None) == '—' and format_angle(None) == '—'
    f = frame(speed=0.0, heading=0.0, cog=0.0)
    text = readout_text(vessel_for(f), f, LIVE, 0.5)
    assert 'SOG\n0.0 kn' in text and 'COG\n000.0°' in text and 'HEADING\n000.0°' in text


def test_heading_zero_is_known_and_drawn_at_zero():
    f = frame(heading=0.0)
    payload = marker_payload(vessel_for(f), f, LIVE, 0.5)
    assert payload['heading'] == 0.0 and payload['heading_source'] == 'HDG'


def test_missing_heading_is_never_invented_as_north():
    f = frame(heading=None, cog=None)
    payload = marker_payload(vessel_for(f), f, LIVE, 0.5)
    assert payload['heading'] is None and payload['heading_source'] is None
    assert 'HEADING\nUNKNOWN' in readout_text(vessel_for(f), f, LIVE, 0.5)
    # Course over ground is a real received orientation, labelled as such.
    f = frame(heading=None, cog=87.0)
    payload = marker_payload(vessel_for(f), f, LIVE, 0.5)
    assert payload['heading'] == 87.0 and payload['heading_source'] == 'COG'
    assert 'UNKNOWN (marker by COG)' in readout_text(vessel_for(f), f, LIVE, 0.5)


# ---- GDS-AUDIT-017: LIVE / STALE / NO DATA ------------------------------------------------------

def test_freshness_states_from_frame_time():
    assert telemetry_freshness(None, NOW) == (NO_DATA, None)
    assert telemetry_freshness(frame(age=0.4), NOW)[0] == LIVE
    state, age = telemetry_freshness(frame(age=42), NOW)
    assert state == STALE and age == pytest.approx(42)
    assert freshness_banner(STALE, 42) == 'TELEMETRY STALE · last update 42 s ago'
    assert freshness_banner(STALE, 754).endswith('12 min 34 s ago')
    assert freshness_banner(NO_DATA, None).startswith('NO TELEMETRY DATA')


def test_track_is_paused_not_recording_when_stale():
    track = TrackManager(); track.append(TrackPoint(NOW, 5, 103, 0, 0, 0))
    assert track_metrics(track, LIVE)['status'] == 'RECORDING'
    assert track_metrics(track, STALE)['status'] == 'PAUSED'
    assert track_metrics(track, NO_DATA)['status'] == 'PAUSED'
    assert track_metrics(TrackManager(), STALE)['status'] == 'IDLE'


class WebSurface(QWidget):
    def __init__(self):
        super().__init__(); self.calls = []; self.reloads = 0
    def page(self): return self
    def runJavaScript(self, code): self.calls.append(code)
    def reload(self): self.reloads += 1


class Signal:
    def __init__(self): self.values = []
    def emit(self, value): self.values.append(value)


@pytest.fixture
def nav(qtbot, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / 'nav.ini'), QSettings.Format.IniFormat)
    for module in ('nav_page', 'presentation_widgets'):
        monkeypatch.setattr('app.ui.pages.nav.' + module + '.QSettings', lambda *args: settings)
    page = NavPage.__new__(NavPage); QWidget.__init__(page); qtbot.addWidget(page)
    page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    page.layer_checks = {}; page.follow = FollowController(); page.maritime_runtime = None
    page.palette = SimpleNamespace(update=lambda **kwargs: None)
    page.spatial = SimpleNamespace(state=SimpleNamespace(metadata={}, feature_counts={'total': 0}), selection=SimpleNamespace(feature=None),
                                   payload=lambda: {})
    page.web = WebSurface(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(page.web)
    page.status = QLabel('NO SOURCE'); page.trackbar = QLabel('TRACK IDLE')
    page.bridge = SimpleNamespace(maritime_service=None, setMaritimeVisibility=lambda *args: None, telemetryChanged=Signal(),
                                  renderStateChanged=Signal(), spatialStateChanged=Signal(), eventStateChanged=Signal(),
                                  getEventState=lambda: {}, publishMaritimeState=lambda: None)
    page.config, page.vessel, page.track = VesselConfig(), VesselState(), TrackManager()
    page.state = SimpleNamespace(latest_frame=None, telemetry_status=SimpleNamespace(value='NO SOURCE'))
    page._init_floating(); page.resize(1100, 740); page.show(); qtbot.wait(10)
    return page


def live_frame(age=0.2, **kwargs):
    now = datetime.now(timezone.utc)
    f = frame(**kwargs); f.received_at = now - timedelta(seconds=age); return f


def test_page_no_data_live_stale_states(nav):
    page = nav
    page.refresh()
    assert page.trackbar.isVisible() and page.trackbar.text().startswith('NO TELEMETRY DATA')
    assert page.trackbar.property('freshness') == 'NO_DATA'
    assert 'NO DATA' in page.readout.text() and '?' not in page.readout.text()
    assert page.web.calls[-1].endswith("setFreshness('NO DATA')")

    page.state.latest_frame = live_frame(speed=0.0, heading=0.0, cog=0.0)
    page.refresh()
    marker = page.bridge.telemetryChanged.values[-1]
    assert marker['heading'] == 0.0 and marker['heading_source'] == 'HDG' and marker['freshness'] == LIVE
    assert 'SOG\n0.0 kn' in page.readout.text() and 'HEADING\n000.0°' in page.readout.text()
    assert 'TELEMETRY LIVE' in page.trackbar.text() and 'TRACK  RECORDING' in page.trackbar.text()
    assert page.web.calls[-1].endswith("setFreshness('LIVE')")

    calls = len(page.web.calls)
    page.state.latest_frame.received_at -= timedelta(seconds=30)
    page.refresh()
    assert page.trackbar.property('freshness') == 'STALE'
    assert 'TELEMETRY STALE · last update 30 s ago' in page.trackbar.text() and 'TRACK  PAUSED' in page.trackbar.text()
    assert page.web.calls[calls:] == ["window.navMap&&navMap.setFreshness&&navMap.setFreshness('STALE')"]
    # Throttled: repeated refreshes in the same state send nothing new to the map.
    page.refresh(); page.refresh()
    assert len(page.web.calls) == calls + 1


def test_page_missing_heading_is_sent_as_unknown(nav):
    nav.state.latest_frame = live_frame(heading=None, cog=None)
    nav.refresh()
    assert nav.bridge.telemetryChanged.values[-1]['heading'] is None
    assert 'HEADING\nUNKNOWN' in nav.readout.text()


def test_no_corrupted_placeholder_text(nav):
    assert '?' not in nav.readout.text()
    nav.spatial.state.metadata = {'name': 'Site', 'revision': '2'}; nav.spatial.state.feature_counts = {'total': 4}
    nav._update_spatial_summary()
    assert '?' not in nav.spatial_summary.text() and 'Features  4   ·   Status  Active' in nav.spatial_summary.text()


# ---- GDS-AUDIT-018: offline startup, retry, regions access --------------------------------------

class Handler:
    def __init__(self, installed):
        from app.nav.online_map import online_config
        self.config = online_config(); self.installed = installed; self.reloads = 0
    def reload_packages(self):
        self.reloads += 1
        self.config = {'installed': self.installed, 'preferred_source': None, 'status': 'MAP · OFFLINE', 'style': {'layers': []}}
        return self.config


def test_offline_startup_uses_installed_regions_and_recovers(nav, monkeypatch):
    page = nav; page._gds_scheme_handler = Handler(True)
    monkeypatch.setattr('app.nav.offline_maps.manager.PackageManager.installed_regions', lambda self, enabled_only=False: ['region'])
    page._bridge_command('online-unavailable')
    assert page._offline_fallback and page.web.reloads == 1
    assert page.bridge.offline_config['online_probe_url'].startswith('https://')
    assert 'SHOWING INSTALLED OFFLINE REGIONS' in page.map_package_status.text()
    page._bridge_command('online-unavailable')  # latched once; no reload loop
    assert page.web.reloads == 1
    page._bridge_command('online-available')  # JS probe saw the network return
    assert not page._offline_fallback and page.web.reloads == 2
    assert page._gds_scheme_handler.config['preferred_source'] == 'online'
    assert page.bridge.offline_config['preferred_source'] == 'online'


def test_offline_startup_without_regions_keeps_local_shell_and_retry(nav, monkeypatch):
    page = nav; page._gds_scheme_handler = Handler(False)
    monkeypatch.setattr('app.nav.offline_maps.manager.PackageManager.installed_regions', lambda self, enabled_only=False: [])
    page._bridge_command('online-unavailable')
    assert not getattr(page, '_offline_fallback', False) and page.web.reloads == 0
    page.retry_map_button.click()
    assert page.web.reloads == 1 and page.map_package_status.text() == 'MAP / ONLINE / RECONNECTING'


def test_map_regions_dialog_is_reachable(nav, monkeypatch):
    opened = []
    monkeypatch.setattr(NavPage, '_map_regions', lambda self: opened.append(True))
    assert nav.map_regions_button.text() == 'Map regions…' and nav.layers_panel.isAncestorOf(nav.map_regions_button)
    nav.map_regions_button.click()
    assert opened == [True]


def test_offline_retry_and_marker_javascript():
    from app.nav.online_map import online_config
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for the NAV browser-script harness')
    result = subprocess.run([node, 'tests/nav_truthfulness_runtime.cjs'], input=json.dumps({'config': online_config()}),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'PASS' in result.stdout


# ---- GDS-AUDIT-020: bounded track ----------------------------------------------------------------

def test_track_history_is_bounded_without_changing_distance_or_duration():
    track = TrackManager(max_points=1000, recent_points=200); exact = 0.0; previous = None
    for i in range(20000):
        point = TrackPoint(NOW + timedelta(seconds=i), 5 + i * 1e-4, 103 + (i % 50) * 1e-4, 0, 0, 5)
        assert track.append(point)
        if previous: exact += haversine_nm(previous.latitude, previous.longitude, point.latitude, point.longitude)
        previous = point
    assert track.point_count <= 1000 and track.total_points == 20000
    assert track.distance_nm == pytest.approx(exact)
    assert track.duration == timedelta(seconds=19999)
    newest = track.segments[-1][-200:]
    assert [p.timestamp for p in newest] == [NOW + timedelta(seconds=i) for i in range(19800, 20000)]
    assert track.start.timestamp == NOW
    assert track_metrics(track)['points'] == 20000


# ---- GDS-AUDIT-022: generalised provider requests -----------------------------------------------

def test_own_vessel_query_never_transmits_exact_position(qapp, tmp_path):
    from app.nav.maritime.runtime import MaritimeRuntime
    from app.nav.maritime.config import MaritimeConfig
    from app.nav.maritime.adapters.overpass import query
    from app.nav.maritime.adapters.aisstream import subscription
    from app.nav.maritime.adapters.provider_common import bbox_parts
    from app.nav.maritime.area_controller import OperatingArea
    runtime = MaritimeRuntime(config=MaritimeConfig({}))
    try:
        lat, lon = 2.512345, 104.098765
        runtime.own_position(lat, lon)
        area = runtime.service.area
        assert (area.latitude, area.longitude) == (2.5, 104.0) and area.radius_nm == 72
        assert runtime.service.own_position == (lat, lon)  # exact fix stays local
        text = query(area) + json.dumps(subscription(area, 'k'))
        assert '2.512345' not in text and '104.098765' not in text and '2.5123' not in text
        # Generalised request still covers the configured 50 NM around the real position.
        needed = bbox_parts(OperatingArea(lat, lon, 50))[0]
        (w, s, e, n), = bbox_parts(area)
        assert w <= needed[0] and s <= needed[1] and e >= needed[2] and n >= needed[3]
        # Moving within the same grid cell sends no new query.
        generation = runtime._generation
        runtime._last_own_query = None; runtime.controller._last = float('-inf')
        runtime.own_position(2.6, 104.1)
        assert runtime._generation == generation
    finally:
        runtime.close()


def test_transmitted_boxes_are_widened_never_narrowed():
    from app.nav.maritime.privacy import widen_bounds, snap_position
    assert widen_bounds(100.12, 3.8, 100.89, 4.26) == (100.1, 3.8, 100.9, 4.3)
    assert widen_bounds(-180, -90, 180, 90) == (-180, -90, 180, 90)
    assert snap_position(2.74, 104.26) == (2.5, 104.5)
    assert snap_position(-0.2, 179.9) == (0.0, 180.0)


def test_overpass_can_be_disabled(qapp):
    from app.nav.maritime.config import MaritimeConfig
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime = MaritimeRuntime(config=MaritimeConfig({'GDS_OVERPASS_ENABLED': 'false'}))
    try:
        assert 'overpass' not in runtime.adapters
        assert str(runtime.service.sources['overpass'].state).endswith('DISABLED')
    finally:
        runtime.close()


# ---- GDS-AUDIT-023: bounded shutdown with a stalled provider ------------------------------------

@pytest.fixture
def stalled_server():
    server = socket.socket(); server.bind(('127.0.0.1', 0)); server.listen(16); held = []
    def accept():
        while True:
            try: conn, _ = server.accept()
            except OSError: return
            held.append(conn)  # never answer: TLS handshake stalls until the client timeout
    threading.Thread(target=accept, daemon=True).start()
    yield server.getsockname()[1], held
    for conn in held: conn.close()
    server.close()


def test_daemon_executor_bounded_shutdown_and_cancellation():
    from app.nav.maritime.executor import DaemonExecutor
    release = threading.Event(); executor = DaemonExecutor(1, 'test')
    running = executor.submit(release.wait, 30); queued = executor.submit(lambda: 'never')
    time.sleep(0.05)
    started = time.monotonic()
    assert executor.shutdown(wait=True, cancel_futures=True, timeout=0.3) is False
    assert time.monotonic() - started < 1.0 and queued.cancelled() and not running.done()
    with pytest.raises(RuntimeError): executor.submit(lambda: None)
    release.set()
    ok = DaemonExecutor(2, 'ok'); future = ok.submit(lambda: 42)
    assert future.result(timeout=2) == 42 and ok.shutdown(wait=True, timeout=1) is True


def test_shutdown_with_stalled_provider_is_prompt(qapp, tmp_path, stalled_server):
    from app.nav.maritime.runtime import MaritimeRuntime
    from app.nav.maritime.config import MaritimeConfig
    port, held = stalled_server
    gis = tmp_path / 'gis'; gis.mkdir()
    env = {'GDS_MARITIME_CACHE_DIR': str(tmp_path / 'cache'), 'GDS_MALAYSIA_GIS_PATH': str(gis),
           'GDS_OVERPASS_ENDPOINT': f'https://127.0.0.1:{port}/api/interpreter',
           'GDS_OVERPASS_FALLBACK_ENDPOINTS': f'https://127.0.0.1:{port}/b',
           'GDS_GEBCO_WMS_ENDPOINT': f'https://127.0.0.1:{port}/mapserv?'}
    runtime = MaritimeRuntime(config=MaritimeConfig(env))
    runtime.own_position(2.5, 104.0); runtime.tick()
    deadline = time.monotonic() + 10
    while len(held) < 1 and time.monotonic() < deadline: time.sleep(0.05)
    assert held and {'overpass', 'gebco'} & runtime._busy, 'providers must be stalled in flight'
    started = time.monotonic()
    drained = runtime.close(wait=True, timeout=2.0)
    elapsed = time.monotonic() - started
    assert elapsed < 3.0 and drained is False
    runtime.close(wait=True, timeout=0.1)  # idempotent second close (closeEvent then main())


def test_provider_requests_have_finite_timeouts():
    from app.nav.maritime.adapters import provider_common
    import inspect
    assert inspect.signature(provider_common.request_bytes).parameters['timeout'].default == provider_common.DEFAULT_TIMEOUT == 20
    assert provider_common.OVERPASS_TIMEOUT == 35


def test_copernicus_subset_is_time_bounded():
    from app.nav.maritime.adapters.copernicus import bounded_call
    from app.nav.maritime.adapters.provider_common import ProviderRequestError
    hang = threading.Event()
    started = time.monotonic()
    with pytest.raises(ProviderRequestError) as error:
        bounded_call(lambda: hang.wait(30), 0.2)
    assert error.value.state == 'TIMEOUT' and time.monotonic() - started < 1.0
    hang.set()
    assert bounded_call(lambda: 7, 1) == 7
    with pytest.raises(ValueError):
        bounded_call(lambda: (_ for _ in ()).throw(ValueError('x')), 1)
