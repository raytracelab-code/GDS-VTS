"""Discover/download official Geofabrik Shortbread assets; no local tile build."""
import argparse
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
import re
from email.utils import parsedate_to_datetime
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT))
from app.core.compat import is_relative_to
from app.nav.offline_maps.manager import checksum

REGIONS = {
    'malaysia_singapore_brunei':('Malaysia / Singapore / Brunei','malaysia-singapore-brunei'),
    'thailand':('Thailand','thailand'), 'vietnam':('Vietnam','vietnam'),
    'myanmar':('Myanmar','myanmar'), 'philippines':('Philippines','philippines'),
    'laos':('Laos','laos'), 'bangladesh':('Bangladesh','bangladesh'),
}


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href')


def official(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname!='download.geofabrik.de' or parsed.username or parsed.password:
        raise ValueError('Only official HTTPS Geofabrik downloads are allowed')
    return url


def discover(page):
    official(page)
    with urllib.request.urlopen(page,timeout=60) as response:
        official(response.url)
        html=response.read(2*1024*1024+1)
    if len(html)>2*1024*1024:raise ValueError('Oversized source page')
    parser=Links();parser.feed(html.decode('utf-8'))
    urls=sorted({urllib.parse.urljoin(page,link) for link in parser.links
                 if 'shortbread' in link.lower() and urllib.parse.urlsplit(link).path.endswith('.mbtiles')})
    if len(urls)!=1:raise ValueError(f'Expected one Shortbread MBTiles link on official page, found {len(urls)}')
    return official(urls[0])


def download(page, sources):
    sources=Path(sources).resolve()
    if is_relative_to(sources, PROJECT):raise ValueError('Production MBTiles must remain outside the repository')
    url=discover(page)
    name=Path(urllib.parse.urlsplit(url).path).name
    target=sources/name;receipt=Path(str(target)+'.source.json')
    if target.exists():
        saved=json.loads(receipt.read_text(encoding='utf-8'))
        if saved['url']!=url or saved['sha256']!=checksum(target):raise ValueError('Existing cached asset failed source/checksum validation')
        return target,saved
    sources.mkdir(parents=True,exist_ok=True)
    partial=Path(str(target)+'.part')
    if partial.exists():raise ValueError(f'Partial download retained: {partial}; inspect before retry')
    started=time.monotonic()
    request=urllib.request.Request(url,headers={'User-Agent':'GDS-VTS-offline-map-import/1.0'})
    with urllib.request.urlopen(request,timeout=120) as response:
        official(response.url)
        length=int(response.headers.get('Content-Length','0'))
        if length and shutil.disk_usage(sources).free<length*4+1024**3:raise ValueError('Insufficient space for download, package and staged installation')
        headers=dict(response.headers)
        with partial.open('xb') as stream:
            total=0;last=0
            while block:=response.read(1024**2):
                stream.write(block);total+=len(block)
                if total-last>=32*1024**2:print(f'DOWNLOAD {total} / {length} bytes',flush=True);last=total
    if length and partial.stat().st_size!=length:raise ValueError('Truncated download; partial retained')
    with partial.open('rb') as stream:
        if stream.read(16)!=b'SQLite format 3\x00':raise ValueError('Download is not SQLite MBTiles')
    partial.rename(target)
    saved={'page':page,'url':url,'http_headers':headers,'bytes':target.stat().st_size,
           'sha256':checksum(target),'downloaded_at':datetime.now(timezone.utc).isoformat(),
           'download_seconds':time.monotonic()-started}
    receipt.write_text(json.dumps(saved,indent=2),encoding='utf-8')
    return target,saved


def raw_inspect(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        metadata=dict(db.execute('SELECT name,value FROM metadata'))
        counts=dict(db.execute('SELECT zoom_level,COUNT(*) FROM tiles GROUP BY zoom_level'))
        return {'metadata':metadata,'tiles_per_zoom':counts,'tile_count':sum(counts.values()),
                'bytes':Path(path).stat().st_size,'sha256':checksum(path)}
    finally:db.close()


def install_asset(path, region, name, details=(), regional=False):
    """Copy unchanged source databases into a validated, atomically installed package."""
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',region):raise ValueError('Invalid regional package ID')
    from app.nav.offline_maps.manager import PackageManager, validate_package
    from app.nav.offline_maps.mbtiles import MBTiles
    from app.nav.offline_maps.schemas import vector_schema
    from tools.maps.build_southeast_asia import inspect_tiles
    path=Path(path).resolve(strict=True)
    if is_relative_to(path, PROJECT):raise ValueError('Production source must remain outside the repository')
    receipt=json.loads(Path(str(path)+'.source.json').read_text(encoding='utf-8'))
    official(receipt['url']);official(receipt['page'])
    if checksum(path)!=receipt['sha256']:raise ValueError('Downloaded source checksum mismatch')
    headers={k.lower():v for k,v in receipt['http_headers'].items()}
    stamp=parsedate_to_datetime(headers['last-modified']).astimezone(timezone.utc)
    revision='shortbread-1.0-'+stamp.strftime('%Y%m%dT%H%M%SZ')+'-'+receipt['sha256'][:12]
    if details:
        if any(is_relative_to(Path(p).resolve(), PROJECT) for p in details):raise ValueError('Production detail sources must remain outside the repository')
        fingerprint=hashlib.sha256(''.join(checksum(p) for p in details).encode()).hexdigest()[:8]
        revision+='-d'+fingerprint
    root=path.parent.parent/'packages'/region/revision
    if regional:
        from app.nav.offline_maps.regions import cache_root
        root=cache_root().parent/'packages'/region/revision
    sources={'basemap':path,**{f'detail-{i}':Path(p).resolve(strict=True) for i,p in enumerate(details)}}
    if regional:
        from app.nav.offline_maps.regions import MARGIN
        if shutil.disk_usage(path.parent).free < sum(p.stat().st_size for p in sources.values())*2+MARGIN:
            raise ValueError('30 GiB disk reserve would be violated by package staging')
    if shutil.disk_usage(path.parent).free < sum(p.stat().st_size for p in sources.values())*3+1024**3:
        raise ValueError('Insufficient free storage for package staging and installation')
    if not root.exists():
        root.mkdir(parents=True)
        assets={}
        for role,source in sources.items():
            reader=MBTiles(source,0)
            try:
                if vector_schema(reader.metadata)!='shortbread-1.0':raise ValueError('Expected actual Shortbread layer metadata')
            finally:reader.close()
            filename=('basemap' if role=='basemap' else role)+'.mbtiles'
            shutil.copy2(source,root/filename)
            assets[role]={'file':filename,'role':role,**inspect_tiles(root/filename)}
        base=assets['basemap']
        manifest={'schema_version':1,'package_id':region,'name':name,'revision':revision,
                  'created_at':datetime.now(timezone.utc).isoformat(),'region':name,
                  'bounds':base['bounds'],'minzoom':base['minzoom'],'maxzoom':base['maxzoom'],
                  'basemap_file':base['file'],'detail_files':[assets[k]['file'] for k in assets if k.startswith('detail-')],
                  'style_revision':'gds-shortbread-maritime-1','vector_schemas':{k:'shortbread-1.0' for k in assets},
                  'attribution':'© OpenStreetMap contributors · Geofabrik GmbH · Open Database License 1.0',
                  'source_date':stamp.isoformat(),'source_date_kind':'HTTP Last-Modified of MBTiles (not OSM replication timestamp)',
                  'source':receipt,'assets':assets,'asset_files':['source.json']}
        (root/'source.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        manifest['checksums']={asset['file']:asset['sha256'] for asset in assets.values()}
        manifest['checksums']['source.json']=checksum(root/'source.json')
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    package=validate_package(root)
    installed=PackageManager().install_region(root) if regional else PackageManager().install(root)
    return {'package_path':str(package.root),'installed_path':str(installed.root),
            'manifest':installed.manifest,'source_unchanged':checksum(path)==receipt['sha256']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('download','inspect','install'))
    parser.add_argument('--region',default='malaysia_singapore_brunei')
    parser.add_argument('--name',help='Display name for an additional regional/subregional pack')
    parser.add_argument('--detail',type=Path,action='append',default=[])
    parser.add_argument('--page',help='Official page for an additional region/subregion (e.g. Indonesia)')
    parser.add_argument('--sources',type=Path,default=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'GDS VTS/map-build/sources')
    parser.add_argument('--path',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',args.region):parser.error('Invalid regional package ID')
    if args.action=='download':
        if args.region not in REGIONS and not args.page:parser.error('Additional regions require their official --page')
        page=args.page or f'https://download.geofabrik.de/asia/{REGIONS[args.region][1]}.html'
        target,receipt=download(page,args.sources)
        print('ASSET '+str(target),flush=True)
        result=receipt
    elif args.action=='inspect':
        if not args.path:parser.error('--path is required')
        result=raw_inspect(args.path)
    else:
        if not args.path:parser.error('--path is required')
        name=args.name or REGIONS.get(args.region,(args.region,''))[0]
        result=install_asset(args.path,args.region,name,args.detail)
    if args.report:args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
