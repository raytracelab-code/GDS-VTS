"""Clear, path-specific errors. Invalid drafts can autosave; export is blocked."""
from datetime import date
import re
from .schema import (META, GENERAL, DEPARTURE, ARRIVAL, TABLES, DECK, INVENTORY,
                     INVENTORY_NAMES, CAPACITIES, COMPASS)
from .calculations import numeric, working_days


def normalized_name(value):
    return ' '.join(str(value).split()).casefold()


def validate_value(value, kind):
    if value in ('',None) or kind in ('derived','automatic','fixed'):
        return
    if kind == 'date':
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            raise ValueError('Use a valid date (YYYY-MM-DD)')
        date.fromisoformat(value)
    elif kind == 'time':
        if not isinstance(value,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):
            raise ValueError('Use 24-hour time HH:MM (00:00–23:59)')
    elif kind in ('ns','ew','compass'):
        choices = ('N','S') if kind == 'ns' else ('E','W') if kind == 'ew' else COMPASS
        if value not in choices:
            raise ValueError('Choose '+', '.join(choices))
    elif kind == 'text':
        if not isinstance(value,str):
            raise ValueError('Expected text')
        if len(value)>32767 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]',value):
            raise ValueError('Text contains unsupported characters or exceeds Excel cell length')
    else:
        number = numeric(value)
        upper = dict(age=120,lat_degree=90,lon_degree=180,minute=59,hour=23,course=359.99).get(kind)
        if number < 0 or (upper is not None and number > upper) or (kind=='second' and number>=60):
            raise ValueError('Value out of range for '+kind)
        if kind in ('age','lat_degree','lon_degree','minute','hour','count') and number != int(number):
            raise ValueError('Use a whole number for '+kind)


def validate(report):
    errors = []
    def fields(row, schema, path):
        for key,label,_,kind in schema:
            try:
                validate_value(row.get(key,''),kind)
            except (ValueError,TypeError,OverflowError) as error:
                errors.append(path+'.'+key+': '+label+' — '+str(error))
    fields(report['meta'],META,'meta')
    for group,schema in TABLES.items():
        rows = report[group]
        if len(rows)>CAPACITIES[group]:
            errors.append('%s: %s rows exceeds template capacity %s' % (group,len(rows),CAPACITIES[group]))
        for index,row in enumerate(rows):
            path = '%s[%s]' % (group,index+1)
            fields(row,schema,path)
            if group in ('waypoints','progress'):
                for axis,limit in (('lat',90),('lon',180)):
                    try:
                        values = [row.get(axis+'_'+key,'') for key in ('degree','minute','second','direction')]
                        populated = [v not in ('',None) for v in values]
                        if any(populated) and not all(populated):
                            errors.append(path+': complete all '+axis+' coordinate fields')
                        if numeric(values[0]) == limit and any(numeric(v) for v in values[1:3]):
                            errors.append(path+': minutes and seconds must be zero at '+str(limit)+'°')
                    except (ValueError,TypeError):
                        pass  # Individual field errors already identify the invalid component.
            if group == 'progress' and ((row.get('hour','')=='') != (row.get('minute','')=='')):
                errors.append(path+': provide both hour and minute')
    for group in ('departure','arrival'):
        row = report[group]
        fields(row,GENERAL+DEPARTURE+ARRIVAL,group)
        if len(row['deck'])>5:
            errors.append(group+'.deck: template capacity is 5 destinations')
        for index,deck in enumerate(row['deck']):
            fields(deck,DECK,group+'.deck[%s]' % (index+1))
        seen = set()
        names = {normalized_name(name) for name in INVENTORY_NAMES}
        for index,item in enumerate(row['inventory']):
            fields(item,INVENTORY,group+'.inventory[%s]' % (index+1))
            name = normalized_name(item.get('product',''))
            if name not in names or name in seen:
                errors.append(group+'.inventory: unknown or duplicate product '+item.get('product',''))
            seen.add(name)
    for index,row in enumerate(report['crew']):
        try:
            days = working_days(row.get('sign_on',''),report['departure']['report_date'],report['arrival']['report_date'])
            if days is not None and days < 1:
                errors.append('crew[%s].sign_on: Sign-on is after the report date' % (index+1))
            elif days is not None and days > 90:
                errors.append('crew[%s].sign_on: %s working days exceeds the 90-day limit in the template' % (index+1,days))
        except (ValueError,TypeError):
            pass
    errors += business_rules(report)
    return errors


# Plausibility ceilings (template guidance; GDS-AUDIT-034). Keys apply to every table.
UPPER_LIMITS = dict(speed=(300,'knots'), visibility=(100,'nm'), wind_speed=(250,'knots'), wave_height=(40,'m'))


def _date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def business_rules(report):
    """Required fields and cross-field order checks (GDS-AUDIT-010)."""
    errors = []
    if not str(report['meta'].get('vessel','')).strip():
        errors.append('meta.vessel: Vessel Name — not set. Enter it in Configure → Vessel & Client')
    departure, arrival = report['departure'], report['arrival']
    for key,label in (('departure_date','Departure Date'),('departure_location','Departure Location')):
        if not str(departure.get(key,'')).strip():
            errors.append('departure.%s: %s — required' % (key,label))
    dep_date, arr_date = _date(departure.get('departure_date')), _date(arrival.get('arrival_date'))
    eta = _date(departure.get('arrival_date'))
    if dep_date and eta and eta < dep_date:
        errors.append('departure.arrival_date: Estimated arrival is before the departure date')
    if dep_date and arr_date and arr_date < dep_date:
        errors.append('arrival.arrival_date: Actual arrival is before the departure date')
    dep_report, arr_report = _date(departure.get('report_date')), _date(arrival.get('report_date'))
    if dep_report and arr_report and arr_report < dep_report:
        errors.append('arrival.report_date: Arrival report date is before the departure report date')
    seen = set()
    for index,row in enumerate(report['progress']):
        day = _date(row.get('date'))
        if day and dep_date and day < dep_date:
            errors.append('progress[%s].date: Progress date is before the departure date' % (index+1))
        if day and arr_date and day > arr_date:
            errors.append('progress[%s].date: Progress date is after the actual arrival date' % (index+1))
        stamp = (row.get('date',''),row.get('hour',''),row.get('minute',''))
        if all(stamp) and stamp in seen:
            errors.append('progress[%s]: Duplicate date and time' % (index+1))
        seen.add(stamp)
    for group in ('waypoints','progress'):
        for index,row in enumerate(report[group]):
            for key,(limit,unit) in UPPER_LIMITS.items():
                try:
                    if row.get(key,'') not in ('',None) and numeric(row[key]) > limit:
                        errors.append('%s[%s].%s: %s %s is above the plausible maximum of %s %s' % (group,index+1,key,row[key],unit,limit,unit))
                except (ValueError,TypeError):
                    pass
    for group in ('departure','arrival'):
        for index,deck in enumerate(report[group]['deck']):
            try:
                weight = deck.get('weight','')
                if weight not in ('',None) and numeric(weight) > 100000:
                    errors.append('%s.deck[%s].weight: Cargo weight above 100000 t' % (group,index+1))
            except (ValueError,TypeError):
                pass
    return errors
