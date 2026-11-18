"""Real-provider contracts tested with deterministic offline responses."""
import asyncio
from datetime import datetime,timezone,timedelta
from dataclasses import replace
import json
from types import SimpleNamespace
import pytest
from app.nav.maritime.area_controller import OperatingArea
from app.nav.maritime.adapters.base import SourceConfig,StaticCache
from app.nav.maritime.adapters.provider_common import bbox_parts,ProviderUnavailable,ProviderResult,canonical_feature
from app.nav.maritime.adapters.aisstream import AISStreamNormalizer,AISStreamAdapter,subscription,MESSAGE_TYPES
from app.nav.maritime.adapters.overpass import OverpassAdapter,query,geometry
from app.nav.maritime.adapters.reference import GebcoAdapter,OpenWatersAdapter
from app.nav.maritime.adapters.regional import BoemAdapter,EmodnetAdapter,US_REGIONS,EUROPE
from app.nav.maritime.adapters.gfw import GfwAdapter
from app.nav.maritime.adapters.navarea import Navarea8Adapter
from app.nav.maritime.adapters.copernicus import CopernicusAdapter,canonical_value
from app.nav.maritime.models import MaritimeDataError
from app.nav.maritime.service import MaritimeObjectService
from app.nav.maritime.config import MaritimeConfig
from app.nav.map_bridge import MapBridge

NOW=datetime(2026,11,1,12,tzinfo=timezone.utc)
AREA=OperatingArea(22,91,50)


def message(kind='PositionReport',mmsi=123456789,**changes):
    body={**(dict(Valid=True,UserID=mmsi,Latitude=22,Longitude=91,Sog=8,Cog=45,TrueHeading=40)), **(changes)}
    return dict(MessageType=kind,MetaData=dict(MMSI=mmsi,time_utc=NOW.isoformat()),Message={kind:body})


def test_subscription_bbox_and_antimeridian():
    p=subscription(AREA,'test-key')
    assert p['APIKey']=='test-key' and p['FilterMessageTypes']==MESSAGE_TYPES
    (south,west),(north,east)=p['BoundingBoxes'][0]
    assert south<22<north and west<91<east and north-south<2
    boxes=bbox_parts(OperatingArea(0,179.9))
    assert len(boxes)==2 and all(-180<=w<e<=180 for w,s,e,n in boxes)


@pytest.mark.parametrize('kind',['PositionReport','StandardClassBPositionReport','ExtendedClassBPositionReport'])
def test_ais_dynamic_class_a_and_b(kind):
    obj=AISStreamNormalizer(lambda:NOW).normalize(message(kind))
    assert obj.object_id=='ais:123456789' and obj.observed_at==NOW
    assert obj.properties['sog']==8 and obj.properties['heading']==40
    assert obj.properties['source_tier']=='LIVE_AIS'


def test_ais_static_before_and_after_position_merge():
    norm=AISStreamNormalizer(lambda:NOW)
    static=message('ShipStaticData',Name='REAL SCHEMA FIXTURE',ImoNumber=9876543,CallSign='TEST',Type=70,Destination='PORT',MaximumStaticDraught=7.2,Eta=dict(Month=11,Day=2,Hour=5,Minute=30))
    assert norm.normalize(static) is None
    obj=norm.normalize(message())
    assert obj.properties['name']=='REAL SCHEMA FIXTURE' and obj.properties['imo']=='9876543'
    changed=norm.normalize(message('StaticDataReport',ReportA=dict(Valid=True,Name='UPDATED'),ReportB=dict(Valid=True,ShipType=80,CallSign='ABC')),obj)
    assert changed.properties['name']=='UPDATED' and changed.properties['ship_type']==80
    assert changed.geometry==obj.geometry and changed.observed_at==obj.observed_at and changed.received_at==obj.received_at


def test_ais_aton_and_unavailable_fields():
    norm=AISStreamNormalizer(lambda:NOW)
    obj=norm.normalize(message(TrueHeading=511,Cog=360,Sog=102.3))
    assert obj.properties['heading'] is None
    aton=norm.normalize(message('AidsToNavigationReport',mmsi=991234567,Name='BUOY',VirtualAtoN=True))
    assert aton.category=='aton' and aton.properties['virtual_aton'] is True and aton.expires_at>NOW
    service=MaritimeObjectService(lambda:NOW+timedelta(seconds=601))
    service.ingest([aton]);assert not service.snapshot()


@pytest.mark.parametrize('bad',[None,[],{},message(Valid=False),message(Latitude=None),message(Longitude=181),message('StaticDataReport',ReportA=5)])
def test_ais_malformed_rejected(bad):
    with pytest.raises(MaritimeDataError):AISStreamNormalizer(lambda:NOW).normalize(bad)


