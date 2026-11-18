"""Presentation contracts using real Malaysia payloads and both NAV scripts."""
import json
import shutil
import subprocess
import pytest
from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider
from app.nav.maritime.malaysia_config import DEFAULT_DIRECTORY
from app.nav.maritime.area_controller import OperatingArea
from app.nav.maritime.service import MaritimeObjectService
from app.nav.map_bridge import MapBridge


@pytest.fixture(scope='module')
def visual_payload():
    provider=MalaysiaOffshoreGISProvider(DEFAULT_DIRECTORY)
    provider.load()
    service=MaritimeObjectService()
    service.set_gis_result(provider.fetch(OperatingArea(5.5,104,150)))
    return json.dumps(MapBridge(maritime_service=service).getMaritimeState())


@pytest.mark.parametrize('scenario',['glow','order','visibility','symbols','stability','selection','restore'])
def test_nav_visual_contract(visual_payload,scenario):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    result=subprocess.run([node,'tests/nav_visual_runtime.cjs',scenario],input=visual_payload,
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
