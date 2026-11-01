"""One explicitly-owned WebEngine profile for the NAV map."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWebEngineCore import QWebEngineProfile


def _probe(path: str) -> None:
    target = Path(path)
    parent = target.parent
    exists = target.exists()
    writable = False
    result = "not attempted"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".gds-webengine-write-probe"
        probe.write_text("probe", encoding="utf-8")
        probe.unlink()
        writable, result = True, "created and removed"
    except OSError as error:
        result = f"failed: {error}"
    print(f"WEB PATH {target} exists={exists} parent_exists={parent.exists()} writable={writable} temp={result}", flush=True)


def create_nav_profile(parent) -> QWebEngineProfile:
    """Configure paths before a page is constructed; retain this profile in NavPage."""
    root = Path(os.environ.get("LOCALAPPDATA", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))) / "GDS VTS" / "webengine"
    cache, storage = root / "cache", root / "storage"
    cache.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    profile = QWebEngineProfile("gds-nav", parent)
    profile.setCachePath(str(cache))
    profile.setPersistentStoragePath(str(storage))
    print("WEB 1 profile acquired", flush=True)
    print(f"WEB PROFILE storageName = {profile.storageName()}", flush=True)
    print(f"WEB PROFILE cachePath = {profile.cachePath()}", flush=True)
    print(f"WEB PROFILE persistentStoragePath = {profile.persistentStoragePath()}", flush=True)
    print(f"WEB PROFILE offTheRecord = {profile.isOffTheRecord()}", flush=True)
    print(f"WEB Qt CacheLocation = {QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)}", flush=True)
    print(f"WEB Qt AppDataLocation = {QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)}", flush=True)
    for path in (profile.cachePath(), profile.persistentStoragePath(), QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation), QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)):
        _probe(path)
    print("WEB 2 profile paths printed", flush=True)
    return profile
