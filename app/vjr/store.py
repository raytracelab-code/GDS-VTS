"""Atomic autosave and bounded snapshot undo/redo, matching the VDR pattern.

Recovery (GDS-AUDIT-003): an unreadable ``report.json`` is preserved as
``report.json.damaged-<timestamp>``; the last-known-good ``report.json.bak`` is
loaded when valid, otherwise a new empty report is started. The user is told
which happened (``notices``). The app never stays in a no-save dead end.
"""
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from .model import new_report, normalize

BACKUP_INTERVAL = 15 * 60
MAX_STORE_BYTES = 32 * 1024 * 1024


class VjrStore:
    def __init__(self, path):
        self.path = Path(path)
        self.report = new_report()
        self.undo_stack, self.redo_stack = [], []
        self.load_error = ''
        self.notices = []
        self.recovered = False   # True after backup/new-file recovery: photo clean-up is paused
        self._last_backup = 0.0
        if self.path.exists():
            try:
                self.report = self._read(self.path)
                self._backup(force=True)
            except (OSError, ValueError, TypeError, KeyError) as error:
                self._recover(error)

    def _read(self, path):
        if path.stat().st_size > MAX_STORE_BYTES:
            raise ValueError('VJR store exceeds 32 MB')
        return normalize(json.loads(path.read_text(encoding='utf-8')))

    def _recover(self, error):
        self.recovered = True
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        damaged = self.path.with_name(f'{self.path.name}.damaged-{stamp}')
        try:
            shutil.copy2(self.path, damaged)
        except OSError:
            # Could not preserve the original: refuse to overwrite it.
            self.load_error = (f'Could not load the VJR file ({error}). The file was not changed and saving is paused. '
                               'Close the app, copy the file to a safe place and contact support.')
            return
        backup = self.path.with_name(self.path.name + '.bak')
        try:
            self.report = self._read(backup)
            when = datetime.fromtimestamp(backup.stat().st_mtime).strftime('%d %b %Y %H:%M')
            self.notices.append(f'The VJR file could not be read ({error}). The journey was restored from the backup taken '
                                f'{when}; edits after that time are missing. The damaged file was kept as {damaged.name}.')
        except (OSError, ValueError, TypeError, KeyError):
            self.report = new_report()
            self.notices.append(f'The VJR file could not be read ({error}) and no usable backup exists. A new empty '
                                f'journey was started. The damaged file was kept as {damaged.name} for support.')

    def mutate(self, action):
        before = deepcopy(self.report)
        after = deepcopy(before)
        action(after)
        if before == after:
            return
        self.save(after)
        self.undo_stack.append(before)
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.report = after

    def _history(self, source, destination):
        if not source:
            return False
        self.save(source[-1])
        destination.append(deepcopy(self.report))
        self.report = source.pop()
        return True

    def undo(self):
        return self._history(self.undo_stack,self.redo_stack)

    def redo(self):
        return self._history(self.redo_stack,self.undo_stack)

    def archive(self):
        """Write the current journey to vjr/archive/<timestamp>.json (atomic) and return the path."""
        folder = self.path.parent/'archive'
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target, n = folder/('journey-' + stamp + '.json'), 1
        while target.exists():  # never overwrite an earlier archive made in the same second
            n += 1; target = folder/(f'journey-{stamp}-{n}.json')
        fd, temp = tempfile.mkstemp(prefix='.vjr-archive-', suffix='.json', dir=str(folder))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.report, stream, ensure_ascii=False); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, str(target))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return target

    def archived_journeys(self):
        """Archived voyages for Voyage History, newest archive first (ordered by the archive
        timestamp in the file name, never by file-system order). Reads vjr/archive only."""
        folder = self.path.parent/'archive'
        rows = []
        for path in folder.glob('journey-*.json') if folder.is_dir() else []:
            match = re.fullmatch(r'journey-(\d{8}-\d{6})(?:-(\d+))?\.json', path.name)
            if not match:
                continue
            archived = datetime.strptime(match.group(1), '%Y%m%d-%H%M%S')
            row = dict(path=path, archived=archived, sequence=int(match.group(2) or 1))
            try:
                report = self._read(path)
                departure, arrival = report['departure'], report['arrival']
                row.update(readable=True, vessel=report['meta'].get('vessel', ''), departure_date=departure.get('departure_date', ''),
                           departure_location=departure.get('departure_location', ''),
                           destination=departure.get('destination', ''), status=journey_status(report))
            except (OSError, ValueError, TypeError, KeyError) as error:
                row.update(readable=False, vessel='', departure_date='', departure_location='', destination='',
                           status='UNREADABLE', error=str(error))
            rows.append(row)
        return sorted(rows, key=lambda r: (r['archived'], r['sequence']), reverse=True)

    def restore_archived(self, path):
        """Swap: archive the current journey, make ``path`` current, remove ``path`` from the
        archive. Both journeys stay on disk. Undo history is cleared (stated in the UI)."""
        restored = self._read(Path(path))
        archived = self.archive()
        self.save(restored)
        self.report = restored
        self.undo_stack.clear(); self.redo_stack.clear()
        os.unlink(str(path))
        return archived

    def _backup(self, force=False):
        if not self.path.exists() or (not force and time.time() - self._last_backup < BACKUP_INTERVAL):
            return
        temp = None
        try:
            fd, temp = tempfile.mkstemp(prefix='.vjr-bak-', suffix='.json', dir=str(self.path.parent))
            os.close(fd)
            shutil.copy2(self.path, temp)
            os.replace(temp, str(self.path.with_name(self.path.name + '.bak')))
            self._last_backup = time.time()
        except OSError:
            if temp and os.path.exists(temp):
                os.unlink(temp)

    def save(self, report=None):
        if self.load_error:
            raise OSError(self.load_error)
        temp = None
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self._backup()
            fd, temp = tempfile.mkstemp(prefix='.vjr-',suffix='.json',dir=str(self.path.parent))
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(self.report if report is None else report,stream,ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp,str(self.path))
        except PermissionError as error:
            raise OSError(f'Not saved: Windows denied access to {self.path.parent}. Your previously saved journey is safe. '
                          f'Check the folder is not read-only or locked. [{error}]') from error
        except OSError as error:
            if str(error).startswith('Not saved'):
                raise
            raise OSError(f'Not saved: the VJR file could not be written ({error.strerror or error}). '
                          'Your previously saved journey is safe. Check free disk space; your next edit retries.') from error
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)


def journey_status(report):
    """Completion state shown in Voyage History."""
    if report['arrival'].get('arrival_date') or report['arrival'].get('report_date'):
        return 'ARRIVED'
    if report['departure'].get('departure_date'):
        return 'UNDER WAY'
    return 'NOT STARTED'