def test_ais_mmsi_identity_and_own_suppression():
    s=MaritimeObjectService(lambda:NOW,own_mmsi='123456789');n=AISStreamNormalizer(lambda:NOW)
    s.ingest([n.normalize(message()),n.normalize(message(mmsi=987654321))])
    s.ingest([n.normalize(message(mmsi=987654321,Longitude=91.1))])
    assert len(s.snapshot())==1 and s.snapshot()[0].geometry['coordinates'][0]==91.1


def test_ais_subscription_updates_without_reconnect(monkeypatch):
    adapter=AISStreamAdapter('test-key');adapter.update_area(AREA);sent=[];connections=[]
    class Socket:
        async def send(self,value):
            sent.append(json.loads(value))
            if len(sent)==1:adapter.update_area(OperatingArea(23,91))
        async def recv(self):
            if len(sent)>=2:adapter._stop.set()
            return json.dumps({'MessageType':'SubscriptionConfirmation','Message':{'CompressionEnabled':True}})
    class Connect:
        async def __aenter__(self):return Socket()
        async def __aexit__(self,*args):pass
    adapter._connector=lambda *a,**kw:(connections.append(kw) or Connect())
    from itertools import count
    ticks=count(0,2);monkeypatch.setattr('app.nav.maritime.adapters.aisstream.time',SimpleNamespace(monotonic=lambda:next(ticks)))
    asyncio.run(adapter._session())
    assert len(connections)==1 and len(sent)==2 and sent[0]['BoundingBoxes']!=sent[1]['BoundingBoxes']
    assert adapter.confirmed and connections[0]['compression']=='deflate'


def test_ais_reconnect_backoff_state(monkeypatch):
    adapter=AISStreamAdapter('test-key');adapter.update_area(AREA);delays=[]
    def fail(*a,**kw):raise OSError('transport unavailable')
    async def sleep(delay):delays.append(delay);raise asyncio.CancelledError()
    adapter._connector=fail;monkeypatch.setattr('app.nav.maritime.adapters.aisstream.asyncio.sleep',sleep)
    with pytest.raises(asyncio.CancelledError):asyncio.run(adapter._session())
    assert adapter.state=='DEGRADED' and 2<=delays[0]<=3


@pytest.mark.parametrize('tags,category',[
    ({'seamark:type':'platform'},'offshore'),({'man_made':'offshore_platform'},'offshore'),
    ({'seamark:type':'buoy_cardinal'},'aton'),({'seamark:type':'beacon_lateral'},'aton'),
    ({'seamark:type':'anchorage'},'anchorages'),({'seamark:type':'separation_lane'},'routes'),
    ({'seamark:type':'pipeline_submarine'},'subsea'),({'seamark:type':'cable_submarine'},'subsea'),
    ({'seamark:type':'wreck'},'hazards'),({'natural':'reef'},'hazards'),({'harbour':'yes'},'ports'),
    ({'seamark:type':'light'},'aton'),({'seamark:type':'lighthouse'},'aton'),
    ({'seamark:type':'offshore_platform'},'offshore'),({'man_made':'cable','location':'underwater'},'subsea'),
    ({'power':'cable','location':'underwater'},'subsea')])
def test_overpass_real_tag_mapping(tags,category):
    p={'elements':[dict(type='node',id=123,lat=22,lon=91,tags=tags,timestamp=NOW.isoformat(),version=2)]}
    obj=OverpassAdapter(SourceConfig('overpass','https://example.invalid')).normalize(p,AREA)[0]
    assert str(obj.category)==category and obj.source_id=='node/123' and obj.properties['source_tier']=='COMMUNITY'


def test_overpass_query_way_relation_and_hole_cache(tmp_path):
    text=query(AREA);assert 'out meta geom' in text and 'nwr' in text and '22' in text
    ring=[dict(lon=91,lat=22),dict(lon=91.1,lat=22),dict(lon=91.1,lat=22.1),dict(lon=91,lat=22)]
    way=dict(type='way',id=1,geometry=ring,tags={'seamark:type':'anchorage'})
    assert geometry(way)['type']=='Polygon'
    relation=dict(type='relation',id=2,tags={'type':'multipolygon','seamark:type':'anchorage'},members=[dict(type='way',role='outer',geometry=ring[:3]),dict(type='way',role='outer',geometry=ring[2:])])
    assert geometry(relation)['type']=='MultiPolygon'
    config=SourceConfig('overpass','https://example.invalid',interval_seconds=86400)
    objects=OverpassAdapter(config).normalize({'elements':[way,relation]},AREA)
    cache=StaticCache(tmp_path);cache.save(config,AREA,objects)
    assert cache.load_fresh(config,AREA)==objects
    assert cache.load(config,OperatingArea(0,0)) is None
    with pytest.raises(MaritimeDataError):OverpassAdapter(config).normalize({'elements':[],'remark':'timeout'},AREA)


