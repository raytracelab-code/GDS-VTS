"""Provider registration only; reuse MaritimeRuntime's I/O, cache and canonical store."""
from .adapters.base import SourceConfig
from .adapters.overpass import OverpassAdapter
from .adapters.reference import GebcoAdapter,OpenWatersAdapter,OpenSeaMapAdapter
from .adapters.regional import BoemAdapter,EmodnetAdapter
from .adapters.gfw import GfwAdapter
from .adapters.copernicus import CopernicusAdapter
from .adapters.navarea import Navarea8Adapter
from .adapters.aisstream import AISStreamAdapter,AISStreamNormalizer
from .source_health import SourceHealth,SourceState


def enabled(env,key,default=False):return str(env.get(key,str(default))).strip().lower() in ('true','1','yes')


def install(runtime,env):
    service=runtime.service
    for key in list(service.sources):
        if key not in runtime.config.sources:del service.sources[key]
    from .adapters.malaysia import MalaysiaOffshoreGISProvider
    from .malaysia_config import dataset_directory, read_manifest
    runtime.malaysia_gis = MalaysiaOffshoreGISProvider(dataset_directory(env))
    service.sources['malaysia_gis'] = SourceHealth()
    service.offshore_source_priority = tuple(key.strip() for key in env.get('GDS_OFFSHORE_SOURCE_PRIORITY','malaysia_gis,overpass').split(',') if key.strip())
    try:
        service.gis_layers = {layer['dataset_id']:layer for layer in read_manifest(runtime.malaysia_gis.directory)['layers']}
        service.visibility.update({key:layer['default_visibility'] for key,layer in service.gis_layers.items()})
    except (OSError,ValueError,KeyError):
        pass  # Worker reports the manifest error without preventing other providers.
    runtime.aisstream=None;runtime.ais_normalizer=AISStreamNormalizer(service.clock,service.stale_seconds,service.expire_seconds)
    def register(name,endpoint,adapter,active=True,state='DISABLED',dynamic=False,interval=86400,key=''):
        service.sources[name]=SourceHealth(state=SourceState.CONNECTING if active else SourceState(state),dynamic=dynamic)
        if active:
            config=SourceConfig(name,endpoint,key,dynamic,interval)
            runtime.config.sources[name]=config;runtime.adapters[name]=adapter(config)
    fallbacks=[url.strip() for url in env.get('GDS_OVERPASS_FALLBACK_ENDPOINTS','https://overpass.private.coffee/api/interpreter').split(',') if url.strip()]
    register('overpass',env.get('GDS_OVERPASS_ENDPOINT') or 'https://overpass-api.de/api/interpreter',lambda c:OverpassAdapter(c,fallbacks))
    ais_enabled=str(env.get('AISSTREAM_ENABLED','')).strip().lower() not in ('false','0','no','off');ais_key=env.get('AISSTREAM_API_KEY','').strip()
    service.sources['aisstream']=SourceHealth(state=SourceState.CONNECTING if ais_enabled and ais_key else SourceState.NOT_CONFIGURED if ais_enabled else SourceState.DISABLED,dynamic=True)
    if ais_enabled and ais_key:runtime.aisstream=AISStreamAdapter(ais_key)
    register('gebco',env.get('GDS_GEBCO_WMS_ENDPOINT') or 'https://wms.gebco.net/mapserv?',GebcoAdapter,enabled(env,'GDS_GEBCO_ENABLED',True),dynamic=True)
    style=env.get('GDS_OPENWATERS_STYLE_URL','').strip()
    register('openwaters',style,OpenWatersAdapter,enabled(env,'GDS_OPENWATERS_ENABLED') and bool(style),'NOT_CONFIGURED',dynamic=True)
    register('openseamap','https://tiles.openseamap.org/seamark/',OpenSeaMapAdapter,enabled(env,'GDS_OPENSEAMAP_ENABLED'),dynamic=True)
    register('boem',env.get('GDS_BOEM_BASE_URL','https://gis.boem.gov/server/rest/services/BOEM_BSEE/'),BoemAdapter,enabled(env,'GDS_BOEM_ENABLED'))
    register('emodnet',env.get('GDS_EMODNET_WFS_ENDPOINT','https://ows.emodnet-humanactivities.eu/wfs?'),EmodnetAdapter,enabled(env,'GDS_EMODNET_ENABLED'))
    gfw_on=enabled(env,'GDS_GFW_ENABLED') and enabled(env,'GDS_GFW_LICENSE_ACK');gfw_key=env.get('GDS_GFW_API_TOKEN','')
    register('gfw','https://gateway.api.globalfishingwatch.org/v3/datasets/public-fixed-infrastructure-filtered:latest',
             lambda c:GfwAdapter(c,True,True),gfw_on and bool(gfw_key),'NOT_CONFIGURED' if gfw_on else 'DISABLED_LICENSE',key=gfw_key)
    for product in ('wave','current','sst','sealevel'):
        dataset=env.get('GDS_CMEMS_'+product.upper()+'_DATASET','');username=env.get('COPERNICUSMARINE_USERNAME','');password=env.get('COPERNICUSMARINE_PASSWORD','')
        register('copernicus_'+product,'https://marine.copernicus.eu/'+dataset,
                 lambda c,p=product,d=dataset,u=username,pw=password:CopernicusAdapter(c,p,d,u,pw),bool(dataset and username and password),'NOT_CONFIGURED',dynamic=True,interval=3600)
    register('navarea8',env.get('GDS_NAVAREA8_SOURCE_URL','https://hydrobharat.gov.in/navarea-warnings/'),Navarea8Adapter,
             False,'NO_STABLE_MACHINE_API' if enabled(env,'GDS_NAVAREA8_ENABLED',True) else 'DISABLED')
