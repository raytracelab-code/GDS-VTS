from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from types import SimpleNamespace
import zipfile
import pytest
from app.nav.offline_maps.mbtiles import MBTiles, MapPackageError, xyz_to_tms
from app.nav.offline_maps.manager import PackageManager, checksum, validate_package, safe_file, safe_name
from app.nav.offline_maps.palette import PaletteEngine, solar_elevation, solar_state, canonical_utc
from app.nav.offline_maps.render_config import render_config


def make_tiles(path, fmt='pbf', data=None):
    # Test-only one-feature MVT, encoded by the existing development dependency.
    if data is None:
        if fmt in ('pbf', 'mvt'):
            data = bytes.fromhex('1a210a05776174657212131803220f090080401a00ff3f8040000080400f2880207802')
        else:
            from app.qt.QtGui import QImage
            from app.qt.QtCore import QByteArray, QBuffer, QIODevice
            image = QImage(2, 2, QImage.Format.Format_RGB32);image.fill(0x112233)
            array=QByteArray();buffer=QBuffer(array);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            assert image.save(buffer, fmt.upper());data=bytes(array)
    metadata = dict(name='TEST ONLY',description='Unit fixture, never installed in production',version='1',type='baselayer',format=fmt,bounds='90,-10,120,30',center='105,10,4',minzoom='4',maxzoom='13',attribution='Test fixture',scheme='tms',json=json.dumps({'vector_layers':[{'id':n,'fields':{}} for n in ('water','landcover','place','boundary','transportation')]}))
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE metadata(name TEXT,value TEXT)')
    db.executemany('INSERT INTO metadata VALUES(?,?)',metadata.items())
    db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB)')
    db.execute('CREATE UNIQUE INDEX tile_index ON tiles(zoom_level,tile_column,tile_row)')
    db.execute('INSERT INTO tiles VALUES(4,12,7,?)',(data,))
    db.commit();db.close()
    return data


