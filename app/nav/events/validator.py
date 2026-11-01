from datetime import datetime,timezone
from math import isfinite
from .models import *
from .exceptions import SquallEventError
def _time(v):
 try:
  result=v if isinstance(v,datetime) else datetime.fromisoformat(v.replace('Z','+00:00'))
  if result.tzinfo is None:raise ValueError('timezone required')
  return result.astimezone(timezone.utc)
 except Exception: raise SquallEventError('invalid timestamp')
def _num(v,name,lo=None,hi=None,allow_none=False):
 if v is None and allow_none:return None
 if not isinstance(v,(int,float)) or isinstance(v,bool) or not isfinite(v):raise SquallEventError(f'invalid {name}')
 if lo is not None and v<lo or hi is not None and v>hi:raise SquallEventError(f'invalid {name}')
 return float(v)
def validate(mapping,now,previous=None):
 if not isinstance(mapping,dict):raise SquallEventError('event must be an object')
 try:op=EventOperation(mapping.get('operation',''))
 except (ValueError,TypeError):raise SquallEventError('invalid operation')
 if mapping.get('event_type','squall')!='squall':raise SquallEventError('unsupported event type')
 eid=mapping.get('event_id');
 if not isinstance(eid,str) or not eid.strip():raise SquallEventError('invalid event_id')
 if op is EventOperation.CLEAR:return op,eid,{},_time(mapping.get('observed_at',now))
 merged={**(previous.__dict__ if previous else {}),**{k:v for k,v in mapping.items() if k not in ('operation','event_type')}}
 required=('observed_at','latitude','longitude','direction_deg')
 if any(merged.get(k) is None for k in required):raise SquallEventError('missing required event state')
 lat=_num(merged['latitude'],'latitude',-90,90);lon=_num(merged['longitude'],'longitude',-180,180);direction=_num(merged['direction_deg'],'direction',0,360)%360
 speed=_num(merged.get('speed_knots'),'speed',0,allow_none=True);impact=_num(merged.get('impact_radius_nm'),'impact radius',0,allow_none=True);surv=_num(merged.get('surveillance_radius_nm'),'surveillance radius',0,allow_none=True)
 if impact==0 or surv==0 or impact and surv and surv<impact:raise SquallEventError('invalid radii')
 path=[]
 for field in ('severity','source','revision','notes'):
  if merged.get(field) is not None and not isinstance(merged[field],str):raise SquallEventError(f'invalid {field}')
 if merged.get('predicted_path') is not None and not isinstance(merged['predicted_path'],(list,tuple)):raise SquallEventError('invalid predicted path')
 for p in merged.get('predicted_path') or ():
  if isinstance(p,PredictedPoint):p=p.__dict__
  if not isinstance(p,dict):raise SquallEventError('invalid predicted point')
  path.append(PredictedPoint(_num(p.get('latitude'),'path latitude',-90,90),_num(p.get('longitude'),'path longitude',-180,180),_time(p['timestamp']) if p.get('timestamp') else None,_num(p.get('eta_seconds'),'eta',0,allow_none=True)))
 return op,eid,dict(observed_at=_time(merged['observed_at']),latitude=lat,longitude=lon,direction_deg=direction,speed_knots=speed,severity=merged.get('severity'),predicted_path=tuple(path),impact_radius_nm=impact,surveillance_radius_nm=surv,source=merged.get('source'),revision=merged.get('revision'),notes=merged.get('notes'),expires_at=_time(merged['expires_at']) if merged.get('expires_at') else None),None
