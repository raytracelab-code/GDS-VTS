# Offline regional maps

These are optional developer utilities for independent official Geofabrik Shortbread MBTiles packages. NAV defaults to online OpenFreeMap; no regional packages remain installed. Set `GDS_MAP_SOURCE=offline` only for intentional offline operation. These tools never run automatically and are absent from the main operator sidebar. These
provide operational context mapping, not an ENC, ECDIS or an official nautical
chart. OpenStreetMap and Geofabrik attribution remains visible.

The historical Malaysia basemap package was removed during cleanup; the operational Malaysia GIS is preserved. The reusable engine still supports a legacy `active.json` pointer.
Additional packages use an atomic `regions.json` index in
`%LOCALAPPDATA%\GDS VTS\maps`. Each region has current/previous revision pointers,
an enabled state and a priority. Updates stage a new revision; rollback swaps only
that region's pointers. Removal protects the accepted active revisions and all
other regions' referenced revisions.

## Discover and plan

```powershell
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --refresh --list
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --profile asia-oceania --dry-run
```

Discovery follows the official Geofabrik JSON hierarchy, reads each relevant
regional HTML page, extracts its actual Shortbread link, and validates it with
HEAD. Unsupported parent regions can use official subregions. Indonesia prefers
available official subregions. No MBTiles download URL is invented. A catalog is
cached under `%LOCALAPPDATA%\GDS VTS\map-build\regions-catalog.json`.

Dry runs show remote bytes, cached/installed state, unavailable regions, selected
actions and a conservative disk budget. Cache + package preparation + installed
revision are budgeted before downloading, with at least 30 GiB left free. Actual
free disk is checked again when each download starts. Existing installed regions
are skipped by default, including Malaysia.

## Install

```powershell
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --region thailand
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --region australia
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --profile core-maritime-asia --workers 4
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --profile oceania-core --workers 4
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --profile asia-oceania --workers 4 --report docs/diagnostics/asia-oceania-install.json
```

Downloads stay outside Git in `map-build\sources`. Interrupted `.part` files carry
a URL/size/revision sidecar. A matching partial resumes with Range/If-Range; an
ignored Range safely restarts the stream. Changed revisions never append to an
old partial. Size, SQLite metadata and Shortbread schema are checked before final
naming. Installation also verifies SHA256 and low/mid/high native zoom samples.
No source MBTiles is rewritten. A failure is recorded per region and does not
undo earlier successful installations. Downloads may run concurrently;
installations and registry mutations remain serialized.

## Optional management code

The reusable `MapRegionsDialog` remains in the codebase for future offline use.
It is not exposed in the normal online NAV sidebar. Use the CLI for intentional
offline installations. Update checks refresh official metadata only. Installing
a newer revision requires an explicit install/update action:

```powershell
.\.venv\Scripts\python.exe tools\maps\install_geofabrik_regions.py --region thailand --refresh --update
```

Older source revisions remain cached separately; they are not overwritten.
An explicitly offline map session discovers CLI-installed packages on restart.
Normal online sessions do not discover or activate offline packages.

## Rendering and resource bounds

The existing Shortbread maritime adapter is shared across every region. Tile
URLs remain `gds://tiles/{package_id}/{role}/{z}/{x}/{y}.pbf`; there is no local
HTTP server or online basemap dependency. A 700 ms settled-view debounce manages
package source/layer activation without global `setStyle`, camera moves or
operational-source replacement.

Intersecting packages use deterministic explicit priority, then smaller-area
priority and package ID. A preferred package covering the entire viewport
suppresses redundant broader packages. Boundary views can retain both regions,
with higher-priority layers above lower-priority layers and shared symbol
collision placement. No synthetic geographic mask or seam geometry is created.

At most six detailed regional packages are active in a very wide view; the
nearest intersecting regions are retained. The read-only reader pool is bounded
to eight readers and releases inactive readers. Regional sources are removed
when inactive; operational layers and the existing palette/glow hierarchy stay
intact. An existing genuine overview source can remain underneath regional
detail. Without an overview asset, wide areas outside active detailed coverage
use the safe background; zoom into an installed region for its detail.

GLOBAL OVERVIEW ASSET PENDING

BATHYMETRY ASSET PENDING

Neither pending asset blocks independent regional basemap installation.
