# Southeast Asia offline asset checkpoint

Date:2026-11-08 (Asia/Dhaka).

**Production asset build is blocked by resource/dependency prerequisites.**
No production MBTiles were generated, imported, installed or activated. No
multi-GB sources were downloaded. Real-tile visual acceptance is not claimed.

Inspected git status/diff/stat before edits. Inherited workspace changes were
preserved. Baseline: **411 passed in27.77s**. Final: **420 passed in26.39s**.
Requested NAV py_compile and compileall app/main.py passed. Build driver
py_compile and git diff --check also passed. PowerShell entry point executed
preflight and returned its expected blocked/nonzero result without downloads.
Final requested `python -u main.py` launch reached window shown/app.exec;
MapLibre, QWebChannel and NAV loaded successfully (`NAV LOAD FINISHED: True`).
This is startup verification of the no-asset fallback, not real-asset acceptance.

## Preflight evidence

`docs/diagnostics/sea-build-preflight.json` records exact values:

| Resource | Observed |
|---|---|
| Disk free |195,898,241,024 bytes, approximately182.4GiB |
| Total physical RAM |16,851,132,416 bytes, approximately15.7GiB |
| Available RAM |4,420,841,472 bytes, approximately4.1GiB at saved preflight; initially3.3GiB |
| CPU |16 logical CPUs |
| Java |Oracle1.8.0_251,32-bit Client VM; current JAR path requires Java25+ |
| Planetiler JAR |Not present in expected external tools directory |
| Docker |Not on PATH; optional |
| GDAL |gdalinfo/gdalwarp/gdaldem/gdaladdo absent from PATH |
| Existing assets |None in expected map-build cache; no matching OSM/GEBCO/Planetiler/MBTiles found in checked Downloads/GDS VTS locations |
| Installed package |PackageManager discovery returned None |

Build policy requires64GiB free disk and8GiB available RAM for the default6GiB
Java heap plus2GiB reserve. Disk passed; available memory failed. Java25+,
Planetiler, GDAL and a genuine GEBCO_2026 subset must be supplied. No attempt was
made to replace Java or install dependencies automatically.

ASSET BUILD PENDING RESOURCE/DEPENDENCY.

## Sources and planned build

- OSM: [Geofabrik SEA](https://download.geofabrik.de/asia/sea.html),
  `sea-latest.osm.pbf`, not Asia/planet. The inspected listing reported OSM through
  2026-11-04T21:21:03Z and3,685,986,927 bytes for its dated extract. This is remote
  listing information, NOT a source consumed by this build. The tooling derives
  each real build's timestamp/bounds from its PBF HeaderBlock and records SHA256.
- Vector tooling: [Planetiler](https://github.com/onthegomap/planetiler) bundled
  OpenMapTiles profile; exact locally provisioned JAR SHA256, source dependency
  hashes, commands and durations are recorded. Default SEA z4–13, optional14;
  global context z0–5, from actual Natural Earth/water sources with regional OSM.
- Bathymetry: [GEBCO_2026](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid),
  user-defined data GeoTIFF subset,15-arc-second contextual source. No subset
  bounds or source timestamp is claimed without an actual input. The pipeline
  checks georeferencing/coverage, applies sea-only depth colors, reprojects to
  EPSG:3857 PNG MBTiles and builds z0–8 by default. Source checksum/release,
  geographic extents and GDAL metadata are retained.

All real source inputs, logs, scratch data and outputs belong under external
map-build storage. No source data is automatically deleted. Installation copies
a validated directory through the existing staged/atomic PackageManager; prior
revisions are retained. No large ZIP is required. See `offline-maps.md` for
exact build/import/validate/install/update/rollback commands and cleanup guidance.

## Changes

Created:

- `tools/maps/build_southeast_asia_offline_map.ps1`: operator entry point;
  default preflight, explicit build/import/inspect and optional installation.
- `tools/maps/build_southeast_asia.py`: resource gates, verified/reused source
  acquisition, Planetiler/GDAL commands, genuine PBF source-header inspection,
  metadata completion for new exports, asset statistics/sample reads, manifests,
  provenance/checksums and integration with the existing package manager.
- `tests/test_map_asset_build.py`: nine focused tests; no real downloads/builds.
- `docs/diagnostics/sea-build-preflight.json` and this checkpoint report.

Modified:

- `app/nav/offline_maps/render_config.py`: confirmed OpenMapTiles compatibility
  correction (landcover is vegetation, not a complete land mask): background uses
  explicit LAND role under water polygons. Deterministic compositing priority
  puts overview below SEA below overlapping details, ordered by native zoom and
  smaller coverage. Overview labels may appear at low zoom. Installed status
  reports readiness and local bathymetry availability.
- `app/ui/pages/nav/nav_page.py`: concise installed bathymetry status alongside
  offline map readiness; no NAV redesign.
- `docs/offline-maps.md`: reproducible source/build/import/update/validation guide.

MBTiles reader, scheme server, registry, palette calculations, Malaysia GIS
normalization, AIS, Squall and spatial systems were not rewritten or modified.
Configure, VDR and VJR were not modified. No commit was made. Other uncommitted
files, including unrelated files already shown by initial git status, are
inherited and untouched by this checkpoint.

## Validation and acceptance limits

The nine new cases cover actual manifest composition with test-only temporary
fixtures, vector/raster roles, SHA256 rejection before activation, source-layer
compatibility, background role, genuine overview/region bounds, overlap priority,
local glyph/tile routes, native zooms, blocked-download behavior and storage
isolation. No tests download data or invoke Planetiler/GDAL full builds.

All420 tests pass, including Phase1/2/3, Malaysia GIS, offline MBTiles and palette
regressions. Local font glyphs and application-generated icons remain in use;
the style has no remote sprite requirement. Independent source bounds allow
global context outside detailed coverage; MapLibre native maxzoom enables
overzoom. Those behaviors have automated coverage, not real-asset acceptance.

Pending: actual OSM acquisition, full vector/overview build, actual GEBCO subset,
full raster build, production tile counts/sizes/performance, real manifests and
checksums, installation/activation, real coverage/CRS/overlay alignment, remote
request audit and DAY/TWILIGHT/NIGHT/overzoom/out-of-coverage visual acceptance.
Bangladesh/Bay of Bengal needs a separately documented compatible regional pack
where not covered by the real SEA extract. Multiple regional/site files compose
through detail_files; databases remain separate at runtime.
