"""Plausibility checks for operational values (soft validation).

``check(kind, value)`` returns None (fine), ('warning', text) for a possible-but-unlikely value,
or ('invalid', text) for a value that cannot be right (e.g. latitude 95). Values are never
changed here; callers only display the result. Ranges are deliberately broad.
"""
import math

INVALID, WARNING = 'invalid', 'warning'

# kind: (hard_min, hard_max, soft_min, soft_max, unit, label)
RULES = {
    # navigation
    'latitude': (-90, 90, None, None, '°', 'Latitude'),
    'longitude': (-180, 180, None, None, '°', 'Longitude'),
    'heading': (0, 360, None, None, '°', 'Heading'),
    'cog': (0, 360, None, None, '°', 'COG'),
    'course': (0, 360, None, None, '°', 'Course'),
    'speed_knots': (0, None, None, 35, 'kn', 'Speed'),
    'planned_speed': (0, 300, None, 35, 'kn', 'Planned speed'),
    'actual_speed': (0, 300, None, 35, 'kn', 'Actual speed'),
    # weather / environment
    'wind_speed_knots': (0, None, None, 100, 'kn', 'Wind speed'),
    'true_wind_speed_knots': (0, None, None, 100, 'kn', 'True wind speed'),
    'wind_direction_deg': (0, 360, None, None, '°', 'Wind direction'),
    'true_wind_direction_deg': (0, 360, None, None, '°', 'True wind direction'),
    'humidity_percent': (0, 100, None, None, '%', 'Humidity'),
    'temperature_c': (-80, 70, -10, 50, '°C', 'Temperature'),
    'pressure_kpa': (50, 115, 87, 108.5, 'kPa', 'Pressure'),
    'rainfall_mm_min': (0, None, None, 10, 'mm/min', 'Rainfall'),
    'illumination_lux': (0, None, None, 150000, 'lx', 'Illumination'),
    'pm25': (0, None, None, 500, 'µg/m³', 'PM2.5'),
    'pm10': (0, None, None, 600, 'µg/m³', 'PM10'),
    'solar_power_w_m2': (0, None, None, 1400, 'W/m²', 'Solar power'),
    'visibility_nm': (0, None, None, 50, 'nm', 'Visibility'),
    'wave_height_m': (0, None, None, 15, 'm', 'Wave / swell height'),
    'swell_m': (0, None, None, 15, 'm', 'Swell'),
    # VDR / VJR quantities
    'draft_m': (0, None, None, 15, 'm', 'Draft'),
    'daily_run_hours': (0, None, None, 24, 'h', 'Daily running hours'),
    'quantity': (0, None, None, 10_000_000, '', 'Quantity'),
}


def _number(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = float(str(value).replace(',', '')) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def check(kind, value):
    """None, (WARNING, message) or (INVALID, message). Blank/non-numeric input is not judged here."""
    number = _number(value)
    if number is None or kind not in RULES:
        return None
    hard_min, hard_max, soft_min, soft_max, unit, label = RULES[kind]
    shown = f'{number:g}{(" " + unit) if unit and unit not in "°%" else unit}'
    if hard_min is not None and number < hard_min or hard_max is not None and number > hard_max:
        limits = f'{hard_min if hard_min is not None else "…"} to {hard_max if hard_max is not None else "…"}{unit}'
        return INVALID, f'{label} {shown} is outside the possible range ({limits}).'
    if soft_max is not None and number > soft_max or soft_min is not None and number < soft_min:
        return WARNING, f'{label} {shown} is unusually {"high" if soft_max is not None and number > soft_max else "low"}. Check the value.'
    return None


def check_frame(frame):
    """Plausibility of a telemetry frame: {field: (level, message)} for every flagged field."""
    found = {}
    for field in RULES:
        result = check(field, getattr(frame, field, None))
        if result:
            found[field] = result
    return found


def vdr_warnings(report):
    """Soft VDR warnings (never block Finalize): list of (section_index, path, message)."""
    from app.vdr.model import calculate, number
    warnings = []
    for key, label in (('fwd', 'Draft FWD'), ('aft', 'Draft AFT')):
        result = check('draft_m', report['meta'][key])
        if result and result[0] == WARNING:
            warnings.append((0, ('meta', key), result[1].replace('Draft', label, 1)))
    for i, row in enumerate(report['wx']):
        result = check('swell_m', row['swell'])
        if result:
            warnings.append((1, ('wx', i, 'swell'), f'{row["t"]}: {result[1]}'))
        result = check('wind_speed_knots', row['wind'])
        if result:
            warnings.append((1, ('wx', i, 'wind'), f'{row["t"]}: {result[1]}'))
    for i, row in enumerate(report['eq']):
        daily = number(row['daily'])
        if daily is not None and daily > 24:
            warnings.append((3, ('eq', i, 'daily'), f'{row["name"]}: {daily:g} running hours in one day is more than 24 h.'))
        total = number(row['total'])
        if daily is not None and total is not None and 0 <= total < daily:
            warnings.append((3, ('eq', i, 'total'), f'{row["name"]}: total running hours ({total:g}) are less than today\'s ({daily:g}).'))
    calc = calculate(report)
    for i, row in enumerate(report['bulk']):
        opening, closing = number(row['open']), calc['bulkClose'][i]
        for key in ('open', 'rcvQty', 'cons'):
            result = check('quantity', row[key])
            if result:
                warnings.append((4, ('bulk', i, key), f'{row["name"]}: {result[1]}'))
        received = number(row['rcvQty'])
        before, after = number(row['rcvB']), number(row['rcvA'])
        if received is not None and before is not None and after is not None and after >= before and received > (after - before) * 1.05 + 1:
            warnings.append((4, ('bulk', i, 'rcvQty'), f'{row["name"]}: received {received:g} is more than the meter difference ({after - before:g}).'))
        if opening is not None and closing is not None and closing > opening and not received and not any(number(t['qty']) for t in row['tr']):
            warnings.append((4, ('bulk', i, 'open'), f'{row["name"]}: closing is higher than opening with nothing received.'))
    return warnings
