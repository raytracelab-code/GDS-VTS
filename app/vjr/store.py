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
        target = folder/('journey-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        fd, temp = tempfile.mkstemp(prefix='.vjr-archive-', suffix='.json', dir=str(folder))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.report, stream, ensure_ascii=False); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, str(target))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return target

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
