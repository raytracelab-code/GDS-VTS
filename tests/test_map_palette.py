"""Deterministic geographic palette/service checks; no network or map data."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, QTimer
from app.nav.offline_maps.controller import PaletteController
from app.nav.offline_maps.palette import PaletteEngine, canonical_utc, position, solar_elevation, solar_state

UTC = datetime(2026, 3, 20, 6, tzinfo=timezone.utc)


@pytest.fixture
def service(qapp, tmp_path):
    state = SimpleNamespace(telemetry_status=SimpleNamespace(value='NO SOURCE'), latest_frame=None)
    clock = SimpleNamespace(now=UTC)
    settings = QSettings(str(tmp_path/'palette.ini'), QSettings.Format.IniFormat)
    controller = PaletteController(state, clock=lambda: clock.now, settings=settings)
    yield controller, state, clock, settings
    controller.minute.stop()
    controller.debounce.stop()
    controller.deleteLater()


def center(controller, latitude, longitude):
    controller.map_center(latitude, longitude)
    controller.debounce.stop()
    controller._settled()


def live(state, now, latitude=23.8, longitude=90.4):
    state.telemetry_status.value = 'LIVE'
    state.latest_frame = SimpleNamespace(valid=True, latitude=latitude, longitude=longitude,
        received_at=now, date=now.strftime('%Y-%m-%d'), utc=now.strftime('%H:%M:%S'))


@pytest.mark.parametrize('latitude,longitude,hour,expected',[
    (3.14,101.69,5,'DAY'), (3.14,101.69,17,'NIGHT'),
    (23.8,90.4,6,'DAY'), (23.8,90.4,18,'NIGHT'),
    (4,104,11,'DAY'), (4,104,11.4,'TWILIGHT'), (4,104,12,'NIGHT'),
    (0,-90,6,'NIGHT'), (0,90,6,'DAY'),
])
def test_fixed_geographic_solar_states(latitude, longitude, hour, expected):
    utc = UTC.replace(hour=0) + timedelta(hours=hour)
    assert solar_state(solar_elevation(utc, latitude, longitude)) == expected


@pytest.mark.parametrize('elevation,previous,expected',[
    (0,None,'DAY'), (-.001,None,'TWILIGHT'), (-6,None,'TWILIGHT'), (-6.001,None,'NIGHT'),
    (-.25,'DAY','DAY'), (-.251,'DAY','TWILIGHT'),
    (.249,'TWILIGHT','TWILIGHT'), (.25,'TWILIGHT','DAY'),
    (-6.25,'TWILIGHT','TWILIGHT'), (-6.251,'TWILIGHT','NIGHT'),
    (-5.751,'NIGHT','NIGHT'), (-5.75,'NIGHT','TWILIGHT'),
])
def test_symmetric_threshold_hysteresis(elevation, previous, expected):
    assert solar_state(elevation, previous) == expected


@pytest.mark.parametrize('bad',[None,(True,90),(0,float('nan')),(91,0),(0,181),('4',104)])
def test_invalid_reference_rejected(bad):
    assert position(bad) is None


def test_follow_changes_reference_immediately(service):
    controller, state, clock, _ = service
    center(controller,0,-90)
    live(state,clock.now)
    controller.update(follow=True)
    assert controller.payload['reference_type']=='OWN_VESSEL'
    assert controller.payload['effective_state']=='DAY'
    controller.update(follow=False)
    assert controller.payload['reference_type']=='MAP_CENTER'
    assert controller.payload['effective_state']=='NIGHT'
    controller.update(follow=True)
    assert controller.payload['reference_type']=='OWN_VESSEL'
    assert controller.payload['time_source']=='GNSS_UTC'


@pytest.mark.parametrize('status',['NO SOURCE','STALE','LOST','WAITING'])
def test_unavailable_telemetry_uses_system_and_center(service,status):
    controller, state, clock, _ = service
    live(state,clock.now)
    state.telemetry_status.value=status
    center(controller,4,104)
    controller.update(follow=True)
    assert controller.payload['reference_type']=='MAP_CENTER'
    assert controller.payload['time_source']=='SYSTEM_UTC'
    assert controller.payload['effective_state']=='DAY'
    assert controller.payload['utc_timestamp']==clock.now.isoformat()


def test_same_utc_different_map_longitudes(service):
    controller, _, _, _ = service
    center(controller,0,90)
    assert controller.payload['effective_state']=='DAY'
    center(controller,0,-90)
    assert controller.payload['effective_state']=='NIGHT'


def test_manual_override_and_restart_persist_only_preference(service):
    controller, state, clock, settings = service
    center(controller,0,-90)
    for mode in ('DAY','NIGHT','AUTO'):
        controller.set_mode(mode)
        assert controller.payload['effective_state']==('NIGHT' if mode=='AUTO' else mode)
    controller.set_mode('DAY')
    second=PaletteController(state,clock=lambda:clock.now,settings=settings)
    try:
        assert second.engine.mode=='DAY'
        center(second,0,-90)
        second.set_mode('AUTO')
        assert second.payload['effective_state']=='NIGHT'
        assert settings.allKeys()==['nav/palette']
    finally:
        second.minute.stop();second.debounce.stop();second.deleteLater()


def test_minute_clock_and_movement_throttle(service,monkeypatch):
    controller, state, clock, _ = service
    live(state,clock.now)
    controller.update(follow=True)
    calls=[]
    calculate=controller.engine.calculate
    def record(*args,**kwargs):
        calls.append(args)
        return calculate(*args,**kwargs)
    monkeypatch.setattr(controller.engine,'calculate',record)
    for delta in (0,.00001,-.00001,.0001):
        state.latest_frame.longitude=90.4+delta
        controller.update()
    assert calls==[]
    state.latest_frame.longitude=90.42
    controller.update()
    assert len(calls)==1
    # A settled map pan is irrelevant while following a valid Own Vessel.
    center(controller,0,-90)
    assert len(calls)==1
    clock.now+=timedelta(minutes=1)
    live(state,clock.now,longitude=90.42)
    controller.minute.timeout.emit()
    assert len(calls)==2
    timers=controller.findChildren(QTimer)
    assert [t.interval() for t in timers if not t.isSingleShot()]==[60000]


def test_settled_center_debounce_uses_latest_position(service,qtbot):
    controller, _, _, _ = service
    changes=[];controller.changed.connect(changes.append)
    controller.map_center(0,90)
    controller.map_center(0,-90)
    assert not changes and controller.center is None
    qtbot.waitUntil(lambda:controller.center==(0.,-90.),timeout=2000)
    assert len(changes)==1
    assert controller.payload['effective_state']=='NIGHT'


@pytest.mark.parametrize('attribute,value',[
    ('date','invalid'),('utc','25:00:00'),('valid',False),
    ('received_at',UTC-timedelta(seconds=3)),('received_at',UTC+timedelta(seconds=1)),
])
def test_bad_gnss_utc_falls_back(service,attribute,value):
    controller, state, clock, _ = service
    live(state,clock.now)
    setattr(state.latest_frame,attribute,value)
    controller.update(force=True)
    assert controller.payload['time_source']=='SYSTEM_UTC'


def test_utc_normalization_and_gnss_age():
    local=UTC.astimezone(timezone(timedelta(hours=6)))
    assert canonical_utc(None,local)==(UTC,'SYSTEM_UTC')
    frame=SimpleNamespace(valid=True,received_at=UTC-timedelta(seconds=1),date='2026-03-20',utc='055959')
    assert canonical_utc(frame,local,True)==(UTC,'GNSS_UTC')
    result=PaletteEngine().calculate(local,center=(4,104))
    assert result['utc_timestamp']==UTC.isoformat()
    with pytest.raises(ValueError):canonical_utc(None,UTC.replace(tzinfo=None))


def test_polar_and_date_line_remain_finite():
    for lat in (-90,90):
        for lon in (-180,180):
            elevation=solar_elevation(UTC,lat,lon)
            assert -90<=elevation<=90


def test_follow_toolbar_notifies_service_without_waiting(qapp):
    from PySide6.QtWidgets import QWidget, QPushButton
    from app.nav.map_controls import FollowController
    from app.ui.pages.nav.nav_page import NavPage
    page=NavPage.__new__(NavPage);QWidget.__init__(page)
    calls=[]
    page.follow=FollowController();page.follow_button=QPushButton(page)
    page.palette=SimpleNamespace(update=lambda **kw:calls.append(kw))
    page.web=SimpleNamespace(page=lambda:SimpleNamespace(runJavaScript=lambda _:None))
    page.command('FOLLOW');page.command('FOLLOW')
    assert calls==[{'follow':True},{'follow':False}]
    page.deleteLater()
