from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .models import SpatialCategory, SpatialState
from .package_loader import read_package
from .repository import SpatialRepository
from .validator import normalize_collection, validate_manifest
from .interaction import SpatialSelection

log = logging.getLogger(__name__)
class SpatialStateService(QObject):
    spatialStateChanged = Signal(dict)
    selectedSpatialFeatureChanged = Signal(dict)
    def __init__(self, repository: SpatialRepository | None = None):
        super().__init__(); self.repository=repository or SpatialRepository(); self.last_error=None; self.state=self.repository.load_active(); self.selection=SpatialSelection()
    def payload(self): return self.state.bridge_payload()
    def emit_state(self): self.spatialStateChanged.emit(self.payload())
    def clear_selection(self) -> None:
        self.selectedSpatialFeatureChanged.emit(self.selection.clear())
    def select_feature(self, category: str, feature_id: str) -> None:
        self.selectedSpatialFeatureChanged.emit(self.selection.select(self.state.collections, category, feature_id))
    def import_package(self, package_path: str | Path) -> SpatialState:
        log.info("Spatial package import started")
        try:
            manifest, raw = read_package(str(package_path)); metadata=validate_manifest(manifest)
            collections={category: normalize_collection(raw[category], category, metadata["package_id"]) for category in SpatialCategory}
            self.repository.save_and_activate(metadata, collections)
            self.clear_selection()
            self.state=SpatialState(dict(metadata, imported_at=datetime.now(timezone.utc).isoformat()), collections, datetime.now(timezone.utc).isoformat()); self.last_error=None; self.emit_state(); log.info("Spatial package activated: %s %s",metadata["package_id"],metadata["revision"]); return self.state
        except Exception as error:
            self.last_error=str(error); log.warning("Spatial package rejected: %s", error); raise
