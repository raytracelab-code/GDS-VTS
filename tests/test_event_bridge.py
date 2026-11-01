"""Event integration without creating a WebEngine view."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from app.nav.events.service import SquallEventService
from app.nav.events.exceptions import SquallEventError
from app.nav.events.impact import evaluate
from app.nav.events.geometry import destination_point, circle
from app.nav.map_bridge import MapBridge
from app.nav.spatial.models import SpatialState, SpatialCategory
from app.ui.pages.nav.nav_page import NavPage
from app.ui.main_window import MainWindow

NOW=datetime(2026,11,1,9,tzinfo=timezone.utc)
def message(operation='CREATE',**changes):
 return dict(operation=operation,event_type='squall',event_id='SQ-001',observed_at=NOW.isoformat(),latitude=0,longitude=0,direction_deg=45,**{})|changes

@pytest.fixture
def integration():
 clock=[NOW];service=SquallEventService(lambda:clock[0]);bridge=MapBridge(service);captured=[]
 bridge.eventStateChanged.connect(captured.append)
 page=SimpleNamespace(bridge=bridge)
 service.add_listener(lambda:NavPage._on_squall_event_state_changed(page))
 owner=SimpleNamespace(squall_event_service=service)
 return clock,service,bridge,captured,owner

def test_live_service_and_controller_ingest(integration):
 _,service,bridge,out,owner=integration
 assert bridge.squall_event_service is service
 assert bridge._event_render_state.service is service
 assert bridge.getEventState()['active_count']==0
 MainWindow.ingest_squall_event(owner,message())
 assert len(out)==1 and out[-1]['active_count']==1
 MainWindow.ingest_squall_json(owner,json.dumps(message(event_id='SQ-002')))
 assert out[-1]['active_count']==2
 assert bridge.getEventState()==out[-1]

def test_telemetry_signal_does_not_emit_events(integration):
 _,s,b,out,_=integration
 b.telemetryChanged.emit({'latitude':22,'longitude':91});b.renderStateChanged.emit({})
 assert out==[]

def test_map_ready_replays_authoritative_snapshots():
 calls=[]
 page=SimpleNamespace(_send_map_state=lambda:calls.append('snapshot'))
 NavPage._bridge_command(page,'other');assert calls==[]
 NavPage._bridge_command(page,'ready');assert calls==['snapshot']

def test_visibility_only_changes_rendering(integration,monkeypatch):
 _,s,b,out,_=integration;s.ingest_mapping(message());before=s.snapshot()['events']
 import app.ui.pages.nav.nav_page as module
 monkeypatch.setattr(module,'QSettings',lambda *args:SimpleNamespace(setValue=lambda *args:None))
 commands=[];page=SimpleNamespace(spatial=SimpleNamespace(selection=SimpleNamespace(feature=None)),web=SimpleNamespace(page=lambda:SimpleNamespace(runJavaScript=commands.append)))
 NavPage.set_layer_visibility(page,'Squall Alerts',False);NavPage.set_layer_visibility(page,'Squall Alerts',True)
 assert s.snapshot()['events']==before and len(commands)==2

@pytest.mark.parametrize('bad',[[],{},dict(operation='CREATE',event_id={}),dict(operation='CREATE',event_id='')])
def test_malformed_identity_is_controlled(bad,integration):
 _,s,b,out,_=integration
 with pytest.raises(SquallEventError):s.ingest_mapping(bad)
 assert not out

def test_update_clear_and_multi_preservation(integration):
 clock,s,b,out,owner=integration
 s.ingest_mapping(message());s.ingest_mapping(message(event_id='SQ-002'))
 second=s._events['SQ-002'];clock[0]+=timedelta(seconds=1)
 s.ingest_mapping(message('UPDATE',longitude=1,observed_at=clock[0].isoformat()))
 assert s._events['SQ-002'] is second and out[-1]['active_count']==2
 assert out[-1]['geojson']['current']['features'][0]['geometry']['coordinates']==[1,0]
 s.ingest_mapping(message('CLEAR'))
 assert out[-1]['active_count']==1 and out[-1]['events'][0]['event_id']=='SQ-002'
 assert all(f['properties']['event_id']=='SQ-002' for c in out[-1]['geojson'].values() for f in c['features'])

def test_rejected_older_and_duplicate_update_do_not_emit(integration):
 clock,s,b,out,_=integration;s.ingest_mapping(message());clock[0]+=timedelta(seconds=5)
 assert not s.ingest_mapping(message('UPDATE')) # receipt time differs, state does not
 assert not s.ingest_mapping(message('UPDATE',observed_at=(NOW-timedelta(seconds=1)).isoformat()))
 assert not s.ingest_mapping(message('CLEAR',event_id='unknown'))
 for bad in (message(),message('UPDATE',latitude=100),message('UPDATE',severity={})): 
  with pytest.raises(SquallEventError):s.ingest_mapping(bad)
 assert len(out)==1

def test_stale_expired_distinct_notifications_and_selection(integration):
 clock,s,b,out,_=integration;s.ingest_mapping(message());b.selectEvent('SQ-001')
 clock[0]+=timedelta(seconds=121);s.evaluate_time()
 assert out[-1]['events'][0]['status']=='STALE' and out[-1]['selected_event_id']=='SQ-001'
 n=len(out);s.evaluate_time();assert len(out)==n
 clock[0]+=timedelta(seconds=480);s.evaluate_time()
 assert out[-1]['active_count']==0 and out[-1]['selected_event_id'] is None
 assert out[-1]['geojson']['selection']['features']==[]
 assert s.lifecycle_log[-1]=='EXPIRED SQ-001'

def test_selection_clear_unknown_and_target_clear(integration):
 _,s,b,out,_=integration;s.ingest_mapping(message());s.ingest_mapping(message(event_id='SQ-002'))
 b.selectEvent('missing');assert b.getEventState()['selected_event_id'] is None
 b.selectEvent('SQ-001');assert all(f['properties']['event_id']=='SQ-001' for f in out[-1]['geojson']['selection']['features'])
 b.selectEvent('SQ-002');assert out[-1]['selected_event_id']=='SQ-002'
 b.clearEventSelection();assert out[-1]['geojson']['selection']['features']==[]
 b.selectEvent('SQ-001');s.ingest_mapping(message('CLEAR'));assert out[-1]['selected_event_id'] is None
 assert out[-1]['active_count']==1

def site(multi=False,offset=0,hole=False):
 state=SpatialState.empty();ring=[[offset+.08,-.02],[offset+.12,-.02],[offset+.12,.02],[offset+.08,.02],[offset+.08,-.02]]
 rings=[ring]
 if hole:rings.append([[offset+.09,-.01],[offset+.11,-.01],[offset+.11,.01],[offset+.09,.01],[offset+.09,-.01]])
 geometry={'type':'MultiPolygon' if multi else 'Polygon','coordinates':[rings] if multi else rings}
 state.collections[SpatialCategory.SITE_BOUNDARY]['features'].append({'type':'Feature','properties':{},'geometry':geometry})
 return state

@pytest.mark.parametrize('multi',[False,True])
@pytest.mark.parametrize('changes,expected',[
 ({},'NONE'),({'surveillance_radius_nm':6},'SURVEILLANCE'),
 ({'impact_radius_nm':6,'surveillance_radius_nm':8},'IMPACT'),
 ({'predicted_path':[{'latitude':0,'longitude':.2,'eta_seconds':300}]},'IMPACT'),
 ({'longitude':.1},'IMPACT')])
def test_impact_scenarios(multi,changes,expected):
 s=SquallEventService(lambda:NOW);s.ingest_mapping(message(**changes))
 assert evaluate(s.snapshot()['events'][0],site(multi))==expected

def test_hole_and_absent_site():
 s=SquallEventService(lambda:NOW);s.ingest_mapping(message(longitude=.1));e=s.snapshot()['events'][0]
 assert evaluate(e,site(hole=True))=='NONE'
 assert evaluate(e,SpatialState.empty())=='NONE'

def test_spatial_impact_rebuild_keeps_event_identity(integration):
 _,s,b,out,_=integration;s.ingest_mapping(message(longitude=.1));e=s._events['SQ-001']
 context=SimpleNamespace(state=SpatialState.empty());b._event_render_state.spatial=context
 b.publishEventState();context.state=site();b.publishEventState()
 assert out[-1]['events'][0]['impact_state']=='IMPACT' and s._events['SQ-001'] is e
 n=len(out);b.publishEventState();assert len(out)==n

def test_payload_geometry_and_json(integration):
 _,s,b,out,_=integration
 s.ingest_mapping(message(impact_radius_nm=2,surveillance_radius_nm=5,predicted_path=[{'latitude':.1,'longitude':.1,'eta_seconds':300}]))
 p=b.getEventState();json.dumps(p,allow_nan=False)
 assert set(p)=={'events','active_count','selected_event_id','updated_at','geojson'}
 for name,c in p['geojson'].items():
  assert c['type']=='FeatureCollection'
  for f in c['features']:assert f['geometry'] and f['properties']['event_id']=='SQ-001'
 assert p['geojson']['prediction_points']['features'][0]['properties']['eta_label']=='5 min'
 ring=p['geojson']['impact_zones']['features'][0]['geometry']['coordinates'][0];assert ring[0]==ring[-1]

def test_no_predicted_path_no_fabricated_trajectory(integration):
 _,s,b,_,_=integration;s.ingest_mapping(message());assert b.getEventState()['geojson']['trajectories']['features']==[]

def test_cross_selection_uses_real_nav_methods(integration):
 _,s,b,out,_=integration;s.ingest_mapping(message())
 selected=[];spatial=SimpleNamespace(clear_selection=lambda:selected.clear(),select_feature=lambda c,i:selected.append((c,i)))
 b.eventSelected.connect(lambda _:spatial.clear_selection())
 page=SimpleNamespace(bridge=b,spatial=spatial)
 selected.append(('pipeline','P'));b.selectEvent('SQ-001');assert selected==[]
 NavPage._select_spatial_feature(page,'pipeline','P');assert b.getEventState()['selected_event_id'] is None
 assert selected==[('pipeline','P')]

def test_card_priority_and_undefined_optional_values(integration):
 _,s,b,out,_=integration;s.ingest_mapping(message());s.ingest_mapping(message(event_id='SQ-002',longitude=.1))
 b._event_render_state.spatial=site();p=b.getEventState()
 assert [e['event_id'] for e in p['events']]==['SQ-002','SQ-001']
 assert p['events'][0]['speed_knots'] is None and p['events'][0]['eta_label']=='—'

def test_geodesic_circle_and_direction():
 lat,lon=destination_point(0,0,0,60);assert .99<lat<1.01 and abs(lon)<1e-6
 ring=circle(0,0,60);assert len(ring)==65 and ring[0]==ring[-1]

def test_map_event_state_cache_visibility_and_click_priority():
 import shutil,subprocess
 node=shutil.which('node')
 if not node:pytest.skip('Node is required for the NAV JavaScript API-double check')
 subprocess.run([node,'tests/nav_event_runtime.cjs'],check=True,capture_output=True,text=True)

@pytest.mark.parametrize('field,value',[('latitude',float('nan')),('longitude',float('inf')),('direction_deg',None),('impact_radius_nm',0),('speed_knots',-1),('severity',{}),('observed_at','2026-01-01'),('predicted_path',[{'latitude':0,'longitude':0,'eta_seconds':-1}])])
def test_validation_rejects_atomically(field,value,integration):
 _,s,b,out,_=integration
 with pytest.raises(SquallEventError):s.ingest_mapping(message(**{field:value}))
 assert not out and s.active_count==0
