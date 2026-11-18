"""Versioned package validation, staging and atomic activation pointers."""
from app.core.compat import is_relative_to, remove_suffix
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from functools import wraps
import time
from .mbtiles import MBTiles, MapPackageError, bounds

ROLES = ('overview_file', 'basemap_file', 'bathymetry_file')


def regional_transaction(method):
    @wraps(method)
    def locked(self,*args,**kwargs):
        with self._region_lock():return method(self,*args,**kwargs)
    return locked


def safe_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or name.startswith('/'):
        return False
    for part in name.split('/'):
        if not part or part in ('.','..') or part.endswith((' ','.')) or any(ord(c)<32 or c in '<>"|?*' for c in part):
            return False
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            return False
    return True


def safe_file(root, name):
    if not safe_name(name):
        raise MapPackageError('Unsafe package path')
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not is_relative_to(path, root) or not path.is_file():
        raise MapPackageError(f'Missing/unsafe package file: {name}')
    return path


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@dataclass
class Package:
    root: Path
    manifest: dict

    def files(self):
        return {**{remove_suffix(role, '_file'): self.manifest[role] for role in ROLES if self.manifest.get(role)},
                **{f'detail-{i}': name for i, name in enumerate(self.manifest.get('detail_files', []))},
                **{f'satellite-{i}': name for i, name in enumerate(self.manifest.get('optional_satellite_files', []))}}