def test_gebco_current_capabilities_and_reference(monkeypatch):
    xml=b'<WMS_Capabilities><Layer><CRS>EPSG:3857</CRS><Layer><Name>GEBCO_2020</Name></Layer><Layer><Name>GEBCO_LATEST</Name></Layer></Layer></WMS_Capabilities>'
    monkeypatch.setattr('app.nav.maritime.adapters.reference.request_bytes',lambda *a,**k:xml)
    a=GebcoAdapter(SourceConfig('gebco','https://wms.gebco.net/mapserv?'))
    p=a.fetch(AREA);ref=p.reference_layers['gebco']
    assert ref['layer']=='GEBCO_LATEST' and '{bbox-epsg-3857}' in ref['tiles'][0]
    assert 'SRS=EPSG%3A3857' in ref['tiles'][0] and p.objects==[]
    with pytest.raises(MaritimeDataError):a.layer_from_capabilities(b'<WMS><Layer><Name>GEBCO_2020</Name></Layer></WMS>')


@pytest.mark.parametrize('enabled,ack',[(False,False),(True,False),(False,True)])
def test_gfw_no_request_without_both_gates(enabled,ack,monkeypatch):
    monkeypatch.setattr('app.nav.maritime.adapters.gfw.request_bytes',lambda *a,**k:pytest.fail('licence gate bypassed'))
    with pytest.raises(ProviderUnavailable,match='DISABLED_LICENSE'):
        GfwAdapter(SourceConfig('gfw','https://example.invalid','test-token'),enabled,ack).fetch(AREA)


def test_gfw_normalizes_only_actual_fields():
    a=GfwAdapter(SourceConfig('gfw','https://example.invalid','test-token'),True,True)
    obj=a.normalize([dict(structure_id=1,lat=22,lon=91,label='oil',label_confidence='high',structure_end_date=NOW.timestamp()*1000)],AREA)[0]
    assert obj.properties['classification']=='oil' and obj.properties['confidence']=='high'
    assert obj.properties['source_tier']=='SATELLITE_DERIVED' and obj.observed_at==NOW


def test_gfw_decodes_binary_tiles_using_provider_wgs84_attributes(monkeypatch):
    mapbox_vector_tile=pytest.importorskip('mapbox_vector_tile')
    content=mapbox_vector_tile.encode({'name':'infrastructure','features':[
        {'geometry':{'type':'Point','coordinates':[2048,2048]},
         'properties':dict(structure_id=1,lat=22.0,lon=91.0,label='oil',
                           structure_end_date=int(NOW.timestamp()*1000))}]})
    calls=[]
    def response(endpoint,**kwargs):
        calls.append((endpoint,kwargs));return content
    monkeypatch.setattr('app.nav.maritime.adapters.gfw.request_bytes',response)
    objects=GfwAdapter(SourceConfig('gfw','https://example.invalid','test-token'),True,True).fetch(AREA)
    assert len(objects)==1 and objects[0].geometry['coordinates']==[91,22]
    assert objects[0].observed_at==NOW and objects[0].properties['classification']=='oil'
    assert all('/context-layers/6/' in url and options['headers']['Authorization']=='Bearer test-token'
               and options['headers']['Accept']=='application/vnd.mapbox-vector-tile' for url,options in calls)


@pytest.mark.parametrize('klass',[BoemAdapter,EmodnetAdapter])
def test_regional_no_irrelevant_requests(klass,monkeypatch):
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',lambda *a,**kw:pytest.fail('out of coverage request'))
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_bytes',lambda *a,**kw:pytest.fail('out of coverage capabilities'))
    with pytest.raises(ProviderUnavailable,match='OUT_OF_COVERAGE'):klass(SourceConfig('regional','https://example.invalid')).fetch(AREA)


def test_boem_capabilities_and_feature_normalization(monkeypatch):
    calls=[]
    def request(url,params):
        calls.append((url,params))
        if url.endswith('FeatureServer'):return {'layers':[{'id':0,'name':'OCS Drilling Platforms'}]}
        return {'type':'FeatureCollection','features':[dict(type='Feature',id=15,geometry={'type':'Point','coordinates':[-90,28]},properties={'NAME':'PLATFORM'})]}
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',request)
    result=BoemAdapter(SourceConfig('boem','https://example.invalid')).fetch(OperatingArea(28,-90))
    assert result[0].category=='offshore' and result[0].properties['source_tier']=='OFFICIAL_GOVERNMENT'
    assert 'geometry' in calls[-1][1] and calls[-1][1]['outSR']==4326


def test_emodnet_discovery_and_geojson(monkeypatch):
    xml=b'<WFS><FeatureType><Name>emodnet:platforms</Name><Title>Offshore Installations</Title></FeatureType></WFS>'
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_bytes',lambda *a,**kw:xml)
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',lambda *a,**kw:{'type':'FeatureCollection','features':[dict(type='Feature',id='platforms.1',geometry={'type':'Point','coordinates':[2,55]},properties={'name':'PLATFORM'})]})
    result=EmodnetAdapter(SourceConfig('emodnet','https://example.invalid')).fetch(OperatingArea(55,2))
    assert result[0].category=='offshore' and result[0].properties['source_tier']=='OFFICIAL_SERVICE'


