"""Real dataset audit plus isolated malformed/reload and end-to-end NAV contracts."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider, GISResult, valid_crs
from app.nav.maritime.malaysia_config import DEFAULT_DIRECTORY, dataset_directory, read_manifest
from app.nav.maritime.models import MaritimeDataError, Category
from app.nav.maritime.service import MaritimeObjectService
from app.nav.maritime.area_controller import MaritimeAreaController, OperatingArea
from app.nav.maritime.inspector import gis_inspector
from app.nav.map_bridge import MapBridge


@pytest.fixture(scope='module')
def real_provider():
    p = MalaysiaOffshoreGISProvider(DEFAULT_DIRECTORY)
    p.load()
    return p


def feature(geometry, name='TEST', **properties):
    return dict(type='Feature', properties={'name':name,**properties},geometry=geometry)


@pytest.fixture
def small_provider(tmp_path):
    layer = {**read_manifest(DEFAULT_DIRECTORY)['layers'][-1], 'dataset_id':'malaysia_test',
        'filename':'test.geojson','canonical_category':'offshore','style_class':'platform_detail',
        'default_visibility':True}
    manifest = {**read_manifest(DEFAULT_DIRECTORY),'layers':[layer]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    def write(features, **extra):
        (tmp_path/'test.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features,**extra)))
    write([
        feature({'type':'Point','coordinates':[103,5]},'inside'),
        feature({'type':'Point','coordinates':[115,6]},'east'),
        feature({'type':'LineString','coordinates':[[102,5],[104,5]]},'crossing'),
        feature({'type':'Polygon','coordinates':[[[102,4],[104,4],[104,6],[102,6],[102,4]]]},'enclosing'),
    ])
    return MalaysiaOffshoreGISProvider(tmp_path), write


def test_discovery_manifest_and_override(real_provider):
    assert len(real_provider.audit)==18
    assert not any('__MACOSX' in r['filename'] or '/._' in r['filename'] for r in real_provider.audit)
    assert len(real_provider.layers)==18
    assert dataset_directory({'GDS_MALAYSIA_GIS_PATH':str(DEFAULT_DIRECTORY)})==DEFAULT_DIRECTORY
    assert all(l['source_tier']=='LOCAL_GIS' and l['inspectable'] for l in real_provider.layers)


@pytest.mark.parametrize('key,category',[
    ('platform',Category.OFFSHORE_INSTALLATION),('pipeline',Category.SUBSEA_INFRASTRUCTURE),
    ('well_location',Category.OFFSHORE_WELL),('fields_all',Category.OIL_GAS_FIELD),
    ('production_within_psc_area',Category.DEVELOPMENT_AREA),('pre_development_psc',Category.DEVELOPMENT_AREA),
    ('development_psc',Category.DEVELOPMENT_AREA),('abandoned_psc',Category.DEVELOPMENT_AREA),
    ('ceased_psc',Category.DEVELOPMENT_AREA),('awarded_block',Category.PETROLEUM_BLOCK),
    ('open_block',Category.PETROLEUM_BLOCK),('basin',Category.PETROLEUM_BASIN),
    ('seismic_3d',Category.SEISMIC_SURVEY_AREA),('ftg',Category.GEOPHYSICAL_SURVEY_AREA),
    ('platforms_134',Category.OFFSHORE_INSTALLATION),('platforms_3',Category.OFFSHORE_INSTALLATION),
    ('platforms_34',Category.OFFSHORE_INSTALLATION),('platforms_496',Category.OFFSHORE_INSTALLATION),
])
def test_all_real_categories(real_provider,key,category):
    layer_id='malaysia_'+key
    objs=[o for o in real_provider._objects if o.properties['gis_layer']==layer_id]
    row=next(r for r in real_provider.audit if Path(r['filename']).name==('malaysia_'+key+'_wgs84.geojson' if not key.startswith('platforms_') else key+'.geojson'))
    assert row['feature_count']>0 and not row.get('layer_error')
    # Supplemental labels can all be duplicates, and must not produce a second installation symbol.
    assert objs or row['duplicates']==row['feature_count']
    assert all(o.category==category and o.properties['source_tier']=='LOCAL_GIS' for o in objs)
    assert all(o.status!='LIVE' for o in objs)


@pytest.mark.parametrize('name', ['EPSG:3857','urn:ogc:def:crs:EPSG::27700','unknown'])
def test_reject_projected_crs(name):
    with pytest.raises(MaritimeDataError,match='Unsupported CRS'):
        valid_crs({'crs':{'properties':{'name':name}}})


def test_bbox_points_crossing_and_polygon(small_provider):
    p,_=small_provider;p.load()
    objs=p.query_bbox(102.9,4.9,103.1,5.1)
    assert {o.properties['name'] for o in objs}=={'inside','crossing','enclosing'}
    assert {o.properties['name'] for o in p.query_bbox(114,5,116,7)}=={'east'}
    assert p.query_bbox(90,1,91,2)==()
    assert p.query_bbox(179,-1,-179,1)==()


def test_invalid_feature_isolation_and_duplicate(small_provider):
    p,write=small_provider
    good=feature({'type':'Point','coordinates':[103,5]})
    write([good,good,feature(None),feature({'type':'Point','coordinates':[float('nan'),5]}),
        feature({'type':'Point','coordinates':[500,5]}),feature({'type':'Polygon','coordinates':[[[0,0],[1,1],[1,0],[0,1],[0,0]]]})])
    p.load();row=p.audit[0]
    assert len(p._objects)==1 and row['duplicates']==1
    assert row['invalid_features']==4 and row['null_geometries']==1


def test_bad_crs_layer_health(small_provider):
    p,write=small_provider
    write([],crs={'properties':{'name':'EPSG:3857'}})
    p.load()
    assert not p._objects and 'Unsupported CRS' in p.metadata['errors'][0]


def test_reload_stable_ids_no_reparse_and_invalidation(small_provider,monkeypatch):
    p,write=small_provider;p.load()
    ids={o.object_id for o in p._objects}
    original=p.load_count
    p.load();assert p.load_count==original
    features=[feature(o.geometry,o.properties['name']) for o in reversed(p._objects)]
    write(features);p.load()
    assert {o.object_id for o in p._objects}==ids and p.load_count==original+1
    write([feature({'type':'Point','coordinates':[117,7]},'replacement')]);p.load()
    assert not p.query_bbox(102,4,104,6) and len(p.query_bbox(116,6,118,8))==1


def test_manifest_path_escape(small_provider):
    p,_=small_provider
    path=p.directory/'manifest.json';m=json.loads(path.read_text());m['layers'][0]['filename']='../outside.geojson';path.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='escapes'):
        p.load()


def test_bridge_visibility_selection_and_inspector(real_provider):
    p=real_provider
    # Load a representative offshore viewport without vessel telemetry.
    area=MaritimeAreaController(debounce_seconds=0).viewport(103,4,105,8)
    result=p.fetch(area)
    assert 0<len(result.objects)<p.metadata['total_features']
    s=MaritimeObjectService();s.area=area;s.set_gis_result(result)
    bridge=MapBridge(maritime_service=s)
    payload=bridge.getMaritimeState()
    assert payload['area']['origin']=='viewport' and s.own_position is None
    assert payload['gis_dataset']['in_view']==len(result.objects)
    assert payload['geojson']['malaysia_platform']['features']
    assert payload['geojson']['malaysia_pipeline']['features']
    assert payload['geojson']['malaysia_fields_all']['features']
    assert payload['geojson']['malaysia_well_location']['features']==[]
    obj=next(o for o in result.objects if o.properties['gis_layer']=='malaysia_platform')
    bridge.selectMaritimeObject(obj.object_id)
    assert s.selected_object_id==obj.object_id
    s.set_gis_result(result);assert s.selected_object_id==obj.object_id
    title,rows=gis_inspector(obj.payload(),p.layers)
    assert title=='OFFSHORE INSTALLATION' and ('Source','MALAYSIA OFFSHORE GIS') in rows
    assert all(value is not None and str(value) not in ('null','undefined') for _,value in rows)
    before=len(s.snapshot());bridge.setMaritimeVisibility('malaysia_platform',False)
    assert not bridge.getMaritimeState()['geojson']['malaysia_platform']['features']
    assert s.selected_object_id is None and len(s.snapshot())==before
    bridge.setMaritimeVisibility('malaysia_platform',True)
    bridge.setMaritimeVisibility('malaysia_well_location',True)
    assert bridge.getMaritimeState()['geojson']['malaysia_well_location']['features']
    assert bridge.getMaritimeState()['geojson']['malaysia_platform']['features']
    json.dumps(bridge.getMaritimeState(),allow_nan=False)


def test_full_dataset_architecture_and_regional_views(real_provider):
    p=real_provider
    assert len(p._objects)>10000
    assert len([o for o in p._objects if o.category==Category.OFFSHORE_WELL])==6967
    assert len(p.query_bbox(103,4,105,8))<len(p._objects)
    assert p.query_bbox(113,4,118,8)
    count=p.load_count
    for _ in range(3):p.fetch(OperatingArea(5,104))
    assert p.load_count==count
    # No Qt objects, per-feature sources, widgets or timers in the loader.
    source=Path('app/nav/maritime/adapters/malaysia.py').read_text()
    assert all(word not in source for word in ('QTimer','QWidget','addSource','PySide6'))


def test_runtime_worker_no_source_and_stale_result(qapp,small_provider):
    from app.nav.maritime.runtime import MaritimeRuntime
    from app.nav.maritime.config import MaritimeConfig
    from app.nav.maritime.source_health import SourceHealth
    import threading,time
    from app.qt.QtCore import QCoreApplication
    p,_=small_provider
    rt=MaritimeRuntime(config=MaritimeConfig({}));rt.timer.stop()
    rt.malaysia_gis=p;rt.service.sources['malaysia_gis']=SourceHealth()
    workers=[];load=p.load
    p.load=lambda:(workers.append(threading.get_ident()),load())[-1]
    try:
        rt.viewport(102,4,104,6);rt.tick()
        deadline=time.monotonic()+10
        while rt.service.sources['malaysia_gis'].state!='READY' and time.monotonic()<deadline:
            QCoreApplication.processEvents();time.sleep(.01)
        assert rt.service.sources['malaysia_gis'].state=='READY'
        assert rt.service.own_position is None and rt.service.gis_dataset['in_view']==3
        assert all(worker!=threading.get_ident() for worker in workers)
        previous=rt.service.snapshot()
        rt._receive('malaysia_gis',rt._generation-1,GISResult((),{},()),None,False)
        assert rt.service.snapshot()==previous
    finally:rt.close()


def test_actual_python_payload_in_maplibre(real_provider):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    s=MaritimeObjectService()
    s.set_gis_result(real_provider.fetch(OperatingArea(5.5,104,150)))
    payload=MapBridge(maritime_service=s).getMaritimeState()
    from app.qt.QtCore import QJsonDocument
    wire=bytes(QJsonDocument.fromVariant(payload).toJson(QJsonDocument.JsonFormat.Compact)).decode()
    assert json.loads(wire)==json.loads(json.dumps(payload))
    result=subprocess.run([node,'tests/nav_malaysia_runtime.cjs'],input=wire,capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_shapely_coordinates_survive_real_qt_json_boundary():
    from shapely.geometry import LineString, mapping
    from app.qt.QtCore import QJsonDocument
    from app.nav.maritime.models import validate_geometry
    geometry=validate_geometry(mapping(LineString([(103,5),(104,6)])))
    wire=json.loads(bytes(QJsonDocument.fromVariant(geometry).toJson()).decode())
    assert wire['coordinates']==[[103,5],[104,6]]


def test_native_id_collision_is_order_independent(small_provider):
    p,write=small_provider
    a=feature({'type':'Point','coordinates':[103,5]},'a',OBJECTID=1)
    b=feature({'type':'Point','coordinates':[104,6]},'b',OBJECTID=1)
    write([a,b]);p.load();before={o.properties['name']:o.object_id for o in p._objects}
    write([b,a]);p.load()
    assert {o.properties['name']:o.object_id for o in p._objects}==before


def test_hidden_dense_gis_stays_in_service_not_webchannel(small_provider):
    p,_=small_provider;p.load()
    s=MaritimeObjectService();s.set_gis_result(GISResult(p._objects,p.metadata,p.layers))
    s.set_visibility('malaysia_test',False)
    assert len(s.render_snapshot())==4
    assert MapBridge(maritime_service=s).getMaritimeState()['objects']==[]
    s.set_visibility('malaysia_test',True)
    assert len(MapBridge(maritime_service=s).getMaritimeState()['objects'])==4


def test_broad_local_view_retains_exact_bounds():
    area=MaritimeAreaController(debounce_seconds=0).viewport(97,0,122,12)
    assert area.local_bounds==(97,0,122,12) and area.viewport_bounds is None
    assert area.radius_nm==250  # Online provider extent remains bounded.


def test_conservative_overpass_priority(real_provider):
    from app.nav.maritime.models import normalize_maritime_feature
    obj=next(o for o in real_provider._objects if o.properties['gis_layer']=='malaysia_platform')
    p=real_provider;s=MaritimeObjectService()
    s.set_gis_result(GISResult((obj,),p.metadata,p.layers))
    other=normalize_maritime_feature(dict(type='Feature',id='same',geometry=obj.geometry,
        properties=dict(category='offshore',object_type='platform',name=obj.properties['name'])),'overpass')
    nearby=replace(other,object_id='overpass:unrelated',properties={**other.properties,'name':'UNRELATED'})
    s.ingest([other,nearby]);assert not s.offshore_duplicates()
    s.offshore_source_priority=('malaysia_gis','overpass')
    assert s.offshore_duplicates()=={other.object_id:obj.object_id}
    assert len(s.snapshot())==3
    s.select(other.object_id);assert s.selected_object_id==obj.object_id
    s.set_visibility('malaysia_platform',False);assert not s.offshore_duplicates()
