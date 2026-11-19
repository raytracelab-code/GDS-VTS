"""Real OSM seamarks; community data, never represented as an official ENC."""
from .base import SourceAdapter, intersects_area
from .provider_common import bbox_parts, request_boxes, request_json, canonical_feature
from .provider_common import ProviderRequestError,query_url,OVERPASS_TIMEOUT
from urllib.parse import urlencode
import time
import logging
log=logging.getLogger(__name__)
from ..models import MaritimeDataError


SEAMARKS = {
    'platform':('offshore','offshore_installation'), 'production_area':('offshore','production_area'), 'mooring':('offshore','mooring'),
    'light_major':('aton','lighthouse'), 'light_minor':('aton','light'),
    'lighthouse':('aton','lighthouse'), 'light':('aton','light'),
    'offshore_platform':('offshore','offshore_installation'),
    'landmark':('aton','landmark'), 'radar_transponder':('aton','radar_beacon'),
    'anchorage':('anchorages','anchorage'), 'anchor_berth':('anchorages','anchor_berth'),
    'fairway':('routes','fairway'), 'navigation_line':('routes','navigation_line'),
    'recommended_track':('routes','recommended_track'), 'channel':('routes','navigation_channel'),
    'precautionary_area':('routes','precautionary_area'), 'pilot_boarding':('routes','pilot_boarding_area'),
    'restricted_area':('restricted','restricted_area'), 'pipeline_submarine':('subsea','submarine_pipeline'),
    'cable_submarine':('subsea','submarine_cable'), 'cable_area':('subsea','cable_area'),
    'wreck':('hazards','wreck'), 'rock':('hazards','rock'), 'obstruction':('hazards','obstruction'),
    'seabed_area':('hazards','seabed_area'), 'harbour':('ports','harbour'),
    'berth':('ports','berth'), 'terminal':('ports','terminal'),
}


def classify(tags):
    kind = tags.get('seamark:type','')
    if kind.startswith(('buoy_','beacon_')): return 'aton',kind
    if kind.startswith('separation_') or kind.startswith('traffic_separation'): return 'routes',kind
    if kind in SEAMARKS: return SEAMARKS[kind]
    man = tags.get('man_made','')
    if man == 'offshore_platform' or (man=='petroleum_well' and tags.get('location')=='offshore'): return 'offshore',man
    if man == 'lighthouse': return 'aton','lighthouse'
    if man == 'pipeline' and tags.get('location') in ('underwater','offshore'): return 'subsea','submarine_pipeline'
    if man == 'submarine_cable' or tags.get('seamark:cable_submarine:category'): return 'subsea','submarine_cable'
    if man=='cable' and tags.get('location')=='underwater':return 'subsea','submarine_cable'
    if tags.get('location')=='underwater' and tags.get('power') in ('cable','line'):return 'subsea','submarine_cable'
    if tags.get('industrial') in ('offshore_platform','oil','gas') and tags.get('location') == 'offshore': return 'offshore','offshore_installation'
    if tags.get('harbour') in ('yes','port','marina'): return 'ports','harbour'
    if tags.get('natural') in ('reef','shoal'): return 'hazards',tags['natural']
    return None


def query(area, boxes=None):
    parts=[]
    for w,s,e,n in request_boxes(area) if boxes is None else boxes:
        box=f'({s:.6f},{w:.6f},{n:.6f},{e:.6f})'
        for selector in ('["seamark:type"]','["man_made"~"^(offshore_platform|petroleum_well|lighthouse|pipeline|submarine_cable)$"]',
                         '["harbour"]','["location"="underwater"]','["industrial"~"^(oil|gas|offshore_platform)$"]["location"="offshore"]','["natural"~"^(reef|shoal)$"]'):
            parts.append('nwr'+selector+box+';')
    # maxsize is server RAM, not the response byte limit. Do not constrain the
    # interpreter to the client's 16 MB response budget.
    return '[out:json][timeout:25];('+''.join(parts)+');out meta geom;'


def join_rings(segments):
    segments=[list(s) for s in segments if len(s)>=2];rings=[]
    while segments:
        ring=segments.pop(0)
        while ring[0]!=ring[-1]:
            found=False
            for i,part in enumerate(segments):
                if part[0]==ring[-1]: ring+=part[1:]
                elif part[-1]==ring[-1]: ring+=list(reversed(part))[1:]
                elif part[-1]==ring[0]: ring=part[:-1]+ring
                elif part[0]==ring[0]: ring=list(reversed(part))[:-1]+ring
                else: continue
                segments.pop(i);found=True;break
            if not found: raise MaritimeDataError('incomplete OSM relation ring')
        rings.append(ring)
    return rings


