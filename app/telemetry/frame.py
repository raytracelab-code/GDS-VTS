from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional
from app.core.models import Source


@dataclass(frozen=True)
class TelemetryFrame:
    pid: Optional[str] = None; date: Optional[str] = None; utc: Optional[str] = None
    latitude: Optional[float] = None; longitude: Optional[float] = None
    speed_knots: Optional[float] = None; cog: Optional[float] = None; heading: Optional[float] = None
    wind_speed_knots: Optional[float] = None; wind_direction_deg: Optional[float] = None
    true_wind_speed_knots: Optional[float] = None; true_wind_direction_deg: Optional[float] = None
    humidity_percent: Optional[float] = None; temperature_c: Optional[float] = None; pressure_kpa: Optional[float] = None
    illumination_lux: Optional[float] = None; noise_db: Optional[float] = None; pm25: Optional[float] = None; pm10: Optional[float] = None
    rainfall_mm_min: Optional[float] = None; solar_power_w_m2: Optional[float] = None
    roll: Optional[float] = None; pitch: Optional[float] = None; yaw: Optional[float] = None; voltage: Optional[float] = None
    error_status: Optional[str] = None; source: Optional[Source] = None; received_at: Optional[datetime] = None; valid: bool = False
