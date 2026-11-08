"""Offline map preparation tools. Never downloads or builds tiles implicitly."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.nav.offline_maps.mbtiles import MBTiles
from app.nav.offline_maps.manager import Package, PackageManager, checksum, validate_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('inspect', 'validate', 'install'):
        p = sub.add_parser(command)
        p.add_argument('path', type=Path)
        if command == 'install':
            p.add_argument('--store', type=Path)
    rollback = sub.add_parser('rollback')
    rollback.add_argument('--store', type=Path)
    build = sub.add_parser('build-manifest')
    build.add_argument('folder', type=Path)
    build.add_argument('--id', required=True)
    build.add_argument('--name', required=True)
    build.add_argument('--revision', required=True)
    build.add_argument('--region', required=True)
    build.add_argument('--basemap', required=True)
    build.add_argument('--overview')
    build.add_argument('--bathymetry')
    build.add_argument('--detail', action='append', default=[])
    build.add_argument('--satellite', action='append', default=[])
    build.add_argument('--asset', action='append', default=[])
    build.add_argument('--attribution', required=True)
    args = parser.parse_args()
    if args.command == 'inspect':
        reader = MBTiles(args.path, 0)
        try:
            print(json.dumps(reader.metadata, indent=2))
        finally:
            reader.close()
    elif args.command == 'validate':
        if args.path.is_dir():
            package = validate_package(args.path)
            print(json.dumps(package.manifest, indent=2))
        else:
            reader = MBTiles(args.path, 0)
            reader.close()
            print('MBTiles valid')
    elif args.command in ('install', 'rollback'):
        manager = PackageManager(args.store)
        package = manager.install(args.path) if args.command == 'install' else manager.rollback()
        print(json.dumps({'root': str(package.root), 'package_id': package.manifest['package_id'], 'revision': package.manifest['revision']}, indent=2))
        print('Restart NAV to load the activated package. Existing map sessions remain stable.')
    else:
        from app.nav.offline_maps.manager import safe_file
        reader = MBTiles(safe_file(args.folder, args.basemap), 0)
        try:
            m = dict(schema_version=1, package_id=args.id, name=args.name, revision=args.revision,
                     created_at=datetime.now(timezone.utc).isoformat(), region=args.region,
                     bounds=list(reader.bounds), minzoom=reader.minzoom, maxzoom=reader.maxzoom,
                     basemap_file=args.basemap, overview_file=args.overview, bathymetry_file=args.bathymetry,
                     detail_files=args.detail, optional_satellite_files=args.satellite, asset_files=args.asset,
                     style_revision='gds-maritime-1', attribution=args.attribution)
        finally:
            reader.close()
        package = Package(args.folder, m)
        m['checksums'] = {name: checksum(safe_file(args.folder, name)) for name in list(package.files().values()) + args.asset}
        target = args.folder / 'manifest.json'
        if target.exists():
            raise ValueError('manifest.json already exists; choose a new package folder/revision')
        target.write_text(json.dumps(m, indent=2), encoding='utf-8')
        try:
            validate_package(args.folder)
        except Exception:
            target.unlink()
            raise
        print(target)


if __name__ == '__main__':
    main()
