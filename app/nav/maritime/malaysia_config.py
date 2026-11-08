"""Shared Malaysia layer contract, read from the customer dataset manifest."""
import json
import os
from pathlib import Path

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[3] / 'data' / 'maritime' / 'malaysia'


def dataset_directory(env=None):
    env = os.environ if env is None else env
    return Path(env.get('GDS_MALAYSIA_GIS_PATH') or DEFAULT_DIRECTORY).expanduser().resolve()


def read_manifest(directory=None):
    directory = Path(directory or dataset_directory()).resolve()
    path = directory / 'manifest.json'
    # An external directory can reuse the bundled layer contract.
    if not path.exists():
        path = DEFAULT_DIRECTORY / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    if manifest.get('dataset_id') != 'malaysia_offshore_gis' or not isinstance(manifest.get('layers'), list):
        raise ValueError('Invalid Malaysia GIS manifest')
    ids = set()
    for layer in manifest['layers']:
        key = layer['dataset_id']
        if not key.startswith('malaysia_') or key in ids:
            raise ValueError('Invalid or duplicate Malaysia layer ID')
        ids.add(key)
        candidate = (directory / layer['filename']).resolve()
        if not candidate.is_relative_to(directory):
            raise ValueError('Malaysia GIS filename escapes dataset directory')
    return manifest