def test_navarea_no_scraping():
    with pytest.raises(ProviderUnavailable,match='NO_STABLE_MACHINE_API'):Navarea8Adapter(SourceConfig('navarea8','https://example.invalid')).fetch(AREA)


def test_copernicus_not_configured_and_bbox_subset(monkeypatch):
    import sys
    adapter=CopernicusAdapter(SourceConfig('copernicus_wave','https://example.invalid'),'wave','','','')
    with pytest.raises(ProviderUnavailable,match='NOT_CONFIGURED'):adapter.fetch(AREA)
    calls=[];closed=[]
    monkeypatch.setitem(sys.modules,'copernicusmarine',SimpleNamespace(open_dataset=lambda **kw:(calls.append(kw) or SimpleNamespace(close=lambda:closed.append(True)))))
    adapter=CopernicusAdapter(SourceConfig('copernicus_wave','https://example.invalid'),'wave','configured-dataset','test-user','test-password')
    monkeypatch.setattr(adapter,'normalize',lambda ds,area,now:[])
    adapter.fetch(AREA)
    p=calls[0]
    assert p['dataset_id']=='configured-dataset' and p['minimum_longitude']<91<p['maximum_longitude']
    assert (p['end_datetime']-p['start_datetime']).total_seconds()==7200 and p['maximum_depth']==1 and closed
    assert canonical_value('wave_height_m',150,'cm')==(1.5,'m')
    with pytest.raises(MaritimeDataError):canonical_value('wave_height_m',1,'unknown')


def test_copernicus_normalized_output_uses_real_cells_and_units():
    class Variable:
        def __init__(self,value,standard=None,unit=None):
            self.values=value;self.ndim=1;self.attrs={'standard_name':standard,'units':unit}
        def isel(self,*args,**kw):return self
    class Dataset:
        def __init__(self):
            self.coords={'latitude':Variable([22]),'longitude':Variable([91]),'time':Variable('2026-11-01T12:00:00.000000000')}
            self.data_vars={'wave':Variable(150,'sea_surface_wave_significant_height','cm')}
            self.sizes={'latitude':1,'longitude':1,'time':1};self.dims=set(self.sizes)
        def __getitem__(self,key):return self if isinstance(key,list) else self.coords[key] if key in self.coords else self.data_vars[key]
        def sel(self,**kw):self.dims.discard('time');return self
        def isel(self,*a,**kw):return self
        def load(self):return self
    a=CopernicusAdapter(SourceConfig('copernicus_wave','https://example.invalid'),'wave','configured-dataset','test-user','test-password')
    obj=a.normalize(Dataset(),AREA,NOW)[0]
    assert obj.geometry['coordinates']==[91,22] and obj.observed_at==NOW
    assert obj.properties['wave_height_m']==1.5 and obj.properties['units']['wave_height_m']=='m'
    assert obj.properties['source_tier']=='MODEL'


def test_current_vectors_use_shared_metocean_source_and_finite_geometry():
    from app.nav.maritime.render_state import build_render_state
    service=MaritimeObjectService(lambda:NOW)
    obj=canonical_feature('copernicus_current','grid-1','metocean','current',{'type':'Point','coordinates':[91,22]},
                          {'current_knots':2,'heading':90},'MODEL',observed_at=NOW.isoformat())
    service.ingest([obj]);payload=build_render_state(service)
    features=payload['geojson']['metocean']['features']
    assert len(features)==2 and features[1]['geometry']['type']=='MultiLineString'
    assert features[1]['properties']['object_id']==obj.object_id and len(service.snapshot())==1
    json.dumps(payload,allow_nan=False)


def test_emodnet_keyless_views_do_not_request_natural_sort(monkeypatch):
    xml=b'<WFS><FeatureType><Name>emodnet:platforms</Name><Title>Offshore Installations</Title></FeatureType><FeatureType><Name>emodnet:pipelines</Name><Title>Pipelines</Title></FeatureType></WFS>'
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_bytes',lambda *a,**kw:xml)
    def response(url,params):
        assert ',' not in params['typeNames'] and 'startIndex' not in params
        return {'type':'FeatureCollection','features':[]}
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',response)
    assert EmodnetAdapter(SourceConfig('emodnet','https://example.invalid')).fetch(OperatingArea(55,2))==[]


