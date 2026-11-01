from dataclasses import dataclass
from app.telemetry.frame import TelemetryFrame
from .antenna_offset import reference_position
from .vessel_config import VesselConfig

@dataclass
class VesselState:
    latitude: float|None=None; longitude: float|None=None; heading: float|None=None; cog: float|None=None; speed_knots: float|None=None
    def update(self,frame:TelemetryFrame,config:VesselConfig):
        if frame.latitude is None or frame.longitude is None: return False
        orientation=frame.heading if frame.heading is not None else frame.cog
        self.latitude,self.longitude=reference_position(frame.latitude,frame.longitude,orientation,config.antenna_offset_x_m,config.antenna_offset_y_m); self.heading=orientation; self.cog=frame.cog; self.speed_knots=frame.speed_knots; return True
