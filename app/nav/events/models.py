from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Optional
class EventStatus(StrEnum): ACTIVE='ACTIVE'; STALE='STALE'; EXPIRED='EXPIRED'; CLEARED='CLEARED'
class EventOperation(StrEnum): CREATE='CREATE'; UPDATE='UPDATE'; CLEAR='CLEAR'
class ImpactState(StrEnum): NONE='NONE'; SURVEILLANCE='SURVEILLANCE'; IMPACT='IMPACT'
@dataclass(frozen=True)
class PredictedPoint: latitude:float; longitude:float; timestamp:Optional[datetime]=None; eta_seconds:Optional[float]=None
@dataclass(frozen=True)
class SquallEvent:
 event_id:str; observed_at:datetime; received_at:datetime; latitude:float; longitude:float; direction_deg:float; event_type:str='squall'; status:EventStatus=EventStatus.ACTIVE; speed_knots:Optional[float]=None; severity:Optional[str]=None; predicted_path:tuple[PredictedPoint,...]=(); impact_radius_nm:Optional[float]=None; surveillance_radius_nm:Optional[float]=None; source:Optional[str]=None; revision:Optional[str]=None; notes:Optional[str]=None; expires_at:Optional[datetime]=None
