"""Official Geofabrik catalog, resumable cache and conservative install planning.

Network I/O is explicit tooling/UI work, never part of map rendering.
"""
from app.core.compat import is_relative_to, remove_suffix
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import threading
import urllib.parse
import urllib.request
from .manager import checksum, PackageManager

GIB=1024**3
MARGIN=30*GIB
_disk_write=threading.Lock()
ROOT=Path(__file__).resolve().parents[3]
INDEX='https://download.geofabrik.de/index-v1.json'
PROFILES={'core-maritime-asia':('malaysia_singapore_brunei','thailand','vietnam','cambodia','laos',
    'philippines','indonesia','bangladesh','myanmar'),
    'oceania-core':('australia','papua-new-guinea','new-zealand')}


def cache_root():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'GDS VTS/map-build/sources'


def official(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='download.geofabrik.de':
        raise ValueError('Only official Geofabrik HTTPS URLs are supported')
    return url


def request(url, method='GET', headers=None):
    class OfficialRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,hdrs,newurl):
            official(newurl)
            return super().redirect_request(req,fp,code,msg,hdrs,newurl)
    response=urllib.request.build_opener(OfficialRedirect()).open(urllib.request.Request(official(url),method=method,
        headers={'User-Agent':'GDS-VTS-regions/1.0',**(headers or {})}),timeout=90)
    official(response.url)
    return response


def fetch(url, limit=8*1024**2):
    with request(url) as response:data=response.read(limit+1)
    if len(data)>limit:raise ValueError('Oversized official metadata')
    return data


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href')


def shortbread_url(page, html):
    parser=Links();parser.feed(html)
    urls={official(urllib.parse.urljoin(page,link)) for link in parser.links
          if 'shortbread' in link.lower() and urllib.parse.urlsplit(link).path.endswith('.mbtiles')}
    if len(urls)>1:raise ValueError('Ambiguous Shortbread links')
    return next(iter(urls),None)


def region_candidates(index):
    props={f['properties']['id']:f['properties'] for f in index['features']}
    geometries={f['properties']['id']:f.get('geometry',{}) for f in index['features']}
    def extent(geometry):
        points=[]
        def walk(value):
            if isinstance(value,list) and len(value)>=2 and all(isinstance(v,(int,float)) for v in value[:2]):points.append(value)
            elif isinstance(value,list):
                for child in value:walk(child)
        walk(geometry.get('coordinates',[]))
        return [min(p[0] for p in points),max(-85.051129,min(p[1] for p in points)),max(p[0] for p in points),min(85.051129,max(p[1] for p in points))] if points else None
    def group(key):
        seen=set()
        while key in props and key not in seen:
            seen.add(key);parent=props[key].get('parent')
            if parent in ('asia','australia-oceania'):return parent
            key=parent
        return None
    result=[]
    for key,p in props.items():
        continent=group(key)
        if not continent:continue
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',key):continue
        # Country packages first; Indonesia subregions are explicitly preferred.
        # Unsupported country packages can fall back to their official children.
        pbf=p.get('urls',{}).get('pbf','')
        if not pbf.endswith('-latest.osm.pbf'):continue
        page=official(remove_suffix(pbf, '-latest.osm.pbf')+'.html')
        result.append(dict(region_id='malaysia_singapore_brunei' if key=='malaysia-singapore-brunei' else key,
            official_id=key,parent=p.get('parent'),display_name=p['name'],group='Asia' if continent=='asia' else 'Oceania',
            official_source_page=page,download_url=None,expected_schema='shortbread-1.0',status='UNAVAILABLE_PREBUILT',
            bounds=extent(geometries[key]),revision=None,source_date=None,download_size=None,installed_revision=None,
            installed_size=0,enabled=False,priority=100))
    return result


