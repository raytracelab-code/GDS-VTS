"""User backup / restore of GDS VTS work (docs/backup-and-restore.md).

Backup ZIP layout (format 1):
  manifest.json                 format, app version, created, file list with SHA-256
  data/vdr/reports.json         VDR store
  data/vjr/report.json          current VJR journey
  data/vjr/archive/*.json       archived voyages
  data/vjr/attachments/**       VJR photos referenced by journeys
  settings.json                 vessel/client identity and app preferences (QSettings)

Restore validates everything first, saves the current data as a safety backup, then replaces
files atomically. On any failure the existing data is left untouched and the archive is kept
for diagnostics. Caches, map tiles, logs and executables are never included.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

FORMAT = 'gds-vts-backup'
FORMAT_VERSION = 1
MAX_BACKUP_BYTES = 2 * 1024 ** 3
DATA_PATTERNS = ('vdr/reports.json', 'vjr/report.json', 'vjr/archive/*.json', 'vjr/attachments/**/*')
SETTINGS_PREFIXES = ('vessel/', 'nav/', 'app/')


class BackupError(ValueError):
    """User-facing backup/restore problem; existing data is never changed when raised."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def data_files(root):
    root = Path(root)
    found = []
    for pattern in DATA_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not path.name.startswith('.') and '.damaged-' not in path.name:
                found.append(path)
    return found


def create_backup(destination, data_root, settings_values=None):
    """Write a backup ZIP atomically; returns the manifest dict."""
    data_root, destination = Path(data_root), Path(destination)
    entries, payload = [], {}
    for path in data_files(data_root):
        name = 'data/' + path.relative_to(data_root).as_posix()
        content = path.read_bytes(); payload[name] = content
        entries.append(dict(path=name, bytes=len(content), sha256=_sha(content)))
    settings = {k: v for k, v in (settings_values or {}).items() if k.startswith(SETTINGS_PREFIXES)}
    settings_bytes = json.dumps(settings, indent=2, sort_keys=True).encode('utf-8'); payload['settings.json'] = settings_bytes
    entries.append(dict(path='settings.json', bytes=len(settings_bytes), sha256=_sha(settings_bytes)))
    from app.version import __version__, edition
    manifest = dict(format=FORMAT, format_version=FORMAT_VERSION, app_version=__version__, edition=edition(),
                    created=datetime.now(timezone.utc).isoformat(timespec='seconds'), files=entries)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.gds-backup-', suffix='.zip', dir=str(destination.parent)); os.close(fd)
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            for name, content in payload.items():
                archive.writestr(name, content)
        os.replace(temp, str(destination))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return manifest


