from __future__ import annotations
import json
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from .exceptions import SpatialPackageError
from .models import CATEGORY_FILES, SpatialCategory

MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_BYTES = 80 * 1024 * 1024
ALLOWED_FILES = {"manifest.json", *CATEGORY_FILES.values()}

def _safe_name(name: str) -> str:
    decoded = urllib.parse.unquote(name).replace("\\", "/")
    path = PurePosixPath(decoded)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1 or decoded not in ALLOWED_FILES:
        raise SpatialPackageError("Package contains unsafe path")
    return decoded

def read_package(path: str) -> tuple[dict[str, Any], dict[SpatialCategory, Any]]:
    if Path(path).stat().st_size > MAX_PACKAGE_BYTES:
        raise SpatialPackageError("Package exceeds size limit")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if sum(info.file_size for info in infos) > MAX_EXTRACTED_BYTES: raise SpatialPackageError("Package exceeds extracted size limit")
            files = {}
            for info in infos:
                name = _safe_name(info.filename)
                if info.is_dir() or info.file_size > MAX_FILE_BYTES or info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise SpatialPackageError("Package contains unsafe file")
                files[name] = archive.read(info)
    except zipfile.BadZipFile as error: raise SpatialPackageError("Invalid spatial package") from error
    if "manifest.json" not in files: raise SpatialPackageError("Manifest missing")
    def parse(name):
        try: return json.loads(files[name].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error: raise SpatialPackageError(f"Malformed {name}") from error
    manifest = parse("manifest.json")
    return manifest, {category: parse(name) if name in files else None for category, name in CATEGORY_FILES.items()}
