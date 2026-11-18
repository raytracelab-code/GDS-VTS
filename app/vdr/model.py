"""Reference-compatible VDR records and calculations, independent of Qt."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import math
import re

SECTIONS = ('Report & HSE', 'Weather', 'Activity log', 'Running hours',
            'Bulk inventory', 'Core crew', 'Contractors')


def number(value):
    try:
        result = float(str(value).replace(',', ''))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


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
                finalizedAt='', identity=deepcopy(identity or {}))


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


def rollover(previous, day):
    result = deepcopy(previous)
    calc = calculate(previous)
    result['meta']['date'] = day
    result['wx'] = new_report(day)['wx']
    result['acts'] = [blank_row('acts')]
    for row in result['eq']:
        if number(row['daily']) is not None:
            row['total'] = str((number(row['total']) or 0) + number(row['daily']))
        row.update(daily='', fm0=row['fm24'] or row['fm0'], fm24='')
    for i, row in enumerate(result['bulk']):
        if calc['bulkClose'][i] is not None:
            row['open'] = str(calc['bulkClose'][i])
        for key in ('rcvQty', 'rcvFrom', 'rcvB', 'rcvA', 'rcvTicket', 'cons'):
            row[key] = ''
        row.update(tr=[], det=False)
    result['hse']['inc24'] = ''
    result.update(finalized=False, finalizedAt='')
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
    result['finalized'] = data.get('finalized') is True
    result['finalizedAt'] = str(data.get('finalizedAt', ''))
    return result
