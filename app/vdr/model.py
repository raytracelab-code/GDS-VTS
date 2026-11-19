"""Reference-compatible VDR records and calculations, independent of Qt."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import math
import re

SECTIONS = ('Report & HSE', 'Weather', 'Activity log', 'Running hours',
            'Bulk inventory', 'Core crew', 'Contractors')


THOUSANDS = re.compile(r'[+-]?\d{1,3}(,\d{3})+(\.\d+)?')


def number(value):
    """Parse a user number. A comma is accepted only as a strict thousands
    separator ("1,250.5"); "2,5" is rejected instead of being read as 25."""
    text = str(value).strip()
    if ',' in text:
        if not THOUSANDS.fullmatch(text):
            return None
        text = text.replace(',', '')
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def number_text(value):
    """Plain stored text for a calculated number: 5650 not '5650.0', never exponent notation."""
    if value is None:
        return ''
    value = round(float(value), 4)
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f'{value:.4f}'.rstrip('0').rstrip('.')


# Maximum characters per stored text field, sized to what the UI, PDF and Excel
# template can present. Longer input is refused with a message, never truncated.
FIELD_LIMITS = {'act': 1000, 'remarks': 1000, 'comments': 1000, 'nextProv': 200, 'inc24': 500}
DEFAULT_FIELD_LIMIT = 200


def field_limit(key):
    return FIELD_LIMITS.get(key, DEFAULT_FIELD_LIMIT)


def oversized_fields(report):
    """Every (where, key, length, limit) that exceeds the per-field limit."""
    found = []

    def check(where, row):
        for key, value in row.items():
            if isinstance(value, str) and len(value) > field_limit(key):
                found.append((where, key, len(value), field_limit(key)))
    for group in ('meta', 'hse', 'end'):
        check(group, report.get(group, {}))
    for group in ('wx', 'acts', 'eq', 'bulk', 'crew', 'ctr'):
        for i, row in enumerate(report.get(group, [])):
            check(f'{group} row {i+1}', row)
            for j, transfer in enumerate(row.get('tr', []) if group == 'bulk' else []):
                check(f'{group} row {i+1} transfer {j+1}', transfer)
    return found


def fmt(value):
    return '—' if value is None else f'{value:,.2f}'.rstrip('0').rstrip('.')


def is_fuel(name):
    """Fuel consumption semantics survive case/whitespace variants in imported names."""
    return str(name).strip().upper().startswith('FUEL')


def minutes(value):
    if not re.fullmatch(r'\d{3,4}', str(value or '')):
        return None
    text = str(value).zfill(4)
    h, m = int(text[:2]), int(text[2:])
    return h * 60 + m if m < 60 and h <= 24 and (h < 24 or m == 0) else None


def hhmm(value, colon=False):
    return f'{value // 60:02d}{":" if colon else ""}{value % 60:02d}'


def blank_row(group, name=''):
    fields = {
        'acts': 'to act cat dp lifts pob loc', 'eq': 'name total daily fm0 fm24',
        'bulk': 'name open rcvQty rcvFrom rcvB rcvA rcvTicket cons remarks',
        'crew': 'name rank age nat ic signon comments', 'ctr': 'name vendor age nat ic',
        'tr': 'to qty mb ma tk',
    }
    row = dict.fromkeys(fields[group].split(), '')
    if 'name' in row:
        row['name'] = name
    if group == 'bulk':
        row.update(det=False, tr=[])
    return row


def new_report(day=None, identity=None):
    return dict(meta=dict(date=day or date.today().isoformat(), captain='', loc24='', fwd='', aft=''),
                hse=dict.fromkeys(('inc24', 'lti', 'inj', 'incd', 'containment_loss'), ''),
                end=dict.fromkeys(('fuel', 'water', 'prov', 'nextProv'), ''),
                wx=[dict(t=t, **dict.fromkeys(('wind', 'swell', 'sea', 'sky', 'vis', 'temp'), ''))
                    for t in ('0000H', '0600H', '1200H', '1800H')],
                acts=[blank_row('acts')], eq=[blank_row('eq', n) for n in
                    ('PORT ME', 'STBD ME', 'GENERATOR 1', 'GENERATOR 2')],
                bulk=[blank_row('bulk', n + ' (ltrs)') for n in
                      ('FUEL', 'FRESH WATER', 'LUB. OIL', 'GEAR OIL', 'DISPERSANT')],
                crew=[blank_row('crew') for _ in range(5)],
                ctr=[blank_row('ctr') for _ in range(3)], finalized=False,
                finalizedAt='', identity=deepcopy(identity or {}), carry=dict(source='', values={}))


def activity_intervals(activity_rows):
    """Authoritative consecutive FROM/TO intervals used by calculations and summaries."""
    end, activities = 0, []
    for row in activity_rows:
        to = minutes(row['to'])
        ok = to is not None and to > end
        activities.append(dict(fromM=end, toM=to, ok=ok, min=to-end if ok else 0))
        if ok:
            end = to
    return activities, end


def derive_location_durations(activity_rows):
    """Read-only, export-ready visits, preserving row order and invalid-row barriers."""
    intervals, _ = activity_intervals(activity_rows)
    visits, merge_previous = [], False
    for row, interval in zip(activity_rows, intervals):
        location = row.get('loc', '').strip()
        if not interval['ok'] or not location:
            merge_previous = False
            continue
        start, end = hhmm(interval['fromM']), hhmm(interval['toM'])
        if merge_previous and visits[-1]['location'] == location and visits[-1]['to'] == start:
            visits[-1]['to'] = end
            visits[-1]['duration'] = hhmm(interval['toM'] - minutes(visits[-1]['from']), True)
        else:
            visits.append({'from': start, 'to': end, 'duration': hhmm(interval['min'], True), 'location': location})
        merge_previous = True
    return visits


def calculate(report):
    activities, end = activity_intervals(report['acts'])
    consumed = [None if number(r['fm0']) is None or number(r['fm24']) is None
                else number(r['fm24']) - number(r['fm0']) for r in report['eq']]
    total = sum(v for v in consumed if v is not None and v >= 0)
    closing = []
    for r in report['bulk']:
        transfer = sum(number(t['qty']) or 0 for t in r['tr'])
        cons = total if is_fuel(r['name']) else number(r['cons']) or 0
        opening = number(r['open'])
        closing.append(None if opening is None else round(opening+(number(r['rcvQty']) or 0)-cons-transfer, 2))
    return dict(actD=activities, coverage=end, eqCons=consumed, totalCons=total, bulkClose=closing)


def tour_days(signon, day):
    try:
        return (date.fromisoformat(day) - date.fromisoformat(signon)).days + 1
    except (ValueError, TypeError):
        return None


def report_number(report, identity=None):
    """Hire date is day one, matching the original VDR report-number formula."""
    identity = report.get('identity', {}) if identity is None else identity
    return tour_days(identity.get('hireDate', ''), report['meta']['date'])


def hse_perfect_days(report, identity=None):
    """Same historical HSE/hire-date calculation used by the VDR display."""
    identity = report.get('identity', {}) if identity is None else identity
    dates = [v for k, v in report['hse'].items() if k != 'inc24' and v]
    hire = identity.get('hireDate', '')
    days = tour_days(max(dates + ([hire] if hire else []), default=''), report['meta']['date'])
    return max(0, days-1) if days is not None else None


def activity_summary(report):
    """Minute totals from authoritative activity intervals and location periods."""
    calc = calculate(report)
    movement, locations, dp = {}, {}, 0
    for row, interval in zip(report['acts'], calc['actD']):
        if interval['ok']:
            category = row['cat'].strip()
            movement[category] = movement.get(category, 0) + interval['min']
            if row['dp'].strip().upper() == 'Y':
                dp += interval['min']
    for period in derive_location_durations(report['acts']):
        location = period['location']
        locations[location] = locations.get(location, 0) + minutes(period['to']) - minutes(period['from'])
    return dict(movement=movement, locations=locations, dp=dp, total=calc['coverage'])


def validate(report):
    errors, calc = [], calculate(report)
    def error(section, message):
        errors.append(dict(s=section, sec=f'{section+1:02d} {SECTIONS[section]}', msg=message))
    for field, label in (('date', 'Report date'), ('captain', 'Captain on duty'), ('loc24', 'Location @ 2400H')):
        if not report['meta'][field].strip():
            error(0, label + ' is required')
    if any(number(report['meta'][key]) is None or number(report['meta'][key]) < 0 for key in ('fwd', 'aft')):
        error(0, 'Draft FWD and AFT are required and must be valid non-negative numbers')
    for row in report['wx']:
        missing = [k for k in ('wind', 'swell', 'sea', 'sky') if not row[k].strip()]
        if missing:
            error(1, f'Weather {row["t"]}: missing {", ".join(missing)}')
        for k in ('wind', 'swell', 'temp'):
            if row[k] and number(row[k]) is None:
                error(1, f'Weather {row["t"]}: invalid {k}')
    for i, row in enumerate(report['acts']):
        if any(row[k].strip() for k in ('to', 'act', 'cat', 'loc')):
            if not calc['actD'][i]['ok']:
                error(2, f'Row {i+1}: TO time invalid or not after previous entry')
            for k, label in (('act', 'activity description'), ('cat', 'vessel movement category'), ('loc', 'location')):
                if not row[k].strip():
                    error(2, f'Row {i+1}: {label} missing')
    if calc['coverage'] != 1440:
        error(2, f'Log must cover 0000–2400 with no gaps (currently ends at {hhmm(calc["coverage"])})')
    for i, row in enumerate(report['eq']):
        for key in ('total', 'daily', 'fm0', 'fm24'):
            if row[key] and (number(row[key]) is None or number(row[key]) < 0):
                error(3, f'{row["name"]}: invalid {key}')
        if calc['eqCons'][i] is not None and calc['eqCons'][i] < 0:
            error(3, row['name'] + ': flowmeter @0000H must be less than @2400H')
    for i, row in enumerate(report['bulk']):
        for key in ('open', 'rcvQty', 'cons', 'rcvB', 'rcvA'):
            if row[key] and (number(row[key]) is None or number(row[key]) < 0):
                error(4, row['name'] + ': invalid ' + key)
        for transfer in row['tr']:
            if transfer['qty'] and (number(transfer['qty']) is None or number(transfer['qty']) < 0):
                error(4, row['name'] + ': invalid transfer quantity')
        if calc['bulkClose'][i] is not None and calc['bulkClose'][i] < 0:
            error(4, row['name'] + ': closing stock is negative')
    if not any(r['name'].strip() for r in report['crew']):
        error(5, 'At least one crew member is required')
    for i, row in enumerate(report['crew']):
        if row['name'].strip():
            days = tour_days(row['signon'], report['meta']['date'])
            if not row['rank'].strip() or days is None:
                error(5, f'Crew {i+1} ({row["name"]}): rank and sign-on date required')
            elif days > 90 or days < 1:
                error(5, f'Crew {i+1} ({row["name"]}): {days} working days outside 1–90 day limit')
    return errors


def _row_key(name):
    return ' '.join(str(name).split()).casefold()


CARRY_LABELS = {'total': 'total run hours', 'fm0': 'flowmeter @0000H', 'open': 'opening @0000H'}


def carried_values(previous):
    """Opening values the next report inherits from ``previous``'s closing figures.

    Keys are ``group|item name|field``; values are stored text. Only figures that
    can be derived (a closing that exists) are returned."""
    calc = calculate(previous)
    values = {}
    for row in previous['eq']:
        key = 'eq|' + _row_key(row['name'])
        if key + '|total' in values or key + '|fm0' in values:
            continue
        total, daily = number(row['total']), number(row['daily'])
        if daily is not None:
            values[key + '|total'] = number_text((total or 0) + daily)
        elif row['total'].strip():
            values[key + '|total'] = row['total'].strip()
        meter = row['fm24'] or row['fm0']
        if meter.strip():
            values[key + '|fm0'] = meter.strip()
    for i, row in enumerate(previous['bulk']):
        key = 'bulk|' + _row_key(row['name']) + '|open'
        if key not in values and calc['bulkClose'][i] is not None:
            values[key] = number_text(calc['bulkClose'][i])
    return values


def _carry_target(report, key):
    group, name, field = key.split('|')
    for row in report[group]:
        if _row_key(row['name']) == name:
            return row, field
    return None, field


def _same(a, b):
    a, b = str(a or '').strip(), str(b or '').strip()
    if a == b:
        return True
    return a != '' and b != '' and number(a) is not None and number(a) == number(b)


def apply_carry_forward(report, previous, source_day):
    """Refresh ``report``'s inherited openings from ``previous`` (closing → opening).

    Rule: a field that still holds the value it last inherited (or is blank) is
    *linked* and follows the source. A field the user changed is a *manual
    override* and is never overwritten. Finalized reports are never changed.
    Returns True if anything changed."""
    if report.get('finalized'):
        return False
    carry = report.setdefault('carry', dict(source='', values={}))
    recorded = carry.setdefault('values', {})
    changed = carry.get('source') != source_day
    carry['source'] = source_day
    for key, value in carried_values(previous).items():
        row, field = _carry_target(report, key)
        if row is None:
            continue
        current = row[field]
        if key in recorded:
            linked = _same(current, recorded[key])
        else:
            # Unknown history (older stores): only blank or already-equal values are linked.
            linked = not current.strip() or _same(current, value)
        if linked:
            if current != value:
                row[field] = value; changed = True
            if recorded.get(key) != value:
                recorded[key] = value; changed = True
    return changed


def carry_forward_status(report, previous):
    """(linked, differing) lists of (label, current, expected) for display."""
    linked, differing = [], []
    if previous is None:
        return linked, differing
    for key, value in carried_values(previous).items():
        row, field = _carry_target(report, key)
        if row is None:
            continue
        item = (f"{row['name']} {CARRY_LABELS[field]}", row[field], value)
        (linked if _same(row[field], value) else differing).append(item)
    return linked, differing


def reset_carry_forward(report, previous, source_day):
    """Explicit user action: replace every inherited opening with the source closing."""
    for key, value in carried_values(previous).items():
        row, field = _carry_target(report, key)
        if row is not None:
            row[field] = value
    report['carry'] = dict(source=source_day, values=carried_values(previous))


def rollover(previous, day):
    """New report for ``day`` seeded from the most recent prior report.

    Crew, contractors, equipment/bulk rows, captain, location and drafts are copied
    as editable defaults; numeric openings are linked via :func:`apply_carry_forward`."""
    result = deepcopy(previous)
    result['meta']['date'] = day
    result['wx'] = new_report(day)['wx']
    result['acts'] = [blank_row('acts')]
    for row in result['eq']:
        row.update(total='', daily='', fm0='', fm24='')
    for row in result['bulk']:
        row['open'] = ''
        for key in ('rcvQty', 'rcvFrom', 'rcvB', 'rcvA', 'rcvTicket', 'cons'):
            row[key] = ''
        row.update(tr=[], det=False)
    result['hse']['inc24'] = ''
    result.update(finalized=False, finalizedAt='', carry=dict(source='', values={}))
    apply_carry_forward(result, previous, previous['meta']['date'])
    return result


def normalize(data):
    """Fill missing older fields without rewriting finalized/imported values."""
    if not isinstance(data, dict) or not isinstance(data.get('meta'), dict):
        raise ValueError('No valid report data found')
    day = data['meta'].get('date', '')
    date.fromisoformat(day)
    result = new_report(day)
    for group in ('meta', 'hse', 'end', 'identity'):
        incoming = data.get(group, {})
        if not isinstance(incoming, dict) or any(not isinstance(v, str) for v in incoming.values()):
            raise ValueError('Invalid report ' + group)
        result[group].update(incoming)
    for group in ('wx', 'acts', 'eq', 'bulk', 'crew', 'ctr'):
        if group not in data:
            continue
        if not isinstance(data[group], list) or len(data[group]) > 500:
            raise ValueError('Invalid report rows: ' + group)
        rows = []
        for i, incoming in enumerate(data[group]):
            if not isinstance(incoming, dict):
                raise ValueError('Invalid report row')
            row = new_report(day)['wx'][i % 4] if group == 'wx' else blank_row(group)
            for k, v in incoming.items():
                if k in ('tr', 'det'):
                    continue
                if not isinstance(v, str) or len(v) > 20000:
                    raise ValueError('Invalid report field')
                row[k] = v
            if group == 'bulk':
                row['det'] = bool(incoming.get('det', False))
                transfers = incoming.get('tr', [])
                if not isinstance(transfers, list) or len(transfers) > 500:
                    raise ValueError('Invalid transfer rows')
                for tr in transfers:
                    if not isinstance(tr, dict) or any(not isinstance(v, str) for v in tr.values()):
                        raise ValueError('Invalid transfer record')
                    row['tr'].append(dict(blank_row('tr'), **tr))
            rows.append(row)
        result[group] = rows
    if len(result['wx']) != 4:
        raise ValueError('Report requires four weather slots')
    carry = data.get('carry', {})
    if isinstance(carry, dict) and isinstance(carry.get('values', {}), dict):
        values = {k: v for k, v in carry.get('values', {}).items()
                  if isinstance(k, str) and isinstance(v, str) and k.count('|') == 2 and k.split('|')[0] in ('eq', 'bulk')}
        result['carry'] = dict(source=str(carry.get('source', ''))[:10], values=values)
    result['finalized'] = data.get('finalized') is True
    result['finalizedAt'] = str(data.get('finalizedAt', ''))
    return result
