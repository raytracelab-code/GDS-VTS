"""Official regional providers, capabilities discovery and bbox-only queries."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from .base import SourceAdapter,intersects_area
from .provider_common import bbox_parts,in_region,request_json,request_bytes,canonical_feature,ProviderUnavailable
from ..models import MaritimeDataError

US_REGIONS={'GOA_Layers':[(-98,18,-80,31)],'ATL_Layers':[(-83,24,-60,46)],
            'POC_Layers':[(-132,30,-117,50)],'AK_Layers':[(-180,48,-130,75),(170,48,180,72)]}
EUROPE=[(-32,27,45,73)]


def classification(name):
    name=name.lower()
    if 'pipeline' in name:return 'subsea','submarine_pipeline'
    if 'cable' in name:return 'subsea','submarine_cable'
    if 'platform' in name or 'offshore installation' in name:return 'offshore','offshore_installation'
    if 'well' in name or 'borehole' in name:return 'offshore','wellhead'
    if 'wind farm' in name or 'windfarm' in name:return 'offshore','offshore_wind_farm'
    if 'wreck' in name:return 'hazards','wreck'
    if 'dump' in name:return 'hazards','dumping_ground'
    if 'military' in name or 'restricted' in name:return 'restricted','restricted_area'
    if 'port' in name or 'marina' in name:return 'ports','harbour'
    return None


def normalize_features(payload,source,layer,category,kind,area,tier,dataset_at=None):
    if not isinstance(payload,dict) or payload.get('type')!='FeatureCollection':raise MaritimeDataError('expected provider GeoJSON')
    objects=[]
    for feature in payload.get('features',[]):
        props=feature.get('properties') or {};lower={k.lower():v for k,v in props.items()};sid=feature.get('id',lower.get('objectid',lower.get('fid')))
        if sid is None:raise MaritimeDataError('provider stable identity missing')
        selected={'attribution':source.upper(),'dataset_version':layer}
        for target,candidates in {'name':['name','platform_name','platform_n','sitename','portname','well_name'],
                                   'operator':['operator','operator_name','company'],'status':['status','p_status']}.items():
            value=next((lower[k] for k in candidates if isinstance(lower.get(k),str) and lower[k].strip()),None)
            if value:selected[target]=value[:512]
        obj=canonical_feature(source,layer+'/'+str(sid),category,kind,feature.get('geometry'),selected,tier,dataset_at=dataset_at)
        if intersects_area(obj.geometry,area):objects.append(obj)
    return objects


class BoemAdapter(SourceAdapter):
    def __init__(self,config):self.config=config;self._services={}
    def fetch(self,area):
        families=[key for key,boxes in US_REGIONS.items() if in_region(area,boxes)]
        if not families:raise ProviderUnavailable('OUT_OF_COVERAGE')
        objects=[]
        for family in families:
            url=self.config.endpoint.rstrip('/')+'/'+family+'/FeatureServer'
            if family not in self._services:self._services[family]=request_json(url,{'f':'json'})
            for layer in self._services[family].get('layers',[]):
                match=classification(layer['name'])
                if not match:continue
                for w,s,e,n in bbox_parts(area):
                    offset=0
                    for page in range(50):
                        p=request_json(url+f"/{layer['id']}/query",dict(f='geojson',where='1=1',outFields='*',returnGeometry='true',
                            geometry=json.dumps(dict(xmin=w,ymin=s,xmax=e,ymax=n,spatialReference={'wkid':4326})),
                            geometryType='esriGeometryEnvelope',inSR=4326,outSR=4326,spatialRel='esriSpatialRelIntersects',resultOffset=offset,resultRecordCount=1000))
                        objects.extend(normalize_features(p,'boem',family+'/'+str(layer['id']),*match,area,'OFFICIAL_GOVERNMENT'))
                        if not p.get('exceededTransferLimit') and len(p.get('features',[]))<1000:break
                        offset+=1000
                    else:raise MaritimeDataError('BOEM result exceeds bounded page limit')
        return list({o.object_id:o for o in objects}.values())


class EmodnetAdapter(SourceAdapter):
    PAGE_SIZE=1000
    def __init__(self,config):self.config=config;self._layers=None;self._requests=0
    def discover(self):
        root=ET.fromstring(request_bytes(self.config.endpoint,dict(service='WFS',version='2.0.0',request='GetCapabilities')))
        result={}
        for node in root.iter():
            if node.tag.split('}')[-1]!='FeatureType':continue
            name=next((c.text for c in node if c.tag.split('}')[-1]=='Name'),None)
            title=next((c.text for c in node if c.tag.split('}')[-1]=='Title'),'')
            match=classification(title)
            # Avoid historical per-year traffic tables: use actual port locations.
            if name and match and 'openstreetmap' not in title.lower() and not ('port' in title.lower() and 'location' not in title.lower()):result[name]=match
        return result
    def fetch(self,area):
        if not in_region(area,EUROPE):raise ProviderUnavailable('OUT_OF_COVERAGE')
        if self._layers is None:self._layers=self.discover()
        if not self._layers:raise MaritimeDataError('no compatible EMODnet feature types advertised')
        objects=[]
        self._requests=0
        # This GeoServer interprets a multi-type GET + BBOX as an invalid join.
        # Query each advertised type independently; cache avoids repeating area loads.
        for layer,match in self._layers.items():
            for w,s,e,n in bbox_parts(area):
                p={'type':'FeatureCollection','features':self._query_features(layer,(w,s,e,n))}
                objects.extend(normalize_features(p,'emodnet',layer,*match,area,'OFFICIAL_SERVICE'))
        return list({o.object_id:o for o in objects}.values())

    def _query_features(self,layer,box,depth=0):
        w,s,e,n=box
        params=dict(service='WFS',version='2.0.0',request='GetFeature',typeNames=layer,
                    srsName='urn:ogc:def:crs:OGC::CRS84',bbox=f'{w},{s},{e},{n},urn:ogc:def:crs:OGC::CRS84',outputFormat='application/json',count=self.PAGE_SIZE)
        def get(extra=None):
            self._requests+=1
            if self._requests>128:raise MaritimeDataError('EMODnet bounded request budget exceeded')
            p=request_json(self.config.endpoint,{**params,**(extra or {})})
            if p.get('type')!='FeatureCollection':raise MaritimeDataError('invalid WFS feature response')
            return p.get('features',[])
        first=get()
        if len(first)<self.PAGE_SIZE:return first
        # Explicit provider ID attributes permit deterministic pagination even when
        # the underlying SQL view has not declared a primary key to GeoServer.
        props=first[0].get('properties') or {}
        key=next((k for k in props if k.lower() in ('id','fid','gid','objectid') and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k)
                  and all(isinstance((f.get('properties') or {}).get(k),(str,int)) for f in first)
                  and len({(f.get('properties') or {})[k] for f in first})==len(first)),None)
        if key:
            features=[]
            for page in range(50):
                rows=get({'sortBy':key+' A','startIndex':page*self.PAGE_SIZE})
                features.extend(rows)
                if len(rows)<self.PAGE_SIZE:return features
            raise MaritimeDataError('EMODnet bounded pagination limit exceeded')
        # Keyless views cannot safely offset-page. Split the actual geographic query,
        # then deduplicate provider IDs, rather than returning a truncated dataset.
        if depth>=3:raise MaritimeDataError('EMODnet keyless result too dense for bounded subdivision')
        x,y=(w+e)/2,(s+n)/2
        rows=[]
        for child in ((w,s,x,y),(x,s,e,y),(w,y,x,n),(x,y,e,n)):rows.extend(self._query_features(layer,child,depth+1))
        return list({f['id']:f for f in rows}.values())
