"""One final-report validation contract shared by Finalize, Excel export and PDF export.

If :func:`final_issues` returns no issues, Finalize succeeds and both exports can
render the report; every condition the exporters would reject is detected here.
Issues use the same shape as :func:`app.vdr.model.validate` (s, sec, msg).
"""
from copy import deepcopy
from datetime import date

from app.core.vessel_identity import report_identity_issues
from .model import SECTIONS, activity_summary, number, oversized_fields, validate

# Template capacities (verified in the original workbook; see docs/vdr-excel-cell-map).
CAPACITY = dict(acts=90, crew=200, ctr=200, locations=22)
TRANSFER_CAPACITY_FUEL = 2
TRANSFER_CAPACITY_OTHER = 1
UI_TRANSFER_LIMIT = 6


def _issue(section, message):
    return dict(s=section, sec=f'{section+1:02d} {SECTIONS[section]}', msg=message)


def _name_key(value):
    return ' '.join(str(value).split()).casefold()


def _is_date(value):
    try:
        return date.fromisoformat(value) >= date(1900, 1, 1)
    except (TypeError, ValueError):
        return False


def export_issues(report):
    """Template and type rules the exporters enforce, collected as a full list."""
    from .excel import BULK_ROWS, EQUIPMENT  # local import: excel imports this module lazily too
    issues = []
    numeric = lambda section, value, label: issues.append(_issue(section, f'{label}: "{value}" is not a valid number')) \
        if str(value).strip() and number(value) is None else None
    for where, key, length, limit in oversized_fields(report):
        section = {'meta': 0, 'hse': 0, 'end': 0, 'wx': 1, 'acts': 2, 'eq': 3, 'bulk': 4, 'crew': 5, 'ctr': 6}.get(where.split(' ')[0], 0)
        issues.append(_issue(section, f'{where.capitalize()}: {key} has {length} characters (maximum {limit}). Shorten it.'))
    for key, label in (('fuel', 'Fuel endurance'), ('water', 'Drinking water endurance'), ('prov', 'Provision endurance')):
        numeric(0, report['end'][key], label)
    for key, label in (('lti', 'Last LTI'), ('inj', 'Last recordable injury'), ('incd', 'Last recordable incident'),
                       ('containment_loss', 'Last containment loss')):
        if report['hse'][key] and not _is_date(report['hse'][key]):
            issues.append(_issue(0, f'{label}: invalid Excel date "{report["hse"][key]}"'))
    for row in report['wx']:
        numeric(1, row['vis'], f'Weather {row["t"]} visibility')
    rows = [r for r in report['acts'] if any(v.strip() for v in r.values())]
    if len(report['acts']) > CAPACITY['acts']:
        issues.append(_issue(2, f'Activity Log has {len(report["acts"])} rows; template capacity = {CAPACITY["acts"]}.'))
    for i, row in enumerate(report['acts']):
        numeric(2, row['lifts'], f'Row {i+1} lifts')
        numeric(2, row['pob'], f'Row {i+1} POB')
    if rows:
        locations = activity_summary(report)['locations']
        if len(locations) > CAPACITY['locations']:
            issues.append(_issue(2, f'Location summary has {len(locations)} locations; template capacity = {CAPACITY["locations"]}. Use catalogue location names.'))
    allowed_eq = {_name_key(n) for n in EQUIPMENT}
    seen = set()
    for row in report['eq']:
        if not any(v for k, v in row.items() if k != 'name'):
            continue
        key = _name_key(row['name'])
        if key not in allowed_eq:
            issues.append(_issue(3, f'Unknown equipment "{row["name"]}": the Excel template has no matching row.'))
        elif key in seen:
            issues.append(_issue(3, f'Duplicate equipment: "{row["name"]}" is listed twice; remove the duplicate row.'))
        seen.add(key)
    allowed_bulk = {_name_key(n) for n in BULK_ROWS}
    seen = set()
    for row in report['bulk']:
        if not any(v for k, v in row.items() if k not in ('name', 'det')):
            continue
        key = _name_key(row['name'])
        if key not in allowed_bulk:
            issues.append(_issue(4, f'Unknown bulk item "{row["name"]}": the Excel template has no matching row.'))
        elif key in seen:
            issues.append(_issue(4, f'Duplicate bulk item: "{row["name"]}" is listed twice; remove the duplicate row.'))
        seen.add(key)
        capacity = TRANSFER_CAPACITY_FUEL if key == _name_key('FUEL (ltrs)') else TRANSFER_CAPACITY_OTHER
        if len(row['tr']) > capacity:
            issues.append(_issue(4, f'FUEL has {len(row["tr"])} transfers. Fleet Management template supports a maximum of two fuel bunker-out transfers.'
                                 if capacity == TRANSFER_CAPACITY_FUEL else f'{row["name"]} has {len(row["tr"])} transfers; template capacity = {capacity}.'))
        for j, transfer in enumerate(row['tr']):
            for field, label in (('mb', 'meter before'), ('ma', 'meter after')):
                numeric(4, transfer[field], f'{row["name"]} transfer {j+1} {label}')
            if transfer['qty'].strip() and not transfer['to'].strip():
                issues.append(_issue(4, f'{row["name"]} transfer {j+1}: recipient ("To") is required'))
    for group, section, label in (('crew', 5, 'Crew'), ('ctr', 6, 'Contractor')):
        people = [p for p in report[group] if any(v.strip() for v in p.values())]
        if len(people) > CAPACITY[group]:
            issues.append(_issue(section, f'{label} list has {len(people)} rows; template capacity = {CAPACITY[group]}.'))
        for i, person in enumerate(report[group]):
            if not any(v.strip() for v in person.values()):
                continue
            if not person['name'].strip():
                issues.append(_issue(section, f'{label} row {i+1}: name is required (or delete the row)'))
            numeric(section, person['age'], f'{label} row {i+1} age')
            if group == 'crew' and person['signon'] and not _is_date(person['signon']):
                issues.append(_issue(section, f'Crew row {i+1}: sign-on: invalid Excel date "{person["signon"]}"'))
    return issues


