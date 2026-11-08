"""Asset composition/schema/priority checks; never download data or run builders."""
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from test_offline_maps import make_package, make_tiles
from tools.maps import build_southeast_asia as build
from app.nav.offline_maps.manager import checksum, validate_package
from app.nav.offline_maps.mbtiles import MapPackageError
from app.nav.offline_maps.render_config import render_config, source_priority


def test_composed_asset_manifest_roles_sources_checksums_and_local_style(tmp_path):
    source=make_package(tmp_path/'fixture')
    record={'revision':'test-only','osm':{'timestamp':'2026-11-01T00:00:00+00:00','source':'TEST FIXTURE'},
            'gebco':{'release':'GEBCO_2026','source':'TEST FIXTURE'}}
    root=tmp_path/'package'
    manifest=build.assemble(root,{'basemap':source/'sea.mbtiles','bathymetry':source/'depth.mbtiles'},'test-only',record)
    assert manifest['source']==record
    assert manifest['assets']['basemap']['role']=='basemap'
    assert manifest['assets']['basemap']['format']=='pbf'
    assert manifest['assets']['bathymetry']['role']=='bathymetry'
    assert manifest['assets']['bathymetry']['format']=='png'
    assert manifest['assets']['basemap']['tile_count']==1
    assert manifest['assets']['basemap']['sample_zooms']==[4]
    for name,sha in manifest['checksums'].items():assert checksum(root/name)==sha
    config=render_config(validate_package(root))
    assert config['status']=='OFFLINE MAP · Southeast Asia · READY'
    assert config['bathymetry_status']=='READY'
    assert config['style']['glyphs'].startswith('gds://map/')
    assert all(s['tiles'][0].startswith('gds://tiles/') for s in config['style']['sources'].values())
    assert 'sprite' not in config['style']


def test_overview_region_and_overlapping_details_draw_from_broad_to_fine(tmp_path):
    source=make_package(tmp_path/'fixture')
    inputs={'basemap':source/'sea.mbtiles','bathymetry':source/'depth.mbtiles'}
    for role,zooms,coverage in [('overview',(0,5),'-180,-85,180,85'),
                              ('detail-0',(4,14),'90,-10,120,30'),
                              ('detail-1',(4,12),'90,-10,120,30')]:
        path=source/(role+'.mbtiles');make_tiles(path)
        with sqlite3.connect(path) as db:
            for key,value in [('minzoom',str(zooms[0])),('maxzoom',str(zooms[1])),('bounds',coverage)]:
                db.execute('UPDATE metadata SET value=? WHERE name=?',(value,key))
        inputs[role]=path
    root=tmp_path/'package'
    build.assemble(root,inputs,'test-only',{'source':'TEST FIXTURE'})
    config=render_config(validate_package(root))
    layers=config['style']['layers']
    positions={role:next(i for i,l in enumerate(layers) if l.get('source')=='offline-'+role) for role in inputs}
    assert positions['overview']<positions['basemap']<positions['detail-1']<positions['detail-0']<positions['bathymetry']
    overview=config['style']['sources']['offline-overview']
    assert overview['bounds']==[-180,-85,180,85] and overview['maxzoom']==5
    assert config['style']['sources']['offline-basemap']['bounds']==[90,-10,120,30]
    assert all(s.get('scheme','xyz')=='xyz' for s in config['style']['sources'].values())
    assert all(s['maxzoom']<=14 for s in config['style']['sources'].values())  # native bound permits MapLibre overzoom


def test_equal_zoom_details_use_smaller_coverage_last():
    broad={'bounds':[90,-10,120,30],'maxzoom':14}
    site={'bounds':[103,4,105,6],'maxzoom':14}
    assert source_priority('detail-0',broad)<source_priority('detail-1',site)


def test_openmaptiles_land_background_and_actual_source_layer_contract(tmp_path):
    package=validate_package(make_package(tmp_path/'fixture'))
    style=render_config(package)['style']
    # OpenMapTiles landcover means vegetation, not a complete dry-land polygon.
    assert style['layers'][0]['metadata']['gds:role']=='LAND'
    assert style['layers'][0]['paint']['background-color']=='#e8e8df'
    actual={l['id'] for l in json.loads(style_meta(package))['vector_layers']}
    assert all(l['source-layer'] in actual for l in style['layers'] if 'source-layer' in l)


def style_meta(package):
    with sqlite3.connect(package.root/'sea.mbtiles') as db:
        return db.execute("SELECT value FROM metadata WHERE name='json'").fetchone()[0]


def test_package_rejects_basemap_in_bathymetry_role(tmp_path):
    source=make_package(tmp_path/'fixture')
    with pytest.raises(MapPackageError,match='role mismatch'):
        build.assemble(tmp_path/'bad',{'basemap':source/'sea.mbtiles','bathymetry':source/'sea.mbtiles'},'test-only',{})


def test_package_requires_both_real_asset_roles(tmp_path):
    with pytest.raises(ValueError,match='Both basemap and bathymetry'):
        build.assemble(tmp_path/'bad',{},'test-only',{})
    assert not (tmp_path/'bad').exists()


def test_asset_checksum_failure_prevents_activation(tmp_path):
    source=make_package(tmp_path/'fixture')
    root=tmp_path/'package'
    build.assemble(root,{'basemap':source/'sea.mbtiles','bathymetry':source/'depth.mbtiles'},'test-only',{})
    (root/'build-record.json').write_text('changed')
    manager=build.PackageManager(tmp_path/'store')
    with pytest.raises(MapPackageError,match='Checksum mismatch'):manager.install(root)
    assert manager.active() is None


def test_blocked_build_never_acquires_sources_or_creates_work(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Source download attempted')
    monkeypatch.setattr(build,'acquire_osm',forbidden)
    root=tmp_path/'uncreated'
    with pytest.raises(ValueError,match='RESOURCE/DEPENDENCY'):
        build.build(SimpleNamespace(work_root=root),{'ready':False,'blockers':['Java missing']})
    assert not root.exists()


def test_large_asset_storage_rejected_inside_project():
    with pytest.raises(ValueError,match='outside the project'):
        build.external_root(build.PROJECT/'data/map-build')
