from app.core.compat import is_relative_to
"""Regional expansion fixtures never download production map assets."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.nav.offline_maps.manager import PackageManager,validate_package,MapPackageError
from app.nav.offline_maps.regional import intersects,resolve,RegionalReaders,regional_config
from app.nav.offline_maps.regions import shortbread_url,official,region_candidates,select_regions,plan_install,MARGIN
from test_offline_maps import make_package


def regional_fixture(tmp_path,key):
    root=make_package(tmp_path/key);path=root/'manifest.json';data=json.loads(path.read_text())
    data.update(package_id=key,name=key);path.write_text(json.dumps(data));return root


def test_independent_region_install_preserves_accepted_pointer_and_restart(tmp_path):
    manager=PackageManager(tmp_path/'store');malaysia=manager.install(regional_fixture(tmp_path,'malaysia'))
    pointer=(manager.store/'active.json').read_bytes()
    thailand=manager.install_region(regional_fixture(tmp_path,'thailand'))
    assert (manager.store/'active.json').read_bytes()==pointer
    assert manager.active().root==malaysia.root
    assert {p.manifest['package_id'] for p in PackageManager(manager.store).installed_regions()}=={'malaysia','thailand'}
    assert thailand.root!=malaysia.root


def test_enable_disable_and_rollback_independent_regions(tmp_path):
    manager=PackageManager(tmp_path/'store');manager.install(regional_fixture(tmp_path,'malaysia'))
    source=regional_fixture(tmp_path,'thailand');first=manager.install_region(source);second=manager.install_region(source)
    manager.set_region_enabled('thailand',False)
    assert [p.manifest['package_id'] for p in manager.installed_regions(True)]==['malaysia']
    manager.rollback_region('thailand');assert manager.regional_index()['thailand']['current']==first.root.name
    manager.set_region_enabled('thailand',True)
    assert len(manager.installed_regions(True))==2
    assert second.root.exists()


def test_invalid_region_does_not_hide_valid_registry_entries(tmp_path):
    manager=PackageManager(tmp_path/'store');manager.install_region(regional_fixture(tmp_path,'thailand'))
    index=manager.regional_index();index['broken']={'current':'../escape'};manager._save_regions(index)
    assert list(manager.regional_index())==['thailand']


def test_failed_install_keeps_existing_packages(tmp_path):
    manager=PackageManager(tmp_path/'store');first=manager.install_region(regional_fixture(tmp_path,'thailand'))
    with pytest.raises((MapPackageError,FileNotFoundError)):manager.install_region(tmp_path/'absent')
    assert manager.installed_regions()[0].root==first.root


def test_accepted_active_revision_cannot_be_removed(tmp_path):
    manager=PackageManager(tmp_path/'store');manager.install(regional_fixture(tmp_path,'malaysia'))
    manager.set_region_enabled('malaysia',True)
    with pytest.raises(MapPackageError,match='protected'):manager.remove_region('malaysia')
    assert manager.active()


def test_removing_one_region_keeps_neighbor_and_accepted_package(tmp_path):
    manager=PackageManager(tmp_path/'store');accepted=manager.install(regional_fixture(tmp_path,'malaysia'))
    removed=manager.install_region(regional_fixture(tmp_path,'thailand'))
    neighbor=manager.install_region(regional_fixture(tmp_path,'vietnam'))
    manager.remove_region('thailand')
    assert not removed.root.exists() and neighbor.root.exists() and accepted.root.exists()
    assert set(manager.regional_index())=={'vietnam'}


@pytest.mark.parametrize('view,expected',[
    ([100,1,105,8],True),([120,1,130,8],False),([100,50,105,60],False),
    ([175,-10,-175,10],False),([110,1,115,8],True)])
def test_viewport_intersection(view,expected):assert intersects(view,[99,0,110,20])==expected


def test_date_line_viewport_and_island_bounds():
    assert intersects([175,-20,-175,10],[178,-18,180,-12])
    assert intersects([175,-20,-175,10],[-180,-18,-178,-12])


def package(key,bounds,priority=100,enabled=True):
    return SimpleNamespace(manifest=dict(package_id=key,bounds=bounds,priority=priority,enabled=enabled))


def test_priority_and_overlapping_coverage():
    large=package('large',[90,0,120,30]);small=package('small',[99,4,105,8])
    assert resolve([large,small],[100,5,104,7])==[small]
    assert resolve([large,small],[98,3,106,9])==[small,large]
    small.manifest['enabled']=False
    assert resolve([large,small],[100,5,104,7])==[large]
    assert resolve([large],[130,5,135,8])==[]


def test_wide_view_has_a_fixed_regional_source_budget():
    packages=[package(str(i),[i,-1,i+.8,1]) for i in range(20)]
    assert len(resolve(packages,[-1,-10,30,10]))==6


def test_official_parser_uses_real_link_and_marks_unavailable():
    page='https://download.geofabrik.de/asia/thailand.html'
    assert shortbread_url(page,'<a href="thailand-shortbread-1.0.mbtiles">vector</a>')=='https://download.geofabrik.de/asia/thailand-shortbread-1.0.mbtiles'
    assert shortbread_url(page,'<a href="thailand-latest.osm.pbf">raw</a>') is None
    with pytest.raises(ValueError):shortbread_url(page,'<a href="https://example.org/x-shortbread.mbtiles">wrong</a>')


@pytest.mark.parametrize('url',['http://download.geofabrik.de/x','https://download.geofabrik.de.evil/x','https://user@download.geofabrik.de/x'])
def test_unofficial_catalog_urls_rejected(url):
    with pytest.raises(ValueError):official(url)


def test_catalog_hierarchy_and_indonesia_selection():
    index={'features':[{'properties':dict(id=key,parent=parent,name=key,urls={'pbf':f'https://download.geofabrik.de/asia/{key}-latest.osm.pbf'})} for key,parent in [('indonesia','asia'),('java','indonesia'),('malaysia-singapore-brunei','asia')]]}
    entries=region_candidates(index)
    for e in entries:e['status']='AVAILABLE'
    selected=select_regions(entries)
    assert {e['region_id'] for e in selected}=={'java','malaysia_singapore_brunei'}


def test_disk_plan_cached_and_unavailable_are_explicit(tmp_path):
    manager=PackageManager(tmp_path/'store')
    entries=[dict(region_id=k,status=status,download_size=10,download_url=f'https://download.geofabrik.de/{k}.mbtiles') for k,status in [('one','AVAILABLE'),('two','AVAILABLE'),('none','UNAVAILABLE_PREBUILT')]]
    plan=plan_install(entries,tmp_path,manager,free=MARGIN+35)
    assert [e['action'] for e in plan['packages']]==['DOWNLOAD_INSTALL','SKIP_DISK_MARGIN','UNAVAILABLE_PREBUILT']
    assert plan['planned_remaining_bytes']>=MARGIN


def test_update_cache_keeps_previous_source_unchanged(tmp_path):
    from app.nav.offline_maps.regions import cache_target
    source=tmp_path/'test.mbtiles';source.write_bytes(b'accepted source')
    Path(str(source)+'.source.json').write_text(json.dumps({'http_headers':{'Last-Modified':'old'}}))
    entry=dict(download_url='https://download.geofabrik.de/test.mbtiles',source_date='new')
    target=cache_target(entry,tmp_path)
    assert target!=source and is_relative_to(target, tmp_path/'revisions')
    assert source.read_bytes()==b'accepted source'


def test_manual_update_plan_is_explicit_and_preserves_default(tmp_path):
    manager=PackageManager(tmp_path/'store');manager.install_region(regional_fixture(tmp_path,'thailand'))
    entries=[dict(region_id='thailand',status='AVAILABLE',download_size=10,source_date='new',download_url='https://download.geofabrik.de/test.mbtiles')]
    assert plan_install(entries,tmp_path,manager,free=MARGIN+100)['packages'][0]['action']=='INSTALLED'
    assert plan_install(entries,tmp_path,manager,free=MARGIN+100,update=True)['packages'][0]['action']=='DOWNLOAD_INSTALL'


def test_download_refuses_to_start_below_disk_reserve(tmp_path,monkeypatch):
    from app.nav.offline_maps import regions
    monkeypatch.setattr(regions.shutil,'disk_usage',lambda path:SimpleNamespace(free=MARGIN+1))
    monkeypatch.setattr(regions,'request',lambda *a,**kw:pytest.fail('Network must not start'))
    entry=dict(download_url='https://download.geofabrik.de/test.mbtiles',download_size=100)
    with pytest.raises(ValueError,match='reserve'):regions.download_region(entry,tmp_path)
    assert not list(tmp_path.glob('*.part'))


def test_reader_pool_is_bounded_and_releases_inactive_regions(tmp_path):
    packages=[validate_package(regional_fixture(tmp_path,key)) for key in ('one','two','three')]
    pool=RegionalReaders(packages,maximum=2)
    for key in ('one','two','three'):assert pool.tile(key,'basemap',4,12,8,'pbf')
    assert len(pool.readers)==2 and ('one','basemap') not in pool.readers
    pool.retain({'three'});assert list(pool.readers)==[('three','basemap')]
    assert pool.tile('unknown','basemap',4,12,8,'pbf') is None
    pool.close();assert not pool.readers


def test_multi_package_config_keeps_primary_style_and_local_routes(tmp_path):
    packages=[validate_package(regional_fixture(tmp_path,key)) for key in ('malaysia','thailand')]
    config=regional_config(packages,packages[0])
    assert 'offline-basemap' in config['style']['sources']
    assert len(config['regional_packages'])==2
    thai=config['regional_packages'][1]
    assert all('thailand' in key for key in thai['style']['sources'])
    assert all(url.startswith('gds://tiles/thailand/') for s in thai['style']['sources'].values() for url in s['tiles'])


def test_disappearing_region_does_not_hide_other_installed_regions(tmp_path,monkeypatch):
    from app.nav.offline_maps import render_config as module
    packages=[validate_package(regional_fixture(tmp_path,key)) for key in ('malaysia','thailand')]
    original=module.render_config
    def render(package):
        if package and package.manifest['package_id']=='malaysia':raise MapPackageError('Removable asset disappeared')
        return original(package)
    monkeypatch.setattr(module,'render_config',render)
    config=regional_config(packages,packages[0])
    assert config['installed'] and config['package_id']=='thailand'
    assert [p['package_id'] for p in config['regional_packages']]==['thailand']
    json.dumps(config) # No circular references when a fallback becomes primary.


def test_javascript_regional_lifecycle_preserves_operational_objects():
    import shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    result=subprocess.run([node,'tests/nav_regions_runtime.cjs'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_interrupted_download_resumes_with_validated_range(tmp_path,monkeypatch):
    import io
    from app.nav.offline_maps import regions
    from test_shortbread_maps import shortbread_package
    source=shortbread_package(tmp_path)/'sea.mbtiles';data=source.read_bytes()
    cache=tmp_path/'cache';cache.mkdir()
    entry=dict(download_url='https://download.geofabrik.de/test-shortbread.mbtiles',download_size=len(data),
               source_date='Sun, 08 Nov 2026 00:00:00 GMT',revision='"fixture"',official_source_page='https://download.geofabrik.de/test.html')
    class Broken(io.BytesIO):
        url=entry['download_url'];status=200;headers={}
        def read(self,n=-1):
            if self.tell():raise OSError('interrupted connection')
            return super().read(len(data)//2)
    monkeypatch.setattr(regions,'request',lambda *a,**kw:Broken(data))
    with pytest.raises(OSError,match='interrupted'):regions.download_region(entry,cache)
    assert not (cache/'test-shortbread.mbtiles').exists()
    offset=(cache/'test-shortbread.mbtiles.part').stat().st_size
    class Resume(io.BytesIO):
        url=entry['download_url'];status=206;headers={'Content-Range':f'bytes {offset}-{len(data)-1}/{len(data)}'}
    def request(url,headers):
        assert headers['Range']==f'bytes={offset}-';assert headers['If-Range']=='"fixture"'
        return Resume(data[offset:])
    monkeypatch.setattr(regions,'request',request)
    target=regions.download_region(entry,cache)
    assert target.read_bytes()==data
    assert json.loads(Path(str(target)+'.source.json').read_text())['sha256']
    assert not Path(str(target)+'.part').exists()
