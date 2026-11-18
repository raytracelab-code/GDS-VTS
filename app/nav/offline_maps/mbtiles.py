"""Bounded read-only MBTiles access. Requests use XYZ; storage uses TMS."""
from collections import OrderedDict
import json
import math
from pathlib import Path
import sqlite3
import threading
import zlib

MAX_TILE_BYTES = 16 * 1024 * 1024
MAX_RASTER_DIMENSION = 4096
MIME = {'pbf': 'application/x-protobuf', 'mvt': 'application/x-protobuf',
        'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}


class MapPackageError(ValueError):
    pass


def _protobuf_fields(data):
    data=memoryview(data);offset=0
    def varint():
        nonlocal offset
        value=0
        for shift in range(0,70,7):
            if offset>=len(data):raise ValueError('Truncated protobuf')
            byte=data[offset];offset+=1;value|=(byte&127)<<shift
            if byte<128:return value
        raise ValueError('Oversized varint')
    while offset<len(data):
        tag=varint();field,wire=tag>>3,tag&7
        if not 0<field<2**29:raise ValueError('Invalid field')
        if wire==0:value=varint()
        else:
            length=varint() if wire==2 else 8 if wire==1 else 4 if wire==5 else -1
            if length<0 or offset+length>len(data):raise ValueError('Invalid field size')
            value=data[offset:offset+length];offset+=length
        yield field,wire,value


def valid_vector(data):
    """Structural MVT validation, without decoding geometries into memory."""
    try:
        for field,wire,value in _protobuf_fields(data):
            if field!=3:continue
            if wire!=2:return False
            name=version=False
            for key,kind,part in _protobuf_fields(value):
                if key==1:
                    if kind!=2 or not 0<len(part)<=256:return False
                    bytes(part).decode('utf-8');name=True
                if key==15:version=kind==0 and part in (1,2)
            if not name or not version:return False
        return True
    except (ValueError,UnicodeError):
        return False


def xyz_to_tms(z, x, y):
    if any(type(v) is not int for v in (z, x, y)) or not 0 <= z <= 22 or not (0 <= x < 2**z and 0 <= y < 2**z):
        raise MapPackageError('Invalid XYZ tile coordinate')
    return 2**z - 1 - y


def valid_raster(data, fmt):
    """Decode with the same image codecs as NAV, after bounding allocation."""
    from app.qt.QtCore import QByteArray, QBuffer, QIODevice
    from app.qt.QtGui import QImageReader

    if fmt == 'png' and not (data.startswith(b'\x89PNG\r\n\x1a\n') and data.endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82')):
        return False
    if fmt in ('jpg', 'jpeg') and not (data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')):
        return False
    if fmt == 'webp' and not (data.startswith(b'RIFF') and data[8:12] == b'WEBP' and int.from_bytes(data[4:8], 'little') + 8 == len(data)):
        return False
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer, b'jpeg' if fmt in ('jpg', 'jpeg') else fmt.encode())
    size = reader.size()
    if not (0 < size.width() <= MAX_RASTER_DIMENSION and 0 < size.height() <= MAX_RASTER_DIMENSION):
        return False
    return not reader.read().isNull()


def bounds(value):
    try:
        b = tuple(float(n) for n in (value.split(',') if isinstance(value, str) else value))
        if len(b) != 4 or not all(math.isfinite(n) for n in b):
            raise ValueError()
        w, s, e, n = b
        if not (-180 <= w < e <= 180 and -85.051129 <= s < n <= 85.051129):
            raise ValueError()
        return b
    except (TypeError, ValueError):
        raise MapPackageError('Invalid Web Mercator bounds') from None


class MBTiles:
    def __init__(self, path, cache_size=128):
        self.path = Path(path).resolve(strict=True)
        self.cache_size = max(0, min(int(cache_size), 4096))
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._lock = threading.RLock()
        self._connection = None
        try:
            self._connection = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, check_same_thread=False, timeout=1)
            self._connection.execute('PRAGMA query_only=ON')
            self._connection.execute('PRAGMA cache_size=-2048')
            # Bound work even for a malformed/untrusted SQL view.
            self._connection.set_progress_handler(lambda: 1, 250000)
            rows = self._connection.execute('SELECT substr(name,1,257),substr(value,1,1048577) FROM metadata LIMIT 257').fetchall()
            if len(rows) > 256 or any(len(str(v)) > 1024 * 1024 for _, v in rows):
                raise MapPackageError('Metadata too large')
            self.metadata = dict(rows)
            # Geofabrik Shortbread supplies author/license rather than the
            # optional MBTiles attribution key. Preserve the database unchanged.
            if 'attribution' not in self.metadata and all(isinstance(self.metadata.get(k),str) and self.metadata[k].strip() for k in ('author','license')):
                self.metadata['attribution'] = self.metadata['author']+' | '+self.metadata['license']
            self._validate()
            # Require the normal MBTiles index; otherwise individual reads may scan gigabytes.
            plan = ' '.join(str(r) for r in self._connection.execute('EXPLAIN QUERY PLAN SELECT tile_data FROM tiles WHERE zoom_level=0 AND tile_column=0 AND tile_row=0'))
            if 'SEARCH' not in plan.upper():
                raise MapPackageError('MBTiles needs an indexed tile coordinate lookup')
            sample = self._connection.execute('SELECT zoom_level,tile_column,tile_row FROM tiles LIMIT 1').fetchone()
            if not sample:
                raise MapPackageError('MBTiles contains no tiles')
            z, x, row = sample
            xyz_to_tms(z, x, row)
            if self.tile(z, x, 2**z - 1 - row) is None:
                raise MapPackageError('Invalid sample tile')
        except (sqlite3.Error, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            self.close()
            raise MapPackageError(f'Invalid MBTiles: {exc}') from exc

    def _validate(self):
        m = self.metadata
        for key in ('name', 'description', 'version', 'type', 'format', 'bounds', 'center', 'minzoom', 'maxzoom', 'attribution'):
            if not isinstance(m.get(key), str) or not m[key].strip():
                raise MapPackageError(f'Missing metadata: {key}')
        self.format = m['format'].lower()
        if self.format not in MIME or m['type'] not in ('baselayer', 'overlay') or m.get('scheme', 'tms') != 'tms':
            raise MapPackageError('Unsupported tile format/type/storage scheme')
        self.bounds = bounds(m['bounds'])
        self.minzoom, self.maxzoom = int(m['minzoom']), int(m['maxzoom'])
        if not 0 <= self.minzoom <= self.maxzoom <= 22:
            raise MapPackageError('Invalid zoom range')
        center = tuple(float(n) for n in m['center'].split(','))
        w, s, e, n = self.bounds
        if len(center) != 3 or not all(math.isfinite(v) for v in center) or not (w <= center[0] <= e and s <= center[1] <= n and self.minzoom <= center[2] <= self.maxzoom):
            raise MapPackageError('Invalid center')
        if self.format in ('pbf', 'mvt'):
            layers = json.loads(m.get('json', '{}')).get('vector_layers', [])
            if not layers or any(not isinstance(layer.get('id'), str) for layer in layers):
                raise MapPackageError('Vector MBTiles needs vector_layers metadata')

    def tile(self, z, x, y):
        row = xyz_to_tms(z, x, y)
        if not self.minzoom <= z <= self.maxzoom:
            return None
        key = (z, x, y)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if self._connection is None:
                return None
            try:
                record = self._connection.execute('SELECT length(tile_data),substr(tile_data,1,?) FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? LIMIT 1', (MAX_TILE_BYTES + 1, z, x, row)).fetchone()
                if not record or record[0] is None or record[0] > MAX_TILE_BYTES:
                    return None
                data = bytes(record[1])
                if self.format in ('pbf', 'mvt') and data.startswith(b'\x1f\x8b'):
                    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    data = decoder.decompress(data, MAX_TILE_BYTES + 1)
                    if len(data) > MAX_TILE_BYTES or not decoder.eof or decoder.unused_data:
                        return None
                if self.format in ('pbf','mvt') and not valid_vector(data):
                    return None
                if self.format not in ('pbf', 'mvt') and not valid_raster(data, self.format):
                    return None
            except (sqlite3.Error, zlib.error, TypeError):
                return None
            if self.cache_size:
                self._cache[key] = data
                self._cache_bytes += len(data)
                while len(self._cache) > self.cache_size or self._cache_bytes > 32 * 1024 * 1024:
                    self._cache_bytes -= len(self._cache.popitem(last=False)[1])
            return data

    def close(self):
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
            self._cache.clear()
            self._cache_bytes = 0
