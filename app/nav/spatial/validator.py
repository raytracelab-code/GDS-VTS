"""Strict GeoJSON/manifest validation; packages are untrusted input."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .exceptions import SpatialPackageError
from .models import SpatialCategory, empty_collection

SUPPORTED_GEOMETRIES = {
    SpatialCategory.SITE_BOUNDARY: {"Polygon", "MultiPolygon"},
    SpatialCategory.PIPELINE: {"LineString", "MultiLineString"},
    SpatialCategory.ANCHOR_PATTERN: {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"},
    SpatialCategory.SURVEY_AREA: {"Polygon", "MultiPolygon"},
    SpatialCategory.OPERATIONAL_ZONE: {"Polygon", "MultiPolygon"},
}
REQUIRED_MANIFEST = {"schema_version", "package_id", "name", "revision", "created_at", "coordinate_reference_system"}


def validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise SpatialPackageError("Invalid manifest.json")
    missing = REQUIRED_MANIFEST - set(manifest)
    if missing:
        raise SpatialPackageError(f"Manifest missing: {', '.join(sorted(missing))}")
    if manifest["schema_version"] != 1:
        raise SpatialPackageError("Unsupported schema version")
    if manifest["coordinate_reference_system"] != "EPSG:4326":
        raise SpatialPackageError("Unsupported coordinate system")
    for key in ("package_id", "name", "revision", "created_at"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise SpatialPackageError(f"Invalid manifest {key}")
    return deepcopy(manifest)


def _coordinate(value: Any) -> None:
    if not isinstance(value, list) or len(value) < 2:
        raise SpatialPackageError("Malformed coordinate")
    longitude, latitude = value[0], value[1]
    if not isinstance(longitude, (int, float)) or not isinstance(latitude, (int, float)) or not math.isfinite(longitude) or not math.isfinite(latitude):
        raise SpatialPackageError("Coordinate must be finite numbers")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise SpatialPackageError("Coordinate out of range")


def _coordinates(value: Any) -> None:
    if isinstance(value, list) and value and isinstance(value[0], (int, float)):
        _coordinate(value)
    elif isinstance(value, list) and value:
        for item in value:
            _coordinates(item)
    else:
        raise SpatialPackageError("Malformed geometry coordinates")


def _validate_polygon_rings(coordinates: Any, multi: bool = False) -> None:
    polygons = coordinates if multi else [coordinates]
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise SpatialPackageError("Malformed polygon")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise SpatialPackageError("Polygon ring must contain four coordinates")
            _coordinates(ring)
            if ring[0] != ring[-1]:
                ring.append(deepcopy(ring[0]))


def normalize_collection(value: Any, category: SpatialCategory, package_id: str) -> dict[str, Any]:
    if value is None:
        return empty_collection()
    if not isinstance(value, dict) or value.get("type") != "FeatureCollection" or not isinstance(value.get("features"), list):
        raise SpatialPackageError(f"Malformed {category.value} GeoJSON")
    if "crs" in value:
        raise SpatialPackageError("GeoJSON CRS declaration is not supported")
    result = empty_collection(); seen: set[str] = set()
    for index, raw in enumerate(value["features"]):
        if not isinstance(raw, dict) or raw.get("type") != "Feature" or not isinstance(raw.get("geometry"), dict):
            raise SpatialPackageError(f"Malformed {category.value} feature")
        geometry = deepcopy(raw["geometry"]); geometry_type = geometry.get("type")
        if geometry_type not in SUPPORTED_GEOMETRIES[category]:
            raise SpatialPackageError(f"Unsupported {category.value} geometry: {geometry_type}")
        _coordinates(geometry.get("coordinates"))
        if geometry_type == "Polygon": _validate_polygon_rings(geometry["coordinates"])
        if geometry_type == "MultiPolygon": _validate_polygon_rings(geometry["coordinates"], True)
        props = deepcopy(raw.get("properties") or {})
        if not isinstance(props, dict): raise SpatialPackageError("Feature properties must be an object")
        feature_id = raw.get("id", props.get("feature_id", f"{package_id}-{category.value}-{index + 1}"))
        if not isinstance(feature_id, (str, int)) or not str(feature_id).strip(): raise SpatialPackageError("Invalid feature ID")
        feature_id = str(feature_id)
        if feature_id in seen: raise SpatialPackageError("Duplicate feature ID")
        seen.add(feature_id)
        canonical = {"feature_id": feature_id, "name": str(props.pop("name", feature_id)), "category": category.value}
        for key in ("description", "status", "source", "revision", "valid_from", "valid_to", "notes"):
            if key in props: canonical[key] = props.pop(key)
        if props: canonical["source_properties"] = props
        result["features"].append({"type": "Feature", "id": feature_id, "properties": canonical, "geometry": geometry})
    return result
