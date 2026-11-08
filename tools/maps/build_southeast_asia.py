"""Explicit SEA asset build/import pipeline. Never invoked by NAV or pytest.

Planetiler's bundled OpenMapTiles profile and GDAL executables are prerequisites.
Large inputs, scratch databases, logs and packages stay outside the repository.
"""
import argparse
import ctypes
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import zlib

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from app.nav.offline_maps.manager import PackageManager, checksum, validate_package
from app.nav.offline_maps.mbtiles import MBTiles, MapPackageError, _protobuf_fields

GIB = 1024**3
OSM_URL = 'https://download.geofabrik.de/asia/sea-latest.osm.pbf'
GEBCO_URL = 'https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid'
ATTRIBUTION = '© OpenStreetMap contributors (ODbL); OpenMapTiles (CC BY 4.0); Planetiler (Apache-2.0)'
GEBCO_ATTRIBUTION = 'GEBCO Bathymetric Compilation Group 2026; GEBCO_2026 Grid; doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa. Contextual bathymetry, not an official navigation chart.'
GDAL = ('gdalinfo', 'gdalwarp', 'gdaldem', 'gdaladdo')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def external_root(value):
    root = Path(value).expanduser().resolve()
    if root == PROJECT or root.is_relative_to(PROJECT):
        raise ValueError('Large map build/storage directories must be outside the project')
    return root


def memory():
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total',
                    'page_available', 'virtual_total', 'virtual_available', 'extended')]
        state = Memory();state.length = ctypes.sizeof(Memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            raise OSError('Cannot inspect physical memory')
        return state.total, state.available
    pages = os.sysconf('SC_PAGE_SIZE')
    return os.sysconf('SC_PHYS_PAGES')*pages, os.sysconf('SC_AVPHYS_PAGES')*pages


def command_version(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return (result.stdout + result.stderr).strip()[:4000]
    except (OSError, subprocess.TimeoutExpired) as error:
        return str(error)


def preflight(args, require_build=True):
    root = external_root(args.work_root)
    ancestor = root
    while not ancestor.exists():ancestor = ancestor.parent
    total, available = memory()
    java = shutil.which(args.java)
    java_version = command_version([java, '-version']) if java else 'NOT INSTALLED'
    match = re.search(r'version "(\d+)(?:\.(\d+))?', java_version)
    major = int(match[2] if match[1]=='1' else match[1]) if match else 0
    gdal = {tool: shutil.which(tool) for tool in GDAL}
    jar = Path(args.planetiler_jar or root/'tools/planetiler.jar').resolve()
    assets = []
    if root.exists():
        assets = [{'path':str(p),'bytes':p.stat().st_size} for p in root.rglob('*')
                  if p.is_file() and p.suffix.lower() in ('.pbf','.mbtiles','.tif','.tiff','.jar')]
    blockers = []
    free = shutil.disk_usage(ancestor).free
    if free < args.min_disk_gib*GIB:blockers.append(f'Need at least {args.min_disk_gib} GiB free build disk')
    if require_build:
        if available < (args.heap_gib+2)*GIB:blockers.append(f'Need {args.heap_gib+2} GiB available RAM for heap plus OS/native reserve')
        if major < 25:blockers.append(f'Java 25+ required; detected major {major}')
        if not jar.is_file():blockers.append(f'Planetiler JAR missing: {jar}')
        blockers.extend(f'{tool} missing from PATH' for tool, path in gdal.items() if not path)
        if not args.gebco or not Path(args.gebco).is_file():blockers.append('Provide a real GEBCO_2026 subset GeoTIFF using --gebco')
    return {'checked_at':utc_now(),'work_root':str(root),'disk_free_bytes':free,
            'ram_total_bytes':total,'ram_available_bytes':available,'cpu_count':os.cpu_count(),
            'java':java,'java_version':java_version,'java_major':major,
            'planetiler_jar':str(jar),'planetiler_present':jar.is_file(),
            'docker':shutil.which('docker'),'gdal':gdal,'existing_assets':assets,
            'blockers':blockers,'ready':not blockers}


def osm_header(path):
    """Read the genuine PBF HeaderBlock timestamp and bounding box, not filename dates."""
    with Path(path).open('rb') as source:
        prefix = source.read(4)
        if len(prefix)!=4:raise ValueError('Truncated OSM PBF')
        length = struct.unpack('>I', prefix)[0]
        if not 0 < length <= 65536:raise ValueError('Invalid OSM blob header size')
        fields = {key: value for key, _, value in _protobuf_fields(source.read(length))}
        if bytes(fields.get(1,b''))!=b'OSMHeader' or not 0 < fields.get(3,0) <= 32*1024**2:
            raise ValueError('Expected an OSMHeader PBF block')
        blob = {key: value for key, _, value in _protobuf_fields(source.read(fields[3]))}
        if 1 in blob:raw = bytes(blob[1])
        elif 3 in blob:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(blob[3], 1024*1024+1)
            if len(raw)>1024*1024 or not decoder.eof:raise ValueError('Oversized/truncated OSM header')
        else:raise ValueError('Unsupported OSM header compression')
    header = {key: value for key, _, value in _protobuf_fields(raw)}
    if 32 not in header or 1 not in header:raise ValueError('OSM source needs actual replication timestamp and bounds')
    coords = {key:(value>>1)^-(value&1) for key, _, value in _protobuf_fields(header[1])}
    coverage = [coords[k]/1e9 for k in (1,4,2,3)]
    from app.nav.offline_maps.mbtiles import bounds
    bounds(coverage)
    return {'timestamp':datetime.fromtimestamp(header[32],timezone.utc).isoformat(),'bounds':coverage}


def digest(path, algorithm):
    value = hashlib.new(algorithm)
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024**2), b''):value.update(block)
    return value.hexdigest()