def _safe_member(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and '..' not in path.parts and (name in ('manifest.json', 'settings.json') or name.startswith('data/'))


def inspect_backup(path):
    """Validate a backup and return a summary dict. Raises BackupError with a plain message."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_BACKUP_BYTES:
            raise BackupError('The backup file is larger than 2 GB and was not opened.')
        archive = zipfile.ZipFile(str(path))
    except (OSError, zipfile.BadZipFile) as error:
        raise BackupError('This file is not a GDS VTS backup (it is not a readable ZIP archive).') from error
    with archive:
        names = archive.namelist()
        if 'manifest.json' not in names:
            raise BackupError('This ZIP is not a GDS VTS backup (manifest.json is missing).')
        try:
            manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as error:
            raise BackupError('The backup manifest is damaged.') from error
        if manifest.get('format') != FORMAT or manifest.get('format_version') != FORMAT_VERSION:
            raise BackupError('This backup was made by an unsupported program or version.')
        unsafe = [n for n in names if not _safe_member(n)]
        if unsafe:
            raise BackupError('The backup contains unexpected files and was rejected: ' + ', '.join(unsafe[:3]))
        listed = {entry['path']: entry for entry in manifest.get('files', [])}
        for name, entry in listed.items():
            if name not in names:
                raise BackupError(f'The backup is incomplete: {name} is missing.')
            if _sha(archive.read(name)) != entry.get('sha256'):
                raise BackupError(f'The backup is damaged: {name} does not match its checksum.')
        summary = dict(manifest=manifest, vdr_reports=0, vjr_current=False, vjr_archived=0, photos=0, settings=0)
        from app.vdr.model import normalize as normalize_vdr
        from app.vjr.model import normalize as normalize_vjr
        try:
            if 'data/vdr/reports.json' in listed:
                data = json.loads(archive.read('data/vdr/reports.json').decode('utf-8'))
                for day, report in data['reports'].items():
                    normalize_vdr(report)
                summary['vdr_reports'] = len(data['reports'])
                summary['vdr_days'] = sorted(data['reports'])
            if 'data/vjr/report.json' in listed:
                normalize_vjr(json.loads(archive.read('data/vjr/report.json').decode('utf-8'))); summary['vjr_current'] = True
            for name in listed:
                if name.startswith('data/vjr/archive/'):
                    normalize_vjr(json.loads(archive.read(name).decode('utf-8'))); summary['vjr_archived'] += 1
                elif name.startswith('data/vjr/attachments/'):
                    summary['photos'] += 1
            if 'settings.json' in listed:
                summary['settings'] = len(json.loads(archive.read('settings.json').decode('utf-8')))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise BackupError(f'The backup contains report data that cannot be read ({error}).') from error
    return summary


def describe(summary):
    m = summary['manifest']
    days = summary.get('vdr_days') or []
    span = f' ({days[0]} to {days[-1]})' if days else ''
    return (f"Backup from {m['created'][:16].replace('T', ' ')} UTC · GDS VTS {m['app_version']} {m['edition']}\n"
            f"• VDR reports: {summary['vdr_reports']}{span}\n"
            f"• VJR current journey: {'yes' if summary['vjr_current'] else 'no'} · archived voyages: {summary['vjr_archived']} · photos: {summary['photos']}\n"
            f"• Settings (vessel & client, preferences): {summary['settings']}")


def restore_backup(path, data_root, safety_dir, apply_settings=None):
    """Validate, save a safety backup of the current data, then replace the data files.

    Returns (summary, safety_backup_path). On failure the current data is unchanged, the failed
    archive is copied to ``safety_dir`` for diagnostics and BackupError is raised."""
    path, data_root, safety_dir = Path(path), Path(data_root), Path(safety_dir)
    safety_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    try:
        summary = inspect_backup(path)
    except BackupError:
        _keep_failed(path, safety_dir, stamp); raise
    current_settings = apply_settings('read') if apply_settings else {}
    safety = safety_dir/f'before-restore-{stamp}.zip'
    create_backup(safety, data_root, current_settings)
    staging = Path(tempfile.mkdtemp(prefix='.gds-restore-', dir=str(data_root.parent if data_root.parent.exists() else safety_dir)))
    try:
        with zipfile.ZipFile(str(path)) as archive:
            names = [n for n in archive.namelist() if n.startswith('data/')]
            for name in names:
                target = staging/PurePosixPath(name).relative_to('data')
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(archive.read(name))
            settings = json.loads(archive.read('settings.json').decode('utf-8')) if 'settings.json' in archive.namelist() else {}
        folders = [f for f in ('vdr', 'vjr') if (staging/f).exists()]
        # Phase 1: copy every folder next to the live data. A failure here changes nothing.
        incoming = {}
        try:
            for folder in folders:
                incoming[folder] = data_root/f'.{folder}-incoming-{stamp}'
                shutil.copytree(str(staging/folder), str(incoming[folder]))
        except OSError:
            for path in incoming.values():
                shutil.rmtree(str(path), ignore_errors=True)
            raise
        # Phase 2: swap folders by rename; roll every swap back if any fails (all-or-nothing).
        swapped = []
        try:
            for folder in folders:
                live, old = data_root/folder, data_root/f'.{folder}-replaced-{stamp}'
                if live.exists():
                    os.replace(str(live), str(old))
                swapped.append((folder, old))
                os.replace(str(incoming[folder]), str(live))
        except OSError:
            for folder, old in reversed(swapped):
                live = data_root/folder
                if live.exists() and old.exists():
                    os.replace(str(live), str(incoming[folder]))
                if old.exists():
                    os.replace(str(old), str(live))
            for path in incoming.values():
                shutil.rmtree(str(path), ignore_errors=True)
            raise
        # Replaced folders are kept (not deleted): they may hold .bak/.damaged copies for support.
        if apply_settings and settings:
            apply_settings(settings)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        _keep_failed(path, safety_dir, stamp)
        raise BackupError(f'Restore did not complete ({error}). Your current data was kept; a safety copy is in {safety}.') from error
    finally:
        shutil.rmtree(str(staging), ignore_errors=True)
    return summary, safety


def _keep_failed(path, safety_dir, stamp):
    try:
        shutil.copy2(str(path), str(safety_dir/f'failed-restore-{stamp}-{Path(path).name}'))
    except OSError:
        pass


def settings_snapshot(settings):
    """QSettings -> plain dict of the keys a backup carries."""
    return {key: settings.value(key) for key in settings.allKeys() if key.startswith(SETTINGS_PREFIXES)}


def apply_settings_to(settings):
    def apply(values):
        if values == 'read':
            return settings_snapshot(settings)
        for key, value in values.items():
            if key.startswith(SETTINGS_PREFIXES):
                settings.setValue(key, value)
        settings.sync()
    return apply
