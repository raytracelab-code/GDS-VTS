from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .models import CATEGORY_FILES, SpatialCategory, SpatialState

def default_storage_root() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "GDS VTS" / "spatial"

class SpatialRepository:
    def __init__(self, root: Path | None = None):
        self.root = root or default_storage_root(); self.packages = self.root / "packages"; self.active_file = self.root / "active.json"
    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"); temporary.replace(path)
    def save_and_activate(self, metadata: dict[str, Any], collections: dict[SpatialCategory, dict[str, Any]]) -> None:
        target = self.packages / metadata["package_id"] / metadata["revision"]
        staging = target.with_name(target.name + ".staging")
        if staging.exists():
            import shutil; shutil.rmtree(staging)
        staging.mkdir(parents=True); enriched = dict(metadata, imported_at=datetime.now(timezone.utc).isoformat())
        self._write_json(staging / "manifest.json", enriched)
        for category, filename in CATEGORY_FILES.items(): self._write_json(staging / filename, collections[category])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            import shutil; shutil.rmtree(target)
        staging.replace(target); self._write_json(self.active_file, {"package_id": metadata["package_id"], "revision": metadata["revision"]})
    def load_active(self) -> SpatialState:
        if not self.active_file.exists(): return SpatialState.empty()
        try:
            pointer = json.loads(self.active_file.read_text(encoding="utf-8")); target = self.packages / pointer["package_id"] / pointer["revision"]
            metadata = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            collections = {category: json.loads((target / filename).read_text(encoding="utf-8")) for category, filename in CATEGORY_FILES.items()}
            return SpatialState(metadata, collections, datetime.now(timezone.utc).isoformat())
        except (OSError, KeyError, json.JSONDecodeError): return SpatialState.empty()
    def history(self) -> list[dict[str, Any]]:
        result=[]
        for manifest in self.packages.glob("*/*/manifest.json"):
            try: result.append(json.loads(manifest.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError): continue
        return sorted(result, key=lambda item: item.get("imported_at", ""), reverse=True)