def acquire_osm(sources, explicit=None, download=False):
    """Reuse the source's locked checksum; a new upstream release needs a new cache file."""
    if explicit:
        path = Path(explicit).resolve(strict=True)
        md5_file = Path(str(path)+'.md5')
        if md5_file.is_file():
            expected = md5_file.read_text(encoding='ascii').split()[0].lower()
            if not re.fullmatch('[a-f0-9]{32}',expected) or digest(path,'md5')!=expected:
                raise ValueError('Supplied OSM MD5 checksum mismatch')
        lock = path.with_suffix(path.suffix+'.source.json')
        if lock.is_file():
            saved = json.loads(lock.read_text(encoding='utf-8'))
            if digest(path,'md5')!=saved['md5']:raise ValueError('Cached OSM checksum mismatch')
        return path
    path = sources/'sea-latest.osm.pbf'
    lock = sources/'sea-latest.osm.pbf.source.json'
    if path.exists():
        if not lock.exists():raise ValueError('Unverified OSM cache; use --osm with an explicitly acquired source')
        saved = json.loads(lock.read_text(encoding='utf-8'))
        if digest(path,'md5')!=saved['md5']:raise ValueError('Cached OSM checksum mismatch; retained for inspection')
        return path
    if not download:raise ValueError('OSM input absent: use --osm or explicit --download-osm')
    with urllib.request.urlopen(OSM_URL+'.md5',timeout=60) as response:
        md5 = response.read(512).decode('ascii').split()[0]
    if not re.fullmatch('[a-fA-F0-9]{32}',md5):raise ValueError('Invalid Geofabrik checksum')
    partial = path.with_suffix('.pbf.part')
    if partial.exists():raise ValueError(f'Previous partial download retained at {partial}; inspect or rename before retry')
    started = time.monotonic()
    with urllib.request.urlopen(OSM_URL,timeout=120) as response, partial.open('xb') as target:
        headers = dict(response.headers)
        shutil.copyfileobj(response,target,1024**2)
    if digest(partial,'md5')!=md5.lower():raise ValueError('Geofabrik MD5 mismatch; partial download retained')
    partial.rename(path)
    dump(lock,{'url':OSM_URL,'md5':md5.lower(),'headers':headers,'download_seconds':time.monotonic()-started,**osm_header(path)})
    return path


def run(command, work, record, log_name):
    started = time.monotonic()
    item = {'command':[str(v) for v in command],'started_at':utc_now(),'log':log_name}
    record.setdefault('commands',[]).append(item)
    print('RUN '+subprocess.list2cmdline(item['command']),flush=True)
    with (work/log_name).open('x',encoding='utf-8') as log:
        result = subprocess.run(item['command'],cwd=work,stdout=log,stderr=subprocess.STDOUT)
    item.update(seconds=time.monotonic()-started,returncode=result.returncode)
    if result.returncode:raise RuntimeError(f'Command failed ({result.returncode}); see {work/log_name}')


