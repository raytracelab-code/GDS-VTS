"""Shortbread integration fixtures only; production downloads never run in tests."""
import json
import shutil
import sqlite3
import subprocess

import pytest
from test_offline_maps import make_package
from app.nav.offline_maps.manager import checksum, validate_package, PackageManager
from app.nav.offline_maps.mbtiles import MBTiles, MapPackageError
from app.nav.offline_maps.schemas import vector_schema, SHORTBREAD
from app.nav.offline_maps.render_config import render_config

LAYERS=sorted(SHORTBREAD|{'land','boundary_labels','pier_lines','pier_polygons','water_polygons_labels','pois'})


def shortbread_package(tmp_path):
    root=make_package(tmp_path/'fixture')
    with sqlite3.connect(root/'sea.mbtiles') as db:
        db.execute('UPDATE metadata SET value=? WHERE name=?',(json.dumps({'vector_layers':[{'id':n,'fields':{}} for n in LAYERS]}),'json'))
        db.execute("DELETE FROM metadata WHERE name='attribution'")
        db.executemany('INSERT INTO metadata VALUES(?,?)',[('author','OpenStreetMap contributors, Geofabrik GmbH'),('license','Open Database License 1.0')])
    m=json.loads((root/'manifest.json').read_text())
    m.update(package_id='regional-fixture',vector_schemas={'basemap':'shortbread-1.0'})
    m['checksums']['sea.mbtiles']=checksum(root/'sea.mbtiles')
    (root/'manifest.json').write_text(json.dumps(m))
    return root


def test_shortbread_author_license_metadata_is_read_without_database_changes(tmp_path):
    root=shortbread_package(tmp_path);path=root/'sea.mbtiles';before=checksum(path)
    reader=MBTiles(path)
    try:
        assert 'OpenStreetMap contributors' in reader.metadata['attribution']
        assert vector_schema(reader.metadata)=='shortbread-1.0'
        assert reader.tile(4,12,8)
    finally:reader.close()
    assert checksum(path)==before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM metadata WHERE name='attribution'").fetchone() is None


@pytest.mark.parametrize('missing',sorted(SHORTBREAD))
def test_partial_shortbread_signature_is_rejected(missing):
    metadata={'json':json.dumps({'vector_layers':[{'id':n} for n in SHORTBREAD-{missing}]})}
    with pytest.raises(MapPackageError,match='Unsupported vector schema'):vector_schema(metadata)


def test_declared_schema_mismatch_is_rejected(tmp_path):
    root=shortbread_package(tmp_path)
    m=json.loads((root/'manifest.json').read_text());m['vector_schemas']['basemap']='openmaptiles'
    (root/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(MapPackageError,match='Declared vector schema'):validate_package(root)


def test_shortbread_style_maps_real_layer_names_properties_and_roles(tmp_path):
    config=render_config(validate_package(shortbread_package(tmp_path)))
    assert config['style']['name']=='GDS Shortbread Maritime'
    layers=config['style']['layers']
    by_id={l['id']:l for l in layers}
    for suffix,role in [('ocean','WATER'),('water','WATER'),('land','LAND'),('roads','ROAD'),('boundaries','BOUNDARY'),('places','LABEL'),('pier-lines','COAST')]:
        assert by_id['offline-basemap-'+suffix]['metadata']['gds:role']==role
    assert all(l['source-layer'] in LAYERS for l in layers if l.get('source')=='offline-basemap')
    assert 'name_en' in json.dumps(by_id['offline-basemap-places']['layout'])
    assert by_id['offline-basemap-roads']['filter']==['in','kind','motorway','trunk','primary','secondary']
    assert all(l.get('source-layer') not in ('buildings','addresses') for l in layers)
    assert config['coverage']==[{'role':'basemap','bounds':[90.,-10.,120.,30.]}]
    assert config['initial_bounds']==[[90.,-10.],[120.,30.]]
    assert config['style']['sources']['offline-basemap']['tiles']==['gds://tiles/regional-fixture/basemap/{z}/{x}/{y}.pbf']


def test_regional_activation_preserves_source_and_bounds_without_bathymetry(tmp_path):
    root=shortbread_package(tmp_path)
    m=json.loads((root/'manifest.json').read_text())
    m.pop('bathymetry_file');m.pop('optional_satellite_files')
    m['checksums']={'sea.mbtiles':checksum(root/'sea.mbtiles')}
    (root/'manifest.json').write_text(json.dumps(m))
    manager=PackageManager(tmp_path/'installed');package=manager.install(root)
    config=render_config(manager.active())
    assert config['installed'] and config['bathymetry_status']=='NOT INSTALLED'
    assert config['bounds']==[90,-10,120,30]
    assert checksum(package.root/'sea.mbtiles')==checksum(root/'sea.mbtiles')
    assert config['tiles']['basemap']['schema']=='shortbread-1.0'


def test_shortbread_bounds_and_palette_javascript():
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    result=subprocess.run([node,'tests/nav_shortbread_runtime.cjs'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