def test_emodnet_dense_keyless_subdivision_avoids_unsafe_offset(monkeypatch):
    adapter=EmodnetAdapter(SourceConfig('emodnet','https://example.invalid'));adapter.PAGE_SIZE=2
    def feature(fid):return {'type':'Feature','id':fid,'properties':{},'geometry':{'type':'Point','coordinates':[2,55]}}
    calls=[]
    def response(url,params):
        assert 'startIndex' not in params
        calls.append(params)
        rows=[feature('one'),feature('two')] if len(calls)==1 else [feature('one')]
        return {'type':'FeatureCollection','features':rows}
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',response)
    rows=adapter._query_features('emodnet:platforms',(1,54,3,56))
    assert len(calls)==5 and len(rows)==1


def test_emodnet_dense_explicit_id_uses_stable_sort(monkeypatch):
    adapter=EmodnetAdapter(SourceConfig('emodnet','https://example.invalid'));adapter.PAGE_SIZE=2
    def feature(i):return {'type':'Feature','id':str(i),'properties':{'ID':i},'geometry':{'type':'Point','coordinates':[2,55]}}
    calls=[]
    def response(url,params):
        calls.append(params)
        if 'sortBy' not in params or params.get('startIndex')==0:rows=[feature(1),feature(2)]
        else:rows=[feature(3)]
        return {'type':'FeatureCollection','features':rows}
    monkeypatch.setattr('app.nav.maritime.adapters.regional.request_json',response)
    assert len(adapter._query_features('emodnet:platforms',(1,54,3,56)))==3
    assert calls[1]['sortBy']=='ID A' and calls[-1]['startIndex']==2


def test_source_tier_priority_is_conservative():
    s=MaritimeObjectService(lambda:NOW)
    p=dict(type='Point',coordinates=[91,22])
    official=canonical_feature('boem','1','offshore','platform',p,{'canonical_id':'shared'},'OFFICIAL_GOVERNMENT')
    community=canonical_feature('overpass','2','offshore','platform',p,{'canonical_id':'shared'},'COMMUNITY')
    s.ingest([official]);s.ingest([community]);assert len(s.snapshot())==1 and s.snapshot()[0].source=='boem'
    unrelated=canonical_feature('overpass','3','offshore','platform',p,{},'COMMUNITY')
    s.ingest([unrelated]);assert len(s.snapshot())==2


def test_real_provider_registration_gates_and_reference_no_deletion(qapp):
    from app.nav.maritime.runtime import MaritimeRuntime
    config=MaritimeConfig({'AISSTREAM_ENABLED':'true','GDS_GFW_ENABLED':'true','GDS_GEBCO_ENABLED':'true'})
    runtime=MaritimeRuntime(config=config);runtime.timer.stop()
    try:
        assert runtime.service.sources['aisstream'].state=='NOT_CONFIGURED'
        assert runtime.service.sources['gfw'].state=='DISABLED_LICENSE' and 'gfw' not in runtime.adapters
        assert all(runtime.service.sources['copernicus_'+p].state=='NOT_CONFIGURED' for p in ('wave','current','sst','sealevel'))
        runtime.own_position(22,91)
        obj=canonical_feature('overpass','1','aton','buoy',{'type':'Point','coordinates':[91,22]})
        runtime.service.ingest([obj])
        runtime._receive('gebco',runtime._generation,ProviderResult(reference_layers={'gebco':{'kind':'raster'}}),None,False)
        b=MapBridge(maritime_service=runtime.service);b.setMaritimeVisibility('bathymetry',False)
        assert b.getMaritimeState()['reference_layers']['gebco']['kind']=='raster' and len(runtime.service.snapshot())==1
    finally:runtime.close()


def test_unreadable_static_cache_is_a_miss(monkeypatch, tmp_path):
    cache=StaticCache(tmp_path)
    class UnreadablePath:
        def is_file(self):raise PermissionError('cache unavailable')
    monkeypatch.setattr(cache,'_path',lambda *args:UnreadablePath())
    assert cache.load(SourceConfig('overpass','https://example.invalid'),AREA) is None


def test_provider_failure_with_unreadable_cache_releases_worker(qtbot, monkeypatch):
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime=MaritimeRuntime(config=MaritimeConfig({'GDS_OVERPASS_ENDPOINT':'https://example.invalid','GDS_GEBCO_ENABLED':'false','GDS_OVERPASS_FALLBACK_ENDPOINTS':''}))
    runtime.timer.stop()
    def unavailable(*args):raise PermissionError('must not reach source health')
    monkeypatch.setattr(runtime.cache,'load_fresh',lambda *args:None)
    monkeypatch.setattr(runtime.cache,'load',unavailable)
    monkeypatch.setattr(runtime.adapters['overpass'],'fetch',unavailable)
    try:
        runtime.own_position(22,91);runtime.tick()
        qtbot.waitUntil(lambda:'overpass' not in runtime._busy,timeout=5000)
        health=runtime.service.sources['overpass']
        assert health.state=='ERROR' and health.error=='PermissionError'
        assert runtime._next['overpass']>0 and not runtime.service.snapshot()
    finally:runtime.close()