def normalize_export(path, name, attribution, revision):
    """Complete export metadata in the new build DB only; never touch installed maps."""
    with sqlite3.connect(path) as db:
        metadata = dict(db.execute('SELECT name,value FROM metadata'))
        lo, hi = db.execute('SELECT MIN(zoom_level),MAX(zoom_level) FROM tiles').fetchone()
        if lo is None:raise ValueError('Exporter produced an empty MBTiles database')
        from app.nav.offline_maps.mbtiles import bounds
        coverage = bounds(metadata['bounds'])
        values = {'name':name,'description':name+'; contextual map, not an official navigation chart',
                  'version':revision,'attribution':attribution,'scheme':'tms',
                  'minzoom':str(lo),'maxzoom':str(hi)}
        values['type']='overlay' if metadata.get('format') in ('png','jpg','jpeg','webp') else 'baselayer'
        values['center']=f'{(coverage[0]+coverage[2])/2},{(coverage[1]+coverage[3])/2},{lo}'
        for key,value in values.items():
            db.execute('DELETE FROM metadata WHERE name=?',(key,))
            db.execute('INSERT INTO metadata(name,value) VALUES(?,?)',(key,value))


def inspect_tiles(path):
    reader = MBTiles(path,0)
    try:
        # Full asset statistics intentionally scan the coordinate index. Keep
        # these off the runtime reader's bounded-work connection.
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as stats:
            rows = stats.execute('SELECT zoom_level,COUNT(*) FROM tiles GROUP BY zoom_level').fetchall()
            zooms = [row[0] for row in rows]
            for zoom in {zooms[0],zooms[len(zooms)//2],zooms[-1]}:
                x,tms = stats.execute('SELECT tile_column,tile_row FROM tiles WHERE zoom_level=? LIMIT 1',(zoom,)).fetchone()
                if reader.tile(zoom,x,2**zoom-1-tms) is None:raise ValueError(f'Unreadable sample at zoom {zoom}')
        return {'metadata':reader.metadata,'bounds':list(reader.bounds),'format':reader.format,
                'minzoom':reader.minzoom,'maxzoom':reader.maxzoom,'bytes':Path(path).stat().st_size,
                'tile_count':sum(r[1] for r in rows),'tiles_per_zoom':dict(rows),
                'sha256':checksum(path),'sample_zooms':sorted({zooms[0],zooms[len(zooms)//2],zooms[-1]})}
    finally:reader.close()


def assemble(folder, inputs, revision, provenance):
    """Compose a genuine vector/raster bundle using the existing package contract."""
    if 'basemap' not in inputs or 'bathymetry' not in inputs:raise ValueError('Both basemap and bathymetry are required')
    folder.mkdir(parents=True,exist_ok=False)
    assets = {}
    for role, source in inputs.items():
        name = {'basemap':'southeast_asia_basemap.mbtiles','bathymetry':'southeast_asia_bathymetry.mbtiles',
                'overview':'global_overview.mbtiles'}.get(role,role+'.mbtiles')
        source = Path(source).resolve(strict=True)
        shutil.copy2(source,folder/name)
        assets[role] = {'file':name,'role':role,**inspect_tiles(folder/name)}
    base = assets['basemap']
    m = dict(schema_version=1,package_id='southeast-asia',name='Southeast Asia',revision=revision,
             created_at=utc_now(),region='Geofabrik South-East Asia',bounds=base['bounds'],
             minzoom=base['minzoom'],maxzoom=base['maxzoom'],
             basemap_file=base['file'],bathymetry_file=assets['bathymetry']['file'],
             overview_file=assets.get('overview',{}).get('file'),
             detail_files=[v['file'] for k,v in assets.items() if k.startswith('detail-')],
             asset_files=['build-record.json'],style_revision='gds-maritime-1',
             attribution=ATTRIBUTION+'; '+GEBCO_ATTRIBUTION,assets=assets,source=provenance)
    dump(folder/'build-record.json',provenance)
    m['checksums']={v['file']:v['sha256'] for v in assets.values()}
    m['checksums']['build-record.json']=checksum(folder/'build-record.json')
    dump(folder/'manifest.json',m)
    validate_package(folder)
    from app.nav.offline_maps.render_config import render_config
    config = render_config(validate_package(folder,verify_checksums=False))
    if any(not url.startswith('gds://') for src in config['style']['sources'].values() for url in src['tiles']):
        raise ValueError('Package has a non-local source')
    return m


def build(args, report):
    if not report['ready']:raise ValueError('ASSET BUILD PENDING RESOURCE/DEPENDENCY: '+'; '.join(report['blockers']))
    root = external_root(args.work_root)
    sources = root/'sources';sources.mkdir(parents=True,exist_ok=True)
    work = root/'runs'/uuid.uuid4().hex;work.mkdir(parents=True)
    started = time.monotonic()
    record = {'started_at':utc_now(),'preflight':report,'commands':[],
              'resource_budget':{'java_heap_gib':args.heap_gib,'available_ram_required_gib':args.heap_gib+2,
                                 'peak_memory_measured':False}}
    try:
        osm = acquire_osm(sources,args.osm,args.download_osm)
        header = osm_header(osm)
        source_lock = Path(str(osm)+'.source.json')
        acquisition = json.loads(source_lock.read_text(encoding='utf-8')) if source_lock.is_file() else {'mode':'explicit local input'}
        stamp = datetime.fromisoformat(header['timestamp']).strftime('%Y%m%dT%H%M%SZ')
        revision = 'osm-'+stamp+'-'+work.name[:8]
        record.update(osm={'url':OSM_URL,'path':str(osm),'bytes':osm.stat().st_size,'sha256':checksum(osm),'acquisition':acquisition,**header},
                      planetiler={'jar':report['planetiler_jar'],'sha256':checksum(report['planetiler_jar'])},
                      gebco={'release':'GEBCO_2026','url':GEBCO_URL,'sha256':checksum(args.gebco),'path':str(Path(args.gebco).resolve())},
                      revision=revision)
        coverage = args.bathymetry_bounds or header['bounds']
        info = subprocess.run([report['gdal']['gdalinfo'],'-json',str(args.gebco)],check=True,capture_output=True,text=True)
        geo = json.loads(info.stdout)
        if not geo.get('coordinateSystem') or not geo.get('geoTransform'):raise ValueError('GEBCO input lacks georeferencing')
        points = [point for ring in geo.get('wgs84Extent',{}).get('coordinates',[]) for point in ring]
        if not points:raise ValueError('GDAL must report GEBCO WGS84 extent')
        source_bounds = [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        if not (source_bounds[0] <= coverage[0]+.01 and source_bounds[1] <= coverage[1]+.01
                and source_bounds[2] >= coverage[2]-.01 and source_bounds[3] >= coverage[3]-.01):
            raise ValueError('GEBCO subset does not cover requested bounds; obtain the missing real grid coverage')
        dump(work/'gebco-input.json',geo)
        record['gebco'].update(requested_subset_bounds=list(coverage),source_bounds=source_bounds,gdal_info=geo)
        common = [report['java'],f'-Xmx{args.heap_gib}g','-jar',report['planetiler_jar'],
                  f'--osm-path={osm}','--download',f'--threads={min(os.cpu_count() or 1,8)}',
                  '--nodemap-storage=mmap','--exclude-layers=housenumber,building',
                  '--use-wikidata=false',f'--natural-earth-path={sources/"natural_earth_vector.sqlite.zip"}',
                  f'--water-polygons-path={sources/"water-polygons-split-3857.zip"}',
                  f'--lake-centerlines-path={sources/"lake_centerline.shp.zip"}']
        vector = work/'southeast_asia_basemap.mbtiles'
        run(common+[f'--output={vector}',f'--minzoom={args.minzoom}',f'--maxzoom={args.maxzoom}',f'--tmpdir={work/"vector-tmp"}'],work,record,'vector.log')
        normalize_export(vector,'Southeast Asia',ATTRIBUTION,revision)
        inspect_tiles(vector)
        inputs = {'basemap':vector}
        overview = work/'global_overview.mbtiles'
        run(common+[f'--output={overview}','--bounds=world','--minzoom=0','--maxzoom=5',
                    '--only-layers=water,landcover,boundary,place,waterway',f'--tmpdir={work/"overview-tmp"}'],work,record,'overview.log')
        normalize_export(overview,'Global Natural Earth context with SEA OSM detail',ATTRIBUTION,revision)
        inputs['overview']=overview
        cropped, colored = work/'gebco-subset.tif',work/'gebco-depth-color.tif'
        run([report['gdal']['gdalwarp'],'-te_srs','EPSG:4326','-te',*map(str,coverage),'-t_srs','EPSG:4326',
             '-r','bilinear','-co','COMPRESS=DEFLATE','-co','TILED=YES',str(args.gebco),str(cropped)],work,record,'gebco-subset.log')
        colors = work/'depth-colors.txt'
        colors.write_text('-12000 20 48 74 255\n-6000 31 69 99 255\n-2000 52 101 132 255\n-200 92 143 166 255\n-1 155 194 205 255\n0 155 194 205 0\n10000 155 194 205 0\nnv 0 0 0 0\n',encoding='ascii')
        run([report['gdal']['gdaldem'],'color-relief',str(cropped),str(colors),str(colored),'-alpha','-co','COMPRESS=DEFLATE','-co','TILED=YES'],work,record,'gebco-colors.log')
        bath = work/'southeast_asia_bathymetry.mbtiles'
        resolution = str(156543.03392804097/2**args.bathymetry_maxzoom)
        run([report['gdal']['gdalwarp'],'-t_srs','EPSG:3857','-tr',resolution,resolution,'-tap','-r','bilinear',
             '-of','MBTiles','-co','TILE_FORMAT=PNG',str(colored),str(bath)],work,record,'bathymetry.log')
        run([report['gdal']['gdaladdo'],'-r','average',str(bath),*[str(2**n) for n in range(1,args.bathymetry_maxzoom+1)]],work,record,'bathymetry-overviews.log')
        normalize_export(bath,'Southeast Asia contextual bathymetry',GEBCO_ATTRIBUTION,revision)
        inputs['bathymetry']=bath
        record.update(completed_at=utc_now(),build_seconds=time.monotonic()-started,
                      auxiliary_sources=[{'file':p.name,'bytes':p.stat().st_size,'sha256':checksum(p)} for p in sources.iterdir() if p.suffix=='.zip'])
        package = work/'package'
        assemble(package,inputs,revision,record)
        if args.install:
            installed=PackageManager(args.store).install(package)
            print('INSTALLED '+str(installed.root),flush=True)
        print('PACKAGE '+str(package),flush=True)
    except Exception as error:
        record.update(failed_at=utc_now(),error=str(error));dump(work/'failed-build.json',record)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preflight','build','package','inspect'))
    default = Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'GDS VTS/map-build'
    parser.add_argument('--work-root',type=Path,default=default)
    parser.add_argument('--planetiler-jar',type=Path)
    parser.add_argument('--java',default='java')
    parser.add_argument('--heap-gib',type=int,choices=range(4,65),default=6)
    parser.add_argument('--min-disk-gib',type=int,default=64)
    parser.add_argument('--osm',type=Path)
    parser.add_argument('--download-osm',action='store_true')
    parser.add_argument('--gebco',type=Path)
    parser.add_argument('--bathymetry-bounds',type=float,nargs=4)
    parser.add_argument('--minzoom',type=int,choices=(0,4),default=4)
    parser.add_argument('--maxzoom',type=int,choices=(13,14),default=13)
    parser.add_argument('--bathymetry-maxzoom',type=int,choices=range(6,10),default=8)
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--store',type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--basemap',type=Path)
    parser.add_argument('--bathymetry',type=Path)
    parser.add_argument('--overview',type=Path)
    parser.add_argument('--detail',type=Path,action='append',default=[])
    parser.add_argument('--provenance',type=Path,help='Actual source/build record JSON for importing existing MBTiles')
    parser.add_argument('--path',type=Path,help='MBTiles to inspect')
    args = parser.parse_args(argv)
    try:
        if args.bathymetry_bounds:
            from app.nav.offline_maps.mbtiles import bounds
            bounds(args.bathymetry_bounds)
        if args.action=='inspect':
            if not args.path:raise ValueError('--path is required')
            print(json.dumps(inspect_tiles(args.path),indent=2));return 0
        if args.store:external_root(args.store)
        report = preflight(args,require_build=args.action!='package')
        if args.report:dump(args.report,report)
        print(json.dumps(report,indent=2),flush=True)
        if args.action=='preflight':return 0 if report['ready'] else 2
        if args.action=='build':build(args,report)
        else:
            if not report['ready']:raise ValueError('; '.join(report['blockers']))
            if not args.provenance or not args.basemap or not args.bathymetry:
                raise ValueError('Import requires --basemap, --bathymetry and --provenance')
            provenance=json.loads(args.provenance.read_text(encoding='utf-8'))
            if not provenance.get('osm',{}).get('timestamp') or provenance.get('gebco',{}).get('release')!='GEBCO_2026':
                raise ValueError('Record actual OSM timestamp and GEBCO_2026 release in provenance')
            revision=provenance['revision']
            root=external_root(args.work_root)/'imports'/uuid.uuid4().hex
            inputs={'basemap':args.basemap,'bathymetry':args.bathymetry}
            if args.overview:inputs['overview']=args.overview
            inputs.update({f'detail-{i}':p for i,p in enumerate(args.detail)})
            required=sum(Path(p).stat().st_size for p in inputs.values())*(3 if args.install else 2)
            if required>report['disk_free_bytes']:raise ValueError('Insufficient disk for package copies/staging/installed revision')
            assemble(root,inputs,revision,provenance)
            if args.install:print('INSTALLED '+str(PackageManager(args.store).install(root).root))
            print('PACKAGE '+str(root))
        return 0
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,sqlite3.Error,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