def make_package(root, revision='1'):
    root.mkdir()
    make_tiles(root/'sea.mbtiles')
    make_tiles(root/'depth.mbtiles','png')
    make_tiles(root/'satellite.mbtiles','jpg')
    m=dict(schema_version=1,package_id='test-sea',name='TEST ONLY',revision=revision,created_at='2026-11-08T00:00:00Z',region='test',bounds=[90,-10,120,30],minzoom=4,maxzoom=13,basemap_file='sea.mbtiles',bathymetry_file='depth.mbtiles',optional_satellite_files=['satellite.mbtiles'],style_revision='gds-maritime-1',attribution='Test fixture')
    m['checksums']={name:checksum(root/name) for name in ('sea.mbtiles','depth.mbtiles','satellite.mbtiles')}
    (root/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
    return root


@pytest.mark.parametrize('z,x,y,row',[(0,0,0,0),(1,0,0,1),(4,12,8,7),(13,1,8191,0),(22,0,0,4194303)])
def test_xyz_tms(z,x,y,row):
    assert xyz_to_tms(z,x,y)==row


@pytest.mark.parametrize('xyz',[(-1,0,0),(23,0,0),(4,16,0),(4,0,16),(1,-1,0),(1,0,-1),(True,0,0),(1.,0,0)])
def test_invalid_xyz(xyz):
    with pytest.raises(MapPackageError):xyz_to_tms(*xyz)


@pytest.mark.parametrize('fmt',['pbf','mvt','png','jpg','jpeg','webp'])
def test_read_tiles_readonly_cache_and_missing(tmp_path,fmt):
    path=tmp_path/'test.mbtiles';data=make_tiles(path,fmt);before=checksum(path)
    reader=MBTiles(path,1)
    try:
        assert reader.tile(4,12,8)==data
        assert reader.tile(4,12,7) is None
        assert reader.tile(3,0,0) is None
        with pytest.raises(sqlite3.OperationalError):reader._connection.execute('DELETE FROM tiles')
        with ThreadPoolExecutor(4) as pool:assert all(x==data for x in pool.map(lambda _:reader.tile(4,12,8),range(30)))
        assert len(reader._cache)==1
    finally:reader.close()
    assert checksum(path)==before
    assert reader.tile(4,12,8) is None


def test_gzip_and_corrupt_tiles(tmp_path):
    path=tmp_path/'good.mbtiles';raw=make_tiles(path)
    zipped=tmp_path/'gzip.mbtiles';make_tiles(zipped,data=gzip.compress(raw))
    reader=MBTiles(zipped);assert reader.tile(4,12,8)==raw;reader.close()
    for index,data in enumerate((b'\x1f\x8bgarbage',gzip.compress(b'x'*(16*1024*1024+1)))):
        bad=tmp_path/f'bad{index}.mbtiles';make_tiles(bad,data=data)
        with pytest.raises(MapPackageError):MBTiles(bad)


@pytest.mark.parametrize('data',[b'garbage',b'\x1a\xff\xff',b'\x1a\x02\x78\x02'])
def test_reject_invalid_vector_payload(tmp_path,data):
    path=tmp_path/'invalid.mbtiles';make_tiles(path,data=data)
    with pytest.raises(MapPackageError):MBTiles(path)


@pytest.mark.parametrize('key,value',[('bounds','120,0,90,20'),('bounds','nan,0,120,20'),('center','0,0,4'),('center','105,10,nan'),('minzoom','-1'),('maxzoom','23'),('format','gif'),('scheme','xyz'),('json','{}'),('name',''),('type','invalid')])
def test_reject_metadata(tmp_path,key,value):
    path=tmp_path/'bad.mbtiles';make_tiles(path)
    with sqlite3.connect(path) as db:db.execute('UPDATE metadata SET value=? WHERE name=?',(value,key))
    with pytest.raises(MapPackageError):MBTiles(path)


def test_missing_corrupt_empty_unindexed(tmp_path):
    with pytest.raises(OSError):MBTiles(tmp_path/'missing')
    (tmp_path/'corrupt').write_bytes(b'not sqlite')
    with pytest.raises(MapPackageError):MBTiles(tmp_path/'corrupt')
    for kind in ('empty','unindexed'):
        path=tmp_path/kind;make_tiles(path)
        with sqlite3.connect(path) as db:db.execute('DELETE FROM tiles' if kind=='empty' else 'DROP INDEX tile_index')
        with pytest.raises(MapPackageError):MBTiles(path)


def test_package_activation_rollback_and_checksums(tmp_path):
    source=make_package(tmp_path/'source');manager=PackageManager(tmp_path/'installed')
    first=manager.install(source);assert first.manifest['revision']=='1'
    m=json.loads((source/'manifest.json').read_text());m['revision']='2';(source/'manifest.json').write_text(json.dumps(m))
    second=manager.install(source);assert second.root!=first.root and first.root.is_dir()
    assert manager.rollback().manifest['revision']=='1'
    assert manager.rollback().manifest['revision']=='2'
    pointer=(manager.store/'active.json').read_bytes()
    with (source/'sea.mbtiles').open('ab') as out:out.write(b'changed')
    with pytest.raises(MapPackageError,match='Checksum'):manager.install(source)
    assert (manager.store/'active.json').read_bytes()==pointer
    assert not list(manager.store.glob('.staging-*'))


def test_zip_install_and_traversal_rejection(tmp_path):
    source=make_package(tmp_path/'source');archive=tmp_path/'valid.gdsmap'
    with zipfile.ZipFile(archive,'w') as z:
        for path in source.iterdir():z.write(path,path.name)
    manager=PackageManager(tmp_path/'installed');manager.install(archive)
    for name in ('../escape','/absolute','C:/escape','nested\\escape'):
        bad=tmp_path/'bad.gdsmap'
        with zipfile.ZipFile(bad,'w') as z:z.writestr(name,'bad')
        with pytest.raises(MapPackageError):manager.install(bad)
    assert manager.active().manifest['package_id']=='test-sea'


@pytest.mark.parametrize('field,value',[('schema_version',2),('package_id','../bad'),('revision','..\\bad'),('created_at','not date'),('bounds',[0,0,0,0]),('checksums',{}),('basemap_file','../outside.mbtiles'),('optional_satellite_files','bad'),('minzoom',True),('maxzoom',10)])
def test_invalid_manifest(tmp_path,field,value):
    source=make_package(tmp_path/'source');m=json.loads((source/'manifest.json').read_text());m[field]=value;(source/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(MapPackageError):validate_package(source)


def test_discovery_and_local_render_contract(tmp_path,monkeypatch):
    source=make_package(tmp_path/'source');monkeypatch.setenv('GDS_MAP_PACKAGE_PATH',str(source))
    monkeypatch.delenv('GDS_MAP_ALLOW_ONLINE_FALLBACK',raising=False)
    package=PackageManager(tmp_path/'empty').discover('test-sea');config=render_config(package)
    assert config['installed'] and not config['allow_online_fallback']
    assert set(config['tiles'])=={'basemap','bathymetry','satellite-0'}
    for spec in config['style']['sources'].values():
        assert spec['tiles'][0].startswith('gds://tiles/test-sea/')
        assert spec['bounds']==[90,-10,120,30]
    assert config['style']['glyphs'].startswith('gds://')
    assert next(l for l in config['style']['layers'] if l['id']=='offline-satellite-0-raster')['layout']['visibility']=='none'
    assert not render_config(None)['installed']
    monkeypatch.setenv('GDS_MAP_ALLOW_ONLINE_FALLBACK','true');assert render_config(None)['allow_online_fallback']


@pytest.mark.parametrize('latitude,longitude',[(0,0),(4,104),(23.8,90.4),(0,-90),(0,179)])
def test_solar_geographic_day_night_twilight(latitude,longitude):
    # Near equinox; local solar noon/midnight and evening civil twilight.
    noon=datetime(2026,3,20,12,tzinfo=timezone.utc)-timedelta(hours=longitude/15)
    assert solar_elevation(noon,latitude,longitude)>60
    assert solar_state(solar_elevation(noon+timedelta(hours=12),latitude,longitude))=='NIGHT'
    assert solar_state(solar_elevation(noon+timedelta(hours=6.35),latitude,longitude))=='TWILIGHT'
    assert solar_elevation(noon,latitude,longitude)==pytest.approx(solar_elevation(noon.astimezone(timezone(timedelta(hours=6))),latitude,longitude))


def test_palette_reference_manual_and_hysteresis():
    now=datetime(2026,3,20,6,tzinfo=timezone.utc);engine=PaletteEngine()
    p=engine.calculate(now,own=(4,104),center=(0,-90),follow=True);assert p['reference_type']=='OWN_VESSEL' and p['computed_solar_state']=='DAY'
    p=engine.calculate(now,own=(4,104),center=(0,-90),follow=False);assert p['reference_type']=='MAP_CENTER' and p['computed_solar_state']=='NIGHT'
    assert engine.calculate(now,own=None,center=(4,104),follow=True)['reference_type']=='MAP_CENTER'
    assert engine.calculate(now,center=(float('nan'),0))['reference_type']=='FALLBACK'
    for mode in ('DAY','NIGHT','AUTO'):
        engine.mode=mode;p=engine.calculate(now,center=(4,104));assert p['effective_state']==('DAY' if mode=='AUTO' else mode)
    assert solar_state(-.1,'DAY')=='DAY'
    assert solar_state(.1,'TWILIGHT')=='TWILIGHT'
    assert solar_state(-5.9,'NIGHT')=='NIGHT'
    with pytest.raises(ValueError):solar_elevation(datetime(2026,1,1),0,0)


@pytest.mark.parametrize('date,utc',[('2026-11-08','12:00:00'),('08/11/2026','120000'),('081126','120000.000')])
def test_gnss_utc_priority_and_freshness(date,utc):
    now=datetime(2026,11,8,12,tzinfo=timezone.utc)
    frame=SimpleNamespace(valid=True,received_at=now,date=date,utc=utc)
    assert canonical_utc(frame,now,True)==(now,'GNSS_UTC')
    assert canonical_utc(frame,now,False)==(now,'SYSTEM_UTC')
    frame.received_at=now-timedelta(seconds=4);assert canonical_utc(frame,now,True)[1]=='SYSTEM_UTC'
    frame.received_at=now;frame.date='N/A';assert canonical_utc(frame,now,True)[1]=='SYSTEM_UTC'


def test_palette_controller_persistence_debounce_and_no_source(qapp,tmp_path):
    from app.qt.QtCore import QSettings
    from app.nav.offline_maps.controller import PaletteController
    telemetry=SimpleNamespace(telemetry_status=SimpleNamespace(value='NO SOURCE'),latest_frame=None)
    controller=PaletteController(telemetry)
    original=controller.settings.value('nav/palette','AUTO')
    try:
        controller.map_center(4,104);assert controller.center is None
        controller.debounce.stop();controller._settled()
        controller.update(follow=True)
        assert controller.payload['reference_type']=='MAP_CENTER'
        assert controller.payload['time_source']=='SYSTEM_UTC'
        controller.set_mode('NIGHT')
        second=PaletteController(telemetry)
        assert second.engine.mode=='NIGHT'
        second.minute.stop();second.deleteLater()
        controller.set_mode('DAY');assert controller.payload['effective_state']=='DAY'
        controller.set_mode('AUTO');assert controller.payload['requested_mode']=='AUTO'
    finally:
        controller.settings.setValue('nav/palette',original);controller.minute.stop();controller.debounce.stop()


def test_real_javascript_palette_preserves_state():
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    result=subprocess.run([node,'tests/nav_offline_runtime.cjs'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_real_webengine_tile_scheme(tmp_path,monkeypatch):
    import os,sys
    source=make_package(tmp_path/'source')
    # Test gzip transport through the actual scheme (not HTTP content encoding).
    with sqlite3.connect(source/'sea.mbtiles') as db:
        raw=db.execute('SELECT tile_data FROM tiles').fetchone()[0]
        db.execute('UPDATE tiles SET tile_data=?',(gzip.compress(raw),))
    manifest=json.loads((source/'manifest.json').read_text());manifest['checksums']['sea.mbtiles']=checksum(source/'sea.mbtiles');(source/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setenv('GDS_MAP_PACKAGE_PATH',str(source));monkeypatch.setenv('GDS_MAP_DEFAULT_PACKAGE','test-sea')
    result=subprocess.run([sys.executable,'tests/offline_webengine_probe.py'],env=os.environ.copy(),capture_output=True,text=True,timeout=35)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('name',['.. /escape','CON','a/NUL.txt','a/COM1.mbtiles','a./file','a /file','./file','a//file','a/../b','C:relative','a\x00b'])
def test_windows_package_path_aliases(name):
    assert not safe_name(name)


def test_activation_failure_retains_pointer(tmp_path,monkeypatch):
    import os
    source=make_package(tmp_path/'source');manager=PackageManager(tmp_path/'installed');first=manager.install(source)
    pointer=(manager.store/'active.json').read_bytes();replace=os.replace
    def fail_pointer(src,dst):
        if Path(dst).name=='active.json':raise OSError('Simulated disk error')
        return replace(src,dst)
    monkeypatch.setattr(os,'replace',fail_pointer)
    with pytest.raises(OSError):manager.install(source)
    assert (manager.store/'active.json').read_bytes()==pointer
    assert manager.active().root==first.root


def test_overview_and_detail_independent_coverage(tmp_path):
    source=make_package(tmp_path/'source');make_tiles(source/'world.mbtiles');make_tiles(source/'detail.mbtiles')
    with sqlite3.connect(source/'world.mbtiles') as db:
        db.execute("UPDATE metadata SET value='-180,-85,180,85' WHERE name='bounds'")
        db.execute("UPDATE metadata SET value='0' WHERE name='minzoom'")
        db.execute("UPDATE metadata SET value='5' WHERE name='maxzoom'")
    m=json.loads((source/'manifest.json').read_text());m['overview_file']='world.mbtiles';m['detail_files']=['detail.mbtiles']
    for name in ('world.mbtiles','detail.mbtiles'):m['checksums'][name]=checksum(source/name)
    (source/'manifest.json').write_text(json.dumps(m))
    config=render_config(validate_package(source))
    assert config['style']['sources']['offline-overview']['bounds']==[-180,-85,180,85]
    assert config['style']['sources']['offline-overview']['maxzoom']==5
    assert config['style']['sources']['offline-detail-0']['bounds']==[90,-10,120,30]


@pytest.mark.parametrize('payload',[None,[],['revision'],'revision',42,True,{'current':[]},{'current':'../../escape'}])
def test_corrupt_registry_falls_back_without_startup_failure(tmp_path,monkeypatch,payload):
    manager=PackageManager(tmp_path/'store');manager.store.mkdir()
    (manager.store/'active.json').write_text(json.dumps(payload),encoding='utf-8')
    source=make_package(tmp_path/'source')
    monkeypatch.setenv('GDS_MAP_PACKAGE_PATH',str(source))
    assert manager.active() is None
    assert manager.discover().root==source.resolve()


def test_registry_invalid_json_and_size_are_bounded(tmp_path):
    manager=PackageManager(tmp_path/'store');manager.store.mkdir()
    pointer=manager.store/'active.json'
    for raw in (b'{broken',b'\xff',b' '*65537):
        pointer.write_bytes(raw)
        assert manager.active() is None


def test_bad_previous_registry_field_preserves_current_package(tmp_path):
    source=make_package(tmp_path/'source');manager=PackageManager(tmp_path/'store')
    package=manager.install(source)
    pointer=manager.store/'active.json';registry=json.loads(pointer.read_text())
    registry['previous']=['damaged'];pointer.write_text(json.dumps(registry))
    assert manager.active().root==package.root
    with pytest.raises(MapPackageError,match='No previous package'):manager.rollback()


@pytest.mark.parametrize('name',['a?.mbtiles','a*.mbtiles','a|b.mbtiles','a<b.mbtiles','a>b.mbtiles','a"b.mbtiles'])
def test_windows_invalid_filename_characters(name):
    assert not safe_name(name)


def test_manifest_boolean_schema_version_rejected(tmp_path):
    source=make_package(tmp_path/'source');path=source/'manifest.json'
    manifest=json.loads(path.read_text());manifest['schema_version']=True
    path.write_text(json.dumps(manifest))
    with pytest.raises(MapPackageError,match='Unsupported/incomplete'):validate_package(source)


@pytest.mark.parametrize('fmt',['png','jpg','jpeg','webp'])
def test_truncated_raster_rejected_at_open_and_during_reads(tmp_path,fmt):
    path=tmp_path/'raster.mbtiles';raw=make_tiles(path,fmt)
    reader=MBTiles(path,0)
    try:
        with sqlite3.connect(path) as db:
            db.execute('INSERT INTO tiles VALUES(4,12,6,?)',(raw[:16],))
        assert reader.tile(4,12,9) is None
        assert reader.tile(4,12,8)==raw
    finally:reader.close()
    with sqlite3.connect(path) as db:
        db.execute('UPDATE tiles SET tile_data=?',(raw[:16],))
    with pytest.raises(MapPackageError,match='Invalid sample tile'):MBTiles(path)


def test_raster_decode_dimensions_are_bounded(tmp_path,monkeypatch):
    from app.nav.offline_maps import mbtiles
    path=tmp_path/'raster.mbtiles';make_tiles(path,'png')
    monkeypatch.setattr(mbtiles,'MAX_RASTER_DIMENSION',1)
    with pytest.raises(MapPackageError,match='Invalid sample tile'):MBTiles(path)


def test_raster_corrupt_image_stream_rejected(tmp_path):
    path=tmp_path/'raster.mbtiles';raw=bytearray(make_tiles(path,'png'))
    # Keep the PNG signature, dimensions and IEND; damage the compressed image.
    raw[raw.index(b'IDAT')+4]^=0xff
    with sqlite3.connect(path) as db:db.execute('UPDATE tiles SET tile_data=?',(bytes(raw),))
    with pytest.raises(MapPackageError,match='Invalid sample tile'):MBTiles(path)


@pytest.mark.parametrize('error',[MapPackageError('damaged package'),OSError('removed package')])
def test_package_disappearing_before_style_setup_falls_back(qapp,tmp_path,monkeypatch,error):
    from app.nav.offline_maps import render_config as config_module
    from app.nav.web_scheme import GdsMapSchemeHandler
    package=validate_package(make_package(tmp_path/'source'))
    monkeypatch.setattr(PackageManager,'discover',lambda *_:package)
    original=config_module.render_config
    def disappearing(candidate):
        if candidate is not None:raise error
        return original(None)
    monkeypatch.setattr(config_module,'render_config',disappearing)
    monkeypatch.delenv('GDS_MAP_ALLOW_ONLINE_FALLBACK',raising=False)
    handler=GdsMapSchemeHandler()
    try:
        assert handler.package is None
        assert not handler.config['installed']
        assert not handler.config['allow_online_fallback']
        assert handler.config['style']['sources']=={}
    finally:handler.close()