def discover_catalog(index=None):
    candidates=region_candidates(index or json.loads(fetch(INDEX)))
    def probe(entry):
        try:
            url=shortbread_url(entry['official_source_page'],fetch(entry['official_source_page']).decode('utf-8'))
            if url:
                with request(url,'HEAD') as response:
                    size=int(response.headers.get('Content-Length',0))
                    if size<=0:raise ValueError('Unknown remote size')
                    entry.update(download_url=url,download_size=size,status='AVAILABLE',
                                 revision=response.headers.get('ETag'),source_date=response.headers.get('Last-Modified'))
        except Exception as error:entry['reason']=str(error)
        return entry
    # Probe top-level countries first and only descend when needed (or Indonesia).
    top=[e for e in candidates if e['parent'] in ('asia','australia-oceania')]
    with ThreadPoolExecutor(max_workers=6) as pool:top=list(pool.map(probe,top))
    parents={e['official_id'] for e in top if e['status']!='AVAILABLE'}|{'indonesia'}
    children=[e for e in candidates if e['parent'] in parents]
    with ThreadPoolExecutor(max_workers=6) as pool:children=list(pool.map(probe,children))
    return sorted(top+children,key=lambda e:(e['group'],e['display_name']))


def select_regions(catalog, profile='asia-oceania', regions=()):
    selected=[]
    wanted=set(regions or PROFILES.get(profile,()))
    for entry in catalog:
        if regions or profile!='asia-oceania':
            if entry['region_id'] not in wanted and entry['parent'] not in wanted:continue
        children=[e for e in catalog if e['parent']==entry['official_id'] and e['status']=='AVAILABLE']
        if children and (entry['official_id']=='indonesia' or entry['status']!='AVAILABLE'):continue
        if entry['parent'] not in ('asia','australia-oceania'):
            parent=next((e for e in catalog if e['official_id']==entry['parent']),None)
            if parent and parent['status']=='AVAILABLE' and parent['official_id']!='indonesia':continue
        selected.append(entry)
    priority=list(PROFILES['core-maritime-asia'])+list(PROFILES['oceania-core'])
    def order(e):
        key=e['region_id'] if e['region_id'] in priority else e['parent']
        return priority.index(key) if key in priority else 50,e['group'],e['display_name']
    return sorted(selected,key=order)


def cache_target(entry,sources):
    base=Path(sources)/Path(urllib.parse.urlsplit(entry.get('download_url') or '').path).name
    receipt=Path(str(base)+'.source.json')
    if base.is_file() and receipt.is_file():
        try:
            saved=json.loads(receipt.read_text(encoding='utf-8'))
            stamp={k.lower():v for k,v in saved.get('http_headers',{}).items()}.get('last-modified')
            if entry.get('source_date') and stamp!=entry['source_date']:
                version=hashlib.sha256((entry['download_url']+entry['source_date']).encode()).hexdigest()[:16]
                return Path(sources)/'revisions'/version/base.name
        except (OSError,ValueError):pass
    return base


def plan_install(entries, sources=None, manager=None, free=None, update=False):
    sources=Path(sources or cache_root());manager=manager or PackageManager()
    installed={p.manifest['package_id']:p for p in manager.installed_regions()}
    free=shutil.disk_usage(sources if sources.exists() else sources.parent).free if free is None else free
    budget=free-MARGIN;rows=[]
    for entry in entries:
        row=dict(entry);key=entry['region_id'];size=entry.get('download_size') or 0
        target=cache_target(entry,sources)
        receipt=Path(str(target)+'.source.json')
        row['cached']=target.is_file() and receipt.is_file() and target.stat().st_size==size
        row['installed']=key in installed
        partial=Path(str(target)+'.part');partial_state=Path(str(partial)+'.json');partial_bytes=0
        try:
            saved=json.loads(partial_state.read_text())
            expected={'url':entry.get('download_url'),'bytes':size,'last_modified':entry.get('source_date'),'etag':entry.get('revision')}
            if saved==expected and partial.is_file() and partial.stat().st_size<=size:partial_bytes=partial.stat().st_size
        except (OSError,ValueError):pass
        row['partial_bytes']=partial_bytes
        required=size*(2 if row['cached'] else 3)-partial_bytes # Existing valid partials already consume free disk.
        local=installed[key].manifest.get('source',{}).get('http_headers',{}) if key in installed else {}
        local_date={k.lower():v for k,v in local.items()}.get('last-modified')
        needs_update=update and row['installed'] and entry.get('source_date') and local_date!=entry['source_date']
        if row['installed'] and not needs_update:row.update(action='INSTALLED',installed_revision=installed[key].manifest['revision'])
        elif entry['status']!='AVAILABLE':row['action']='UNAVAILABLE_PREBUILT'
        elif required>budget:row['action']='SKIP_DISK_MARGIN'
        else:row['action']='INSTALL_CACHED' if row['cached'] else 'DOWNLOAD_INSTALL';budget-=required
        row['required_disk']=0 if row['action']=='INSTALLED' else required
        rows.append(row)
    return dict(free_bytes=free,reserve_bytes=MARGIN,planned_remaining_bytes=budget+MARGIN,
        download_bytes=sum(r['download_size']-r['partial_bytes'] for r in rows if r['action']=='DOWNLOAD_INSTALL'),
        required_disk_bytes=sum(r['required_disk'] for r in rows if r['action'] in ('DOWNLOAD_INSTALL','INSTALL_CACHED')),
        packages=rows)


