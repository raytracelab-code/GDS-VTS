"""Atomic, versioned local storage with bounded report-level history.

Resilience rules (GDS-AUDIT-003):
* One invalid report is *quarantined* (kept verbatim in the file under
  ``quarantined``) instead of making every other day unreadable.
* An unreadable file is preserved as ``reports.json.damaged-<timestamp>`` and
  the last-known-good backup ``reports.json.bak`` is loaded if it is valid.
* ``reports.json.bak`` is refreshed from the current (known-good) file at most
  every ``BACKUP_INTERVAL`` seconds, so there is one backup, never a pile.
* Over-long fields are refused before they are written (never truncated).

Carry-forward rule (GDS-AUDIT-002/008): a report's openings come from the most
recent *earlier* report that the user has actually created or edited. Linked
openings follow corrections of that report; manual overrides are kept.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from .model import apply_carry_forward, new_report, normalize, rollover

BACKUP_SUFFIX = '.bak'
ACTIVITY_KEYS = ('modifiedAt', 'revision', 'reopenedAt', 'reopenCount')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
BACKUP_INTERVAL = 15 * 60
MAX_STORE_BYTES = 32 * 1024 * 1024


class StoreError(OSError):
    """User-facing storage failure. ``message`` says what happened, whether saved
    data is safe and what to do next."""


class ReportStore:
    def __init__(self, path, today=None, identity=None):
        self.path = Path(path)
        self.today = today or date.today().isoformat()
        self.current = self.today
        self.identity = identity or {}
        self.reports = {}
        self.quarantined = {}
        self.layout = 'scroll'
        self.custom_ranks = []
        self.undo_stack, self.redo_stack = [], []
        self.load_error = ''          # kept for compatibility; set only when nothing could be loaded safely
        self.notices = []             # user-facing recovery notices (shown as a banner)
        self._auto = {}               # day -> id() of an auto-created, never-edited report (derived, not persisted)
        self._last_backup = 0.0
        self.activity = {}            # day -> {modifiedAt, revision, reopenedAt, reopenCount}; persisted as 'reportActivity'
        self._load()
        self.select(self.today)

    # ----------------------------------------------------------------- loading
    def _read(self, path):
        if path.stat().st_size > MAX_STORE_BYTES:
            raise ValueError('report store exceeds the 32 MB size limit')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('reports'), dict):
            raise ValueError('file does not contain VDR reports')
        reports, quarantined = {}, dict(data.get('quarantined') or {}) if isinstance(data.get('quarantined'), dict) else {}
        for day, report in data['reports'].items():
            try:
                normalized = normalize(report)
                if normalized['meta']['date'] != day:
                    raise ValueError('stored report date does not match its key')
                reports[day] = normalized
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                quarantined[str(day)] = dict(error=str(error), data=report)
        return data, reports, quarantined

    def _preserve_damaged(self):
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = self.path.with_name(f'{self.path.name}.damaged-{stamp}')
        try:
            shutil.copy2(self.path, target)
            return target
        except OSError:
            return None

    def _load(self):
        if not self.path.exists():
            return
        backup = self.path.with_name(self.path.name + BACKUP_SUFFIX)
        try:
            data, self.reports, self.quarantined = self._read(self.path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            damaged = self._preserve_damaged()
            kept = f'The damaged file was kept as {damaged.name}.' if damaged else 'The damaged file was left in place.'
            try:
                data, self.reports, self.quarantined = self._read(backup)
                when = datetime.fromtimestamp(backup.stat().st_mtime).strftime('%d %b %Y %H:%M')
                self.notices.append(f'The VDR report file could not be read ({error}). Reports were restored from the '
                                    f'backup taken {when}; edits made after that time are missing. {kept} '
                                    'Check recent days, then continue working normally.')
            except (OSError, ValueError, KeyError, TypeError):
                self.reports, self.quarantined = {}, {}
                if damaged is None:
                    # Nothing preserved: refuse to overwrite the original.
                    self.load_error = (f'Could not load report store: {error}. The file was not changed. '
                                       'Close the app, copy the file shown below to a safe place and contact support.')
                    return
                data = {}
                self.notices.append(f'The VDR report file could not be read ({error}) and no usable backup exists. '
                                    f'{kept} A new empty report file is being used. Contact support to recover data from the damaged copy.')
        self.layout = 'steps' if data.get('layout') == 'steps' else 'scroll'
        self.custom_ranks = [s for s in data.get('customRanks', []) if isinstance(s, str)]
        activity = data.get('reportActivity', {})
        if isinstance(activity, dict):
            self.activity = {str(day): {k: v for k, v in value.items() if k in ACTIVITY_KEYS and isinstance(v, (str, int))}
                             for day, value in activity.items() if isinstance(value, dict)}
        if self.quarantined:
            days = ', '.join(sorted(self.quarantined)[:6])
            self.notices.append(f'{len(self.quarantined)} stored report(s) could not be read and were set aside ({days}). '
                                'All other days are available. The set-aside data is kept unchanged in the report file for support.')
        if not self.notices and not self.load_error:
            self._backup(force=True)

    # --------------------------------------------------------------- reporting
    @property
    def report(self):
        return self.reports[self.current]

    def is_untouched(self, day):
        """True for a day the app created automatically and nobody has edited or replaced."""
        return day in self._auto and day in self.reports and id(self.reports[day]) == self._auto[day]

    def source_day(self, day):
        """Most recent earlier report the user created or edited (skipped days allowed)."""
        earlier = [d for d in self.reports if d < day and not self.is_untouched(d)]
        return max(earlier) if earlier else None

    def refresh_carry_forward(self):
        """Re-derive linked openings for every non-finalized day, oldest first, so a
        correction to any day flows into all later days."""
        changed = False
        for day in sorted(self.reports):
            source = self.source_day(day)
            if source is None:
                continue
            if self.is_untouched(day) and self.reports[day].get('carry', {}).get('source') != source:
                # Never edited: rebuild entirely from the (new) source so crew, rows and openings all follow.
                self.reports[day] = rollover(self.reports[source], day)
                self._auto[day] = id(self.reports[day]); changed = True
                continue
            changed |= apply_carry_forward(self.reports[day], self.reports[source], source)
        return changed

    def select(self, day):
        parsed = date.fromisoformat(day)
        delta = (date.fromisoformat(self.today) - parsed).days
        if delta < 0:
            raise ValueError('Report date cannot be in the future')
        if day not in self.reports:
            source = self.source_day(day)
            self.reports[day] = rollover(self.reports[source], day) if source else new_report(day, self.identity)
            self._auto[day] = id(self.reports[day])
        self.current = day
        self.refresh_carry_forward()

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
        self._record(self.current, modifiedAt=_now())
        self._auto.pop(self.current, None)

    def _history(self, source, destination):
        if not source:
            return False
        day, report = source.pop()
        destination.append((day, deepcopy(self.reports[day])))
        self.current = day
        self.reports[day] = report
        self._auto.pop(day, None)
        return True

    def undo(self):
        return self._history(self.undo_stack, self.redo_stack)

    def redo(self):
        return self._history(self.redo_stack, self.undo_stack)

    def finalize(self, identity=None, template_check=True):
        from .validation import final_issues
        identity = self.identity if identity is None else identity
        issues = final_issues(self.report, identity, template_check=template_check)
        if issues:
            return issues
        snapshot = {k: v for k, v in (identity or {}).items() if isinstance(v, str)}
        self.mutate(lambda r: r.update(finalized=True, finalizedAt=datetime.now(timezone.utc).isoformat(),
                                       identity=snapshot), finalized=True)
        self._record(self.current, revision=int(self.activity.get(self.current, {}).get('revision', 0)) + 1)
        return []

    def reopen(self):
        """Explicit, recorded return to draft (the only way a finalized report changes)."""
        if self.report['finalized']:
            self.mutate(lambda r: r.update(finalized=False, finalizedAt=''))
            entry = self.activity.get(self.current, {})
            self._record(self.current, reopenedAt=_now(), reopenCount=int(entry.get('reopenCount', 0)) + 1)

    def _record(self, day, **values):
        self.activity.setdefault(day, {}).update(values)

    def status(self, day):
        """DRAFT, FINALIZED (Rev n when finalized again after a reopen) or REOPENED (draft after reopen)."""
        report, entry = self.reports[day], self.activity.get(day, {})
        if report['finalized']:
            revision = int(entry.get('revision', 1) or 1)
            return 'FINALIZED' + (f' · REV {revision}' if revision > 1 else '')
        return 'REOPENED · DRAFT' if entry.get('reopenCount') else 'DRAFT'

    def history(self, identity=None):
        """Stored reports for the History view, newest report date first. Reads this store only."""
        from .model import report_number
        identity = self.identity if identity is None else identity
        rows = []
        for day, report in self.reports.items():
            if self.is_untouched(day):
                continue
            entry = self.activity.get(day, {})
            snapshot = report.get('identity') or {}
            vessel = (snapshot.get('vessel') if report['finalized'] else '') or (identity or {}).get('vessel', '')
            number = report_number(report, identity or {})
            rows.append(dict(day=day, report_no=str(number) if number is not None and number >= 1 else '—', vessel=vessel or '—',
                             status=self.status(day), modified=entry.get('modifiedAt') or report.get('finalizedAt') or '',
                             openable=True))
        for day, item in self.quarantined.items():
            rows.append(dict(day=str(day), report_no='—', vessel='—', status='UNREADABLE · SET ASIDE', modified='',
                             openable=False, error=str(item.get('error', '')) if isinstance(item, dict) else ''))
        return sorted(rows, key=lambda row: row['day'], reverse=True)

    def import_report(self, report, identity=None):
        """Import a report. A report marked finalized is re-validated; if it would
        not pass today's final checks it is imported as a draft. Returns the issues."""
        from .validation import final_issues
        imported = normalize(report)
        issues = []
        if imported['finalized']:
            issues = final_issues(imported, self.identity if identity is None else identity, template_check=False, check_identity=False)
            if issues:
                imported.update(finalized=False, finalizedAt='')
        day = imported['meta']['date']
        self.select(day)
        self.mutate(lambda r: (r.clear(), r.update(imported)), finalized=True)
        return issues

    # ------------------------------------------------------------------ saving
    def _backup(self, force=False):
        if not self.path.exists() or (not force and time.time() - self._last_backup < BACKUP_INTERVAL):
            return
        backup = self.path.with_name(self.path.name + BACKUP_SUFFIX)
        try:
            fd, temp = tempfile.mkstemp(prefix='.vdr-bak-', suffix='.json', dir=self.path.parent)
            os.close(fd)
            shutil.copy2(self.path, temp)
            os.replace(temp, backup)
            self._last_backup = time.time()
        except OSError:
            try:
                os.unlink(temp)
            except (OSError, UnboundLocalError):
                pass

    def save(self):
        # Never overwrite an unreadable original that could not be preserved.
        if self.load_error:
            raise StoreError(self.load_error)
        self.refresh_carry_forward()
        persisted = {day: report for day, report in self.reports.items() if not self.is_untouched(day)}
        # Round-trip guard: never write a report that could not be read back, because
        # that is what used to make the whole store unreadable after a restart.
        for day, report in persisted.items():
            try:
                normalize(deepcopy(report))
            except (ValueError, KeyError, TypeError) as error:
                raise StoreError(f'Not saved: the report for {day} contains data that could not be read back ({error}). '
                                 'Your previously saved data is safe. Undo (Ctrl+Z) or shorten the last change and saving resumes.') from error
        payload = dict(schemaVersion=1, reports=persisted, current=self.current,
                       layout=self.layout, customRanks=self.custom_ranks)
        if self.quarantined:
            payload['quarantined'] = self.quarantined
        payload['reportActivity'] = {day: value for day, value in self.activity.items() if day in persisted}
        temp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._backup()
            fd, temp = tempfile.mkstemp(prefix='.vdr-', suffix='.json', dir=self.path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        except PermissionError as error:
            raise StoreError(f'Not saved: Windows denied access to {self.path.parent}. Your previously saved data is safe. '
                             f'Check that the folder is not read-only or locked by another program. [{error}]') from error
        except OSError as error:
            raise StoreError(f'Not saved: the report file could not be written ({error.strerror or error}). '
                             'Your previously saved data is safe. Check free disk space; saving retries on your next change.') from error
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
