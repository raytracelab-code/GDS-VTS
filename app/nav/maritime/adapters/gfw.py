"""GFW satellite infrastructure; mandatory enable + licence acknowledgement gate."""
from datetime import datetime,timezone
import math
from .base import SourceAdapter,intersects_area
from .provider_common import bbox_parts,request_bytes,canonical_feature,ProviderUnavailable
from ..models import MaritimeDataError


class GfwAdapter(SourceAdapter):
    def __init__(self,config,enabled=False,license_ack=False):self.config=config;self.enabled=enabled;self.license_ack=license_ack
    def fetch(self,area):
        if not self.enabled or not self.license_ack:raise ProviderUnavailable('DISABLED_LICENSE')
        if not self.config.api_key:raise ProviderUnavailable('NOT_CONFIGURED')
        import mapbox_vector_tile
        tiles=set();z=6;size=2**z
        def tile(lon,lat):
            lat=max(-85.051128,min(85.051128,lat))
            return min(size-1,max(0,int((lon+180)/360*size))),min(size-1,max(0,int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size)))
        for w,s,e,n in bbox_parts(area):
            x0,y0=tile(w,n);x1,y1=tile(e,s)
            tiles.update((x,y) for x in range(x0,x1+1) for y in range(y0,y1+1))
        if len(tiles)>100:raise MaritimeDataError('GFW request area too large')
        objects=[]
        for x,y in sorted(tiles):
            content=request_bytes(self.config.endpoint+f'/context-layers/{z}/{x}/{y}',
                headers={'Authorization':'Bearer '+self.config.api_key,'Accept':'application/vnd.mapbox-vector-tile'})
            layers=mapbox_vector_tile.decode(content)
            rows=[]
            for layer in layers.values():
                for feature in layer['features']:
                    # MVT geometry is tile-local; GFW supplies actual WGS84 lat/lon
                    # attributes. Use those, never treat tile coordinates as degrees.
                    rows.append(feature['properties'])
                    if len(rows)>50000:raise MaritimeDataError('GFW tile exceeds feature limit')
            objects.extend(self.normalize(rows,area))
        return list({o.object_id:o for o in objects}.values())
    def normalize(self,payload,area):
        if not isinstance(payload,list) and (not isinstance(payload,dict) or payload.get('type')!='FeatureCollection'):
            raise MaritimeDataError('invalid GFW response envelope')
        rows=payload if isinstance(payload,list) else payload.get('features',[])
        if not isinstance(rows,list):raise MaritimeDataError('invalid GFW response')
        objects=[]
        for row in rows:
            p=row.get('properties',row);sid=p.get('structure_id')
            if sid is None:raise MaritimeDataError('missing GFW structure identity')
            geometry=row.get('geometry') or dict(type='Point',coordinates=[p.get('lon'),p.get('lat')])
            props={'classification':p.get('label','unknown'),'dataset_version':'public-fixed-infrastructure-filtered:latest',
                   'attribution':'Global Fishing Watch · satellite-derived infrastructure; observation lag applies'}
            if p.get('label_confidence') is not None:props['confidence']=p['label_confidence']
            stamp=p.get('structure_end_date')
            if isinstance(stamp,(int,float)):stamp=datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat()
            obj=canonical_feature('gfw',sid,'offshore','offshore_installation',geometry,props,'SATELLITE_DERIVED',observed_at=stamp)
            if intersects_area(obj.geometry,area):objects.append(obj)
        return objects
