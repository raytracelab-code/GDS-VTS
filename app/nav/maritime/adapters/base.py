from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from ..models import Category, MaritimeDataError, normalize_ais, normalize_maritime_feature, utcnow

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class SourceAdapter(ABC):
    """Called off GUI thread. Streaming adapters may deliver canonical batches instead.

    A response must cover only the supplied operating area. Stop must release resources.
    Raw S-57/S-101, NMEA AIS and PMTiles decoding are NOT implemented by this boundary.
    """
    @abstractmethod
    def fetch(self, area):
        raise NotImplementedError

    def start(self, area):
        return self.fetch(area)

    def update_area(self, area):
        return self.fetch(area)

    def stop(self):
        pass


@dataclass(frozen=True)
class SourceConfig:
    name: str
    endpoint: str
    api_key: str = field(default='', repr=False)
    dynamic: bool = False
    interval_seconds: float = 300


class JsonPollingAdapter(SourceAdapter):
    """HTTP(S) AIS JSON records, or local/HTTP GeoJSON FeatureCollections.

    HTTP requests include latitude, longitude, radius_nm. API keys use Authorization
    Bearer headers and are never included in map state, cache keys or error messages.
    """
    def __init__(self, config):
        self.config = config

    def fetch(self, area):
        endpoint = self.config.endpoint
        parsed = urlsplit(endpoint)
        if parsed.scheme in ('http', 'https'):
            if parsed.username or parsed.password:
                raise MaritimeDataError('use an API key header, not URL credentials')
            # Generalised centre (0.05 deg grid) with the radius widened to keep coverage.
            from ..privacy import snap_position, BBOX_STEP_DEGREES
            latitude, longitude = snap_position(area.latitude, area.longitude, BBOX_STEP_DEGREES)
            query = list(parse_qsl(parsed.query, keep_blank_values=True)) + [
                ('latitude', str(latitude)), ('longitude', str(longitude)), ('radius_nm', str(min(250, area.radius_nm + 3)))]
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))
            headers = {'Accept': 'application/json', 'User-Agent': 'GDS-VTS-Maritime/4'}
            if self.config.api_key:
                headers['Authorization'] = 'Bearer ' + self.config.api_key
            with urlopen(Request(url, headers=headers), timeout=10) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        elif not parsed.scheme or (len(parsed.scheme) == 1 and len(endpoint) > 2 and endpoint[1] == ':'):
            with Path(endpoint).open('rb') as handle:
                data = handle.read(MAX_RESPONSE_BYTES + 1)
        else:
            raise MaritimeDataError('unsupported provider endpoint scheme')
        if len(data) > MAX_RESPONSE_BYTES:
            raise MaritimeDataError('source response exceeds limit')
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError) as error:
            raise MaritimeDataError('invalid source JSON') from error
        return self.normalize(payload, area)

    def normalize(self, payload, area):
        if self.config.name == 'ais':
            records = payload.get('vessels') if isinstance(payload, dict) else payload
            if not isinstance(records, list) or len(records) > 50000:
                raise MaritimeDataError('expected bounded AIS vessels list')
            objects = [normalize_ais(r, 'ais', utcnow()) for r in records]
        else:
            if not isinstance(payload, dict) or payload.get('type') != 'FeatureCollection' or not isinstance(payload.get('features'), list) or len(payload['features']) > 50000:
                raise MaritimeDataError('expected bounded GeoJSON FeatureCollection')
            objects = [normalize_maritime_feature(f, self.config.name, payload.get('dataset_at')) for f in payload['features']]
        return [o for o in objects if intersects_area(o.geometry, area)]


