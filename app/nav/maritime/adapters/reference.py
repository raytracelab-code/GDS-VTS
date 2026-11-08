"""Reference imagery only; no duplicate canonical targets or ENC claims."""
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from .base import SourceAdapter
from .provider_common import ProviderResult, request_bytes, request_json, query_url,ProviderUnavailable
from ..models import MaritimeDataError


class GebcoAdapter(SourceAdapter):
    def __init__(self,config):self.config=config;self._reference=None
    @staticmethod
    def layer_from_capabilities(content):
        root=ET.fromstring(content)
        layers=[n for n in root.iter() if n.tag.split('}')[-1]=='Layer']
        names=[]
        for layer in layers:
            name=next((c.text for c in layer if c.tag.split('}')[-1]=='Name'),None)
            if name:names.append(name)
        selected=next((n for n in names if n.upper()=='GEBCO_LATEST'),None)
        if not selected:raise MaritimeDataError('GEBCO current shaded-relief layer not advertised')
        if not any((n.text or '').upper() in ('EPSG:3857','EPSG:900913') for n in root.iter() if n.tag.split('}')[-1] in ('SRS','CRS')):
            raise MaritimeDataError('GEBCO Web Mercator not advertised')
        return selected
    def fetch(self,area):
        if self._reference is None:
            layer=self.layer_from_capabilities(request_bytes(self.config.endpoint,{'SERVICE':'WMS','REQUEST':'GetCapabilities'}))
            tile=query_url(self.config.endpoint,dict(SERVICE='WMS',VERSION='1.1.1',REQUEST='GetMap',LAYERS=layer,STYLES='',SRS='EPSG:3857',BBOX='{bbox-epsg-3857}',WIDTH=256,HEIGHT=256,FORMAT='image/png',TRANSPARENT='TRUE'))
            tile=tile.replace('%7Bbbox-epsg-3857%7D','{bbox-epsg-3857}')
            self._reference={'kind':'raster','tiles':[tile],'group':'Bathymetry','opacity':.4,'attribution':'GEBCO Compilation Group · GEBCO Grid · bathymetric context, not an ENC','layer':layer}
        return ProviderResult(reference_layers={'gebco':self._reference})


class OpenWatersAdapter(SourceAdapter):
    def __init__(self,config):self.config=config
    def fetch(self,area):
        payload=request_json(self.config.endpoint)
        if payload.get('version')!=8 or not payload.get('sources') or not payload.get('layers'):
            raise MaritimeDataError('invalid Open Waters MapLibre style')
        # Import nautical layers only, never replace the operational basemap.
        keywords=('seamark','nautical','bathym','depth','buoy','beacon','wreck','anchorage','tss')
        layers=[];sources={}
        for layer in payload['layers']:
            source=layer.get('source');spec=payload['sources'].get(source)
            title=' '.join(str(layer.get(k,'')) for k in ('id','source','source-layer')).lower()
            if not spec or not any(word in title for word in keywords):continue
            if layer.get('type') not in ('raster','line','fill','circle','symbol'):continue
            spec=dict(spec)
            if 'url' in spec:spec['url']=query_url(urljoin(self.config.endpoint,spec['url']),{})
            if 'tiles' in spec:spec['tiles']=[urljoin(self.config.endpoint,tile) for tile in spec['tiles']]
            if any(not tile.startswith('https://') for tile in spec.get('tiles',[])):raise MaritimeDataError('Open Waters requires HTTPS tiles')
            sources[source]=spec;layer=dict(layer)
            if layer['type']=='symbol':
                # Remote sprite atlases cannot be transplanted into the basemap.
                # Keep actual point geometry visible without relying on that atlas.
                layer={k:v for k,v in layer.items() if k not in ('layout','paint')}
                layer.update(type='circle',paint={'circle-radius':3,'circle-color':'#287c73'},filter=['==',['geometry-type'],'Point'])
            layers.append(layer)
        if not layers:raise ProviderUnavailable('NOT_CONFIGURED')
        return ProviderResult(reference_layers={'openwaters':{'kind':'overlay','sources':sources,'layers':layers,'group':'Aids to Navigation'}})


class OpenSeaMapAdapter(SourceAdapter):
    def __init__(self,config):self.config=config
    def fetch(self,area):
        content=request_bytes('https://tiles.openseamap.org/seamark/0/0/0.png')
        if not content.startswith(b'\x89PNG'):raise MaritimeDataError('invalid HTTPS seamark tile')
        return ProviderResult(reference_layers={'openseamap':{'kind':'raster','tiles':['https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png'],
            'group':'Aids to Navigation','opacity':1,'attribution':'© OpenSeaMap · © OpenStreetMap contributors (ODbL)'}})
