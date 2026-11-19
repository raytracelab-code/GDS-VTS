"""VJR calculations shared by the UI and the exporter; no NAV changes."""
from datetime import date
import math


def numeric(value):
    if value in ('', None):
        return None
    if isinstance(value, bool):
        raise ValueError('Expected a number')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Expected a finite number')
    return result


def working_days(sign_on, departure_report_date, arrival_report_date=''):
    reference = arrival_report_date or departure_report_date
    if not sign_on or not reference:
        return None
    return (date.fromisoformat(reference)-date.fromisoformat(sign_on)).days+1


def decimal_to_dms(value, latitude=True):
    value = numeric(value)
    limit = 90 if latitude else 180
    if value is None or abs(value) > limit:
        raise ValueError('Coordinate must be between -%s and %s' % (limit, limit))
    # Round total arcseconds first so rounding carries across minutes/degrees.
    total = round(abs(value)*3600, 6)
    degree = int(total//3600)
    minute = int((total-degree*3600)//60)
    second = round(total-degree*3600-minute*60, 6)
    return dict(degree=degree, minute=minute, second=second,
                direction=('S' if value < 0 else 'N') if latitude else ('W' if value < 0 else 'E'))


def deck_values(row, capacity):
    components = [numeric(row.get(key,'')) for key in ('ops','fso','drilling')]
    total = sum(v or 0 for v in components) if any(v is not None for v in components) else None
    capacity = numeric(capacity)
    return dict(total=total, utilization=total/capacity if total is not None and capacity else None)


def deck_totals(rows, capacity):
    output = {}
    for key in ('lifts','ops','fso','drilling','weight'):
        values = [numeric(row.get(key,'')) for row in rows]
        output[key] = sum(v or 0 for v in values) if any(v is not None for v in values) else None
    output.update(deck_values(output, capacity))
    return output
