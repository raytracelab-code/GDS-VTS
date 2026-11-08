"""Local reference GIS. Worker-owned immutable snapshots and one STRtree per load."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path

from shapely.geometry import shape, box, mapping
from shapely import get_num_coordinates
from shapely.strtree import STRtree
from shapely.validation import explain_validity

from ..malaysia_config import dataset_directory, read_manifest
from ..models import normalize_maritime_feature, MaritimeDataError, validate_geometry

log = logging.getLogger(__name__)
SOURCE = 'malaysia_gis'

# Actual attribute names from the supplied data. No synthetic metadata.
ATTRIBUTES = {
    'name': ('PLAT_FULL_NAME', 'PIPE_NAME', 'WELL_NAME', 'FIELD_NAME', 'BLK_NAME', 'BASIN_NAME', 'SURVEY_NAME', 'USI_CODE', 'platform_full_name', 'name', 'Name', 'text_label'),
    'type': ('PLAT_TYPE', 'TYPE', 'WELL_CLASS', 'FIELD_TYPE', 'platform_type', 'type'),
    'status': ('PLAT_STATUS', 'CURRENT_WELL_STATUS', 'FIELD_STATUS', 'STATUS'),
    'operator': ('PLAT_OPERATOR', 'OPERATOR', 'CURRENT_OPERATOR'),
    'installation_year': ('PLAT_PRO_INSTALL_YEAR', 'INSTALL_YEAR'),
    'water_depth_m': ('WATER_DPTH_M', 'WATER_DEPTH_M', 'WATER_DEPTH_METER'),
    'number_of_wells': ('NUM_OF_WELLS', 'NO_WELL_BY_FIELD'),
    'field': ('PLAT_FIELD_LOC', 'FIELD', 'FIELD_NAME', 'field_location'),
    'psc_block': ('PSC_REF', 'PSC_NAME', 'LEASE_NAME', 'BLOCK_NAME', 'BLOCK'),
    'content': ('CONTENT',), 'from': ('FRM_LOC',), 'to': ('TO_LOC',),
    'from_facility': ('FRM_FACILITY',), 'to_facility': ('TO_FACILITY',),
    'length_km': ('LGTH_KM', 'LENGTH_KM_CALC'), 'outer_diameter_inch': ('OUTER_DIA_INCH',),
    'maximum_pressure': ('MAX_PRESSURE',), 'depth_m': ('TD_TVD_M', 'DRILLERS_TD_M'),
    'region': ('REGION',), 'area_sqkm': ('AREA_SQKM_CALC', 'AREA_KM_SQUARE', 'SURVEY_ACREAGE_SQKM_NUM'),
    'acquisition_year': ('ACQUI_YEAR_NUM', 'ACQUISIITION_YEAR', 'ACQUI_YEAR'),
    'processing_year': ('PROCESSING_YEAR', 'DATA_PROCESS_YEAR'),
    'contractor': ('FIELD_CONTRACTOR',), 'discovery_year': ('DISC_YR',),
}


def available(value):
    return value is not None and (not isinstance(value, str) or value.strip().lower() not in
        ('', 'null', 'undefined', 'n/a', 'not applicable', 'to be confirmed'))


def native_id(feature):
    raw = feature.get('properties') or {}
    return raw.get('GLOBALID') or feature.get('id') or raw.get('OBJECTID') or raw.get('UWI')


def normalize(feature, layer, render_geometry=None):
    raw = feature.get('properties')
    if not isinstance(raw, dict):
        raise MaritimeDataError('properties must be an object')
    props = {}
    for target, names in ATTRIBUTES.items():
        value = next((raw[k] for k in names if available(raw.get(k))), None)
        if value is not None:
            props[target] = value.strip() if isinstance(value, str) else value
    subtype = layer['subtype']
    if layer['style_class'] == 'platform_detail':
        subtype = {'platform.crane':'platform_crane_coverage', 'platform.zone':'platform_reference_zone',
            'platform.label':'platform_reference_point', 'platform':'platform_layout'}.get(raw.get('type'),'offshore_facility_detail')
    if layer['style_class'] == 'platform':
        subtype = {'FPSO': 'fpso', 'FSO': 'fso', 'WELLHEAD': 'wellhead_platform',
            'FIXED STEEL': 'platform', 'TRIPOD STRUC': 'platform', 'GUYED WIRE': 'platform',
            'JACKUP': 'drilling_platform', 'FLOAT.PROD.STOR&OFF': 'fpso',
            'PLEM': 'pipeline_end_manifold', 'UNDERWATER MANIFOLD': 'subsea_manifold',
            'SUBSEA TEMPLATE': 'subsea_template', 'RISER': 'riser'}.get(raw.get('PLAT_TYPE'), subtype)
    # Native IDs are scoped to the dataset. Content hash resolves conflicting native IDs.
    digest = hashlib.sha256(json.dumps({'geometry': feature.get('geometry'), 'properties': raw},
        sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()[:24]
    native = native_id(feature)
    sid = layer['dataset_id'] + ':' + (str(native) if native is not None else digest)
    props.update(gis_layer=layer['dataset_id'], source_tier='LOCAL_GIS',
        source_name='MALAYSIA OFFSHORE GIS', source_attributes=raw)
    obj = normalize_maritime_feature(dict(type='Feature', id=sid, geometry=render_geometry or feature.get('geometry'),
        properties={**props, 'category': layer['canonical_category'], 'object_type': subtype}), SOURCE)
    if subtype == 'pipeline':
        from dataclasses import replace
        obj = replace(obj,object_type='pipeline')  # Dataset includes no proof that every segment is submarine.
    return obj, digest


def valid_crs(document):
    crs = document.get('crs')
    if crs is None:
        return 'RFC7946 WGS84 / CRS84 (implicit)'
    name = str(crs.get('properties', {}).get('name', '')) if isinstance(crs, dict) else ''
    if name.upper() not in ('URN:OGC:DEF:CRS:OGC:1.3:CRS84', 'OGC:CRS84', 'EPSG:4326',
                             'URN:OGC:DEF:CRS:EPSG::4326'):
        raise MaritimeDataError('Unsupported CRS: ' + name)
    return name


@dataclass(frozen=True)
class GISResult:
    objects: tuple
    metadata: dict
    layers: tuple


class MalaysiaOffshoreGISProvider:
    def __init__(self, directory=None):
        self.directory = Path(directory or dataset_directory()).resolve()
        self._signature = None
        self._objects, self._geometries, self.layers, self.audit = (), (), (), []
        self._tree = STRtree([])
        self.load_count = 0
        self.metadata = {}
        self._stopped = False

    def _files(self):
        return sorted(p for p in self.directory.rglob('*.geojson')
            if '__MACOSX' not in p.parts and not p.name.startswith('._'))

    def load(self):
        manifest = read_manifest(self.directory)
        files = self._files()
        from ..malaysia_config import DEFAULT_DIRECTORY
        manifest_path = self.directory / 'manifest.json'
        if not manifest_path.exists():
            manifest_path = DEFAULT_DIRECTORY / 'manifest.json'
        signatures = files + [manifest_path]
        signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in signatures)
        if signature == self._signature:
            return
        by_path = {(self.directory / layer['filename']).resolve(): layer for layer in manifest['layers']}
        objects, geometries, audit, ids, fingerprints = [], [], [], {}, set()
        native_overlaps = Counter()
        # Main installation points precede detailed customer layout/label datasets.
        files.sort(key=lambda p: (by_path.get(p.resolve(),{}).get('style_class')=='platform_detail', str(p)))
        platform_aliases = {}
        for path in files:
            if self._stopped:
                raise RuntimeError('Malaysia GIS provider stopped')
            layer = by_path.get(path.resolve())
            row = dict(filename=path.relative_to(self.directory).as_posix(), feature_count=0, valid_features=0,
                invalid_features=0, null_geometries=0, duplicates=0, geometry_types={}, bounds=None,
                important_properties=[], errors=[], simplified_features=0)
            audit.append(row)
            try:
                document = json.loads(path.read_text(encoding='utf-8-sig'))
                row['feature_count'] = len(document.get('features', []))
                row['crs'] = valid_crs(document)
                if document.get('type') != 'FeatureCollection' or not isinstance(document.get('features'), list):
                    raise MaritimeDataError('Expected FeatureCollection')
                if layer is None:
                    raise MaritimeDataError('Unmapped dataset: add an explicit manifest entry')
                row['category'] = layer['canonical_category']
                types, keys, bounds = Counter(), set(), []
                row['feature_count'] = len(document['features'])
                native_counts = Counter(str(native_id(f)) for f in document['features']
                    if isinstance(f,dict) and isinstance(f.get('properties'),dict) and native_id(f) is not None)
                for feature in document['features']:
                    if self._stopped:
                        raise RuntimeError('Malaysia GIS provider stopped')
                    try:
                        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
                            raise MaritimeDataError('Expected Feature')
                        if feature.get('geometry') is None:
                            row['null_geometries'] += 1
                            raise MaritimeDataError('Null geometry')
                        types[feature['geometry'].get('type')] += 1
                        keys.update((feature.get('properties') or {}).keys())
                        geometry = shape(validate_geometry(feature['geometry'],max_points=2000000))
                        if not geometry.is_empty:
                            bounds.append(geometry.bounds)
                        if geometry.is_empty or not geometry.is_valid:
                            raise MaritimeDataError(explain_validity(geometry))
                        render_geometry = None
                        if get_num_coordinates(geometry)>20000 and layer['style_class']!='platform_detail':
                            # Only the map copy is simplified. Index and audit retain full source geometry.
                            tolerance = .000001
                            rendered = geometry
                            while get_num_coordinates(rendered)>20000 and tolerance<=.001:
                                rendered = geometry.simplify(tolerance,preserve_topology=True)
                                tolerance *= 2
                            render_geometry = mapping(rendered)
                            row['simplified_features'] += 1
                        obj, digest = normalize(feature, layer, render_geometry)
                        if native_id(feature) is not None and native_counts[str(native_id(feature))]>1:
                            from dataclasses import replace
                            obj = replace(obj,object_id=obj.object_id+':'+digest)
                        raw = obj.properties['source_attributes']
                        alias = lambda value: ''.join(str(value or '').upper().split())
                        if layer['style_class']=='platform':
                            for name in ('PLAT_FULL_NAME','PLAT_ABBREV_NAME'):
                                if raw.get(name):
                                    platform_aliases.setdefault(alias(raw[name]),[]).append(geometry)
                        elif layer['style_class']=='platform_detail' and geometry.geom_type=='Point':
                            names = [raw.get(k) for k in ('name','Name','platform_full_name','platform_abbreviation','text_label')]
                            if any(geometry.distance(g)<.0005 for name in names if name for g in platform_aliases.get(alias(name),[])):
                                row['duplicates'] += 1
                                continue
                        # Identical copies within the same logical layer only; status overlays remain separate.
                        fingerprint = (layer['dataset_id'], digest)
                        if fingerprint in fingerprints:
                            row['duplicates'] += 1
                            continue
                        if obj.object_id in ids and ids[obj.object_id] != digest:
                            from dataclasses import replace
                            obj = replace(obj, object_id=obj.object_id + ':' + digest)
                        ids[obj.object_id] = digest
                        fingerprints.add(fingerprint)
                        objects.append(obj); geometries.append(geometry)
                        row['valid_features'] += 1
                        native = obj.properties['source_attributes'].get('GLOBALID')
                        if native:
                            native_overlaps[native] += 1
                    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
                        row['invalid_features'] += 1
                        if len(row['errors']) < 5:
                            row['errors'].append(str(error))
                row['geometry_types'] = dict(types)
                row['important_properties'] = sorted(keys)
                if bounds:
                    row['bounds'] = [min(b[0] for b in bounds), min(b[1] for b in bounds),
                                     max(b[2] for b in bounds), max(b[3] for b in bounds)]
            except (OSError, ValueError, TypeError, AttributeError) as error:
                row['errors'].append(str(error)); row['layer_error'] = True
            log.info('MALAYSIA GIS %s valid=%s invalid=%s null=%s', path.name,
                row['valid_features'], row['invalid_features'], row['null_geometries'])
        for path, layer in by_path.items():
            if path not in files:
                audit.append(dict(filename=layer['filename'], layer_error=True, errors=['Dataset file missing'],
                    feature_count=0, valid_features=0, invalid_features=0, null_geometries=0, duplicates=0))
        bounds = [g.bounds for g in geometries]
        metadata = dict(display_name=manifest['display_name'], source_tier='LOCAL_GIS',
            licence_authority='NOT YET RECORDED', directory=str(self.directory),
            total_features=len(objects), in_view=0, file_count=len(files),
            invalid_features=sum(r['invalid_features'] for r in audit),
            null_geometries=sum(r['null_geometries'] for r in audit),
            duplicate_features=sum(r['duplicates'] for r in audit),
            cross_layer_native_overlaps=sum(n-1 for n in native_overlaps.values() if n>1),
            errors=[r['filename'] + ': ' + '; '.join(r['errors']) for r in audit if r.get('layer_error')],
            bounds=[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)] if bounds else None)
        # Publish an entire new snapshot only after index construction succeeds.
        self._tree = STRtree(geometries)
        self._objects, self._geometries = tuple(objects), tuple(geometries)
        self.layers, self.audit, self.metadata = tuple(manifest['layers']), audit, metadata
        self._signature = signature
        self.load_count += 1

    def query_bbox(self, west, south, east, north):
        from ..models import number
        for v, lo, hi in ((west,-180,180),(east,-180,180),(south,-90,90),(north,-90,90)):
            number(v,lo,hi,'bbox')
        if south >= north:
            raise MaritimeDataError('Invalid bbox latitude order')
        parts = [(west,south,east,north)] if west <= east else [(west,south,180,north),(-180,south,east,north)]
        matches = set()
        for bounds in parts:
            matches.update(int(i) for i in self._tree.query(box(*bounds), predicate='intersects'))
        return tuple(self._objects[i] for i in sorted(matches))

    def fetch(self, area):
        self.load()
        from .provider_common import bbox_parts
        selected = {}
        for bounds in ([area.local_bounds] if area.local_bounds else bbox_parts(area)):
            selected.update((o.object_id,o) for o in self.query_bbox(*bounds))
        objects = tuple(selected.values())
        return GISResult(objects, {**self.metadata, 'in_view': len(objects)}, self.layers)

    def stop(self):
        self._stopped = True
