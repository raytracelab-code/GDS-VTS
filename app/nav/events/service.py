import json
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from .models import *
from .validator import validate
from .exceptions import SquallEventError
SQUALL_STALE_SECONDS=120; SQUALL_EXPIRE_SECONDS=600
class SquallEventService:
 def __init__(self,clock=lambda:datetime.now(timezone.utc)):self.clock=clock;self._events={};self.lifecycle_log=[];self._listeners=[]
 def add_listener(self, callback):
  if callback not in self._listeners:self._listeners.append(callback)
 def remove_listener(self, callback):
  if callback in self._listeners:self._listeners.remove(callback)
 def _notify_changed(self):
  for callback in tuple(self._listeners):callback()
 @property
 def active_count(self):return len(self._events)
 def snapshot(self):return {'events':tuple(self._events.values()),'active_count':len(self._events),'updated_at':self.clock()}
 def ingest_json(self,text):
  try:payload=json.loads(text)
  except (ValueError,TypeError) as error:raise SquallEventError('invalid event JSON') from error
  return self.ingest_mapping(payload)
 def ingest_mapping(self,mapping):
  if not isinstance(mapping,dict):raise SquallEventError('event must be an object')
  now=self.clock();eid=mapping.get('event_id')
  if not isinstance(eid,str) or not eid.strip():raise SquallEventError('invalid event_id')
  prev=self._events.get(eid);op,eid,data,clear_time=validate(mapping,now,prev)
  if op is EventOperation.CLEAR:
   if eid in self._events:del self._events[eid];self.lifecycle_log.append(f'CLEAR {eid}');self._notify_changed();return True
   return False
  if op is EventOperation.CREATE and prev:raise SquallEventError('duplicate CREATE')
  if op is EventOperation.UPDATE and not prev:raise SquallEventError('unknown UPDATE')
  if prev and data['observed_at']<prev.observed_at:return False
  event=SquallEvent(event_id=eid,received_at=now,**data)
  if prev and replace(prev,received_at=now,status=EventStatus.ACTIVE)==event:return False
  self._events[eid]=event;self.lifecycle_log.append(f'{op.value} {eid}');self._notify_changed();return True
 def evaluate_time(self,now=None):
  now=now or self.clock()
  for eid,event in list(self._events.items()):
   deadline=event.expires_at or event.received_at+timedelta(seconds=SQUALL_EXPIRE_SECONDS)
   if now>=deadline:del self._events[eid];self.lifecycle_log.append(f'EXPIRED {eid}');self._notify_changed()
   elif now-event.received_at>timedelta(seconds=SQUALL_STALE_SECONDS) and event.status is EventStatus.ACTIVE:self._events[eid]=replace(event,status=EventStatus.STALE);self.lifecycle_log.append(f'STALE {eid}');self._notify_changed()