def test_no_telemetry_viewport_fetches_real_adapter_and_publishes_bridge(qtbot,monkeypatch):
    from app.nav.maritime.runtime import MaritimeRuntime
    config=MaritimeConfig({'GDS_OVERPASS_ENDPOINT':'https://example.invalid','GDS_GEBCO_ENABLED':'false','GDS_OVERPASS_FALLBACK_ENDPOINTS':''})
    runtime=MaritimeRuntime(config=config);runtime.timer.stop()
    bridge=MapBridge(maritime_service=runtime.service)
    bridge.maritimeViewportChanged.connect(runtime.viewport)
    runtime.changed.connect(bridge.publishMaritimeState)
    payloads=[];bridge.maritimeStateChanged.connect(payloads.append)
    calls=[]
    def response(endpoint,**kwargs):
        calls.append(kwargs)
        return {'elements':[dict(type='node',id=123,lat=4.1,lon=100.6,tags={'seamark:type':'light_minor'})]}
    monkeypatch.setattr('app.nav.maritime.adapters.overpass.request_json',response)
    monkeypatch.setattr(runtime.cache,'load_fresh',lambda *args:None)
    monkeypatch.setattr(runtime.cache,'save',lambda *args:None)
    try:
        bridge.reportMaritimeViewport(100.12,3.8,100.89,4.26);runtime.tick()
        qtbot.waitUntil(lambda:bool(runtime.service.snapshot()),timeout=5000)
        runtime.tick()
        assert runtime.service.own_position is None and runtime.service.area.origin=='viewport'
        assert len(calls)==1 and b'nwr' in calls[0]['data']
        assert payloads[-1]['counts']['aton']==1 and len(bridge.getMaritimeState()['objects'])==1
        assert payloads[-1]['geojson']['aton']['features'][0]['geometry']['coordinates']==[100.6,4.1]
    finally:runtime.close()


def test_viewport_query_uses_actual_bounds_and_can_shrink_after_broad_failure():
    from app.nav.maritime.area_controller import MaritimeAreaController
    controller=MaritimeAreaController(debounce_seconds=0)
    broad=controller.viewport(98,2,103,6)
    bounds=(100.12,3.8,100.89,4.26)
    area=controller.viewport(*bounds)
    assert broad is not None and area is not None and area.radius_nm==50
    assert bbox_parts(area)==[bounds]
    assert '(3.800000,100.120000,4.260000,100.890000)' in query(area)
    assert '99.28' not in query(area)  # No inflated own-vessel-radius bbox.
    assert controller.viewport(*bounds) is None
    dateline=controller.viewport(179,-1,-179,1)
    assert bbox_parts(dateline)==[(179,-1,180,1),(-180,-1,-179,1)]


def test_normalized_bridge_payload_reaches_js_sources():
    import shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node required for the Python-to-JS bridge regression')
    area=OperatingArea(4.03,100.5)
    adapter=OverpassAdapter(SourceConfig('overpass','https://example.invalid'))
    objects=adapter.normalize({'elements':[
        dict(type='node',id=1,lat=4.1,lon=100.6,tags={'seamark:type':'light_minor'}),
        dict(type='way',id=2,tags={'seamark:type':'pipeline_submarine'},geometry=[dict(lat=4,lon=100.5),dict(lat=4.1,lon=100.6)])]},area)
    service=MaritimeObjectService();service.ingest(objects)
    payload=MapBridge(maritime_service=service).getMaritimeState()
    result=subprocess.run([node,'tests/nav_event_runtime.cjs','--bridge-payload'],input=json.dumps(payload),
                          capture_output=True,text=True,check=True)
    assert 'Python bridge to JS maritime setData: PASS count=2' in result.stdout


@pytest.mark.parametrize('env,state,active',[
    ({},'NOT_CONFIGURED',False),({'AISSTREAM_API_KEY':'test-key'},'CONNECTING',True),
    ({'AISSTREAM_API_KEY':'test-key','AISSTREAM_ENABLED':'false'},'DISABLED',False)])
def test_public_defaults_and_ais_key_activation(qapp,env,state,active):
    from app.nav.maritime.runtime import MaritimeRuntime
    config=MaritimeConfig({**({'GDS_OVERPASS_FALLBACK_ENDPOINTS':''}), **(env)})
    runtime=MaritimeRuntime(config=config);runtime.timer.stop()
    try:
        assert 'overpass' in runtime.adapters and 'gebco' in runtime.adapters
        assert runtime.service.sources['aisstream'].state==state
        assert (runtime.aisstream is not None)==active
        assert runtime.service.sources['gfw'].state=='DISABLED_LICENSE'
        assert runtime.service.sources['openwaters'].state=='NOT_CONFIGURED'
    finally:runtime.close()


