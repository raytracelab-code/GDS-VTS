"""Validated canonical records. No provider payload is passed directly to the map."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from app.core.compat import StrEnum
import json
import math


class MaritimeDataError(ValueError):
    pass


class Category(StrEnum):
    VESSEL = 'vessels'
    OFFSHORE_INSTALLATION = 'offshore'
    AID_TO_NAVIGATION = 'aton'
    PORT_HARBOUR = 'ports'
    ANCHORAGE = 'anchorages'
    TRAFFIC_ROUTE = 'routes'
    RESTRICTED_AREA = 'restricted'
    SUBSEA_INFRASTRUCTURE = 'subsea'
    HAZARD = 'hazards'
    BATHYMETRY = 'bathymetry'
    NAV_WARNING = 'warnings'
    METOCEAN = 'metocean'
    OFFSHORE_WELL = 'offshore_wells'
    OIL_GAS_FIELD = 'oil_gas_fields'
    DEVELOPMENT_AREA = 'development_areas'
    PETROLEUM_BLOCK = 'petroleum_blocks'
    PETROLEUM_BASIN = 'basins'
    SEISMIC_SURVEY_AREA = 'seismic_surveys'
    GEOPHYSICAL_SURVEY_AREA = 'geophysical_surveys'


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    if value is None:
        return None
    try:
        if isinstance(value, str) and len(value) > 80:
            raise ValueError()
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError) as error:
        raise MaritimeDataError('invalid timezone-aware timestamp') from error


def text(value, field, required=False, limit=512):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise MaritimeDataError(f'invalid {field}')
    return value.strip()


def number(value, low, high, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise MaritimeDataError(f'invalid {field}')
    return value


def validate_geometry(geometry, max_points=20000):
    if not isinstance(geometry, dict):
        raise MaritimeDataError('geometry is required')
    kind, coordinates = geometry.get('type'), geometry.get('coordinates')
    count = [0]

    def point(p):
        count[0] += 1
        if count[0] > max_points or not isinstance(p, (list, tuple)) or len(p) not in (2, 3):
            raise MaritimeDataError('invalid coordinate count')
        number(p[0], -180, 180, 'longitude'); number(p[1], -90, 90, 'latitude')
        if len(p) == 3:
            number(p[2], -1e6, 1e6, 'altitude')

    def line(c, ring=False):
        if not isinstance(c, (list, tuple)) or len(c) < (4 if ring else 2):
            raise MaritimeDataError('invalid line/ring')
        for p in c:
            point(p)
        if ring and c[0] != c[-1]:
            raise MaritimeDataError('unclosed polygon')

    def polygon(c):
        if not isinstance(c, (list, tuple)) or not c:
            raise MaritimeDataError('empty polygon')
        for ring in c:
            line(ring, True)

    if kind == 'Point':
        point(coordinates)
    elif kind == 'LineString':
        line(coordinates)
    elif kind == 'Polygon':
        polygon(coordinates)
    elif kind in ('MultiPoint', 'MultiLineString', 'MultiPolygon'):
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise MaritimeDataError('empty multi geometry')
        for c in coordinates:
            {'MultiPoint': point, 'MultiLineString': line, 'MultiPolygon': polygon}[kind](c)
    else:
        raise MaritimeDataError('unsupported geometry')
    # Shapely mapping() returns tuples. Qt's QVariant/QJson boundary serializes
    # nested tuples as null even though Python json.dumps accepts them.
    def arrays(value):
        return [arrays(item) for item in value] if isinstance(value,(tuple,list)) else value
    return {'type': kind, 'coordinates': arrays(coordinates)}


def safe_properties(value):
    if not isinstance(value, dict) or len(value) > 100:
        raise MaritimeDataError('invalid properties')

    def check(item, depth=0):
        if depth > 4:
            raise MaritimeDataError('properties too deeply nested')
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, str):
            text(item, 'property', limit=4096)
        elif isinstance(item, (int, float)):
            number(item, -1e15, 1e15, 'property')
        elif isinstance(item, list) and len(item) <= 100:
            for v in item:
                check(v, depth + 1)
        elif isinstance(item, dict) and len(item) <= 100:
            for k, v in item.items():
                text(k, 'property name', True, 80); check(v, depth + 1)
        else:
            raise MaritimeDataError('invalid property value')
    check(value)
    return deepcopy(value)


@dataclass(frozen=True)
class MaritimeObject:
    object_id: str
    object_type: str
    category: Category
    geometry: dict
    source: str
    source_id: str | None = None
    observed_at: datetime | None = None
    dataset_at: datetime | None = None
    expires_at: datetime | None = None
    received_at: datetime | None = None
    properties: dict = None
    status: str = 'CURRENT'
    freshness: str = 'UNKNOWN'

    def __post_init__(self):
        text(self.object_id, 'object_id', True, 256)
        text(self.object_type, 'object_type', True, 80)
        text(self.source, 'source', True, 128)
        text(self.source_id, 'source_id', limit=256)
        text(self.status, 'status', True, 80)
        try:
            object.__setattr__(self, 'category', Category(self.category))
        except ValueError as error:
            raise MaritimeDataError('invalid category') from error
        # Detailed local facility drawings can contain many separate short line
        # segments which topology-preserving simplification cannot eliminate.
        object.__setattr__(self, 'geometry', validate_geometry(self.geometry,
            max_points=200000 if self.source == 'malaysia_gis' else 20000))
        object.__setattr__(self, 'properties', safe_properties(self.properties or {}))
        for field in ('observed_at', 'dataset_at', 'expires_at', 'received_at'):
            object.__setattr__(self, field, timestamp(getattr(self, field)))

    def payload(self, now=None):
        now = now or utcnow()
        stamp = self.observed_at or self.dataset_at
        return dict(object_id=self.object_id, object_type=self.object_type, category=str(self.category),
                    geometry=deepcopy(self.geometry), source=self.source, source_id=self.source_id,
                    observed_at=self.observed_at.isoformat() if self.observed_at else None,
                    dataset_at=self.dataset_at.isoformat() if self.dataset_at else None,
                    received_at=self.received_at.isoformat() if self.received_at else None,
                    expires_at=self.expires_at.isoformat() if self.expires_at else None,
                    age_seconds=max(0, (now-stamp).total_seconds()) if stamp else None,
                    freshness=self.freshness, status=self.status, properties=deepcopy(self.properties))


def normalize_ais(record, source, now=None):
    """Normalized AIS JSON contract, not an NMEA/AIVDM decoder."""
    if not isinstance(record, dict):
        raise MaritimeDataError('AIS record must be an object')
    mmsi = str(record.get('mmsi', ''))
    if len(mmsi) != 9 or not mmsi.isascii() or not mmsi.isdigit() or int(mmsi) == 0:
        raise MaritimeDataError('MMSI must be nine digits')
    p = {'mmsi': mmsi}
    for key in ('imo', 'name', 'call_sign', 'ship_type', 'navigation_status', 'destination', 'eta'):
        if record.get(key) is not None:
            if isinstance(record[key], bool) or not isinstance(record[key], (str, int)):
                raise MaritimeDataError('invalid AIS '+key)
            p[key] = text(str(record[key]), key, limit=256)
    for key, low, high in [('sog', 0, 102.2), ('cog', 0, 359.9999), ('heading', 0, 359.9999), ('draught', 0, 100)]:
        val = record.get(key)
        if key in record and (val is None or (key == 'heading' and val == 511) or (key == 'cog' and val == 360) or (key == 'sog' and val == 102.3)):
            p[key] = None  # Explicit unavailability clears an older value on update.
        elif val is not None:
            p[key] = number(val, low, high, key)
    observed = timestamp(record.get('position_timestamp') or record.get('observed_at') or record.get('last_update'))
    now = now or utcnow()
    if observed and (observed-now).total_seconds() > 300:
        raise MaritimeDataError('AIS timestamp is in the future')
    return MaritimeObject('ais:'+mmsi, 'vessel', Category.VESSEL,
                          {'type': 'Point', 'coordinates': [record.get('longitude'), record.get('latitude')]},
                          source, mmsi, observed_at=observed, received_at=now, properties=p,
                          status='LIVE', freshness='LIVE' if observed else 'UNKNOWN')


def normalize_maritime_feature(feature, source, dataset_at=None):
    if not isinstance(feature, dict) or feature.get('type') != 'Feature':
        raise MaritimeDataError('expected GeoJSON Feature')
    p = safe_properties(feature.get('properties') or {})
    for field in ('name','description','operator','characteristic','title'):
        if p.get(field) is not None:
            text(p[field], field, limit=4096 if field == 'description' else 512)
    if p.get('category') == str(Category.VESSEL):
        geometry = validate_geometry(feature.get('geometry'))
        if geometry['type'] != 'Point':
            raise MaritimeDataError('AIS vessel geometry must be a point')
        return normalize_ais({**p, 'longitude': geometry['coordinates'][0], 'latitude': geometry['coordinates'][1]}, source)
    sid = feature.get('id', p.get('source_id'))
    if sid is None:
        raise MaritimeDataError('static features require stable id or source_id')
    sid = text(str(sid), 'source_id', True, 256)
    canonical = p.pop('canonical_id', None)
    if canonical is not None:
        text(canonical, 'canonical_id', True, 200)
    kind = p.pop('object_type', 'maritime_feature')
    text(kind, 'object_type', True, 80)
    kind = kind.strip().lower().replace(' ', '_').replace('-', '_')
    kind = {'tss': 'traffic_separation_scheme', 'cable': 'submarine_cable', 'pipeline': 'submarine_pipeline',
            'oil_rig': 'drilling_rig', 'light_buoy': 'light_buoy', 'racon': 'radar_beacon'}.get(kind, kind)
    return MaritimeObject('maritime:'+canonical if canonical else source+':'+sid,
                          kind, p.pop('category', None),
                          feature.get('geometry'), source, sid,
                          observed_at=timestamp(p.pop('observed_at', None)),
                          dataset_at=timestamp(p.pop('dataset_at', dataset_at)),
                          expires_at=timestamp(p.pop('expires_at', None)),
                          properties=p, status=p.get('status', 'CURRENT'))
