"""NASA config and real-script basemap contracts; no live NASA requests."""
import json
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
import pytest
from app.nav.satellite_map import satellite_config, imagery_dates, tile_template, LAYER, MATRIX
from test_nav_visual import visual_payload
from test_nav_map_first import floating


def test_nasa_configuration_needs_no_credentials(monkeypatch):
    for name in ('NASA_API_KEY','MAPTILER_API_KEY','ARCGIS_API_KEY'):monkeypatch.delenv(name,raising=False)
    config=satellite_config(datetime(2026,11,9,tzinfo=timezone.utc))
    assert config['state']=='READY' and config['requires_key'] is False
    assert config['provider']=='NASA GIBS' and config['layer']==LAYER
    assert config['projection']=='EPSG:3857' and config['tile_matrix_set']==MATRIX
    assert config['tile_size']==256 and config['maxzoom']==9 and config['format']=='image/jpeg'
    assert 'NASA' in config['attribution'] and 'EOSDIS' in config['attribution']
    assert all('key=' not in c['source']['tiles'][0] for c in config['candidates'])


@pytest.mark.parametrize('instant,expected',[
    (datetime(2026,11,9,0,tzinfo=timezone.utc),['2026-11-09','2026-11-08','2026-11-07','2026-11-06']),
    (datetime(2026,3,1,1,tzinfo=timezone(timedelta(hours=6))),['2026-02-28','2026-02-27','2026-02-26','2026-02-25']),
    (datetime(2024,3,1,tzinfo=timezone.utc),['2024-03-01','2024-02-29','2024-02-28','2024-02-27']),
])
def test_imagery_dates_use_system_utc_order(instant,expected):assert imagery_dates(instant)==expected


def test_ambiguous_imagery_clock_rejected():
    with pytest.raises(ValueError):imagery_dates(datetime(2026,11,9))


def test_official_wmts_template_uses_row_then_column():
    template=tile_template('2026-11-09')
    assert template==f'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{LAYER}/default/2026-11-09/{MATRIX}/{{z}}/{{y}}/{{x}}.jpeg'
    with pytest.raises(ValueError):tile_template('../default')


def test_bridge_exposes_config_and_only_valid_mode_status(qapp):
    from app.nav.map_bridge import MapBridge
    bridge=MapBridge();events=[];bridge.basemapStateChanged.connect(lambda *args:events.append(args))
    assert bridge.getSatelliteMapConfig()['date_source']=='SYSTEM_UTC'
    bridge.reportBasemapState('SATELLITE','READY','2026-11-08')
    assert events==[('SATELLITE','READY','2026-11-08')]
    bridge.reportBasemapState('SATELLITE','READY','invalid')
    bridge.reportBasemapState('bad','READY','2026-11-08');assert len(events)==1


def test_satellite_controls_reflect_actual_mode_and_date(floating):
    page,_=floating
    page.control_buttons['SATELLITE'].setEnabled(True)
    page._basemap_state_changed('SATELLITE','READY','2026-11-08')
    assert page.control_buttons['SATELLITE'].isChecked() and not page.control_buttons['MARINE'].isChecked()
    assert '2026-11-08' in page.control_buttons['SATELLITE'].toolTip()
    page._basemap_state_changed('MARINE','ERROR','2026-11-08')
    assert page.control_buttons['MARINE'].isChecked() and not page.control_buttons['SATELLITE'].isChecked()
    assert 'unavailable' in page.control_buttons['SATELLITE'].toolTip()


def test_mode_buttons_preserve_open_layers_and_search_results(floating,qtbot):
    from app.qt.QtCore import Qt
    page,_=floating;page.toggle_layers();page.search.setText('5.5, 104');page._search_loaded()
    page.control_buttons['SATELLITE'].setEnabled(True)
    for mode in ('SATELLITE','MARINE'):
        qtbot.mouseClick(page.control_buttons[mode],Qt.MouseButton.LeftButton)
        assert page.layers_panel.isVisible() and page.search_results.isVisible()
        assert page.search.text()=='5.5, 104'


@pytest.mark.parametrize('scenario',['switch','dates','unavailable','tile-error','timeout','cancel','network','probe','hybrid','gebco-error','both-error','bathy-toggle'])
def test_satellite_runtime_contract(visual_payload,scenario):
    from app.nav.online_map import online_config
    payload=dict(config=online_config(),maritime=json.loads(visual_payload),
                 satellite=satellite_config(datetime(2026,11,9,tzinfo=timezone.utc)))
    result=subprocess.run([shutil.which('node'),'tests/nav_satellite_runtime.cjs',scenario],
        input=json.dumps(payload),text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_gebco_current_official_context():
    from app.nav.satellite_map import bathymetry_config
    config=bathymetry_config()
    assert config['layer']=='GEBCO_LATEST'
    assert 'CRS=EPSG:3857&BBOX={bbox-epsg-3857}' in config['source']['tiles'][0]
    assert 'GEBCO_2026' in config['source']['attribution']
    assert 'not for navigation' in config['source']['attribution']
    assert config['contours']=='DEPTH CONTOUR VECTOR SOURCE NOT AVAILABLE'