def download_region(entry,sources=None):
    sources=Path(sources or cache_root()).resolve()
    if is_relative_to(sources, ROOT):raise ValueError('Production MBTiles must remain outside Git')
    sources.mkdir(parents=True,exist_ok=True)
    url=official(entry['download_url']);size=entry['download_size']
    target=cache_target(entry,sources);target.parent.mkdir(parents=True,exist_ok=True)
    receipt=Path(str(target)+'.source.json');part=Path(str(target)+'.part');state=Path(str(part)+'.json')
    if target.exists():
        saved=json.loads(receipt.read_text(encoding='utf-8'))
        if saved['url']!=url or saved['sha256']!=checksum(target):raise ValueError('Cached asset failed checksum')
        return target
    expected={'url':url,'bytes':size,'last_modified':entry.get('source_date'),'etag':entry.get('revision')}
    if part.exists() and (not state.exists() or json.loads(state.read_text())!=expected):
        raise ValueError('Partial belongs to a different remote revision; retained for inspection')
    offset=part.stat().st_size if part.exists() else 0
    if offset>size:raise ValueError('Oversized partial')
    if shutil.disk_usage(sources).free<size*3-offset+MARGIN:raise ValueError('30 GiB disk reserve would be violated')
    state.write_text(json.dumps(expected),encoding='utf-8')
    headers={'Range':f'bytes={offset}-','If-Range':entry.get('revision') or entry.get('source_date') or ''} if offset else {}
    if offset<size:
        with request(url,headers=headers) as response:
            for field,value in [('Last-Modified',entry.get('source_date')),('ETag',entry.get('revision'))]:
                observed=response.headers.get(field)
                if value and observed and value!=observed:raise ValueError('Remote revision changed; refresh catalog before resuming')
            resumed=offset and response.status==206
            if resumed and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise ValueError('Invalid resume range')
            if resumed and not response.headers.get('Content-Range','').endswith('/'+str(size)):raise ValueError('Remote size changed')
            with part.open('ab' if resumed else 'wb') as stream:
                total=offset if resumed else 0
                while block:=response.read(1024**2):
                    total+=len(block)
                    if total>size:raise ValueError('Remote size exceeded')
                    with _disk_write:
                        if shutil.disk_usage(sources).free<MARGIN+len(block):raise ValueError('30 GiB disk reserve reached; partial retained')
                        stream.write(block)
                stream.flush();os.fsync(stream.fileno())
    if part.stat().st_size!=size:raise ValueError('Incomplete download retained for resume')
    with part.open('rb') as stream:
        if stream.read(16)!=b'SQLite format 3\0':raise ValueError('Not SQLite')
    # Validate before final naming; a completed byte stream is not yet trusted.
    from .mbtiles import MBTiles
    from .schemas import vector_schema
    reader=MBTiles(part,0)
    try:
        if vector_schema(reader.metadata)!='shortbread-1.0':raise ValueError('Unsupported schema')
    finally:reader.close()
    saved={'page':entry['official_source_page'],'url':url,'bytes':size,'sha256':checksum(part),
        'http_headers':{'Last-Modified':entry['source_date']},'downloaded_at':datetime.now(timezone.utc).isoformat()}
    os.replace(part,target);receipt.write_text(json.dumps(saved,indent=2),encoding='utf-8');state.unlink(missing_ok=True)
    return target
