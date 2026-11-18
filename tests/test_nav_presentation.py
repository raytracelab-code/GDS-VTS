"""Behavior checks for the preserved NAV presentation changes; no WebEngine."""
from types import SimpleNamespace
import pytest
from app.qt.QtCore import QSettings, Qt
from app.qt.QtWidgets import QWidget, QScrollArea, QPushButton
from app.ui.pages.nav.nav_page import NavPage
from app.ui.pages.nav.presentation_widgets import Disclosure, SourceStatusPanel, source_rows
from app.nav.maritime.render_state import GIS_GROUPS, GIS_DEFAULTS


@pytest.fixture
def presentation(qtbot,tmp_path,monkeypatch):
    settings=QSettings(str(tmp_path/'nav.ini'),QSettings.Format.IniFormat)
    monkeypatch.setattr('app.ui.pages.nav.nav_page.QSettings',lambda *args:settings)
    monkeypatch.setattr('app.ui.pages.nav.presentation_widgets.QSettings',lambda *args:settings)
    page=NavPage.__new__(NavPage);QWidget.__init__(page);qtbot.addWidget(page)
    page.layer_checks={};page.spatial=SimpleNamespace(state=SimpleNamespace(metadata={},feature_counts={'total':0}))
    panel=page._side();panel.setParent(page)
    return page,panel,settings


def test_panel_width_structure_and_retained_controls(presentation):
    page,panel,_=presentation
    assert panel.minimumWidth()==panel.maximumWidth()==292
    assert panel.horizontalScrollBarPolicy()==Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not panel.findChildren(QScrollArea)
    assert set(GIS_GROUPS)<=set(page.layer_checks)
    assert all(page.layer_checks[key].isChecked()==GIS_DEFAULTS[key] for key in GIS_GROUPS)
    assert page.nav_groups['own-vessel'].expanded and page.nav_groups['live'].expanded
    assert page.nav_groups['malaysia-offshore'].expanded and not page.nav_groups['project'].expanded
    assert not page.nav_groups['legend'].expanded
    fit=next(b for b in panel.findChildren(QPushButton) if b.accessibleName()=='FIT MALAYSIA GIS')
    assert page.nav_groups['malaysia-offshore'].isAncestorOf(fit)
    assert page.nav_groups['project'].isAncestorOf(page.spatial_summary)


def test_disclosure_persistence(presentation):
    page,_,settings=presentation
    group=page.nav_groups['malaysia-offshore'];group.set_expanded(False)
    assert settings.value(group.key,True,type=bool) is False
    replacement=Disclosure('MALAYSIA OFFSHORE','malaysia-offshore',True,settings=settings)
    assert replacement.expanded is False
    replacement.deleteLater()


def test_inspector_temporary_priority_preserves_preferences(presentation,qtbot):
    page,_,settings=presentation
    page.sources_section.set_expanded(True)
    page.maritime_heading.show();page.maritime_info.show();page.show_object_button.show()
    page._sync_inspector('platform:test');qtbot.wait(1)
    assert not page.inspector_box.isHidden() and not page.sources_section.expanded
    assert settings.value(page.sources_section.key,True,type=bool) is True
    page.maritime_heading.hide();page.maritime_info.hide();page.show_object_button.hide();page._sync_inspector()
    assert page.inspector_box.isHidden() and page.sources_section.expanded


def test_source_status_rows_group_models_without_changing_health(qtbot):
    payload=dict(objects=[],sources={'malaysia_gis':{'state':'READY'},'aisstream':{'state':'NOT_CONFIGURED'},
        'overpass':{'state':'READY'},'gebco':{'state':'READY'},'copernicus_wave':{'state':'NOT_CONFIGURED'},
        'copernicus_current':{'state':'NOT_CONFIGURED'},'gfw':{'state':'DISABLED_LICENSE'}},
        gis_dataset={'in_view':126,'total_features':10268})
    rows=source_rows(payload)
    assert next(r for r in rows if r['key']=='malaysia_gis')['count']==126
    assert next(r for r in rows if r['key']=='overpass')['count']==0
    assert sum(r['key']=='copernicus' for r in rows)==1
    panel=SourceStatusPanel();qtbot.addWidget(panel);panel.set_payload(payload)
    assert panel.rows['malaysia_gis'][4].text()=='126'
    assert panel.rows['aisstream'][3].text()=='Not Configured'
    assert '10,268 total' in panel.detail.text()
    panel.set_payload(payload);assert len(panel.rows)==len(rows)


def test_platform_inspector_prioritizes_operational_fields(presentation):
    page,_,_=presentation
    selected=dict(object_id='platform:test',category='offshore',source='malaysia_gis',
        properties=dict(gis_layer='platform',name='TEST',type='Platform',operator='Operator',
                        status='Active',water_depth_m=45,field='Field'),
        geometry=dict(type='Point',coordinates=[104,5]))
    payload=dict(objects=[selected],selected_object_id=selected['object_id'],sources={},counts={},
                 gis_layers=[dict(dataset_id='platform',style_class='platform')])
    page._update_maritime(payload)
    assert page.maritime_heading.text()=='OFFSHORE INSTALLATION'
    assert [line.split('  ')[0] for line in page.maritime_info.text().splitlines()][:6]==[
        'Name','Type','Operator','Status','Water Depth (m)','Position']


def test_legend_includes_producing_area_and_stays_collapsed(presentation):
    from app.qt.QtWidgets import QLabel
    page,_,_=presentation
    assert not page.nav_groups['legend'].expanded
    assert 'Producing area' in [label.text() for label in page.nav_groups['legend'].findChildren(QLabel)]
