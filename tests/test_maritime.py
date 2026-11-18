"""Phase 4 domain, adapter, Qt seam and map contract tests. No WebEngine required."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace

import pytest

from app.nav.maritime import Category, MaritimeObjectService, AISService, MaritimeDataError
from app.nav.maritime.models import normalize_ais, normalize_maritime_feature, MaritimeObject
from app.nav.maritime.area_controller import MaritimeAreaController, OperatingArea, distance_bearing
from app.nav.maritime.render_state import build_render_state, LAYER_GROUPS
from app.nav.maritime.source_health import SourceState
from app.nav.maritime.config import MaritimeConfig
from app.nav.maritime.adapters.base import JsonPollingAdapter, SourceConfig, StaticCache
from app.nav.map_bridge import MapBridge
from app.nav.events import SquallEventService

NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def ais(**changes):
    return {**(dict(mmsi='123456789', name='TEST CARGO', ship_type='cargo', latitude=22, longitude=91,
                sog=10, cog=40, heading=45, position_timestamp=NOW.isoformat())), **(changes)}


def feature(category='offshore', kind='oil platform', **changes):
    return {**(dict(type='Feature', id='TEST-1', geometry={'type': 'Point', 'coordinates': [91, 22]},
                properties=dict(category=category, object_type=kind, name='TEST / SYNTHETIC'))), **(changes)}


@pytest.fixture
def store():
    clock = [NOW]
    service = MaritimeObjectService(lambda: clock[0])
    return clock, service


def test_empty_and_domain_separation(store):
    _, s = store
    p = build_render_state(s)
    assert p['objects'] == [] and sum(p['counts'].values()) == 0
    assert set(p['sources']) == {'ais', 'chart', 'offshore', 'warnings', 'metocean'}
    assert all(h['state'] == 'NOT_CONFIGURED' for h in p['sources'].values())
    assert all(c == {'type': 'FeatureCollection', 'features': []} for c in p['geojson'].values())
    assert not {'telemetry', 'events', 'package'}.intersection(p)
    json.dumps(p, allow_nan=False)


def test_ais_normalization_and_sentinels():
    obj = normalize_ais(ais(), 'ais', NOW)
    assert obj.object_id == 'ais:123456789' and obj.category == Category.VESSEL
    assert obj.geometry['coordinates'] == [91, 22]
    assert obj.properties['heading'] == 45
    minimal = normalize_ais(ais(heading=511, cog=360, sog=102.3, name=None), 'ais', NOW)
    assert all(minimal.properties[k] is None for k in ('heading', 'cog', 'sog'))
    assert 'name' not in minimal.properties
    assert 'imo' not in obj.properties


@pytest.mark.parametrize('field,value', [('latitude', None), ('latitude', 91), ('longitude', -181),
    ('longitude', float('nan')), ('latitude', float('inf')), ('sog', -1), ('cog', None),
    ('heading', 361), ('mmsi', 'bad'), ('mmsi', '000000000'), ('position_timestamp', '2026-11-01'),
    ('position_timestamp', (NOW+timedelta(hours=1)).isoformat())])
def test_bad_ais_rejected_atomically(store, field, value):
    _, s = store
    if field == 'cog' and value is None:
        assert normalize_ais(ais(cog=None), 'ais', NOW).properties['cog'] is None
        return
    with pytest.raises(MaritimeDataError):
        AISService(s).ingest([ais(), ais(**{field: value})])
    assert s.snapshot() == ()


def test_stable_identity_merge_older_idempotent_and_multi(store):
    clock, s = store
    a = AISService(s)
    a.ingest([ais(), ais(mmsi='987654321')])
    rev = s.revision
    clock[0] += timedelta(seconds=1)
    assert not a.ingest([ais()]) and s.revision == rev
    assert not a.ingest([ais(position_timestamp=(NOW-timedelta(seconds=1)).isoformat(), longitude=92)])
    a.ingest([ais(name=None, longitude=91.1, position_timestamp=clock[0].isoformat())])
    p = build_render_state(s)
    assert p['counts']['vessels'] == 2
    target = next(o for o in p['objects'] if o['object_id'] == 'ais:123456789')
    assert target['geometry']['coordinates'][0] == 91.1
    assert target['properties']['name'] == 'TEST CARGO'


def test_stale_expire_source_timestamp_selection_and_replay(store):
    clock, s = store
    a = AISService(s)
    a.ingest([ais()]); s.select('ais:123456789')
    clock[0] += timedelta(seconds=121)
    s.evaluate_time()
    assert s.snapshot()[0].status == 'STALE'
    assert build_render_state(s)['geojson']['selection']['features']
    rev = s.revision
    s.evaluate_time(); assert s.revision == rev
    clock[0] += timedelta(seconds=480)
    s.evaluate_time()
    assert s.snapshot() == () and s.selected_object_id is None
    assert not a.ingest([ais()])  # delayed old feed cannot resurrect expired target


def test_unknown_source_time_not_fabricated(store):
    clock, s = store
    AISService(s).ingest([ais(position_timestamp=None)])
    obj = build_render_state(s)['objects'][0]
    assert obj['observed_at'] is None and obj['age_seconds'] is None and obj['freshness'] == 'UNKNOWN'
    clock[0] += timedelta(seconds=601); s.evaluate_time(); assert not s.snapshot()


def test_receive_time_fallback_refreshes_stationary_unknown_time_target(store):
    clock, s = store
    feed = AISService(s)
    feed.ingest([ais(position_timestamp=None)])
    clock[0] += timedelta(seconds=100)
    feed.ingest([ais(position_timestamp=None)])
    clock[0] += timedelta(seconds=100); s.evaluate_time()
    assert s.snapshot()[0].status == 'LIVE' and len(s.snapshot()) == 1


def test_unavailable_heading_clears_previous_and_falls_back_to_cog(store):
    clock, s = store
    feed = AISService(s); feed.ingest([ais()])
    clock[0] += timedelta(seconds=1)
    feed.ingest([ais(heading=511,cog=90,position_timestamp=clock[0].isoformat())])
    props = build_render_state(s)['geojson']['vessels']['features'][0]['properties']
    assert props['rotation'] == 90 and props['oriented']
    feed.ingest([ais(heading=511,cog=360,position_timestamp=clock[0].isoformat())])
    props = build_render_state(s)['geojson']['vessels']['features'][0]['properties']
    assert props['rotation'] == 0 and not props['oriented']


def test_own_vessel_suppression():
    s = MaritimeObjectService(lambda: NOW, own_mmsi='123456789')
    AISService(s).ingest([ais(), ais(mmsi='987654321')])
    assert [o.object_id for o in s.snapshot()] == ['ais:987654321']


@pytest.mark.parametrize('category,kind', [('offshore', 'FPSO'), ('aton', 'light buoy'), ('ports', 'terminal'),
    ('anchorages', 'anchorage'), ('routes', 'TSS'), ('restricted', 'safety zone'), ('subsea', 'cable'),
    ('hazards', 'wreck'), ('bathymetry', 'sounding'), ('warnings', 'navigation warning'), ('metocean', 'wind')])
def test_all_categories_and_canonical_identity(category, kind, store):
    _, s = store
    f = feature(category, kind)
    f['properties']['canonical_id'] = 'GLOBAL-1'
    s.ingest([normalize_maritime_feature(f, 'chart')])
    s.ingest([normalize_maritime_feature(f, 'offshore')])
    assert len(s.snapshot()) == 1
    p = build_render_state(s)
    assert p['counts'][category] == 1 and p['geojson'][category]['features']
    assert p['objects'][0]['object_id'] == 'maritime:GLOBAL-1'


@pytest.mark.parametrize('geometry', [
    {'type': 'LineString', 'coordinates': [[91, 22], [91.1, 22.1]]},
    {'type': 'Polygon', 'coordinates': [[[91, 22], [92, 22], [92, 23], [91, 22]]]},
    {'type': 'MultiPoint', 'coordinates': [[91, 22], [92, 23]]},
    {'type': 'MultiLineString', 'coordinates': [[[91, 22], [92, 23]]]},
    {'type': 'MultiPolygon', 'coordinates': [[[[91, 22], [92, 22], [92, 23], [91, 22]]]]},
])
def test_supported_geometry(geometry, store):
    _, s = store
    s.ingest([normalize_maritime_feature(feature('routes', 'fairway', geometry=geometry), 'chart')])
    json.dumps(build_render_state(s), allow_nan=False)


@pytest.mark.parametrize('geometry', [None, {}, {'type': 'Point', 'coordinates': [None, 0]},
    {'type': 'Point', 'coordinates': [0, float('inf')]}, {'type': 'LineString', 'coordinates': [[0, 0]]},
    {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [2, 2]]]},
    {'type': 'MultiPoint', 'coordinates': []}, {'type': 'GeometryCollection', 'geometries': []}])
def test_invalid_geometry(geometry):
    with pytest.raises(MaritimeDataError):
        normalize_maritime_feature(feature(geometry=geometry), 'chart')


def test_static_replacement_no_stale_duplicates(store):
    _, s = store
    one = normalize_maritime_feature(feature(), 'chart', NOW.isoformat())
    two = normalize_maritime_feature(feature(id='TEST-2'), 'chart')
    s.ingest([one, two]); s.select(one.object_id)
    s.ingest([two], replace_source='chart')
    assert len(s.snapshot()) == 1 and s.selected_object_id is None


def test_properties_json_and_input_isolation(store):
    _, s = store
    bad = feature(); bad['properties']['depth'] = float('nan')
    with pytest.raises(MaritimeDataError):
        normalize_maritime_feature(bad, 'chart')
    good = feature(); s.ingest([normalize_maritime_feature(good, 'chart')])
    good['properties']['name'] = 'mutated'
    snap = s.snapshot(); snap[0].properties['name'] = 'mutated again'
    assert s.snapshot()[0].properties['name'] == 'TEST / SYNTHETIC'
    bad = feature(); bad['properties']['name'] = {'not': 'a label'}
    with pytest.raises(MaritimeDataError):
        normalize_maritime_feature(bad, 'chart')


def test_initial_area_movement_and_debounce():
    clock = [0]
    c = MaritimeAreaController(clock=lambda: clock[0])
    assert c.request(22, 91).radius_nm == 50
    assert c.request(22.001, 91.001) is None
    assert c.request(23, 91) is None
    clock[0] = 4
    assert c.request(23, 91).latitude == 23
    assert c.request(23, 91) is None


def test_viewport_area_bounded_and_dateline():
    c = MaritimeAreaController(debounce_seconds=0)
    assert c.viewport(-180, -80, 180, 80) is None
    area = c.viewport(90, 21, 92, 23)
    assert area.origin == 'viewport' and 50 <= area.radius_nm <= 250
    assert c.viewport(90, 21, 92, 23) is None
    assert c.viewport(179, -1, -179, 1).longitude == -180
    assert distance_bearing(0, 179.9, 0, -179.9)[0] < 13


@pytest.mark.parametrize('state', list(SourceState))
def test_health_states_and_recovery(state, store):
    clock, s = store
    s.set_source('ais', state, error='controlled' if state == SourceState.ERROR else None)
    assert build_render_state(s)['sources']['ais']['state'] == state
    s.set_source('ais', SourceState.LIVE, success=True)
    assert s.sources['ais'].error is None and s.sources['ais'].last_success_at == NOW
    clock[0] += timedelta(seconds=121); s.evaluate_time()
    assert s.sources['ais'].state == SourceState.STALE


def test_bridge_visibility_json_and_independent_signals(store):
    _, s = store
    bridge = MapBridge(maritime_service=s)
    output, events = [], []
    bridge.maritimeStateChanged.connect(output.append)
    bridge.eventStateChanged.connect(events.append)
    AISService(s).ingest([ais()]); s.ingest([normalize_maritime_feature(feature(), 'offshore')])
    bridge.selectMaritimeObject('ais:123456789')
    assert output[-1]['selected_object_id'] == 'ais:123456789' and not events
    bridge.setMaritimeVisibility('vessels', False)
    assert output[-1]['geojson']['vessels']['features'] == [] and len(s.snapshot()) == 2
    assert output[-1]['selected_object_id'] is None
    bridge.setMaritimeVisibility('vessels', True)
    assert len(output[-1]['geojson']['vessels']['features']) == 1
    assert output[-1] == bridge.getMaritimeState()
    json.dumps(output[-1], allow_nan=False)
    assert MapBridge().getMaritimeState()['objects'] == []


@pytest.mark.parametrize('category,kind',[('offshore','oil_platform'),('aton','buoy'),('warnings','navigation_warning')])
def test_bridge_static_selection_and_clear(category,kind,store):
    _,s=store
    obj=normalize_maritime_feature(feature(category,kind),'chart')
    s.ingest([obj]);bridge=MapBridge(maritime_service=s)
    bridge.selectMaritimeObject(obj.object_id)
    payload=bridge.getMaritimeState()
    assert payload['selected_object_id']==obj.object_id
    assert payload['geojson']['selection']['features'][0]['properties']['category']==category
    bridge.clearMaritimeSelection()
    assert bridge.getMaritimeState()['geojson']['selection']['features']==[]
    assert len(s.snapshot())==1


def test_cross_selection_with_squall_and_spatial(store):
    from app.ui.pages.nav.nav_page import NavPage
    _, s = store
    events = SquallEventService(lambda: NOW)
    events.ingest_mapping(dict(operation='CREATE', event_id='SQ-TEST', event_type='squall', observed_at=NOW.isoformat(), latitude=22, longitude=91, direction_deg=0))
    b = MapBridge(events, maritime_service=s)
    AISService(s).ingest([ais()])
    b.selectMaritimeObject('ais:123456789'); b.selectEvent('SQ-TEST')
    assert s.selected_object_id is None
    b.selectMaritimeObject('ais:123456789')
    assert b.getEventState()['selected_event_id'] is None
    calls = []
    page = SimpleNamespace(bridge=b, spatial=SimpleNamespace(select_feature=lambda *x: calls.append(x), clear_selection=lambda: calls.append(None)))
    NavPage._select_spatial_feature(page, 'pipeline', 'P')
    assert s.selected_object_id is None and calls[-1] == ('pipeline', 'P')
    b.selectMaritimeObject('ais:123456789'); NavPage._select_spatial_feature(page, '', '')
    assert s.selected_object_id is None and calls[-1] is None


def test_distance_bearing_only_with_own_position(store):
    _, s = store
    AISService(s).ingest([ais()])
    assert 'distance_nm' not in build_render_state(s)['objects'][0]
    s.own_position = (21, 91)
    s.select('ais:123456789')
    obj = build_render_state(s)['objects'][0]
    assert 59 < obj['distance_nm'] < 61 and obj['bearing_deg'] == 0


def test_adapter_contract_filtering_and_cache(tmp_path):
    c = SourceConfig('chart', 'local.json')
    area = OperatingArea(22, 91)
    adapter = JsonPollingAdapter(c)
    payload = dict(type='FeatureCollection', dataset_at=NOW.isoformat(), features=[feature(), feature(id='FAR', geometry={'type': 'Point', 'coordinates': [0, 0]})])
    objects = adapter.normalize(payload, area)
    assert len(objects) == 1 and objects[0].dataset_at == NOW
    cache = StaticCache(tmp_path)
    cache.save(c, area, objects)
    restored = cache.load(c, area)
    assert restored == objects
    assert cache.load(c, OperatingArea(0, 0)) is None
    ais_config = SourceConfig('ais', 'no-file', dynamic=True)
    cache.save(ais_config, area, [normalize_ais(ais(), 'ais', NOW)])
    assert cache.load(ais_config, area) is None
    path = tmp_path/'feed.json'; path.write_text(json.dumps(payload))
    assert len(JsonPollingAdapter(SourceConfig('chart', str(path))).fetch(area)) == 1


def test_default_configuration_and_secrets():
    c = MaritimeConfig({})
    assert c.sources == {} and c.radius_nm == 50
    config = MaritimeConfig({'GDS_AIS_ENDPOINT': 'https://example.invalid/feed', 'GDS_AIS_API_KEY': 'secret'})
    assert 'secret' not in repr(config.sources['ais'])
    with pytest.raises(MaritimeDataError):
        MaritimeConfig({'GDS_AIS_STALE_SECONDS': 'nan'})


def test_hundreds_of_targets_share_collections(store):
    _, s = store
    AISService(s).ingest([ais(mmsi=str(100000000+i), longitude=91+i*.001) for i in range(800)])
    p = build_render_state(s)
    assert p['counts']['vessels'] == 800 and len(p['geojson']['vessels']['features']) == 800
    assert len(p['geojson']) == len(Category)+1
    json.dumps(p, allow_nan=False)


def test_runtime_no_provider_and_viewport_not_overridden(qapp):
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime = MaritimeRuntime(config=MaritimeConfig({}))
    try:
        assert all(h.state == SourceState.NOT_CONFIGURED for h in runtime.service.sources.values())
        assert not runtime.service.snapshot()
        runtime.controller.debounce_seconds = 0
        runtime.own_position(22, 91)
        runtime.viewport(92, 23, 93, 24); runtime.tick()
        area = runtime.service.area
        assert area.origin == 'viewport'
        runtime.own_position(22.001, 91.001)
        assert runtime.service.area is area
        runtime.own_position(22.5, 91)
        assert runtime.service.area.origin == 'own_vessel'
    finally:
        runtime.close()


def test_runtime_stale_area_result_ignored_and_failure_retains_state(qapp):
    from app.nav.maritime.runtime import MaritimeRuntime
    config = MaritimeConfig({'GDS_CHART_SOURCE': 'not-a-real-file'})
    runtime = MaritimeRuntime(config=config)
    try:
        runtime.own_position(22, 91)
        objects = [normalize_maritime_feature(feature(), 'chart')]
        runtime._receive('chart', runtime._generation-1, objects, None, False)
        assert not runtime.service.snapshot()
        runtime._receive('chart', runtime._generation, objects, None, False)
        runtime._receive('chart', runtime._generation, None, 'URLError', False)
        assert len(runtime.service.snapshot()) == 1 and runtime.service.sources['chart'].state == SourceState.DEGRADED
        runtime._receive('chart', runtime._generation, objects, None, False)
        assert runtime.service.sources['chart'].state == SourceState.LIVE
    finally:
        runtime.close()


def test_polling_is_worker_only_and_delivery_is_gui_thread(qtbot, tmp_path):
    import threading
    from app.nav.maritime.runtime import MaritimeRuntime
    config = MaritimeConfig({'GDS_CHART_SOURCE': str(tmp_path/'chart.json')})
    runtime = MaritimeRuntime(config=config)
    runtime.timer.stop()
    main_thread, workers, callbacks = threading.get_ident(), [], []
    runtime.adapters['chart'].fetch = lambda area: (workers.append(threading.get_ident()) or [normalize_maritime_feature(feature(), 'chart')])
    runtime.service.add_listener(lambda: callbacks.append(threading.get_ident()))
    try:
        runtime.own_position(22, 91); runtime.tick()
        qtbot.waitUntil(lambda: len(runtime.service.snapshot()) == 1, timeout=5000)
        assert workers and workers[0] != main_thread
        assert callbacks and all(t == main_thread for t in callbacks)
    finally:
        runtime.close()


def test_http_contract_headers_and_bounded_area(monkeypatch):
    from app.nav.maritime.adapters import base
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            return json.dumps({'vessels': [ais(position_timestamp=datetime.now(timezone.utc).isoformat())]}).encode()
    def urlopen(request, timeout):
        captured.append(request)
        assert timeout == 10
        return Response()
    monkeypatch.setattr(base, 'urlopen', urlopen)
    adapter = JsonPollingAdapter(SourceConfig('ais', 'https://example.invalid/feed', 'secret', True))
    objects = adapter.fetch(OperatingArea(22, 91))
    assert len(objects) == 1
    assert 'radius_nm=50' in captured[0].full_url
    assert 'secret' not in captured[0].full_url
    assert captured[0].get_header('Authorization') == 'Bearer secret'


def test_batch_replace_rejects_older_dataset_and_recovers_cached_freshness(store):
    _, s = store
    obj = normalize_maritime_feature(feature(), 'chart', NOW.isoformat())
    s.ingest([replace(obj, freshness='CACHED')])
    s.ingest([replace(obj, dataset_at=NOW-timedelta(days=1))], replace_source='chart')
    assert s.snapshot()[0].dataset_at == NOW and s.snapshot()[0].freshness == 'CACHED'
    s.ingest([obj], replace_source='chart')
    assert s.snapshot()[0].freshness == 'UNKNOWN'


def test_warning_expiry_leaves_other_categories(store):
    clock, s = store
    warning = normalize_maritime_feature(feature('warnings', 'navigation_warning'), 'warnings')
    s.ingest([replace(warning, expires_at=NOW+timedelta(seconds=10)), normalize_maritime_feature(feature(), 'chart')])
    s.select(warning.object_id)
    clock[0] += timedelta(seconds=11); s.evaluate_time()
    assert len(s.snapshot()) == 1 and s.selected_object_id is None


def test_runtime_rejects_invalid_own_position(qapp):
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime = MaritimeRuntime(config=MaritimeConfig({}))
    try:
        runtime.own_position(float('nan'), 91)
        runtime.own_position(91, 91)
        assert runtime.service.area is None and runtime.service.own_position is None
    finally:
        runtime.close()
