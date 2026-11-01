from dataclasses import dataclass
from enum import Enum
from typing import Any


class SpatialCategory(str, Enum):
    SITE_BOUNDARY = "site-boundary"
    PIPELINE = "pipeline"
    ANCHOR_PATTERN = "anchor-pattern"
    SURVEY_AREA = "survey-area"
    OPERATIONAL_ZONE = "operational-zone"


CATEGORY_FILES = {
    SpatialCategory.SITE_BOUNDARY: "site_boundaries.geojson",
    SpatialCategory.PIPELINE: "pipelines.geojson",
    SpatialCategory.ANCHOR_PATTERN: "anchor_patterns.geojson",
    SpatialCategory.SURVEY_AREA: "survey_areas.geojson",
    SpatialCategory.OPERATIONAL_ZONE: "operational_zones.geojson",
}

BRIDGE_KEYS = {
    SpatialCategory.SITE_BOUNDARY: "siteBoundary",
    SpatialCategory.PIPELINE: "pipelines",
    SpatialCategory.ANCHOR_PATTERN: "anchorPatterns",
    SpatialCategory.SURVEY_AREA: "surveyAreas",
    SpatialCategory.OPERATIONAL_ZONE: "operationalZones",
}


def empty_collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": []}


@dataclass(frozen=True)
class SpatialState:
    metadata: dict[str, Any] | None
    collections: dict[SpatialCategory, dict[str, Any]]
    loaded_at: str | None = None

    @property
    def feature_counts(self) -> dict[str, int]:
        counts = {category.value: len(self.collections[category]["features"]) for category in SpatialCategory}
        counts["total"] = sum(counts.values())
        return counts

    def bridge_payload(self) -> dict[str, Any]:
        payload = {BRIDGE_KEYS[category]: self.collections[category] for category in SpatialCategory}
        payload["metadata"] = self.metadata or {}
        payload["featureCounts"] = self.feature_counts
        return payload

    @classmethod
    def empty(cls) -> "SpatialState":
        return cls(None, {category: empty_collection() for category in SpatialCategory})
