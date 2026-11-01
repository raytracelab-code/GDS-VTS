from datetime import datetime, timezone
from app.core.models import Source
from .frame import TelemetryFrame

KEYS = {'PID':'pid','Date':'date','UTC':'utc','Speed_Knots':'speed_knots','COG':'cog','Heading':'heading','Wind_Speed_Knt':'wind_speed_knots','Wind_Dir_Deg':'wind_direction_deg','True_Wind_Speed_Knt':'true_wind_speed_knots','True_Wind_Dir_Deg':'true_wind_direction_deg','Humidity':'humidity_percent','Temperature_C':'temperature_c','Pressure_Kpa':'pressure_kpa','Illumination_Lux':'illumination_lux','Noise_dB':'noise_db','PM2_5_ug/m3':'pm25','PM10_ug/m3':'pm10','Rainfall_mm/min':'rainfall_mm_min','Solar_Pwr_W/m2':'solar_power_w_m2','Roll':'roll','Pitch':'pitch','Yaw':'yaw','Voltage':'voltage','Error_Status':'error_status'}

def _number(value):
    if value is None or (isinstance(value, str) and value.strip().upper() in ('', 'N/A')): return None
    try: return float(value)
    except (TypeError, ValueError): return None

def _coordinate(value):
    n = _number(value)
    if n is None: return None
    # Patroller-I milliminutes are values outside degree bounds: DDMM.mmm -> decimal degrees.
    limit = 90 if abs(n) <= 90000 else 180
    if abs(n) > limit:
        sign = -1 if n < 0 else 1; raw = abs(n); return sign * (int(raw / 100) + (raw % 100) / 60)
    return n

class TelemetryNormalizer:
    def normalize(self, payload: dict, source: Source, valid: bool) -> TelemetryFrame:
        values = {target: (str(payload[key]) if target in ('pid','date','utc','error_status') and payload.get(key) not in (None,'N/A') else _number(payload.get(key))) for key, target in KEYS.items()}
        values['latitude'] = _coordinate(payload.get('Latitude')); values['longitude'] = _coordinate(payload.get('Longitude'))
        return TelemetryFrame(**values, source=source, received_at=datetime.now(timezone.utc), valid=valid)
