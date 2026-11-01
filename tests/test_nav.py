from datetime import datetime,timedelta,timezone
from app.nav.antenna_offset import reference_position
from app.nav.vessel_config import VesselConfig
from app.nav.track_manager import TrackManager,TrackPoint
from app.nav.vessel_state import VesselState
from app.telemetry.frame import TelemetryFrame
from app.nav.render_geometry import vector_geojson
from app.nav.presentation import format_duration,track_metrics,telemetry_age
from app.nav.map_controls import FollowController,LAYER_VISIBILITY
def p(t,lat=22,lon=91): return TrackPoint(t,lat,lon,10,20,3)
def test_config_validation(): VesselConfig().validate()
def test_offset_zero(): assert reference_position(22,91,0,0,0)==(22,91)
def test_offset_forward_aft_starboard_port():
 assert reference_position(22,91,0,10,0)[0]>22; assert reference_position(22,91,0,-10,0)[0]<22; assert reference_position(22,91,0,0,10)[1]>91; assert reference_position(22,91,0,0,-10)[1]<91
def test_track_start_order_gap_and_bounds():
 t=datetime.now(timezone.utc); m=TrackManager(10); m.append(p(t)); m.append(p(t+timedelta(seconds=1),23,92)); m.append(p(t+timedelta(seconds=20),24,93)); assert m.start.latitude==22 and len(m.segments)==2 and m.bounds()==(91,22,93,24)
def test_track_rejects_invalid(): assert not TrackManager().append(p(datetime.now(timezone.utc),100,91))
def test_state_heading_and_cog_fallback():
 s=VesselState(); s.update(TelemetryFrame(latitude=22,longitude=91,heading=45,cog=90),VesselConfig()); assert s.heading==45
 s.update(TelemetryFrame(latitude=22,longitude=91,cog=90),VesselConfig()); assert s.heading==90
def test_segment_geojson_and_vector():
 t=datetime.now(timezone.utc);m=TrackManager();m.append(p(t));m.append(p(t+timedelta(seconds=1),23,92));assert len(m.geojson_segments()['geometry']['coordinates'][0])==2 and m.start_geojson()['geometry']['coordinates']==[91,22] and len(vector_geojson(22,91,90)['geometry']['coordinates'])==2
def test_track_presentation(): assert format_duration(timedelta(seconds=3661))=='01:01:01' and track_metrics(TrackManager())['status']=='IDLE'
def test_follow_defaults_off_and_toggles():
 f=FollowController();assert not f.enabled;assert f.toggle();assert f.enabled;assert not f.toggle()
def test_centering_does_not_change_follow_state():
 f=FollowController();assert not f.enabled
def test_layer_visibility_mapping(): assert LAYER_VISIBILITY['Track']==('track','track-start') and LAYER_VISIBILITY['Heading / COG']==('heading-vector','cog-vector')
def test_deterministic_route_metrics_and_gap_distance():
 t=datetime(2026,1,1,tzinfo=timezone.utc);m=TrackManager()
 for offset,lat,lon in ((0,22.2000,91.7500),(1,22.1988,91.7513),(2,22.1975,91.7527),(20,22.1920,91.7590),(21,22.1908,91.7604)): m.append(p(t+timedelta(seconds=offset),lat,lon))
 direct=TrackManager(999)
 for offset,lat,lon in ((0,22.2000,91.7500),(1,22.1988,91.7513),(2,22.1975,91.7527),(20,22.1920,91.7590),(21,22.1908,91.7604)): direct.append(p(t+timedelta(seconds=offset),lat,lon))
 assert m.point_count==5 and [len(segment) for segment in m.segments]==[3,2] and m.duration==timedelta(seconds=21) and 0<m.distance_nm<direct.distance_nm
def test_telemetry_age_refreshes_from_the_same_frame():
 t=datetime(2026,1,1,tzinfo=timezone.utc);f=TelemetryFrame(received_at=t,valid=True)
 assert telemetry_age(f,t+timedelta(seconds=0.5))=='0.5 s' and telemetry_age(f,t+timedelta(seconds=1.5))=='1.5 s'
