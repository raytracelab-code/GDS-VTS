"""Small transport/coverage helpers shared by real providers, not another store."""
from dataclasses import dataclass, field
import json
import math
import logging
import socket
import ssl
import time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from .base import MAX_RESPONSE_BYTES
from ..models import MaritimeDataError, normalize_maritime_feature

log=logging.getLogger(__name__)


class ProviderRequestError(MaritimeDataError):
    """Only bounded, non-secret reason codes cross the worker/UI boundary."""
    def __init__(self,reason,retry_after=0):
        self.state=reason;self.retry_after=retry_after
        super().__init__(reason)


def retry_delay(value):
    try:
        seconds=float(value)
        return min(86400,max(0,seconds)) if math.isfinite(seconds) else 0
    except (ValueError,TypeError):
        try:return max(0,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError,OverflowError):return 0


def network_reason(error):
    if isinstance(error,HTTPError):return f'HTTP {error.code}'
    reason=error.reason if isinstance(error,URLError) else error
    if isinstance(reason,(TimeoutError,socket.timeout)):return 'TIMEOUT'
    if isinstance(reason,socket.gaierror):return 'DNS ERROR'
    if isinstance(reason,ssl.SSLError):return 'TLS ERROR'
    return 'NETWORK ERROR'


class ProviderUnavailable(MaritimeDataError):
    def __init__(self, state):
        self.state = state
        super().__init__(state)


@dataclass
class ProviderResult:
    objects: list = field(default_factory=list)
    reference_layers: dict = field(default_factory=dict)


def bbox_parts(area):
    """WGS84 west/south/east/north boxes, split at the antimeridian."""
    if area.viewport_bounds is not None:
        w,s,e,n=area.viewport_bounds
        return [(w,s,e,n)] if w<e else [(w,s,180,n),(-180,s,e,n)]
    angular = area.radius_nm/3440.065
    dy = math.degrees(angular)
    south, north = max(-90, area.latitude-dy), min(90, area.latitude+dy)
    cosine=math.cos(math.radians(area.latitude))
    dx=180 if abs(cosine)<.0001 or math.sin(angular)>=cosine else math.degrees(math.asin(math.sin(angular)/cosine))
    if south <= -90 or north >= 90 or dx >= 180:
        return [(-180, south, 180, north)]
    west, east = area.longitude-dx, area.longitude+dx
    if west < -180:
        return [(west+360, south, 180, north), (-180, south, east, north)]
    if east > 180:
        return [(west, south, 180, north), (-180, south, east-360, north)]
    return [(west, south, east, north)]


def request_boxes(area):
    """Boxes for transmission to external services: outward-snapped, never narrower."""
    from ..privacy import widen_bounds
    return [widen_bounds(*box) for box in bbox_parts(area)]


def in_region(area, boxes):
    return any(w <= re and e >= rw and s <= rn and n >= rs
               for w,s,e,n in bbox_parts(area) for rw,rs,re,rn in boxes)


def query_url(endpoint, params):
    p = urlsplit(endpoint)
    if p.scheme != 'https' or p.username or p.password:
        raise MaritimeDataError('provider requires HTTPS without embedded credentials')
    replace = {k.lower() for k in params}
    query = [(k,v) for k,v in parse_qsl(p.query) if k.lower() not in replace]
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(query+list(params.items())),''))


# Socket timeout (connect and each read). Overpass passes OVERPASS_TIMEOUT because its
# server-side query budget is [timeout:25]; shutdown never waits for either.
DEFAULT_TIMEOUT = 20
OVERPASS_TIMEOUT = 35


def request_bytes(endpoint, params=None, *, data=None, headers=None, timeout=DEFAULT_TIMEOUT):
    url = query_url(endpoint, params or {})
    h = {'User-Agent':'GDS-VTS-Maritime/4R','Accept':'application/json, application/xml, text/xml'}
    h.update(headers or {})
    started=time.monotonic();public=urlsplit(endpoint)
    label=urlunsplit((public.scheme,public.netloc,public.path,'',''))
    try:
        with urlopen(Request(url,data=data,headers=h),timeout=timeout) as response:
            content = response.read(MAX_RESPONSE_BYTES+1)
            safe_headers={key:response.headers.get(key) for key in ('Content-Type','Content-Length','Retry-After','Server') if getattr(response,'headers',None) and response.headers.get(key)}
            log.info('PROVIDER HTTP endpoint=%s status=%s bytes=%s elapsed=%.2fs headers=%s',label,getattr(response,'status',200),len(content),time.monotonic()-started,safe_headers)
    except (HTTPError,URLError,TimeoutError,ssl.SSLError,OSError) as error:
        reason=network_reason(error)
        delay=retry_delay(error.headers.get('Retry-After')) if isinstance(error,HTTPError) and error.headers else 0
        size=0;safe_headers={}
        if isinstance(error,HTTPError):
            safe_headers={key:error.headers.get(key) for key in ('Content-Type','Content-Length','Retry-After','Server') if error.headers and error.headers.get(key)}
            try:size=len(error.read(MAX_RESPONSE_BYTES+1))
            except OSError:pass
        log.warning('PROVIDER HTTP endpoint=%s result=%s bytes=%s elapsed=%.2fs retry_after=%.0fs headers=%s',label,reason,size,time.monotonic()-started,delay,safe_headers)
        raise ProviderRequestError(reason,delay) from None
    if len(content) > MAX_RESPONSE_BYTES:
        raise ProviderRequestError('RESPONSE TOO LARGE')
    return content


def request_json(endpoint, params=None, **kwargs):
    content=request_bytes(endpoint,params,**kwargs)
    try:payload = json.loads(content)
    except (ValueError,UnicodeError):raise ProviderRequestError('INVALID RESPONSE') from None
    if isinstance(payload,dict) and (payload.get('error') or payload.get('remark')):
        remark=str(payload.get('remark','')).lower()
        reason='QUERY MEMORY LIMIT' if 'memory' in remark else 'QUERY TIMEOUT' if 'timed out' in remark or 'timeout' in remark else 'PROVIDER ERROR'
        raise ProviderRequestError(reason)
    return payload


def canonical_feature(source, sid, category, kind, geometry, properties=None, tier='COMMUNITY', observed_at=None, dataset_at=None):
    props = dict(properties or {}, category=category, object_type=kind, source_tier=tier)
    if observed_at: props['observed_at'] = observed_at
    if dataset_at: props['dataset_at'] = dataset_at
    return normalize_maritime_feature(dict(type='Feature',id=str(sid),geometry=geometry,properties=props),source)
