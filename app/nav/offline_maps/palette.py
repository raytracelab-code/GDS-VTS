"""Geographic solar palette; NOAA fractional-year equations, geometric elevation.

https://gml.noaa.gov/grad/solcalc/solareqns.PDF
No timezone, network, OS theme or display brightness dependency.
"""
from app.core.compat import remove_suffix
import calendar
from datetime import datetime, timezone, timedelta
import math


def position(value):
    try:
        lat, lon = value
        if all(type(v) in (int, float) and math.isfinite(v) for v in (lat, lon)) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return float(lat), float(lon)
    except (TypeError, ValueError):
        pass
    return None


def solar_elevation(utc, latitude, longitude):
    if utc.tzinfo is None or not position((latitude, longitude)):
        raise ValueError('Solar calculation needs aware UTC and valid position')
    utc = utc.astimezone(timezone.utc)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    gamma = 2 * math.pi / (366 if calendar.isleap(utc.year) else 365) * (utc.timetuple().tm_yday - 1 + (hour - 12) / 24)
    c, s = math.cos, math.sin
    eq = 229.18 * (.000075 + .001868*c(gamma) - .032077*s(gamma) - .014615*c(2*gamma) - .040849*s(2*gamma))
    decl = .006918 - .399912*c(gamma) + .070257*s(gamma) - .006758*c(2*gamma) + .000907*s(2*gamma) - .002697*c(3*gamma) + .00148*s(3*gamma)
    angle = math.radians(((hour*60 + eq + 4*longitude) % 1440) / 4 - 180)
    lat = math.radians(latitude)
    return math.degrees(math.asin(max(-1, min(1, s(lat)*s(decl) + c(lat)*c(decl)*c(angle)))))


def solar_state(elevation, previous=None):
    # 0.25 degree exit hysteresis around the civil twilight boundaries.
    if previous == 'DAY' and elevation >= -.25:
        return 'DAY'
    if previous == 'NIGHT' and elevation < -5.75:
        return 'NIGHT'
    if previous == 'TWILIGHT' and -6.25 <= elevation < .25:
        return 'TWILIGHT'
    return 'DAY' if elevation >= 0 else 'TWILIGHT' if elevation >= -6 else 'NIGHT'


def canonical_utc(frame, now, live=False):
    """Only fresh authoritative GNSS Date+UTC; never use a time-only date guess.

    ISO dates, DD/MM/YYYY and NMEA DDMMYY dates; colon or HHMMSS UTC.
    Reject >24h skew, >3s-old reception, future receptions and invalid fields.
    Advance GNSS time by reception age between minute ticks.
    """
    if now.tzinfo is None:
        raise ValueError('Palette time requires an aware UTC clock')
    now = now.astimezone(timezone.utc)
    try:
        if not live or not frame or not frame.valid or not frame.received_at or frame.received_at.tzinfo is None:
            raise ValueError()
        age = (now - frame.received_at).total_seconds()
        if not 0 <= age < 3:
            raise ValueError()
        date = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d%m%y'):
            try:
                date = datetime.strptime(str(frame.date), fmt).date()
                break
            except ValueError:
                pass
        if date is None:
            raise ValueError()
        raw = remove_suffix(str(frame.utc), 'Z')
        fmt = '%H:%M:%S' if ':' in raw else '%H%M%S'
        clock = datetime.strptime(raw, fmt + ('.%f' if '.' in raw else '')).time()
        instant = datetime.combine(date, clock, timezone.utc) + timedelta(seconds=age)
        if abs((instant - now).total_seconds()) > 86400:
            raise ValueError()
        return instant, 'GNSS_UTC'
    except (ValueError, TypeError, AttributeError, OverflowError):
        return now, 'SYSTEM_UTC'


class PaletteEngine:
    def __init__(self, mode='AUTO'):
        self.mode = mode if mode in ('AUTO', 'DAY', 'NIGHT') else 'AUTO'
        self.previous = None

    def calculate(self, utc, own=None, center=None, follow=False, time_source='SYSTEM_UTC'):
        utc = utc.astimezone(timezone.utc) if utc.tzinfo is not None else utc
        own, center = position(own), position(center)
        reference = own if follow and own else center
        ref_type = 'OWN_VESSEL' if follow and own else 'MAP_CENTER' if center else 'FALLBACK'
        # Explicit deterministic fallback, never a fabricated vessel position.
        lat, lon = reference or (0., 0.)
        elevation = solar_elevation(utc, lat, lon)
        state = solar_state(elevation, self.previous)
        self.previous = state
        return {'requested_mode': self.mode, 'computed_solar_state': state,
                'effective_state': state if self.mode == 'AUTO' else self.mode,
                'solar_elevation': elevation, 'reference_type': ref_type,
                'latitude': lat, 'longitude': lon, 'time_source': time_source,
                'utc_timestamp': utc.isoformat()}
