import json
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from .models import *
from .validator import validate
from .exceptions import SquallEventError
SQUALL_STALE_SECONDS=120; SQUALL_EXPIRE_SECONDS=600
# Feed-level states (GDS-AUDIT-021). A feed is LIVE while messages arrive within FEED_STALE_SECONDS.
FEED_LIVE,FEED_STALE,FEED_NO_DATA,FEED_UNAVAILABLE='LIVE','STALE','NO DATA','PROVIDER UNAVAILABLE'
FEED_STALE_SECONDS=SQUALL_STALE_SECONDS
class SquallEventService:
 def __init__(self,clock=lambda:datetime.now(timezone.utc)):
  self.clock=clock;self._events={};self.lifecycle_log=[];self._listeners=[]
  # No production squall transport exists in this build: until a provider attaches (or a message
  # arrives through MainWindow.ingest_squall_*), the feed is PROVIDER UNAVAILABLE.
  self.provider_name=None;self.provider_connected=False;self.provider_error='';self.last_message_at=None
 def attach_provider(self,name):
  """A squall feed adapter announces itself; the feed is NO DATA until its first message."""
  self.provider_name=str(name);self.provider_connected=True;self.provider_error='';self._notify_changed()
 def provider_failed(self,reason='provider unavailable'):
  """The adapter lost its source. Existing events are marked STALE at once (never shown as current)
  and then expire through the normal lifecycle."""
  self.provider_connected=False;self.provider_error=str(reason)
  for eid,event in list(self._events.items()):
   if event.status is EventStatus.ACTIVE:self._events[eid]=replace(event,status=EventStatus.STALE);self.lifecycle_log.append(f'STALE {eid} (provider failed)')
  self._notify_changed()
 def provider_recovered(self):
  self.provider_connected=True;self.provider_error='';self._notify_changed()
 def heartbeat(self):
  """A keep-alive from the provider: the feed is current even when there are no events."""
  self.last_message_at=self.clock();self.provider_connected=True;self.provider_error=''
 def feed_status(self,now=None):
  now=now or self.clock()
  age=None if self.last_message_at is None else max(0.0,(now-self.last_message_at).total_seconds())
  if self.provider_error and not self.provider_connected:state=FEED_UNAVAILABLE
  elif self.provider_name is None and self.last_message_at is None:state=FEED_UNAVAILABLE
  elif self.last_message_at is None:state=FEED_NO_DATA
  else:state=FEED_LIVE if age<FEED_STALE_SECONDS else FEED_STALE
  detail=self.provider_error or ('No squall provider is configured in this build' if self.provider_name is None and self.last_message_at is None else '')
  return {'state':state,'provider':self.provider_name or ('external ingest' if self.last_message_at else None),
          'last_update':self.last_message_at.isoformat() if self.last_message_at else None,'age_seconds':age,'detail':detail}
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
  # A valid message proves the feed is delivering (receipt time; source timestamps are kept per event).
  self.last_message_at=now;self.provider_connected=True;self.provider_error=''
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
