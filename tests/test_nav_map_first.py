"""Presentation behavior with a recording web surface, without network/WebEngine."""
from types import SimpleNamespace
import pytest
from app.qt.QtCore import Qt,QSettings
from app.qt.QtWidgets import QWidget,QVBoxLayout,QLabel
from app.ui.pages.nav.nav_page import NavPage
from app.ui.components.top_tabs import TopTabs
from app.nav.map_controls import FollowController
from app.nav.maritime.render_state import GIS_DEFAULTS


class WebSurface(QWidget):
    def __init__(self):super().__init__();self.calls=[]
    def page(self):return self
    def runJavaScript(self,code):self.calls.append(code)


@pytest.fixture
def floating(qtbot,tmp_path,monkeypatch):
    settings=QSettings(str(tmp_path/'nav.ini'),QSettings.Format.IniFormat)
    for module in ('nav_page','presentation_widgets'):
        monkeypatch.setattr('app.ui.pages.nav.'+module+'.QSettings',lambda *args:settings)
    page=NavPage.__new__(NavPage);QWidget.__init__(page);qtbot.addWidget(page)
    page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
    page.layer_checks={};page.follow=FollowController();page.maritime_runtime=None
    page.palette=SimpleNamespace(update=lambda **kwargs:None)
    page.spatial=SimpleNamespace(state=SimpleNamespace(metadata={},feature_counts={'total':0}),selection=SimpleNamespace(feature=None))
    page.web=WebSurface();layout=QVBoxLayout(page);layout.setContentsMargins(0,0,0,0);layout.addWidget(page.web)
    page.status=QLabel('NO SOURCE');page.trackbar=QLabel('TRACK IDLE')
    page.bridge=SimpleNamespace(maritime_service=None,setMaritimeVisibility=lambda *args:None)
    page._init_floating();page.resize(1100,740);page.show();qtbot.wait(10)
    return page,settings


def test_map_fills_workspace_without_permanent_sidebar(floating):
    page,_=floating
    assert page.web.geometry()==page.rect()
    assert page.layers_panel.isHidden() and page.selection_panel.isHidden()
    assert page.layout().count()==1
    assert len(page.control_groups)==4
    assert page.palette_control.count()==3


def test_layers_toggle_escape_and_outside_click_preserve_map(floating,qtbot):
    page,_=floating;before=list(page.web.calls)
    qtbot.mouseClick(page.layers_button,Qt.MouseButton.LeftButton)
    assert page.layers_panel.isVisible() and page.layers_button.isChecked()
    qtbot.keyClick(page.layers_button,Qt.Key.Key_Escape)
    assert page.layers_panel.isHidden() and not page.layers_button.isChecked()
    page.toggle_layers();qtbot.mouseClick(page.web,Qt.MouseButton.LeftButton,pos=page.web.rect().center())
    assert page.layers_panel.isHidden()
    assert page.web.calls==before  # Opening panels never changes camera, style or sources.


def test_layer_preferences_survive_panel_lifecycle(floating):
    page,settings=floating
    key=next(iter(GIS_DEFAULTS));checkbox=page.layer_checks[key]
    checkbox.setChecked(not checkbox.isChecked());saved=checkbox.isChecked()
    for _ in range(3):page.toggle_layers();page.toggle_layers()
    assert checkbox.isChecked()==saved
    assert settings.value('nav/layers/'+key,type=bool)==saved


@pytest.mark.parametrize('width,height',[(1100,740),(800,600),(600,500)])
def test_capsules_and_panels_stay_in_view(floating,width,height):
    page,_=floating;page.resize(width,height);page._position_floating()
    widgets=[page.search_capsule,page.utility,*page.control_groups,page.layers_panel,page.selection_panel]
    for widget in widgets:assert page.rect().contains(widget.geometry()),widget.accessibleName()
    assert not page.search_capsule.geometry().intersects(page.utility.geometry())
    for i,group in enumerate(page.control_groups):
        for other in page.control_groups[i+1:]:assert not group.geometry().intersects(other.geometry())


def test_selection_card_details_escape_and_update_does_not_reopen(floating,qtbot):
    page,_=floating
    page.maritime_heading.show();page.maritime_info.show();page.show_object_button.show()
    page.maritime_info.setText('\n'.join('Field  value' for _ in range(12)))
    page._sync_inspector('rig:1')
    assert page.selection_panel.isVisible() and page.maritime_info.compact
    page.toggle_details();assert not page.maritime_info.compact
    assert sum(not row[0].isHidden() for row in page.maritime_info.rows)==12
    qtbot.keyClick(page.search,Qt.Key.Key_Escape)
    assert page.selection_panel.isHidden()
    page._sync_inspector('rig:1');assert page.selection_panel.isHidden()
    page.reopen_selection('rig:1');assert page.selection_panel.isVisible()
    page._sync_inspector('rig:2');assert page.selection_panel.isVisible()
    page.toggle_layers();page._sync_inspector('rig:2')
    assert page.layers_panel.isVisible() and page.selection_panel.isHidden()


def test_coordinate_search_and_input_validation(floating):
    page,_=floating;page.search.setText('5.25, 104.1');page._search_loaded()
    assert page.search_results.count()==1
    page._activate_first_result()
    assert 'focusGeometry' in page.web.calls[-1] and '[104.1, 5.25]' in page.web.calls[-1]
    page.search.setText('95, 104');page._search_loaded()
    assert page.search_results.item(0).data(Qt.ItemDataRole.UserRole) is None


def test_search_uses_loaded_records_and_selects_existing_id(floating):
    page,_=floating;selected=[]
    obj=SimpleNamespace(properties={'name':'Duyong A','mmsi':'123456789'},source_id='a',category='offshore',object_id='rig:a',geometry={'type':'Point','coordinates':[104,5]})
    page.bridge.maritime_service=SimpleNamespace(render_snapshot=lambda:[obj])
    page.bridge.selectMaritimeObject=selected.append
    page.search.setText('Duyong');page._search_loaded()
    assert 'Duyong' in page.search_results.item(0).text()
    page._activate_search(page.search_results.item(0));assert selected==['rig:a']
    page.search.setText('123456789');page._search_loaded();assert page.search_results.count()==1


def test_follow_keeps_existing_semantics_without_text_expansion(floating):
    page,_=floating;page.command('FOLLOW')
    assert page.follow.enabled and page.follow_button.isChecked()
    assert page.follow_button.text()==''
    assert 'navMap.setFollow(true)' in page.web.calls[-1]
    page.command('FOLLOW');assert not page.follow.enabled


def test_rail_selection_allows_manual_vjr(qtbot):
    calls=[];rail=TopTabs(calls.append);qtbot.addWidget(rail)
    assert rail.width()==60 and rail.buttons['VDR'].isEnabled() and rail.buttons['VJR'].isEnabled()
    rail.buttons['Nav'].click();assert calls==['Nav'] and rail.buttons['Nav'].isChecked()
    rail.set_locked(True);assert rail.buttons['VDR'].isEnabled() and rail.buttons['VJR'].isEnabled()


def test_hud_real_script_preserves_camera_and_sources():
    import shutil,subprocess
    result=subprocess.run([shutil.which('node'),'tests/nav_hud_runtime.cjs'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
