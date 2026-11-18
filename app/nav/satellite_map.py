"""NASA GIBS raster metadata, verified against its EPSG:3857 capabilities.

No credentials, network access, vessel time or persistent imagery cache here.
"""
from datetime import datetime, timedelta, timezone

PROVIDER = 'NASA GIBS'
# Suomi NPP daily metadata stops at 2026-11-02. NOAA-20 is the current
# equivalent VIIRS true-color product (advertised through 2026-11-09).
LAYER = 'VIIRS_NOAA20_CorrectedReflectance_TrueColor'
ENDPOINT = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best'
MATRIX = 'GoogleMapsCompatible_Level9'
ATTRIBUTION = '<a href="https://nasa-gibs.github.io/gibs-api-docs/" target="_blank" rel="noopener">NASA GIBS / EOSDIS</a> · VIIRS NOAA-20 True Color'

# Verified from the official WMS 1.3.0 capabilities, 2026-11-09.
GEBCO_ENDPOINT = 'https://wms.gebco.net/mapserv?'
GEBCO_LAYER = 'GEBCO_LATEST'
GEBCO_ATTRIBUTION = ('Imagery reproduced from the GEBCO_2026 Grid, '
    '<a href="https://doi.org/10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa">'
    'GEBCO Compilation Group (2026) GEBCO 2026 Grid</a> · Context only; not for navigation')


def bathymetry_config():
    return dict(layer=GEBCO_LAYER, endpoint=GEBCO_ENDPOINT,
        contours='DEPTH CONTOUR VECTOR SOURCE NOT AVAILABLE',
        source=dict(type='raster', tileSize=256, minzoom=0, maxzoom=9,
            attribution=GEBCO_ATTRIBUTION, tiles=[GEBCO_ENDPOINT+
                'SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS='+GEBCO_LAYER+
                '&STYLES=default&CRS=EPSG:3857&BBOX={bbox-epsg-3857}'
                '&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=TRUE']))


def imagery_dates(now=None):
    """Most recent four UTC data days, independent of telemetry/GNSS time."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Imagery clock must be timezone-aware')
    today = now.astimezone(timezone.utc).date()
    return [(today-timedelta(days=days)).isoformat() for days in range(4)]


def tile_template(day):
    # Require an ISO date, rather than allowing arbitrary path components.
    if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
        raise ValueError('Invalid imagery date')
    return f'{ENDPOINT}/{LAYER}/default/{day}/{MATRIX}/{{z}}/{{y}}/{{x}}.jpeg'


def satellite_config(now=None):
    dates = imagery_dates(now)
    return dict(provider=PROVIDER, layer=LAYER, endpoint=ENDPOINT,
                state='READY', requires_key=False, projection='EPSG:3857',
                tile_matrix_set=MATRIX, format='image/jpeg', tile_size=256,
                minzoom=0, maxzoom=9, date_source='SYSTEM_UTC', dates=dates,
                attribution=ATTRIBUTION,
                bathymetry=bathymetry_config(),
                limitation='Regional Earth-observation context; infrastructure is shown by local GIS.',
                candidates=[dict(date=day, source=dict(type='raster', tiles=[tile_template(day)],
                    tileSize=256, minzoom=0, maxzoom=9, scheme='xyz', attribution=ATTRIBUTION))
                    for day in dates])