def inside(point,ring):
    x,y=point;result=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result


def geometry(element):
    def points(items): return [[p['lon'],p['lat']] for p in items]
    if element['type']=='node': return dict(type='Point',coordinates=[element['lon'],element['lat']])
    if element['type']=='way':
        pts=points(element.get('geometry',[]))
        polygon=len(pts)>=4 and pts[0]==pts[-1] and element.get('tags',{}).get('area')!='no'
        return dict(type='Polygon' if polygon else 'LineString',coordinates=[pts] if polygon else pts)
    members=element.get('members',[])
    if element.get('tags',{}).get('type') in ('multipolygon','boundary'):
        outer=join_rings([points(m.get('geometry',[])) for m in members if m.get('type')=='way' and m.get('role','outer') in ('','outer')])
        inner=join_rings([points(m.get('geometry',[])) for m in members if m.get('type')=='way' and m.get('role')=='inner'])
        polygons=[[r] for r in outer]
        for hole in inner:
            owners=[p for p in polygons if inside(hole[0],p[0])]
            if len(owners)!=1: raise MaritimeDataError('ambiguous OSM inner ring')
            owners[0].append(hole)
        return dict(type='MultiPolygon',coordinates=polygons)
    lines=[points(m.get('geometry',[])) for m in members if m.get('type')=='way' and m.get('geometry')]
    return dict(type='MultiLineString',coordinates=lines)


class OverpassAdapter(SourceAdapter):
    def __init__(self,config,fallbacks=(),clock=time.monotonic):
        self.config=config;self.clock=clock;self._cooldown={};self._preferred=config.endpoint
        from threading import Event
        self._stopped=Event()
        self.endpoints=list(dict.fromkeys([config.endpoint]+list(fallbacks)[:2]))
        for endpoint in self.endpoints:query_url(endpoint,{})
    def fetch(self,area):
        candidates=sorted(self.endpoints,key=lambda endpoint:endpoint!=self._preferred)
        now=self.clock();available=[e for e in candidates if self._cooldown.get(e,0)<=now]
        if not available:raise ProviderRequestError('PROVIDER BACKOFF',min(self._cooldown.values())-now)
        last=None
        for endpoint in available[:2]:
            if self._stopped.is_set():raise ProviderRequestError('DISABLED')
            try:
                payload=request_json(endpoint,data=urlencode({'data':query(area)}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'},timeout=OVERPASS_TIMEOUT)
                objects=self.normalize(payload,area);self._preferred=endpoint
                return objects
            except ProviderRequestError as error:
                last=error;self._cooldown[endpoint]=self.clock()+max(120,error.retry_after)
                # Respect explicit rate limiting; do not evade 429 by hopping hosts.
                if error.state in ('HTTP 400','HTTP 401','HTTP 403','HTTP 429'):raise
        raise last
    def stop(self):
        # A closing application must not start a second network request after
        # an in-flight request returns. Existing I/O keeps its finite timeout.
        self._stopped.set()
    def normalize(self,payload,area):
        if not isinstance(payload,dict) or not isinstance(payload.get('elements'),list) or payload.get('remark'):
            raise MaritimeDataError('invalid or incomplete Overpass response')
        objects=[]
        for item in payload['elements']:
            tags=item.get('tags',{});classification=classify(tags)
            if not classification:continue
            try:
                props={'attribution':'© OpenStreetMap contributors (ODbL)','dataset_version':str(item.get('version','unknown'))}
                for key in ('name','operator','description'):
                    if isinstance(tags.get(key),str):props[key]=tags[key]
                characteristics=[f'{k}: {v}' for k,v in tags.items() if k.startswith('seamark:light:') and isinstance(v,str)]
                if characteristics:props['characteristic']='; '.join(characteristics)[:512]
                obj=canonical_feature('overpass',f"{item['type']}/{item['id']}",*classification,geometry(item),props,observed_at=item.get('timestamp'))
                if intersects_area(obj.geometry,area):objects.append(obj)
            except (KeyError,TypeError,ValueError):
                # Incomplete OSM geometry is not replaced with an invented centroid.
                continue
        from collections import Counter
        log.info('OVERPASS RAW ELEMENTS: %s NORMALIZED FEATURES: %s categories=%s types=%s',len(payload['elements']),len(objects),dict(Counter(str(o.category) for o in objects)),dict(Counter(o.object_type for o in objects)))
        return objects
