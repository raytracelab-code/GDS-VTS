import os
from pathlib import Path
from .adapters.base import SourceConfig
from .models import number, MaritimeDataError


def setting_number(env, key, default, low, high):
    try:
        return number(float(env.get(key, default)), low, high, key)
    except ValueError as error:
        raise MaritimeDataError('invalid maritime numeric configuration') from error


class MaritimeConfig:
    def __init__(self, env=None):
        real_providers = env is None or any(k.startswith(('AISSTREAM_','COPERNICUSMARINE_','GDS_OVERPASS_','GDS_GEBCO_','GDS_BOEM_','GDS_EMODNET_','GDS_GFW_','GDS_CMEMS_','GDS_OPENWATERS_','GDS_OPENSEAMAP_','GDS_NAVAREA8_','GDS_MALAYSIA_')) for k in env)
        env = os.environ if env is None else env
        self.provider_env = {k:v for k,v in env.items() if k.startswith(('AISSTREAM_','COPERNICUSMARINE_','GDS_'))} if real_providers else None
        self.radius_nm = setting_number(env, 'GDS_MARITIME_RADIUS_NM', 50, 1, 250)
        self.movement_nm = setting_number(env, 'GDS_MARITIME_MOVE_NM', min(10, self.radius_nm), .1, self.radius_nm)
        self.debounce_seconds = setting_number(env, 'GDS_MARITIME_DEBOUNCE_SECONDS', 3, 0, 600)
        self.stale_seconds = setting_number(env, 'GDS_AIS_STALE_SECONDS', 120, 1, 86400)
        self.expire_seconds = setting_number(env, 'GDS_AIS_EXPIRE_SECONDS', 600, self.stale_seconds+1, 604800)
        self.own_mmsi = env.get('GDS_OWN_MMSI')
        self.cache_directory = Path(env.get('GDS_MARITIME_CACHE_DIR', str(Path(os.environ.get('LOCALAPPDATA', Path.home()))/'GDS'/'VTS'/'maritime-cache')))
        self.sources = {}
        for name in ('ais', 'chart', 'offshore', 'warnings', 'metocean'):
            prefix = 'GDS_'+name.upper()
            endpoint = env.get(prefix+'_ENDPOINT') or env.get(prefix+'_SOURCE', '')
            if endpoint:
                dynamic = name in ('ais', 'warnings', 'metocean')
                self.sources[name] = SourceConfig(name, endpoint, env.get(prefix+'_API_KEY', ''), dynamic,
                    setting_number(env, prefix+'_POLL_SECONDS', 10 if name == 'ais' else 300, 1, 86400))
