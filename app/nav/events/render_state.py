from datetime import datetime,timezone
from .geometry import render
from .presentation import age,eta
from .models import ImpactState
from .impact import evaluate,evaluate_vessel,site_polygons
RANK={'IMPACT':2,'SURVEILLANCE':1,'NONE':0}
def empty(): return {'type':'FeatureCollection','features':[]}
class EventRenderStateBuilder:
 def __init__(self,service,spatial=None):
  self.service=service;self.spatial=spatial;self.selected_event_id=None
  self.vessel_position=None  # (lat, lon) of the own vessel, set by NAV; None when unknown
 def select_event(self,event_id):
  if event_id not in self.service._events:return False
  self.selected_event_id=event_id;return True
 def clear_event_selection(self):self.selected_event_id=None
 def payload(self):
  now=self.service.clock();collections={k:empty() for k in ('current','direction','trajectories','impact_zones','surveillance_zones','prediction_points','selection')};events=[]
  for event in sorted(self.service.snapshot()['events'],key=lambda e:e.event_id):
   site=str(evaluate(event,self.spatial.state if hasattr(self.spatial,'state') else self.spatial))
   vessel=str(evaluate_vessel(event,self.vessel_position))
   impact=site if RANK[site]>=RANK[vessel] else vessel
   r=render(event); props={'event_id':event.event_id,'event_type':'squall','status':str(event.status),'severity':event.severity,'impact_state':impact}
   for key,target in (('current','current'),('direction','direction'),('trajectory','trajectories')):
    f=r[key]
    if f is not None:
     f['properties'].update(props);collections[target]['features'].append(f)
   for key,target in (('impact','impact_zones'),('surveillance','surveillance_zones')):
    if r[key]:collections[target]['features'].append({'type':'Feature','properties':props,'geometry':{'type':'Polygon','coordinates':[r[key]]}})
   # ETAs are relative to the observation time; count down from now (GDS-AUDIT-021).
   elapsed=max(0.0,(now-event.observed_at).total_seconds())
   for point in event.predicted_path:
    seconds=point.eta_seconds if point.eta_seconds is not None else ((point.timestamp-event.observed_at).total_seconds() if point.timestamp else None)
    if seconds is not None:
     remaining=seconds-elapsed
     collections['prediction_points']['features'].append({'type':'Feature','properties':{**props,'eta_seconds':remaining,'eta_label':eta(remaining) if remaining>0 else 'PASSED'},'geometry':{'type':'Point','coordinates':[point.longitude,point.latitude]}})
   if event.event_id==self.selected_event_id:
    collections['selection']['features'] += [f for name,collection in collections.items() if name in ('current','trajectories','impact_zones') for f in collection['features'] if f['properties']['event_id']==event.event_id]
   etas=[remaining for remaining in ((p.eta_seconds if p.eta_seconds is not None else (p.timestamp-event.observed_at).total_seconds())-elapsed for p in event.predicted_path if p.eta_seconds is not None or p.timestamp) if remaining>0]
   events.append({'event_id':event.event_id,'status':str(event.status),'severity':event.severity,'impact_state':impact,'impact_reason':'own vessel' if vessel!='NONE' and RANK[vessel]>=RANK[site] else ('no site geometry' if not site_polygons(self.spatial.state if hasattr(self.spatial,'state') else self.spatial) else None),'vessel_impact':vessel,'observed_at':event.observed_at.isoformat(),'age_label':age(max(0,(now-event.received_at).total_seconds()),str(event.status)),'latitude':event.latitude,'longitude':event.longitude,'direction_deg':event.direction_deg,'speed_knots':event.speed_knots,'eta_label':eta(min(etas)) if etas else '—','source':event.source,'notes':event.notes})
  if self.selected_event_id not in self.service._events:self.selected_event_id=None
  events.sort(key=lambda e:({'IMPACT':0,'SURVEILLANCE':1,'NONE':2}[e['impact_state']],-datetime.fromisoformat(e['observed_at']).timestamp(),e['event_id']))
  feed=self.service.feed_status(now) if hasattr(self.service,'feed_status') else None
  return {'events':events,'active_count':len(events),'selected_event_id':self.selected_event_id,'updated_at':now.isoformat(),'geojson':collections,'feed':feed}