def test_overpass_fallback_post_sticky_success_and_cooldown(monkeypatch):
    from urllib.parse import parse_qs
    from app.nav.maritime.adapters.provider_common import ProviderRequestError
    calls=[]
    def response(endpoint,**kwargs):
        calls.append(endpoint)
        text=parse_qs(kwargs['data'].decode())['data'][0]
        assert text.startswith('[out:json][timeout:25];') and '[maxsize:16777216]' not in text
        assert '["location"="underwater"]' in text and 'nwr' in text and 'out meta geom' in text
        assert kwargs['headers']['Content-Type']=='application/x-www-form-urlencoded'
        if endpoint.endswith('/primary'):raise ProviderRequestError('HTTP 502')
        return {'elements':[]}
    monkeypatch.setattr('app.nav.maritime.adapters.overpass.request_json',response)
    adapter=OverpassAdapter(SourceConfig('overpass','https://example.invalid/primary'),['https://example.invalid/fallback'],clock=lambda:0)
    assert adapter.fetch(AREA)==[] and adapter.fetch(AREA)==[]
    assert calls==['https://example.invalid/primary','https://example.invalid/fallback','https://example.invalid/fallback']


def test_overpass_429_does_not_hop_hosts_and_honors_retry_after(monkeypatch):
    from app.nav.maritime.adapters.provider_common import ProviderRequestError
    calls=[]
    def response(endpoint,**kwargs):calls.append(endpoint);raise ProviderRequestError('HTTP 429',600)
    monkeypatch.setattr('app.nav.maritime.adapters.overpass.request_json',response)
    adapter=OverpassAdapter(SourceConfig('overpass','https://example.invalid/primary'),['https://example.invalid/fallback'],clock=lambda:0)
    with pytest.raises(ProviderRequestError) as caught:adapter.fetch(AREA)
    assert caught.value.retry_after==600 and calls==['https://example.invalid/primary']


def test_retry_after_survives_viewport_change(qtbot,monkeypatch):
    import time
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime=MaritimeRuntime(config=MaritimeConfig({'GDS_OVERPASS_ENDPOINT':'https://example.invalid','GDS_GEBCO_ENABLED':'false'}));runtime.timer.stop()
    try:
        runtime.own_position(22,91)
        runtime._receive('overpass',runtime._generation,None,('HTTP 429',600),False)
        deadline=runtime._retry_until['overpass'];runtime.controller.debounce_seconds=0
        monkeypatch.setattr(runtime.cache,'load_fresh',lambda *args:None)
        monkeypatch.setattr(runtime.cache,'load',lambda *args:None)
        monkeypatch.setattr(runtime.adapters['overpass'],'fetch',lambda *args:pytest.fail('rate limit bypassed'))
        runtime.viewport(100,3,101,4);runtime.tick()
        qtbot.waitUntil(lambda:'overpass' not in runtime._busy,timeout=5000)
        assert deadline>time.monotonic()+590 and 'overpass' not in runtime._busy
        assert runtime.service.sources['overpass'].error=='PROVIDER BACKOFF'
    finally:runtime.close()


@pytest.mark.parametrize('error,expected',[
    ('timeout','TIMEOUT'),('dns','DNS ERROR'),('tls','TLS ERROR'),('http','HTTP 429')])
def test_transport_error_classification_and_redaction(monkeypatch,error,expected):
    import socket,ssl
    from urllib.error import URLError,HTTPError
    from io import BytesIO
    from app.nav.maritime.adapters import provider_common as common
    failures={'timeout':TimeoutError('secret-token'),'dns':URLError(socket.gaierror('secret-token')),
              'tls':URLError(ssl.SSLError('secret-token')),
              'http':HTTPError('https://example.invalid?token=secret-token',429,'secret-token',{'Retry-After':'321'},BytesIO(b'private body'))}
    def fail(*args,**kwargs):raise failures[error]
    monkeypatch.setattr(common,'urlopen',fail)
    with pytest.raises(common.ProviderRequestError) as caught:common.request_json('https://example.invalid?token=secret-token')
    assert str(caught.value)==expected and 'secret-token' not in str(caught.value)
    if error=='http':assert caught.value.retry_after==321


def test_overpass_containing_cache_reuse_is_ttl_and_endpoint_scoped(tmp_path):
    from app.nav.maritime.area_controller import MaritimeAreaController
    controller=MaritimeAreaController(debounce_seconds=0)
    area=controller.viewport(100,3,101,4)
    smaller=MaritimeAreaController().viewport(100.2,3.2,100.8,3.8)
    config=SourceConfig('overpass','https://example.invalid',interval_seconds=86400)
    obj=canonical_feature('overpass','1','aton','light',{'type':'Point','coordinates':[100.5,3.5]})
    cache=StaticCache(tmp_path);cache.save(config,area,[obj])
    assert cache.load_fresh(config,smaller)==[obj]
    assert cache.load_fresh(SourceConfig('overpass','https://other.invalid'),smaller) is None
    assert cache.load_fresh(SourceConfig('overpass','https://example.invalid',interval_seconds=0),smaller) is None


