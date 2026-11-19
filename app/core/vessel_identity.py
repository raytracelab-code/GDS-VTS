"""Authoritative vessel / client identity shared by Configure, VDR, VJR and exports.

Configure is the only writer. Every display and export reads :func:`load_identity`
so the screen, PDF and Excel outputs can never use different sources.

Stored in QSettings('GDS', 'VTS') under the historical ``vessel/*`` keys that
VDR and VJR already read, so existing installations keep their values.
"""
from datetime import date
import re

# key, QSettings key, user-facing label, maximum length
FIELDS = (
    ('vessel', 'vessel/name', 'Vessel Name', 100),
    ('imo', 'vessel/imo', 'Vessel IMO', 7),
    ('client', 'vessel/client', 'Client Name', 100),
    ('client_id', 'vessel/client_id', 'Client ID', 50),
    ('hireDate', 'vessel/date_of_hire', 'Date of Hire', 10),
    ('capacity', 'vessel/deck_capacity', 'Total Deck Space (m²)', 12),
)
KEYS = tuple(field[0] for field in FIELDS)
LABELS = {field[0]: field[2] for field in FIELDS}
CONTROL = re.compile(r'[\x00-\x1f\x7f]')


class IdentityError(ValueError):
    """Raised with a mapping of field key -> user-facing message."""

    def __init__(self, errors):
        super().__init__('; '.join(errors.values()))
        self.errors = errors


def _settings(settings=None):
    if settings is not None:
        return settings
    from app.qt.QtCore import QSettings
    return QSettings('GDS', 'VTS')


def load_identity(settings=None):
    """Every identity key as a string; missing values are ''."""
    store = _settings(settings)
    result = {}
    for key, setting, _label, _limit in FIELDS:
        value = store.value(setting, '')
        result[key] = '' if value is None else str(value)
    return result


def normalize_identity(values):
    result = {}
    for key in KEYS:
        value = values.get(key, '')
        value = '' if value is None else ' '.join(str(value).split())
        if key == 'imo':
            value = re.sub(r'^IMO\s*', '', value, flags=re.I).replace(' ', '')
        result[key] = value
    return result


def imo_check_digit_ok(imo):
    if not re.fullmatch(r'\d{7}', imo):
        return False
    total = sum(int(digit) * weight for digit, weight in zip(imo[:6], range(7, 1, -1)))
    return total % 10 == int(imo[6])


def validate_identity(values, today=None):
    """Field -> message for every invalid value. Blank values are allowed here;
    whether a blank blocks a report is decided by that report's final validation."""
    values = normalize_identity(values)
    errors = {}
    for key, _setting, label, limit in FIELDS:
        value = values[key]
        if len(value) > limit:
            errors[key] = f'{label} is too long ({len(value)} characters; maximum {limit}).'
        elif CONTROL.search(value):
            errors[key] = f'{label} contains control characters.'
    if values['imo'] and 'imo' not in errors and not imo_check_digit_ok(values['imo']):
        errors['imo'] = 'Vessel IMO must be 7 digits with a valid check digit (for example 9074729).'
    if values['hireDate'] and 'hireDate' not in errors:
        try:
            hire = date.fromisoformat(values['hireDate'])
            if hire < date(1990, 1, 1):
                errors['hireDate'] = 'Date of Hire must be on or after 01 Jan 1990.'
            elif hire > (today or date.today()):
                errors['hireDate'] = 'Date of Hire cannot be in the future.'
        except ValueError:
            errors['hireDate'] = 'Date of Hire must be a valid date (YYYY-MM-DD).'
    if values['capacity'] and 'capacity' not in errors:
        try:
            capacity = float(values['capacity'])
            if not 0 < capacity <= 100000:
                raise ValueError
        except ValueError:
            errors['capacity'] = 'Total Deck Space must be a number greater than 0 and at most 100000 m².'
    return errors


def save_identity(values, settings=None, today=None):
    """Validate, normalize and persist. Returns the stored identity."""
    values = normalize_identity(values)
    errors = validate_identity(values, today)
    if errors:
        raise IdentityError(errors)
    store = _settings(settings)
    for key, setting, _label, _limit in FIELDS:
        store.setValue(setting, values[key])
    store.sync()
    from app.qt.QtCore import QSettings
    if store.status() != QSettings.Status.NoError:
        raise OSError('Vessel identity could not be written to Windows settings.')
    return values


def report_identity_issues(identity, report_day):
    """Identity problems that block a finalized report (Report No. needs Date of Hire)."""
    identity = normalize_identity(identity or {})
    issues = []
    if not identity['vessel']:
        issues.append('Vessel Name is not set. Enter it in Configure → Vessel & Client.')
    if not identity['hireDate']:
        issues.append('Date of Hire is not set, so Report No. cannot be calculated. Enter it in Configure → Vessel & Client.')
    else:
        try:
            hire = date.fromisoformat(identity['hireDate'])
            if report_day and hire > date.fromisoformat(report_day):
                issues.append(f'Date of Hire ({hire:%d %b %Y}) is after this report date; Report No. would be below 1. Check Configure → Vessel & Client.')
        except ValueError:
            issues.append('Date of Hire in Configure is not a valid date.')
    return issues