def validate_package(root, verify_checksums=True):
    root = Path(root).resolve()
    try:
        manifest_path = safe_file(root, 'manifest.json')
        if manifest_path.stat().st_size > 1024 * 1024:
            raise MapPackageError('Manifest too large')
        m = json.loads(manifest_path.read_text(encoding='utf-8'))
        required = ('package_id', 'name', 'revision', 'created_at', 'region', 'bounds', 'minzoom', 'maxzoom', 'basemap_file', 'style_revision', 'attribution', 'checksums')
        if not isinstance(m, dict) or type(m.get('schema_version')) is not int or m['schema_version'] != 1 or any(k not in m for k in required):
            raise MapPackageError('Unsupported/incomplete manifest')
        for key in ('package_id', 'revision'):
            if not isinstance(m[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', m[key]):
                raise MapPackageError(f'Invalid {key}')
        for key in ('name', 'created_at', 'region', 'style_revision', 'attribution'):
            if not isinstance(m[key], str) or not m[key].strip():
                raise MapPackageError(f'Invalid {key}')
        from datetime import datetime
        if datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')).tzinfo is None:
            raise MapPackageError('created_at needs a UTC offset')
        bounds(m['bounds'])
        if any(type(m[k]) is not int for k in ('minzoom', 'maxzoom')) or not 0 <= m['minzoom'] <= m['maxzoom'] <= 22:
            raise MapPackageError('Invalid manifest zoom range')
        for key in ('detail_files', 'optional_satellite_files', 'asset_files'):
            if not isinstance(m.get(key, []), list):
                raise MapPackageError(f'Invalid {key}')
        package = Package(root, m)
        files = package.files()
        if not files.get('basemap'):
            raise MapPackageError('Basemap is required')
        for role, name in files.items():
            path = safe_file(root, name)
            if path.suffix.lower() != '.mbtiles':
                raise MapPackageError('Tiles must be extracted MBTiles')
            reader = MBTiles(path, 0)
            try:
                vector = reader.format in ('pbf', 'mvt')
                if vector != (role in ('basemap', 'overview') or role.startswith('detail-')):
                    raise MapPackageError('Vector/raster role mismatch')
                if vector:
                    from .schemas import vector_schema
                    vector_schema(reader.metadata,m.get('vector_schemas',{}).get(role))
                if role == 'basemap' and (tuple(m['bounds']) != reader.bounds or m['minzoom'] != reader.minzoom or m['maxzoom'] != reader.maxzoom):
                    raise MapPackageError('Manifest coverage differs from basemap metadata')
            finally:
                reader.close()
        all_names = list(files.values()) + m.get('asset_files', [])
        if not isinstance(m['checksums'], dict) or set(m['checksums']) != set(all_names):
            raise MapPackageError('Checksums must cover exactly all package assets')
        for name in all_names:
            path = safe_file(root, name)
            expected = m['checksums'][name]
            if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                raise MapPackageError('Invalid SHA256')
            if verify_checksums and checksum(path) != expected:
                raise MapPackageError(f'Checksum mismatch: {name}')
        return package
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        if isinstance(exc, MapPackageError):
            raise
        raise MapPackageError(f'Invalid package: {exc}') from exc


def default_store():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'GDS VTS/maps'


class PackageManager:
    def __init__(self, store=None):
        self.store = Path(store) if store else default_store()

    @contextmanager
    def _region_lock(self):
        """Serialize short registry mutations across the installer and NAV UI."""
        self.store.mkdir(parents=True,exist_ok=True)
        with (self.store/'.regions.lock').open('a+b') as stream:
            if stream.tell()==0:stream.write(b'0');stream.flush()
            if os.name=='nt':
                import msvcrt
                for attempt in range(200):
                    try:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);break
                    except OSError:
                        if attempt==199:raise MapPackageError('Regional registry is busy')
                        time.sleep(.025)
                try:yield
                finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX)
                try:yield
                finally:fcntl.flock(stream,fcntl.LOCK_UN)

    def _pointer(self):
        try:
            with (self.store / 'active.json').open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                return {}
            pointer = json.loads(raw)
            if not isinstance(pointer, dict):
                return {}
            # Treat damaged registry fields as absent. A malformed previous
            # revision must not hide a valid current package or break startup.
            return {key: value for key in ('current', 'previous')
                    if isinstance(value := pointer.get(key), str)
                    and re.fullmatch('[a-f0-9]{32}', value)}
        except (OSError, ValueError):
            return {}

    def _resolve(self, revision):
        if not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{32}', revision):
            raise MapPackageError('Invalid installed revision')
        return self.store / 'revisions' / revision

    def _activate(self, current, previous):
        self.store.mkdir(parents=True, exist_ok=True)
        temp = self.store / f'.active-{uuid.uuid4().hex}.json'
        try:
            with temp.open('w', encoding='utf-8') as stream:
                json.dump({'current': current, 'previous': previous}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.store / 'active.json')
        finally:
            temp.unlink(missing_ok=True)

    def active(self):
        pointer = self._pointer()
        if pointer.get('current'):
            return validate_package(self._resolve(pointer['current']), verify_checksums=False)
        return None

    def install(self, source, activate=True):
        self.store.mkdir(parents=True, exist_ok=True)
        revision = uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix='.staging-', dir=self.store) as temp:
            stage = Path(temp) / 'package'
            source = Path(source).resolve(strict=True)
            if source.is_dir():
                if is_relative_to(self.store.resolve(), source):
                    raise MapPackageError('Source must not contain installed map storage')
                # Validate before copying and reject links (including Windows junctions).
                validate_package(source)
                if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()) for p in source.rglob('*')):
                    raise MapPackageError('Package links are not supported')
                shutil.copytree(source, stage)
            else:
                if source.suffix.lower() != '.gdsmap':
                    raise MapPackageError('Expected folder or .gdsmap archive')
                stage.mkdir()
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if len(entries) > 20000 or sum(e.file_size for e in entries) > 100 * 1024**3:
                        raise MapPackageError('Archive exceeds package limits')
                    seen = set()
                    for entry in entries:
                        name = entry.filename
                        if name.casefold() in seen or not safe_name(remove_suffix(name, '/')) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                            raise MapPackageError('Unsafe archive entry')
                        seen.add(name.casefold())
                    archive.extractall(stage)
            validate_package(stage)
            destination = self._resolve(revision)
            destination.parent.mkdir(exist_ok=True)
            os.replace(stage, destination)
            if activate:self._activate(revision, self._pointer().get('current'))
        return validate_package(destination, verify_checksums=False)

    def regional_index(self):
        """Independent region pointers; the legacy accepted active pointer stays intact."""
        self.invalid_regions={}
        try:
            path=self.store/'regions.json'
            if path.stat().st_size>1024*1024:raise ValueError()
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError()
            result={}
            for key,entry in data.items():
                if not isinstance(entry,dict):self.invalid_regions[key]='Invalid registry entry';continue
                try:package=validate_package(self._resolve(entry.get('current')),verify_checksums=False)
                except (MapPackageError,OSError) as error:self.invalid_regions[key]=str(error);continue
                if key==package.manifest['package_id']:
                    result[key]={**entry,'enabled':entry.get('enabled') is not False}
                else:self.invalid_regions[key]='Regional package ID mismatch'
            return result
        except (OSError,ValueError,TypeError):return {}

    def _save_regions(self, data):
        self.store.mkdir(parents=True,exist_ok=True)
        temp=self.store/('.regions-'+uuid.uuid4().hex+'.json')
        try:
            with temp.open('w',encoding='utf-8') as stream:
                json.dump(data,stream);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.store/'regions.json')
        finally:temp.unlink(missing_ok=True)

    def installed_regions(self, enabled_only=False):
        entries=self.regional_index();packages={}
        legacy=self.discover()
        if legacy:packages[legacy.manifest['package_id']]=legacy
        for key,entry in entries.items():
            if enabled_only and not entry['enabled']:
                packages.pop(key,None);continue
            package=validate_package(self._resolve(entry['current']),verify_checksums=False)
            package.manifest={**package.manifest,'enabled':entry['enabled'],'priority':entry.get('priority',100)}
            packages[key]=package
        return list(packages.values())

    def install_region(self, source, priority=100):
        package=self.install(source,activate=False)
        return self._register_region(package,priority)

    @regional_transaction
    def _register_region(self, package, priority):
        entries=self.regional_index();key=package.manifest['package_id'];old=entries.get(key,{})
        entries[key]={'current':package.root.name,'previous':old.get('current'),
                      'enabled':old.get('enabled',True),'priority':int(priority)}
        self._save_regions(entries)
        return package

    @regional_transaction
    def set_region_enabled(self, key, enabled):
        entries=self.regional_index()
        if key not in entries:
            package=next((p for p in self.installed_regions() if p.manifest['package_id']==key),None)
            if not package or package.root.parent!=self.store/'revisions':raise MapPackageError('Region not installed in registry')
            entries[key]={'current':package.root.name,'previous':None,'priority':100}
        entries[key]['enabled']=bool(enabled);self._save_regions(entries)

    @regional_transaction
    def rollback_region(self, key):
        entries=self.regional_index();entry=entries.get(key,{})
        previous=entry.get('previous')
        if not previous:raise MapPackageError('No previous regional revision')
        package=validate_package(self._resolve(previous))
        if package.manifest['package_id']!=key:raise MapPackageError('Regional revision mismatch')
        entry['current'],entry['previous']=previous,entry['current'];self._save_regions(entries)

    @regional_transaction
    def remove_region(self, key):
        entries=self.regional_index();entry=entries.get(key)
        if not entry:raise MapPackageError('Region not registered')
        protected=set(self._pointer().values())
        protected.update(v for k,e in entries.items() if k!=key for v in (e.get('current'),e.get('previous')) if isinstance(v,str))
        targets={self._resolve(v).resolve() for v in (entry.get('current'),entry.get('previous')) if v}
        root=(self.store/'revisions').resolve()
        if any(p.name in protected or p.parent!=root for p in targets):raise MapPackageError('Accepted active revisions are protected')
        if any(p.exists() and validate_package(p,verify_checksums=False).manifest['package_id']!=key for p in targets):raise MapPackageError('Regional revision mismatch')
        del entries[key];self._save_regions(entries)
        for path in targets:
            if path.exists():shutil.rmtree(path)

    def rollback(self):
        pointer = self._pointer()
        previous = pointer.get('previous')
        if not previous:
            raise MapPackageError('No previous package')
        validate_package(self._resolve(previous))
        self._activate(previous, pointer.get('current'))
        return self.active()

    def discover(self, selection=''):
        paths = os.environ.get('GDS_MAP_PACKAGE_PATH', '').split(os.pathsep)
        candidates = [Path(p) for p in paths if p] + [Path(__file__).resolve().parents[3] / 'data/maps/default']
        active = None
        try:
            active = self.active()
        except MapPackageError:
            pass
        packages = []
        if active:
            packages.append(active)
        for path in candidates:
            try:
                packages.append(validate_package(path, verify_checksums=False))
            except MapPackageError:
                pass
        preference = os.environ.get('GDS_MAP_DEFAULT_PACKAGE') or selection
        return next((p for p in packages if p.manifest['package_id'] == preference), packages[0] if packages else None)
