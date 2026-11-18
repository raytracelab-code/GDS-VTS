"""Viewport resolution and a bounded reader pool around the accepted MBTiles reader."""
from app.core.compat import remove_prefix
from collections import OrderedDict
from copy import deepcopy
import os
import threading
from .manager import safe_file
from .mbtiles import MBTiles,MapPackageError

MAX_ACTIVE_REGIONS=6


def intersects(a,b):
    """Web viewports may cross the date line; package bounds do not wrap."""
    if a[1]>b[3] or a[3]<b[1]:return False
    spans=[(a[0],a[2])] if a[0]<=a[2] else [(a[0],180),(-180,a[2])]
    return any(w<=b[2] and e>=b[0] for w,e in spans)


def priority(package):
    m=package.manifest;w,s,e,n=m['bounds']
    rank=m.get('priority',100)
    if type(rank) is not int or not 0<=rank<=1000:rank=100
    return (-rank,(e-w)*(n-s),m['package_id'])


def resolve(packages, viewport):
    eligible=sorted((p for p in packages if p.manifest.get('enabled',True) and intersects(viewport,p.manifest['bounds'])),key=priority)
    # If a single higher-priority package covers the entire viewport, rendering
    # a broader overlapping regional package adds no coverage and is redundant.
    for p in eligible[:1]:
        w,s,e,n=p.manifest['bounds'];vw,vs,ve,vn=viewport
        if vw<=ve and w<=vw<=ve<=e and s<=vs<=vn<=n:return [p]
    if len(eligible)>MAX_ACTIVE_REGIONS:
        center=(((viewport[0]+viewport[2]+(360 if viewport[0]>viewport[2] else 0))/2+180)%360-180,(viewport[1]+viewport[3])/2)
        def distance(p):
            w,s,e,n=p.manifest['bounds'];dx=((w+e)/2-center[0]+180)%360-180
            return dx*dx+((s+n)/2-center[1])**2
        eligible=sorted(sorted(eligible,key=distance)[:MAX_ACTIVE_REGIONS],key=priority)
    return eligible


class RegionalReaders:
    def __init__(self,packages=(),maximum=8):
        self.packages={p.manifest['package_id']:p for p in packages}
        self.maximum=max(1,maximum);self.readers=OrderedDict();self.lock=threading.RLock()
        try:self.cache_size=int(os.environ.get('GDS_MAP_TILE_CACHE_SIZE','128'))
        except ValueError:self.cache_size=128

    def tile(self,key,role,z,x,y,extension):
        with self.lock:
            package=self.packages.get(key)
            if not package or not package.manifest.get('enabled',True):return None
            filename=package.files().get(role)
            if not filename:return None
            cache_key=(key,role)
            reader=self.readers.pop(cache_key,None)
            if reader is None:
                while len(self.readers)>=self.maximum:self.readers.popitem(last=False)[1].close()
                reader=MBTiles(safe_file(package.root,filename),self.cache_size)
            self.readers[cache_key]=reader
            return reader.tile(z,x,y) if reader.format==extension else None

    def retain(self,ids):
        with self.lock:
            for key in list(self.readers):
                if key[0] not in ids:self.readers.pop(key).close()

    def close(self):
        self.retain(set())

    def pause(self):
        with self.lock:
            self.close();self.packages={}


def regional_config(packages,primary=None):
    from .render_config import render_config
    prepared=[]
    for package in packages:
        try:prepared.append((package,render_config(package)))
        except (MapPackageError,OSError):continue
    primary_id=primary.manifest['package_id'] if primary else None
    chosen=next((item for package,item in prepared if package.manifest['package_id']==primary_id),prepared[0][1] if prepared else None)
    config=deepcopy(chosen) if chosen else render_config(None)
    primary_id=config.get('package_id');catalog=[]
    for package,item in prepared:
        key=package.manifest['package_id']
        item.update(name=package.manifest['name'],priority=-priority(package)[0],enabled=package.manifest.get('enabled',True))
        # Preserve accepted Malaysia IDs, including diagnostics and initial frame.
        if key==primary_id:catalog.append(item);continue
        mapping={source:'offline-'+key+'-'+remove_prefix(source, 'offline-') for source in item['style']['sources']}
        item['style']['sources']={mapping[k]:v for k,v in item['style']['sources'].items()}
        layers=[]
        for layer in item['style']['layers']:
            if 'source' not in layer:continue
            old=layer['source'];layer['id']=mapping[old]+layer['id'][len(old):];layer['source']=mapping[old];layers.append(layer)
        item['style']['layers']=layers;catalog.append(item)
    config['regional_packages']=catalog
    config['installed']=bool(catalog)
    config['overview_status']='GLOBAL OVERVIEW ASSET PENDING'
    config['bathymetry_status']='BATHYMETRY ASSET PENDING'
    return config
