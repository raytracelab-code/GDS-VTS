"""Remaining P1 fixes: 005 (history/reopen), 019 (renderer health), 021 (squall feed).
009 (PDF row splitting) is covered in tests/test_pdf_row_split.py."""
from datetime import datetime, timedelta, timezone
import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app.nav import renderer_health as rh
from app.nav.events import SquallEventService
from app.nav.events.render_state import EventRenderStateBuilder
from app.nav.presentation import squall_feed_text
from app.vdr.store import ReportStore
from test_vdr import TEST_IDENTITY, fixture_report


# ------------------------------------------------------------------ 019 renderer health
def test_renderer_health_states_and_retry():
    h = rh.RendererHealth(); h.start_load(0)
    assert h.load_finished(True, 1) == rh.LOADING and h.map_ready() == rh.OK and h.message() is None
    assert h.load_finished(False, 2) == rh.LOAD_FAILED and h.message()[0] == 'Map failed to load'
    assert h.retry(3) and h.state == rh.LOADING and not h.retry(3.1)  # no stacked retries while loading
    h.load_finished(True, 4); h.map_ready()
    assert h.renderer_terminated('CrashedTerminationStatus', -1) == rh.RENDERER_STOPPED
    assert h.load_finished(True, 5) == rh.RENDERER_STOPPED  # a late load event is not a recovery
    assert 'CrashedTerminationStatus' in h.detail and 'Crashed' not in h.message()[1]  # no raw Qt text for users
    assert h.retry(6) and h.retries == 2


def test_renderer_watchdog_detects_blank_map_and_webgl_failure():
    h = rh.RendererHealth(); h.start_load(0); h.load_finished(True, 1)
    assert h.check(1 + rh.READY_TIMEOUT_SECONDS - 1) == rh.LOADING
    assert h.check(1 + rh.READY_TIMEOUT_SECONDS) == rh.NOT_RESPONDING and h.message()[0] == 'Map not responding'
    assert h.map_ready() == rh.OK  # a late style report clears the watchdog failure
    assert h.webgl_failed('renderer-webgl-lost') == rh.WEBGL_UNAVAILABLE and h.can_retry()


def test_nav_overlay_shows_failure_and_retry_reuses_the_same_view(qtbot):
    from app.qt.QtWidgets import QLabel, QWidget
    from app.ui.pages.nav.nav_page import NavPage
    loads = []
    page = NavPage.__new__(NavPage); QWidget.__init__(page); qtbot.addWidget(page)
    page.web = SimpleNamespace(setUrl=lambda url: loads.append(url.toString()))
    page.map_package_status = QLabel(); page._map_url = 'gds://map/index.html'
    page.renderer_health = rh.RendererHealth()
    from app.qt.QtWidgets import QFrame, QPushButton
    page.renderer_overlay, page.renderer_title, page.renderer_message, page.renderer_retry = QFrame(page), QLabel(), QLabel(), QPushButton()
    page.resize(900, 600)
    page._renderer_terminated(SimpleNamespace(name=b'CrashedTerminationStatus'), -1073741819)  # PySide2 bytes name
    assert not page.renderer_overlay.isHidden() and page.renderer_title.text() == 'Map renderer stopped'
    assert "b'" not in page.renderer_health.detail
    assert page.retry_renderer() and not page.retry_renderer()
    assert loads == ['gds://map/index.html']  # one reload of the same view; no new WebEngine objects
    page._bridge_command('renderer-ok') if hasattr(page, 'bridge') else page.renderer_health.map_ready()
    page._show_renderer_health(); assert page.renderer_overlay.isHidden()


