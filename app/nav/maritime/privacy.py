"""Position generalisation for requests sent to public/third-party services.

The exact own-vessel fix stays local (distance/bearing, map marker). Anything
transmitted to an external provider is generalised first:

* own-vessel operating areas are centred on the nearest 0.5 degree grid node,
  with the radius enlarged by the worst-case snap offset, so the area that is
  requested still covers the configured radius around the real position;
* bounding boxes placed in request URLs/bodies are widened outward to a
  0.05 degree (~3 NM) grid, so a map view centred on the vessel (FOLLOW mode)
  does not reveal the vessel position to more than the grid resolution.

See docs/nav-external-data-privacy.md.
"""
import math

SNAP_DEGREES = 0.5
# Half-diagonal of a 0.5 degree cell at the equator: sqrt(2)*0.25 deg = 21.2 NM.
SNAP_MARGIN_NM = 22.0
BBOX_STEP_DEGREES = 0.05


def _snap(value, step):
    return math.floor(value / step + 0.5) * step


def snap_position(latitude, longitude, step=SNAP_DEGREES):
    lat = max(-90.0, min(90.0, _snap(latitude, step)))
    lon = _snap(longitude, step)
    lon = (lon + 180.0) % 360.0 - 180.0 if not -180.0 <= lon <= 180.0 else lon
    return round(lat, 6), round(lon, 6)


def widen_bounds(west, south, east, north, step=BBOX_STEP_DEGREES):
    """Outward-snap a WGS84 box; never shrinks the requested coverage."""
    w = max(-180.0, math.floor(west / step + 1e-9) * step)
    s = max(-90.0, math.floor(south / step + 1e-9) * step)
    e = min(180.0, math.ceil(east / step - 1e-9) * step)
    n = min(90.0, math.ceil(north / step - 1e-9) * step)
    return round(w, 6), round(s, 6), round(e, 6), round(n, 6)