def test_openwaters_imports_nautical_overlay_without_basemap(monkeypatch):
    monkeypatch.setattr('app.nav.maritime.adapters.reference.request_json',lambda *a,**kw:{
        'version':8,'sources':{'marine':{'type':'vector','url':'tiles.json'},'base':{'type':'raster','tiles':['https://example.invalid/{z}/{x}/{y}.png']}},
        'layers':[{'id':'land','type':'raster','source':'base'},
                  {'id':'seamark-lights','type':'symbol','source':'marine','source-layer':'lights','layout':{'icon-image':'remote-buoy'}}]})
    result=OpenWatersAdapter(SourceConfig('openwaters','https://example.invalid/style.json')).fetch(AREA)
    overlay=result.reference_layers['openwaters']
    assert overlay['kind']=='overlay' and len(overlay['layers'])==1
    assert overlay['layers'][0]['type']=='circle' and overlay['sources']['marine']['url']=='https://example.invalid/tiles.json'


def test_ais_mock_stream_to_runtime_merge_render_and_expiry(qapp):
    from app.nav.maritime.runtime import MaritimeRuntime
    from app.nav.maritime.render_state import build_render_state
    runtime=MaritimeRuntime(config=MaritimeConfig({}));runtime.timer.stop()
    runtime.config.sources.clear();runtime.service.clock=lambda:NOW
    runtime.service.own_mmsi='123456789'
    runtime.ais_normalizer=AISStreamNormalizer(lambda:runtime.service.clock())
    class Stream:
        def drain(self):return ([message(),message(mmsi=987654321),message(mmsi=987654321,Name='UPDATED')],'LIVE',True)
        def start(self,*args):pass
        def stop(self):pass
    from app.nav.maritime.source_health import SourceHealth
    runtime.aisstream=Stream();runtime.service.sources['aisstream']=SourceHealth(dynamic=True)
    try:
        runtime.own_position(22,91);runtime.tick()
        payload=build_render_state(runtime.service)
        assert payload['counts']['vessels']==1 and len(payload['geojson']['vessels']['features'])==1
        runtime.service.clock=lambda:NOW+timedelta(seconds=121);runtime.service.evaluate_time()
        assert runtime.service.snapshot()[0].status=='STALE'
        runtime.service.clock=lambda:NOW+timedelta(seconds=601);runtime.service.evaluate_time()
        assert not runtime.service.snapshot()
    finally:runtime.close()


def test_minor_viewport_motion_keeps_active_query_and_cache_identity():
    from app.nav.maritime.area_controller import MaritimeAreaController
    controller=MaritimeAreaController(debounce_seconds=0)
    original=controller.viewport(100.12,3.8,100.89,4.26)
    assert controller.viewport(100.11,3.79,100.90,4.27) is None
    assert controller.area is original
    assert controller.viewport(100.4,3.9,100.6,4.1) is not None


def test_cached_view_is_available_during_provider_rate_limit(qtbot,monkeypatch):
    import time
    from app.nav.maritime.runtime import MaritimeRuntime
    runtime=MaritimeRuntime(config=MaritimeConfig({'GDS_OVERPASS_ENDPOINT':'https://example.invalid','GDS_GEBCO_ENABLED':'false'}));runtime.timer.stop()
    obj=canonical_feature('overpass','1','aton','light',{'type':'Point','coordinates':[100.5,3.5]})
    monkeypatch.setattr(runtime.cache,'load_fresh',lambda *args:[obj])
    monkeypatch.setattr(runtime.adapters['overpass'],'fetch',lambda *args:pytest.fail('cached view must not request network'))
    try:
        runtime._retry_until['overpass']=time.monotonic()+600
        runtime.viewport(100,3,101,4);runtime.tick()
        qtbot.waitUntil(lambda:len(runtime.service.snapshot())==1,timeout=5000)
        assert runtime.service.sources['overpass'].state=='READY' and runtime.service.sources['overpass'].cached
    finally:runtime.close()


def test_successful_empty_overpass_is_visibly_ready_with_zero_objects(qapp):
    from app.qt.QtWidgets import QLabel
    from app.ui.pages.nav.nav_page import NavPage
    from app.nav.maritime.render_state import build_render_state
    service=MaritimeObjectService()
    from app.nav.maritime.source_health import SourceHealth
    service.sources['overpass']=SourceHealth(state='READY')
    view=SimpleNamespace(source_info=QLabel(),maritime_heading=QLabel(),maritime_info=QLabel(),show_object_button=QLabel())
    NavPage._update_maritime(view,build_render_state(service))
    assert 'OVERPASS  READY | 0 objects' in view.source_info.text()