def test_nav_js_reports_renderer_failures():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js not available')
    result = subprocess.run([node, 'tests/nav_renderer_runtime.cjs'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


# ------------------------------------------------------------------ 021 squall feed
def clock(start):
    state = {'now': start}
    return state, (lambda: state['now'])


def message(now, **changes):
    return dict(dict(operation='CREATE', event_type='squall', event_id='SQ-1', observed_at=now.isoformat(), latitude=5.0,
                     longitude=104.0, direction_deg=90, speed_knots=20, severity='moderate', impact_radius_nm=2,
                     surveillance_radius_nm=6, predicted_path=[dict(latitude=5.0, longitude=104.1, eta_seconds=600)],
                     source='TEST FIXTURE'), **changes)


def test_squall_feed_states_live_stale_no_data_unavailable():
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now)
    assert service.feed_status()['state'] == 'PROVIDER UNAVAILABLE'  # this build: no provider configured
    service.attach_provider('fixture feed'); assert service.feed_status()['state'] == 'NO DATA'
    service.ingest_mapping(message(t0)); assert service.feed_status()['state'] == 'LIVE'
    assert service.feed_status()['last_update'] == t0.isoformat()  # receipt time, never invented
    state['now'] = t0 + timedelta(seconds=121); assert service.feed_status()['state'] == 'STALE'
    service.heartbeat(); assert service.feed_status()['state'] == 'LIVE'


def test_provider_failure_marks_events_stale_then_expires_and_recovers():
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now); builder = EventRenderStateBuilder(service)
    service.attach_provider('fixture feed'); service.ingest_mapping(message(t0))
    service.provider_failed('connection refused')
    payload = builder.payload()
    assert payload['feed']['state'] == 'PROVIDER UNAVAILABLE' and payload['events'][0]['status'] == 'STALE'
    assert all(f['properties']['status'] == 'STALE' for f in payload['geojson']['current']['features'])  # dimmed, not current
    state['now'] = t0 + timedelta(seconds=601); service.evaluate_time()
    assert builder.payload()['geojson']['current']['features'] == []  # shapes cleared after expiry
    service.provider_recovered(); state['now'] = t0 + timedelta(seconds=620)
    service.ingest_mapping(message(state['now']))
    assert builder.payload()['feed']['state'] == 'LIVE' and builder.payload()['events'][0]['status'] == 'ACTIVE'


def test_eta_counts_down_from_observation_time():
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now); builder = EventRenderStateBuilder(service)
    service.ingest_mapping(message(t0))
    assert builder.payload()['events'][0]['eta_label'] == '10 min'
    state['now'] = t0 + timedelta(minutes=4); assert builder.payload()['events'][0]['eta_label'] == '6 min'
    state['now'] = t0 + timedelta(minutes=11)
    point = builder.payload()['geojson']['prediction_points']['features'][0]['properties']
    assert point['eta_label'] == 'PASSED' and builder.payload()['events'][0]['eta_label'] == '—'


def test_squall_panel_text_never_reads_as_all_clear_unless_live():
    assert 'PROVIDER UNAVAILABLE' in squall_feed_text(None, 0)[0]
    assert 'NOT an all-clear' in squall_feed_text(None, 0)[1]
    assert squall_feed_text({'state': 'LIVE', 'age_seconds': 5}, 0)[0].startswith('SQUALL FEED LIVE · updated 5 s ago')
    assert 'may be out of date' in squall_feed_text({'state': 'STALE', 'age_seconds': 300}, 2)[0]


def test_bridge_does_not_republish_each_second_for_countdown_only():
    from app.nav.map_bridge import MapBridge
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now); service.ingest_mapping(message(t0))
    bridge = MapBridge(service); sent = []; bridge.eventStateChanged.connect(sent.append)
    state['now'] = t0 + timedelta(seconds=1); bridge.publishEventState()   # ETA label '9 min'
    state['now'] = t0 + timedelta(seconds=30); bridge.publishEventState()  # still '9 min'; age/countdown ticked
    assert len(sent) == 1  # same visible labels → no resend
    state['now'] = t0 + timedelta(minutes=2); bridge.publishEventState()
    assert len(sent) == 2  # visible ETA label changed → map updated


# ------------------------------------------------------------------ 005 VDR history / reopen
def test_vdr_history_lists_saved_reports_newest_first_with_status(tmp_path):
    s = ReportStore(tmp_path/'reports.json', today='2026-11-19', identity=TEST_IDENTITY)
    for day in ('2026-11-17', '2026-11-18'):
        s.reports[day] = fixture_report(day)
    s.select('2026-11-17'); assert s.finalize() == []
    s.reopen(); assert s.finalize() == []
    s.select('2026-11-18'); assert s.finalize() == []; s.reopen()
    rows = s.history(TEST_IDENTITY)
    assert [r['day'] for r in rows] == ['2026-11-18', '2026-11-17']  # untouched today (19th) is not listed
    assert rows[0]['status'] == 'REOPENED · DRAFT' and rows[1]['status'] == 'FINALIZED · REV 2'
    assert rows[1]['report_no'] == '321' and rows[1]['vessel'] == 'TEST VESSEL' and rows[1]['modified']
    s.save(); reopened = ReportStore(s.path, today='2026-11-19', identity=TEST_IDENTITY)
    assert [r['status'] for r in reopened.history(TEST_IDENTITY)] == ['REOPENED · DRAFT', 'FINALIZED · REV 2']


