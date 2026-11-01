"""Pure spatial-selection helpers; no Qt or MapLibre dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SPATIAL_SELECTION_PRIORITY = {
    "operational-zone": 0, "anchor-pattern": 1, "pipeline": 2,
    "survey-area": 3, "site-boundary": 4,
}
SELECTION_PRIORITY = tuple(SPATIAL_SELECTION_PRIORITY)
SELECTABLE_LAYER_CATEGORIES = {
    "operational-zones-fill": "operational-zone", "operational-zones-line": "operational-zone",
    "anchor-patterns-fill": "anchor-pattern", "anchor-patterns-line": "anchor-pattern", "anchor-patterns-point": "anchor-pattern",
    "pipelines-line": "pipeline", "survey-areas-fill": "survey-area", "survey-areas-line": "survey-area",
    "site-boundary-fill": "site-boundary", "site-boundary-line": "site-boundary",
}
DISPLAY_FIELDS = ("name", "category", "feature_id", "status", "description", "source", "revision", "valid_from", "valid_to", "notes")

def feature_identity(feature: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict): return None
    props = feature["properties"]; category, feature_id = props.get("category"), props.get("feature_id")
    if category not in SPATIAL_SELECTION_PRIORITY or feature_id in (None, ""): return None
    return {"category": category, "feature_id": str(feature_id)}

def choose_feature(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick candidates independently of MapLibre's return order."""
    candidates = [feature for feature in features if feature_identity(feature)]
    return min(candidates, key=lambda f: (SPATIAL_SELECTION_PRIORITY[f["properties"]["category"]], str(f["properties"]["feature_id"])), default=None)

def feature_info(feature: dict[str, Any] | None) -> dict[str, str]:
    """Return only a display allow-list, never arbitrary package properties."""
    if not feature_identity(feature): return {}
    props = feature["properties"]
    return {key: str(props[key]) for key in DISPLAY_FIELDS if props.get(key) not in (None, "", "None", "null", "undefined")}

def selected_feature_payload(feature: dict[str, Any] | None) -> dict[str, Any]:
    identity = feature_identity(feature)
    if not identity or not isinstance(feature.get("geometry"), dict): return {}
    return {**feature_info(feature), "geometry": feature["geometry"]}

def find_feature(collections: dict[Any, dict[str, Any]], category: str, feature_id: str) -> dict[str, Any] | None:
    for key, collection in collections.items():
        if getattr(key, "value", key) != category: continue
        for feature in collection.get("features", []):
            identity = feature_identity(feature)
            if identity and identity["feature_id"] == str(feature_id): return feature
    return None

def coordinates_bounds(coordinates: Any) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []
    def walk(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)): points.append((value[0], value[1]))
        elif isinstance(value, (list, tuple)):
            for item in value: walk(item)
    walk(coordinates)
    return None if not points else (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))

def feature_bounds(feature: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    geometry = feature.get("geometry") if isinstance(feature, dict) else None
    if not isinstance(geometry, dict) or geometry.get("type") not in {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}: return None
    return coordinates_bounds(geometry.get("coordinates"))

@dataclass
class SpatialSelection:
    """Small Python-authoritative selection state."""
    feature: dict[str, Any] | None = None
    def clear(self) -> dict[str, Any]: self.feature = None; return {}
    def select(self, collections: dict[Any, dict[str, Any]], category: str, feature_id: str) -> dict[str, Any]:
        self.feature = find_feature(collections, category, feature_id)
        return selected_feature_payload(self.feature)
