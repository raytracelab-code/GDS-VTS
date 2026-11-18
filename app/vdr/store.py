"""Atomic, versioned local storage with bounded report-level history."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile

from .model import new_report, normalize, rollover, validate


class ReportStore:
    def __init__(self, path, today=None, identity=None):
        self.path = Path(path)
        self.today = today or date.today().isoformat()
        self.current = self.today
        self.identity = identity or {}
        self.reports = {}
        self.layout = 'scroll'
        self.custom_ranks = []
        self.undo_stack, self.redo_stack = [], []
        self.load_error = ''
        if self.path.exists():
            try:
                if self.path.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError('Report store exceeds size limit')
                data = json.loads(self.path.read_text(encoding='utf-8'))
                for day, report in data['reports'].items():
                    normalized = normalize(report)
                    if normalized['meta']['date'] != day:
                        raise ValueError('Stored report date mismatch')
                    self.reports[day] = normalized
                self.layout = 'steps' if data.get('layout') == 'steps' else 'scroll'
                self.custom_ranks = [s for s in data.get('customRanks', []) if isinstance(s, str)]
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.reports = {}
                self.load_error = 'Could not load report store: ' + str(error)
        self.select(self.today)

    @property
    def report(self):
        return self.reports[self.current]

    def select(self, day):
        parsed = date.fromisoformat(day)
        delta = (date.fromisoformat(self.today) - parsed).days
        if delta < 0:
            raise ValueError('Report date cannot be in the future')
        if day not in self.reports:
            previous = (parsed-timedelta(days=1)).isoformat()
            self.reports[day] = rollover(self.reports[previous], day) if previous in self.reports else new_report(day, self.identity)
        self.current = day

    def mutate(self, action, finalized=False):
        previous = deepcopy(self.report)
        updated = deepcopy(previous)
        action(updated)
        if not finalized:
            updated.update(finalized=False, finalizedAt='')
        if updated == previous:
            return
        self.undo_stack.append((self.current, previous))
        self.undo_stack = self.undo_stack[-100:]
        self.redo_stack.clear()
        self.reports[self.current] = updated

    def _history(self, source, destination):
        if not source:
            return False
        day, report = source.pop()
        destination.append((day, deepcopy(self.reports[day])))
        self.current = day
        self.reports[day] = report
        return True

    def undo(self):
        return self._history(self.undo_stack, self.redo_stack)

    def redo(self):
        return self._history(self.redo_stack, self.undo_stack)

    def finalize(self):
        errors = validate(self.report)
        if errors:
            return errors
        self.mutate(lambda r: r.update(finalized=True, finalizedAt=datetime.now(timezone.utc).isoformat()), finalized=True)
        return []

    def import_report(self, report):
        imported = normalize(report)
        day = imported['meta']['date']
        self.select(day)
        self.mutate(lambda r: (r.clear(), r.update(imported)), finalized=True)

    def save(self):
        # Never overwrite an unreadable original with a newly empty workspace.
        if self.load_error:
            raise OSError(self.load_error + '; original file preserved')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.vdr-', suffix='.json', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(dict(schemaVersion=1, reports=self.reports, current=self.current,
                               layout=self.layout, customRanks=self.custom_ranks), stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
