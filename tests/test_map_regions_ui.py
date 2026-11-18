"""The package surface is NAV-only and never downloads during tests."""
import json
import pytest
from app.qt.QtCore import Qt
from app.ui.pages.nav.map_regions_dialog import MapRegionsDialog
from app.nav.offline_maps.manager import PackageManager
from test_map_regions import regional_fixture


@pytest.fixture
def regions_dialog(qtbot,tmp_path,monkeypatch):
    manager=PackageManager(tmp_path/'store');manager.install_region(regional_fixture(tmp_path,'thailand'))
    catalog=[dict(region_id='thailand',display_name='Thailand',group='Asia',status='AVAILABLE'),
             dict(region_id='australia',display_name='Australia',group='Oceania',status='AVAILABLE',download_size=100)]
    (tmp_path/'regions-catalog.json').write_text(json.dumps(catalog))
    monkeypatch.setattr('app.ui.pages.nav.map_regions_dialog.PackageManager',lambda:manager)
    monkeypatch.setattr('app.ui.pages.nav.map_regions_dialog.cache_root',lambda:tmp_path/'sources')
    events=[];dialog=MapRegionsDialog(changed=lambda:events.append('changed'),release=lambda:events.append('release'))
    qtbot.addWidget(dialog)
    return dialog,manager,events


def test_package_surface_reports_group_status_size_and_revision(regions_dialog):
    dialog,manager,_=regions_dialog
    assert dialog.windowTitle()=='OFFLINE MAP REGIONS'
    assert dialog.tree.topLevelItemCount()==2
    thai=dialog.tree.topLevelItem(0).child(0)
    assert thai.text(0)=='Thailand' and thai.text(1)=='INSTALLED'
    assert thai.text(2).endswith('MiB') and thai.text(3)
    assert thai.data(0,Qt.ItemDataRole.UserRole)=='thailand'


def test_disabling_package_releases_readers_before_registry_change(regions_dialog):
    dialog,manager,events=regions_dialog
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0).child(0));dialog.toggle(False)
    assert events==['release','changed']
    assert not manager.regional_index()['thailand']['enabled']
    assert dialog.tree.topLevelItem(0).child(0).text(1)=='DISABLED'


def test_install_and_update_check_use_explicit_background_tooling(regions_dialog,monkeypatch):
    dialog,_,_=regions_dialog;calls=[]
    monkeypatch.setattr(dialog,'run',lambda args:calls.append(args))
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0).child(0));dialog.install();dialog.check_updates()
    assert calls==[['--region','thailand','--update'],['--refresh','--list']]


def test_invalid_registered_package_is_visible_without_activation(regions_dialog):
    dialog,manager,_=regions_dialog
    registry=manager.regional_index();registry['thailand']['current']='invalid';manager._save_regions(registry)
    dialog.refresh()
    row=dialog.tree.topLevelItem(0).child(0)
    assert row.text(1)=='INVALID' and row.toolTip(1)
    assert not manager.installed_regions()