def template_issues(report, identity):
    """Backstop: run the real Excel cell mapping as a dry run (nothing is written)."""
    from .excel import ExcelExportError, VdrExcelExporter
    exporter = VdrExcelExporter()
    try:
        _raw, workbook = exporter._template()
    except ExcelExportError as error:
        return [_issue(0, f'Excel template problem: {error}')]
    try:
        candidate = deepcopy(report); candidate['finalized'] = True
        exporter.values(candidate, workbook, identity, checked=True)
        return []
    except ExcelExportError as error:
        return [_issue(0, f'Excel export check: {error}')]
    finally:
        workbook.close()


def final_issues(report, identity, template_check=True, check_identity=True):
    """Every reason this report cannot be finalized/exported, grouped by section.

    ``check_identity=False`` is used when importing a finalized report: its own
    content is re-checked, but this PC's Configure identity is not a property of it."""
    issues = list(validate(report))
    if check_identity:
        issues += [_issue(0, message) for message in report_identity_issues(identity, report['meta'].get('date', ''))]
    issues += export_issues(report)
    if not issues and template_check:
        issues += template_issues(report, identity)
    unique, seen = [], set()
    for issue in issues:
        if (issue['s'], issue['msg']) not in seen:
            seen.add((issue['s'], issue['msg'])); unique.append(issue)
    return sorted(unique, key=lambda issue: issue['s'])


def format_issues(issues, limit=12):
    lines = [f"• {issue['sec']}: {issue['msg']}" for issue in issues[:limit]]
    if len(issues) > limit:
        lines.append(f'• … and {len(issues)-limit} more')
    return '\n'.join(lines)
