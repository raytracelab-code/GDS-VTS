"""AISStream WebSocket transport and schema normalizer; canonical store remains authoritative."""
import asyncio
from collections import OrderedDict, deque
from dataclasses import replace
import json
import logging
import random
import re
import threading
import time
from .base import SourceAdapter
from .provider_common import bbox_parts, request_boxes, canonical_feature
from ..models import normalize_ais, MaritimeDataError, timestamp, utcnow, text, number

ENDPOINT='wss://stream.aisstream.io/v0/stream'
MESSAGE_TYPES=['PositionReport','StandardClassBPositionReport','ExtendedClassBPositionReport',
               'ShipStaticData','StaticDataReport','AidsToNavigationReport']


def subscription(area,key):
    return {'APIKey':key,'BoundingBoxes':[[[s,w],[n,e]] for w,s,e,n in request_boxes(area)],'FilterMessageTypes':MESSAGE_TYPES}


def source_time(metadata):
    value=metadata.get('time_utc')
    if not value:return None
    return timestamp(re.sub(r' ([+-]\d{4}) UTC$',r'\1',value)).isoformat()


class AISStreamNormalizer:
    def __init__(self,clock=utcnow,stale_seconds=120,expire_seconds=600):
        self.clock=clock;self._metadata=OrderedDict();self.stale_seconds=stale_seconds;self.expire_seconds=expire_seconds
    def normalize(self,envelope,existing=None):
        try:return self._normalize(envelope,existing)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as error:
            raise MaritimeDataError('invalid AISStream message') from error
    def _normalize(self,envelope,existing=None):
        if not isinstance(envelope,dict):raise MaritimeDataError('invalid AISStream envelope')
        kind=envelope.get('MessageType')
        if kind=='SubscriptionConfirmation':return None
        if kind not in MESSAGE_TYPES:raise MaritimeDataError('unsupported AISStream message')
        meta=envelope.get('MetaData');messages=envelope.get('Message')
        if not isinstance(meta,dict) or not isinstance(messages,dict):raise MaritimeDataError('invalid AISStream metadata')
        body=messages.get(kind)
        if not isinstance(body,dict) or body.get('Valid') is not True:raise MaritimeDataError('invalid AISStream body')
        mmsi=str(body.get('UserID',meta.get('MMSI','')))
        if len(mmsi)!=9 or not mmsi.isascii() or not mmsi.isdigit():raise MaritimeDataError('invalid MMSI')
        if meta.get('MMSI') is not None and str(meta['MMSI'])!=mmsi:raise MaritimeDataError('mismatched AIS identity')
        observed=source_time(meta)
        if observed and (timestamp(observed)-self.clock()).total_seconds()>300:raise MaritimeDataError('future AIS timestamp')
        if kind=='AidsToNavigationReport':
            props={'mmsi':mmsi,'attribution':'AISStream.io'}
            for field,target in [('VirtualAtoN','virtual_aton'),('OffPosition','off_position'),('Type','ais_aton_type')]:
                if field in body:props[target]=body[field]
            if body.get('Name'):props['name']=body['Name'].strip('@ ')
            obj=canonical_feature('aisstream','aton/'+mmsi,'aton','ais_aid_to_navigation',
                {'type':'Point','coordinates':[body.get('Longitude'),body.get('Latitude')]},props,'LIVE_AIS',observed_at=observed)
            from datetime import timedelta
            base=timestamp(observed) if observed else self.clock()
            state='STALE' if (self.clock()-base).total_seconds()>=self.stale_seconds else 'LIVE'
            return replace(obj,received_at=self.clock(),expires_at=base+timedelta(seconds=self.expire_seconds),status=state,freshness=state if observed else 'UNKNOWN')
        metadata={}
        for field,target in [('Name','name'),('ImoNumber','imo'),('CallSign','call_sign'),('Type','ship_type'),('Destination','destination'),('MaximumStaticDraught','draught')]:
            value=body.get(field)
            if value not in (None,'',0):
                value=value.strip('@ ') if isinstance(value,str) else value
                if value!='':metadata[target]=value
        eta=body.get('Eta')
        if isinstance(eta,dict) and 1<=eta.get('Month',0)<=12 and 1<=eta.get('Day',0)<=31 and 0<=eta.get('Hour',24)<24 and 0<=eta.get('Minute',60)<60:
            metadata['eta']=f"{eta['Month']:02d}-{eta['Day']:02d} {eta['Hour']:02d}:{eta['Minute']:02d} UTC (year unavailable)"
        if kind=='StaticDataReport':
            a,b=body.get('ReportA',{}),body.get('ReportB',{})
            if a.get('Valid') and a.get('Name'):metadata['name']=a['Name'].strip('@ ')
            if b.get('Valid'):
                if b.get('CallSign'):metadata['call_sign']=b['CallSign'].strip('@ ')
                if b.get('ShipType'):metadata['ship_type']=b['ShipType']
        old=self._metadata.get(mmsi,({},None))
        for key,value in metadata.items():
            if key=='draught':number(value,0,100,key)
            elif isinstance(value,(str,int)) and not isinstance(value,bool):text(str(value),key,limit=256)
            else:raise MaritimeDataError('invalid static metadata')
        if not old[1] or not observed or observed>=old[1]:
            metadata={**old[0],**metadata};self._metadata[mmsi]=(metadata,observed);self._metadata.move_to_end(mmsi)
        else:metadata=old[0]
        while len(self._metadata)>10000:self._metadata.popitem(last=False)
        static=kind in ('ShipStaticData','StaticDataReport')
        if static:
            if existing is None:return None
            return replace(existing,properties={**existing.properties,**metadata,'source_tier':'LIVE_AIS','attribution':'AISStream.io'})
        if existing and existing.observed_at and observed and timestamp(observed)<existing.observed_at:return None
        data={**metadata,'mmsi':mmsi,'latitude':body.get('Latitude',meta.get('latitude',meta.get('Latitude'))),
              'longitude':body.get('Longitude',meta.get('longitude',meta.get('Longitude'))),'position_timestamp':observed}
        if not data.get('name') and meta.get('ShipName'):data['name']=meta['ShipName'].strip('@ ')
        for field,target in [('Sog','sog'),('Cog','cog'),('TrueHeading','heading'),('NavigationalStatus','navigation_status')]:
            if field in body:data[target]=body[field]
        obj=normalize_ais(data,'aisstream',self.clock())
        return replace(obj,properties={**obj.properties,'source_tier':'LIVE_AIS','attribution':'AISStream.io'})