def test_vdr_history_dialog_search_empty_state_and_open(qtbot, tmp_path):
    from app.ui.pages.vdr.history_dialog import ReportHistoryDialog
    empty = ReportHistoryDialog([], '2026-11-19'); qtbot.addWidget(empty)
    assert 'No saved reports yet' in empty.empty.text() and empty.table.isHidden()
    s = ReportStore(tmp_path/'reports.json', today='2026-11-19', identity=TEST_IDENTITY)
    for day in ('2026-11-15', '2026-11-17'):
        s.reports[day] = fixture_report(day)
    dialog = ReportHistoryDialog(s.history(TEST_IDENTITY), '2026-11-19'); qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 2 and dialog.table.item(0, 0).text() == '17 Nov 2026'
    dialog.search.setText('15 nov'); assert dialog.table.rowCount() == 1
    dialog.search.setText('319'); assert dialog.table.rowCount() == 1  # Report No. of 15 Nov
    dialog.search.setText('nothing-matches'); assert 'No reports match' in dialog.empty.text()
    dialog.search.setText(''); dialog.table.selectRow(1); dialog.open_selected()
    assert dialog.selected_day == '2026-11-15'


def test_opening_old_finalized_report_from_history_does_not_modify_it(qtbot, tmp_path, monkeypatch):
    from app.ui.pages.vdr import workspace
    from app.ui.pages.vdr.workspace import VdrPage
    s = ReportStore(tmp_path/'reports.json', today='2026-11-19', identity=TEST_IDENTITY)
    s.reports['2026-11-17'] = fixture_report('2026-11-17'); s.select('2026-11-17'); assert s.finalize() == []
    s.select('2026-11-19')
    page = VdrPage(s, identity_provider=lambda: dict(TEST_IDENTITY)); qtbot.addWidget(page)
    before = json.dumps(s.reports['2026-11-17'], sort_keys=True)
    monkeypatch.setattr('app.ui.dialogs.exec_dialog', lambda dialog, parent=None: (dialog.table.selectRow(0), dialog.open_selected()) and 1)
    assert page.show_history() == '2026-11-17' and page.store.current == '2026-11-17'
    page.edit(('meta', 'captain'), 'typo')  # read-only until reopened
    assert json.dumps(s.reports['2026-11-17'], sort_keys=True) == before
    monkeypatch.setattr('app.ui.dialogs.confirm', lambda *a, **k: False)
    assert not page.finalize() and page.report['finalized']  # Reopen declined → unchanged
    assert s.reports['2026-11-19'] is not s.reports['2026-11-17']  # no other day touched


# ------------------------------------------------------------------ 005 VJR voyage history
def make_store(tmp_path):
    from app.vjr.store import VjrStore
    from vjr_fixture import full_report
    store = VjrStore(tmp_path/'vjr'/'report.json'); store.mutate(lambda r: (r.clear(), r.update(full_report())))
    return store


def test_vjr_archives_listed_newest_first_and_never_overwritten(tmp_path):
    store = make_store(tmp_path)
    first = store.archive(); second = store.archive()  # same second: must not overwrite
    assert first != second and first.exists() and second.exists()
    (tmp_path/'vjr'/'archive'/'journey-20200101-000000.json').write_text('{broken', encoding='utf-8')
    rows = store.archived_journeys()
    assert [r['path'] for r in rows][:2] == [second, first] and rows[-1]['status'] == 'UNREADABLE'
    assert rows[0]['departure_location'] == 'Supply Base' and rows[0]['status'] == 'ARRIVED'


def test_vjr_restore_swaps_journeys_without_losing_either(tmp_path):
    store = make_store(tmp_path); archived = store.archive()
    store.mutate(lambda r: r['departure'].update(departure_location='Second voyage port'))
    swapped_out = store.restore_archived(archived)
    assert store.report['departure']['departure_location'] == 'Supply Base' and not archived.exists()
    assert json.loads(swapped_out.read_text(encoding='utf-8'))['departure']['departure_location'] == 'Second voyage port'
    assert store.undo_stack == [] and json.loads(store.path.read_text(encoding='utf-8'))['departure']['departure_location'] == 'Supply Base'


