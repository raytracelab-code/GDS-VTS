"""Online NAV startup must never depend on production offline assets."""
import json
import shutil
import subprocess
from pathlib import Path
from app.nav.offline_maps.manager import PackageManager
from app.nav.online_map import online_config, PRIMARY_REGION


def test_online_startup_never_discovers_packages(qapp, monkeypatch):
    from app.nav.web_scheme import GdsMapSchemeHandler
    monkeypatch.delenv('GDS_MAP_SOURCE', raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Online startup must not scan offline packages')
    monkeypatch.setattr(PackageManager, 'discover', forbidden)
    monkeypatch.setattr(PackageManager, 'installed_regions', forbidden)
    handler = GdsMapSchemeHandler()
    try:
        assert handler.config['preferred_source'] == 'online'
        assert handler.package is None and not handler.readers
        assert not handler.config['installed']
        assert 'Bangladesh' in handler.config['primary_region']
    finally:
        handler.close()


def test_online_region_is_context_without_bounds():
    config = online_config()
    assert len(PRIMARY_REGION) == 11
    assert 'bounds' not in config and 'initial_bounds' not in config
    assert config['style']['sources'] == {}
    assert config['style']['layers'][0]['metadata']['gds:role'] == 'WATER'


def test_empty_registry_has_no_stale_packages(tmp_path):
    (tmp_path/'active.json').write_text('{}')
    (tmp_path/'regions.json').write_text('{}')
    manager = PackageManager(tmp_path)
    assert manager.active() is None
    assert manager.regional_index() == {}
    assert manager.installed_regions() == []


from test_nav_visual import visual_payload


def test_online_runtime_success_failure_and_palette(visual_payload):
    node = shutil.which('node')
    assert node, 'Node required for NAV runtime contracts'
    result = subprocess.run([node, 'tests/nav_online_runtime.cjs'],
                            input=json.dumps({'config': online_config(), 'maritime': json.loads(visual_payload)}), text=True,
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