class AISStreamAdapter(SourceAdapter):
    def __init__(self,key,connector=None):
        self._key=key;self._area=None;self._lock=threading.Lock();self._messages=deque(maxlen=5000)
        self._connector=connector
        self._stop=threading.Event();self._thread=None;self._loop=None;self._task=None
        self.state='CONNECTING';self.message_count=0;self.dropped=0;self.confirmed=False
    def fetch(self,area):raise RuntimeError('AISStream is a streaming adapter')
    def start(self,area):
        self.update_area(area)
        if self._thread is None:
            self._thread=threading.Thread(target=self._run,name='aisstream',daemon=True);self._thread.start()
    def update_area(self,area):
        with self._lock:self._area=area
    def drain(self):
        with self._lock:
            messages=list(self._messages);self._messages.clear()
            return messages,self.state,self.confirmed
    def stop(self):
        self._stop.set()
        if self._loop and self._task and self._loop.is_running():self._loop.call_soon_threadsafe(self._task.cancel)
        if self._thread:self._thread.join(timeout=2)
    def _run(self):
        try:asyncio.run(self._session())
        except asyncio.CancelledError:pass
        except Exception:self.state='ERROR'
    async def _session(self):
        connect=self._connector
        if connect is None:
            from websockets.asyncio.client import connect
        self._loop=asyncio.get_running_loop();self._task=asyncio.current_task();attempt=0
        # WebSocket frame debug logs would contain the subscription API key.
        transport_log=logging.Logger('gds.aisstream.transport',level=logging.CRITICAL+1)
        transport_log.disabled=True
        while not self._stop.is_set():
            self.state='CONNECTING';self.confirmed=False
            try:
                async with connect(ENDPOINT,compression='deflate',open_timeout=10,close_timeout=2,ping_interval=20,max_size=1024*1024,max_queue=32,logger=transport_log) as socket:
                    with self._lock:area=self._area
                    await socket.send(json.dumps(subscription(area,self._key)));sent=time.monotonic()
                    while not self._stop.is_set():
                        with self._lock:current=self._area
                        if current!=area and time.monotonic()-sent>=1:
                            await socket.send(json.dumps(subscription(current,self._key)));area=current;sent=time.monotonic()
                        try:frame=await asyncio.wait_for(socket.recv(),timeout=1)
                        except asyncio.TimeoutError:continue
                        try:
                            payload=json.loads(frame)
                            if not isinstance(payload,dict):continue
                            if payload.get('MessageType')=='SubscriptionConfirmation':
                                self.confirmed=True;attempt=0;self.state='LIVE';continue
                            if payload.get('error') or payload.get('Error'):raise ConnectionError('AISStream rejected subscription')
                            if payload.get('MessageType') not in MESSAGE_TYPES:continue
                            with self._lock:
                                if len(self._messages)==self._messages.maxlen:self.dropped+=1
                                self._messages.append(payload);self.message_count+=1
                        except (ValueError,UnicodeError):continue
            except asyncio.CancelledError:raise
            except Exception:
                self.state='DEGRADED';attempt+=1
                await asyncio.sleep(min(30,2**min(attempt,5))+random.random())
