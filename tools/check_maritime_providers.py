"""Bounded real-provider diagnostics. Never injects diagnostic objects into NAV.

python tools/check_maritime_providers.py overpass gebco boem emodnet
Only public diagnostic bboxes are used; credentials and full GeoJSON are not printed.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import math
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.nav.maritime.area_controller import OperatingArea
from app.nav.maritime.adapters.base import SourceConfig
from app.nav.maritime.adapters.overpass import OverpassAdapter
from app.nav.maritime.adapters.reference import GebcoAdapter,OpenWatersAdapter,OpenSeaMapAdapter
from app.nav.maritime.adapters.regional import BoemAdapter,EmodnetAdapter
from app.nav.maritime.adapters.provider_common import request_bytes


def check(name,overpass_radius=10):
    if name=='openwaters' and not os.environ.get('GDS_OPENWATERS_STYLE_URL','').strip():
        return dict(provider=name,result='NOT_CONFIGURED',reason='No configured MapLibre style URL; no request made')
    definitions={
        'overpass':(OverpassAdapter,'https://overpass-api.de/api/interpreter',OperatingArea(22.25,91.8,overpass_radius,'diagnostic')),
        'gebco':(GebcoAdapter,'https://wms.gebco.net/mapserv?',OperatingArea(22.25,91.8,10,'diagnostic')),
        'boem':(BoemAdapter,'https://gis.boem.gov/server/rest/services/BOEM_BSEE/',OperatingArea(28.5,-90,2,'diagnostic')),
        'emodnet':(EmodnetAdapter,'https://ows.emodnet-humanactivities.eu/wfs?',OperatingArea(55,2,5,'diagnostic')),
        'openwaters':(OpenWatersAdapter,'https://tiles.openwaters.io/seamap/style.json',OperatingArea(22.25,91.8,10,'diagnostic')),
        'openseamap':(OpenSeaMapAdapter,'https://tiles.openseamap.org/seamark/',OperatingArea(22.25,91.8,10,'diagnostic'))}
    cls,endpoint,area=definitions[name]
    setting={'overpass':'GDS_OVERPASS_ENDPOINT','gebco':'GDS_GEBCO_WMS_ENDPOINT',
             'boem':'GDS_BOEM_BASE_URL','emodnet':'GDS_EMODNET_WFS_ENDPOINT','openwaters':'GDS_OPENWATERS_STYLE_URL'}
    endpoint=os.environ.get(setting.get(name,''),endpoint)
    try:
        result=cls(SourceConfig(name,endpoint)).fetch(area)
        if name=='gebco':
            ref=result.reference_layers['gebco']
            x=6378137*math.radians(area.longitude);y=6378137*math.log(math.tan(math.pi/4+math.radians(area.latitude)/2))
            tile=ref['tiles'][0].replace('{bbox-epsg-3857}',','.join(str(v) for v in (x-10000,y-10000,x+10000,y+10000)))
            image=request_bytes(tile)
            return dict(provider=name,result='REAL NETWORK VALIDATED' if image.startswith(b'\x89PNG') else 'INVALID TILE',layer=ref['layer'],tile_bytes=len(image),area=area.payload())
        if name in ('openwaters','openseamap'):
            return dict(provider=name,result='REAL NETWORK VALIDATED',kind=result.reference_layers[name]['kind'],area=area.payload())
        return dict(provider=name,result='REAL NETWORK VALIDATED',count=len(result),categories=dict(Counter(str(o.category) for o in result)),
                    object_types=dict(Counter(o.object_type for o in result)),area=area.payload())
    except Exception as error:
        return dict(provider=name,result='FAILED',error=type(error).__name__,
                    reason=getattr(error,'state',None),http_status=getattr(error,'code',None),area=area.payload())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('providers',nargs='*',choices=['overpass','gebco','boem','emodnet','openwaters','openseamap'])
    parser.add_argument('--overpass-radius-nm',type=float,default=10,help='Chattogram diagnostic radius (1–250 NM)')
    parser.add_argument('--output',type=Path,help='Save bounded diagnostics without credentials or response bodies')
    args=parser.parse_args()
    if not 1<=args.overpass_radius_nm<=250:parser.error('diagnostic radius must be between 1 and 250 NM')
    failed=False;results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(check,name,args.overpass_radius_nm) for name in (args.providers or ['overpass','gebco','boem','emodnet'])]):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
            failed|=result['result'] not in ('REAL NETWORK VALIDATED','NOT_CONFIGURED')
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({'providers':sorted(results,key=lambda r:r['provider'])},indent=2)+'\n',encoding='utf-8')
    return int(failed)


if __name__=='__main__':raise SystemExit(main())
