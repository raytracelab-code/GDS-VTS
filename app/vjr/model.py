"""Versioned JSON VJR state. Only template fields belong to the report."""
from copy import deepcopy
from .schema import META, GENERAL, DEPARTURE, ARRIVAL, TABLES, DECK, INVENTORY_NAMES


def blank_row(fields):
    return {key:'' for key, _, _, kind in fields if kind not in ('derived','automatic')}


def new_report():
    report = dict(schemaVersion=1, meta=blank_row(META))
    report['meta']['report_name'] = 'Vessel Journey Report'
    for group in TABLES:
        report[group] = []
    for group in ('departure','arrival'):
        report[group] = blank_row(GENERAL+DEPARTURE+ARRIVAL)
        report[group]['deck'] = [blank_row(DECK) for _ in range(5)]
        report[group]['inventory'] = [dict(product=name, quantity='', remarks='',
            unit='ltrs' if i < 6 else ('mt' if i in (6,7,8,10) else 'bbls'))
            for i,name in enumerate(INVENTORY_NAMES)]
    return report


def normalize(data):
    if not isinstance(data, dict) or data.get('schemaVersion',1) != 1:
        raise ValueError('Unsupported VJR store schema')
    report = new_report()
    if 'photos' in data or 'photo_report_id' in data:
        from .photo_storage import validate_photo_state
        validate_photo_state(data)
        report['photos'] = deepcopy(data.get('photos',{}))
        report['photo_report_id'] = data.get('photo_report_id','')
    for group in ('meta','departure','arrival'):
        source = data.get(group,{})
        if not isinstance(source,dict):
            raise ValueError('Invalid VJR '+group)
        report[group].update(deepcopy(source))
    for group in TABLES:
        source = data.get(group,[])
        if not isinstance(source,list) or any(not isinstance(row,dict) for row in source):
            raise ValueError('Invalid VJR '+group)
        report[group] = [dict(blank_row(TABLES[group]), **deepcopy(row)) for row in source]
    for group in ('departure','arrival'):
        for table in ('deck','inventory'):
            rows = report[group][table]
            if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):
                raise ValueError('Invalid VJR '+group+' '+table)
        report[group]['deck'] += [blank_row(DECK) for _ in range(max(0,5-len(report[group]['deck'])))]
        existing = {' '.join(str(item.get('product','')).split()).casefold() for item in report[group]['inventory']}
        for item in new_report()[group]['inventory']:
            if item['product'].casefold() not in existing:
                report[group]['inventory'].append(item)
    return report


def with_identity(report, identity):
    output = deepcopy(report)
    # A provided Configure value is authoritative, including a deliberate blank.
    for key,value in identity.items():
        if key in output['meta']:
            output['meta'][key] = value
    return output


def arrival_fields(report):
    result = dict(report['departure'])
    for key in ('report_date','arrival_date','arrival_time','arrival_remarks','deck','inventory'):
        result[key] = report['arrival'].get(key,'')
    # The original Arrival D26 links to Departure D26.
    return result