def intersects_area(geometry, area):
    """Conservative bounds intersection includes long lines/polygons crossing area."""
    points = []
    def walk(c):
        if isinstance(c[0], (int, float)):
            points.append(c)
        else:
            for child in c:
                walk(child)
    walk(geometry['coordinates'])
    if any(area.contains(p[1], p[0]) for p in points):
        return True
    # Conservative dateline-safe bounding box; may include extra features, never world queries.
    import math
    relative = [((p[0]-area.longitude+180) % 360-180, p[1]-area.latitude) for p in points]
    dy, dx = area.radius_nm/60, min(180, area.radius_nm/(60*max(.01, math.cos(math.radians(area.latitude)))))
    return min(p[0] for p in relative) <= dx and max(p[0] for p in relative) >= -dx and min(p[1] for p in relative) <= dy and max(p[1] for p in relative) >= -dy


class StaticCache:
    """Per-source/per-area last successful static snapshot. Never caches AIS."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def _path(self, config, area):
        fingerprint = json.dumps([config.name, config.endpoint, area.payload()], sort_keys=True)
        return self.directory / (sha256(fingerprint.encode()).hexdigest()+'.json')

    def save(self, config, area, objects):
        if config.dynamic:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(config, area)
        features = []
        for obj in objects:
            if obj.category == Category.VESSEL:
                continue
            p = dict(obj.properties, category=str(obj.category), object_type=obj.object_type,
                     observed_at=obj.observed_at.isoformat() if obj.observed_at else None,
                     dataset_at=obj.dataset_at.isoformat() if obj.dataset_at else None,
                     expires_at=obj.expires_at.isoformat() if obj.expires_at else None)
            if obj.object_id.startswith('maritime:'):
                p['canonical_id'] = obj.object_id[len('maritime:'):]
            features.append(dict(type='Feature', id=obj.source_id, properties=p, geometry=obj.geometry))
        payload = dict(type='FeatureCollection', source=config.name, area=area.payload(), cached_at=utcnow().isoformat(), features=features)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload, allow_nan=False), encoding='utf8')
        temporary.replace(path)
        # Bound local cache growth across operating areas.
        paths = sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in paths[100:]:
            old.unlink(missing_ok=True)

    def load(self, config, area):
        if config.dynamic:
            return None
        path = self._path(config, area)
        try:
            if not path.is_file() or path.stat().st_size > MAX_RESPONSE_BYTES:
                return None
            payload = json.loads(path.read_text(encoding='utf8'))
            if payload.get('source') != config.name or payload.get('area') != area.payload():
                return None
            return JsonPollingAdapter(config).normalize(payload, area)
        except (OSError, ValueError, TypeError):
            return None

    def load_fresh(self, config, area):
        if config.dynamic:return None
        path=self._path(config,area)
        try:
            if path.stat().st_size>MAX_RESPONSE_BYTES:return None
            from ..models import timestamp
            age=(utcnow()-timestamp(json.loads(path.read_text(encoding='utf8'))['cached_at'])).total_seconds()
            return self.load(config,area) if 0<=age<config.interval_seconds else None
        except (OSError,ValueError,KeyError,TypeError):pass
        # Reuse a recent snapshot that fully covers this view (including harmless
        # floating-point camera jitter). Never label a partially covered area fresh.
        if config.name!='overpass' or area.viewport_bounds is None:return None
        try:
            from ..area_controller import OperatingArea
            from .provider_common import bbox_parts
            from ..models import timestamp
            paths=sorted(self.directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:10]
            for candidate in paths:
                if candidate==path or candidate.stat().st_size>MAX_RESPONSE_BYTES:continue
                payload=json.loads(candidate.read_text(encoding='utf8'))
                if payload.get('source')!=config.name:continue
                previous=OperatingArea(**payload['area'])
                if self._path(config,previous)!=candidate:continue
                age=(utcnow()-timestamp(payload['cached_at'])).total_seconds()
                if not 0<=age<config.interval_seconds:continue
                covered=all(any(ow-1e-8<=w and os-1e-8<=s and oe+1e-8>=e and on+1e-8>=n for ow,os,oe,on in bbox_parts(previous)) for w,s,e,n in bbox_parts(area))
                if covered:return JsonPollingAdapter(config).normalize(payload,area)
        except (OSError,ValueError,KeyError,TypeError):pass
        return None