def test_vjr_voyage_history_dialog(qtbot, tmp_path, monkeypatch):
    from app.ui.pages import vjr_history
    from app.ui.pages.vjr_history import VoyageHistoryDialog
    from app.vjr.store import VjrStore
    empty = VoyageHistoryDialog(VjrStore(tmp_path/'empty'/'report.json')); qtbot.addWidget(empty)
    assert 'No archived voyages yet' in empty.empty.text()
    store = make_store(tmp_path); store.archive()
    dialog = VoyageHistoryDialog(store); qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 1 and dialog.table.item(0, 1).text() == 'Supply Base'
    dialog.search.setText('platform alpha'); assert dialog.table.rowCount() == 1
    dialog.search.setText(''); dialog.table.selectRow(0)
    monkeypatch.setattr('app.ui.dialogs.confirm', lambda *a, **k: True)
    assert dialog.restore_selected() and dialog.restored.exists()


def test_impact_is_judged_against_own_vessel_position():
    from app.nav.presentation import squall_alert_text
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now); builder = EventRenderStateBuilder(service)
    service.ingest_mapping(message(t0))  # at 5.0N 104.0E, impact 2 NM, surveillance 6 NM, path to 104.1E
    assert builder.payload()['events'][0]['impact_state'] == 'NONE'  # no position: never invented
    builder.vessel_position = (5.0, 104.1)  # on the predicted path
    event = builder.payload()['events'][0]
    assert event['impact_state'] == 'IMPACT' and event['impact_reason'] == 'own vessel'
    text, level = squall_alert_text(builder.payload())
    assert level == 'IMPACT' and 'own vessel inside impact zone' in text and 'ETA 10 min' in text
    builder.vessel_position = (5.0, 104.0 + 4/60)  # ~4 NM east of the squall, off the path end
    assert builder.payload()['events'][0]['impact_state'] in ('SURVEILLANCE', 'IMPACT')
    builder.vessel_position = (6.0, 104.0)  # 60 NM away
    assert builder.payload()['events'][0]['impact_state'] == 'NONE' and squall_alert_text(builder.payload()) == ('', '')


def test_alert_from_stale_feed_is_labelled_last_received():
    from app.nav.presentation import squall_alert_text
    t0 = datetime(2026, 11, 19, 12, tzinfo=timezone.utc); state, now = clock(t0)
    service = SquallEventService(clock=now); builder = EventRenderStateBuilder(service); builder.vessel_position = (5.0, 104.0)
    service.ingest_mapping(message(t0)); service.provider_failed('lost')
    text, level = squall_alert_text(builder.payload())
    assert level == 'IMPACT' and 'LAST RECEIVED DATA' in text and 'PROVIDER UNAVAILABLE' in text


def test_map_reload_restores_layers_with_a_single_maritime_publish(qtbot, monkeypatch):
    """Found while testing 019: each per-layer publish rebuilt the full maritime state (~27 s with GIS)."""
    from app.qt.QtWidgets import QCheckBox, QWidget
    from app.ui.pages.nav import nav_page
    from app.ui.pages.nav.nav_page import NavPage
    published, visibility = [], []
    bridge = SimpleNamespace(maritime_service=object(), publishMaritimeState=lambda: published.append(1),
                             setMaritimeVisibility=lambda c, v: (visibility.append(c), None if getattr(bridge, '_batch_visibility', False) else published.append(1)),
                             spatialStateChanged=SimpleNamespace(emit=lambda *a: None), eventStateChanged=SimpleNamespace(emit=lambda *a: None),
                             getEventState=lambda: {}, telemetryChanged=SimpleNamespace(emit=lambda *a: None))
    page = NavPage.__new__(NavPage); QWidget.__init__(page); qtbot.addWidget(page)
    page.bridge = bridge; page.vessel = SimpleNamespace(latitude=None); page.state = SimpleNamespace(latest_frame=None)
    page.spatial = SimpleNamespace(payload=lambda: {}, selection=SimpleNamespace(feature=None))
    page.web = SimpleNamespace(page=lambda: SimpleNamespace(runJavaScript=lambda *a: None))
    names = [n for n in nav_page.LAYER_GROUPS][:6]; page.layer_checks = {n: QCheckBox(n) for n in names}
    monkeypatch.setattr(nav_page, 'QSettings', lambda *a: SimpleNamespace(setValue=lambda *a: None))
    page._send_map_state()
    assert len(visibility) == len(names) and len(published) == 2  # 1 initial publish + 1 after all layers (not 1 per layer)
