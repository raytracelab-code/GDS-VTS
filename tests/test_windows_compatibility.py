"""Behavioral regressions for shared Python/Qt compatibility and optional providers."""
import json
from enum import auto
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from app.core.compat import LegacyStrEnum, ThreadPoolExecutor, is_relative_to, remove_prefix, remove_suffix
from app.core import platform_capabilities as capabilities


def test_legacy_enum_preserves_wire_values():
    class Mode(LegacyStrEnum):
        AUTO=auto()
        DAY='DAY'
    assert str(Mode.AUTO)=='auto'
    assert f'{Mode.DAY}'=='DAY'
    assert json.dumps({'mode':Mode.DAY})=='{"mode": "DAY"}'
    assert {Mode.DAY:1}['DAY']==1


@pytest.mark.parametrize('value,affix,prefix,suffix',[
    ('abc','a','bc','abc'),('abc','c','abc','ab'),('abc','','abc','abc'),
    ('abc','abc','',''),('abc','abcd','abc','abc')])
def test_affix_helpers_preserve_exact_semantics(value,affix,prefix,suffix):
    assert remove_prefix(value,affix)==prefix
    assert remove_suffix(value,affix)==suffix


def test_path_containment_rejects_sibling_prefix(tmp_path):
    assert is_relative_to(tmp_path/'maps'/'a',tmp_path/'maps')
    assert not is_relative_to(tmp_path/'maps-other',tmp_path/'maps')


def test_executor_cancels_queued_work_without_aborting_running_task():
    started=Event();release=Event()
    pool=ThreadPoolExecutor(max_workers=1)
    def work():started.set();release.wait(5);return 'finished'
    running=pool.submit(work)
    try:
        assert started.wait(3)
        pending=pool.submit(lambda:'must not run')
        pool.shutdown(wait=False,cancel_futures=True)
        assert pending.cancelled() and not running.cancelled()
        with pytest.raises(RuntimeError):pool.submit(lambda:None)
    finally:
        release.set();pool.shutdown()
    assert running.result()=='finished'


@pytest.mark.parametrize('version',[(6,1,7601),(6,2,9200),(6,3,9600)])
def test_legacy_ble_rejects_before_backend_import(monkeypatch,version):
    from app.transports import ble_transport as module
    monkeypatch.setattr(capabilities,'windows_version',lambda:version)
    transport=module.BleTransport();errors=[];transport.on_error=errors.append
    assert transport.scan()==[]
    assert transport.connect(SimpleNamespace(address='test')) is False
    assert errors==[capabilities.BLE_UNAVAILABLE]*2
    assert transport._client is None


def test_modern_ble_scanner_still_uses_backend(monkeypatch):
    import sys
    from app.transports.ble_transport import BleTransport
    monkeypatch.setattr(capabilities,'windows_version',lambda:(10,0,19045))
    class Scanner:
        @staticmethod
        async def discover(timeout):
            assert timeout==4.0
            return [SimpleNamespace(name='Patroller',address='device',rssi=-40)]
    monkeypatch.setitem(sys.modules,'bleak',SimpleNamespace(BleakScanner=Scanner))
    devices=BleTransport().scan()
    assert len(devices)==1 and devices[0].address=='device'


def test_missing_copernicus_is_actionable_and_does_not_import_sdk(monkeypatch):
    from app.nav.maritime.adapters import copernicus as module
    from app.nav.maritime.adapters.base import SourceConfig
    from app.nav.maritime.adapters.provider_common import ProviderUnavailable
    from app.nav.maritime.area_controller import OperatingArea
    monkeypatch.setattr(module,'copernicus_available',lambda:False)
    adapter=module.CopernicusAdapter(SourceConfig('copernicus_wave','https://example.invalid'),'wave','dataset','user','password')
    with pytest.raises(ProviderUnavailable,match='Copernicus Marine data is unavailable'):
        adapter.fetch(OperatingArea(22,91,5))


def test_loopback_resources_restrict_origin_host_token_and_traversal():
    from app.nav.legacy_resources import LegacyResourceServer
    server=LegacyResourceServer(SimpleNamespace())
    try:
        with urlopen(server.url,timeout=3) as response:
            html=response.read()
            assert b'MapLibre' in html and server.base.encode() in html
        with urlopen(server.base+'map/assets/qwebchannel.js',timeout=3) as response:
            assert b'QWebChannel' in response.read()
        for request in [Request(server.origin+'/wrong/map/index.html'),
                        Request(server.url,headers={'Origin':'https://evil.invalid'}),
                        Request(server.url,headers={'Host':'evil.invalid'}),
                        Request(server.base+'map/../nav.js')]:
            with pytest.raises(HTTPError) as error:urlopen(request,timeout=3)
            assert error.value.code in (403,404)
    finally:server.close()
    assert not server.thread.is_alive()
