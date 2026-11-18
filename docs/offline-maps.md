# Offline maritime maps

## Current NAV default

NAV now uses OpenFreeMap Liberty online, with Bangladesh and Southeast Asia as
its primary operational region and no geographic clipping. Production offline
assets and the build/download cache were removed on 2026-11-09. No offline
packages are installed. Malaysia Offshore GIS remains local and independent.

The engine and the developer workflows below remain available for intentional
future use. Set `GDS_MAP_SOURCE=offline` only when using an installed package.
Normal startup does not discover or scan offline assets, and never runs these
download/build tools. See [online validation](online-map-cleanup.md).

## Historical asset strategy: prebuilt Geofabrik Shortbread

The first historical offline region was: **Malaysia / Singapore / Brunei**.
Use prebuilt Shortbread MBTiles for this route. Planetiler, Java and GDAL are
not prerequisites for downloading/importing vector packs. Offline bathymetry
and a separate global overview remain pending.

The official [Geofabrik region page](https://download.geofabrik.de/asia/malaysia-singapore-brunei.html)
currently links to
`https://download.geofabrik.de/asia/malaysia-singapore-brunei-shortbread-1.0.mbtiles`.
The importer discovers the link from the official page instead of constructing
a presumed asset filename. It restricts downloads to official HTTPS Geofabrik
URLs and keeps production files outside the repository.

```powershell
.\.venv\Scripts\python.exe tools/maps/import_shortbread.py download --region malaysia_singapore_brunei

$shortbreadPath = Join-Path $env:LOCALAPPDATA 'GDS VTS\map-build\sources\malaysia-singapore-brunei-shortbread-1.0.mbtiles'
.\.venv\Scripts\python.exe tools/maps/import_shortbread.py inspect --path $shortbreadPath
.\.venv\Scripts\python.exe tools/maps/import_shortbread.py install --region malaysia_singapore_brunei --path $shortbreadPath
```

The historical first asset was294,547,456 bytes,390,078 tiles, native z0–14,
bounds `[99.25611,0.830813,119.6683,7.736849]`. Its source package HTTP
Last-Modified is2026-11-08T03:54:19Z; this is **not** an asserted OSM replication
timestamp. SHA256:
`5acc0e97f0d5b68289c4bc03ceef1aa72ffdae48dc4849a984ccc340588fbc86`.

`schemas.py` detects actual vector-layer signatures independently for every
source and checks any declared manifest schema. The dedicated Shortbread style
uses `ocean`, `water_polygons`, `water_lines`, `boundaries`, `streets`,
`place_labels`, `boundary_labels`, piers and optional source-attribute-based
maritime POIs. It uses `name_en` with a nonempty fallback to `name`, not the
OpenMapTiles `name:en` field. Roads are limited to major classes; buildings,
addresses and dense retail POIs are omitted from the style. No tiles or source
metadata are rewritten. When optional attribution metadata is absent, the
reader uses the supplied author/license in memory; the package supplies explicit
© OpenStreetMap contributors / Geofabrik / ODbL attribution to MapLibre.

All Shortbread layers declare explicit palette roles. Styles, glyphs and icons
stay local. Source bounds constrain local tile requests; startup frames the
installed regional bounds. Outside coverage the map reports the safe fallback
without fetching a remote basemap or claiming additional regional detail.

`REGIONS` in `tools/maps/import_shortbread.py` prepares Thailand, Vietnam,
Myanmar, Philippines, Laos and Bangladesh. Only Malaysia/Singapore/Brunei was
downloaded here. Additional official pages can be supplied with `--page`,
`--region` and `--name`; this supports Indonesian subregions without choosing
a huge national pack. The exact MBTiles link must exist on the supplied official
page. No third-party mirrors are used.

`install --detail <existing-real-shortbread.mbtiles>` can be repeated to compose
additional regional/site sources in the same active package. Their actual bounds
and zooms remain independent and existing priority rules draw finer sources
above regional data. A later global overview can remain a separate source below
regional data; it is not required for this checkpoint. No database merge or
local HTTP server is involved.

Verified cached downloads are reused. To acquire a newer upstream revision while
retaining an old cache, use `download --sources <new-external-cache-directory>`.
Install the newly verified asset, restart NAV, and retain the previous installed
revision for `tools/maps/maps.py rollback`. Source receipt, metadata, full
checksums and activation evidence are in `docs/shortbread-map-validation.md`
and the corresponding `docs/diagnostics/shortbread-*.json` files.

Completely offline map validation, including local Malaysia GIS:

```powershell
.\.venv\Scripts\python.exe tools/maps/validate_runtime.py --seconds 65 --offline-providers --output docs/diagnostics/shortbread-runtime.json
```

`--offline-providers` disables online adapters in the diagnostic process only;
WebEngine HTTP is blocked and local tile/glyph URLs are audited. Production
provider settings stay unchanged. Bathymetry remains separate:
**BATHYMETRY ASSET PENDING**.

## Optional source-build workflow (previous checkpoint)

Use `tools/maps/build_southeast_asia_offline_map.ps1`. Its default action is a
read-only preflight; it never starts a download merely because NAV or pytest is
running. This older source-build path remains blocked on its prerequisites;
it is not needed for the installed Shortbread pack. See `offline-map-asset-checkpoint.md` and
`diagnostics/sea-build-preflight.json` for the actual machine result.

Prerequisites: the project virtual environment,64GiB free build-disk headroom,
Java25+ for the current Planetiler JAR, a locally provisioned/pinned Planetiler
JAR, and GDAL's `gdalinfo`, `gdalwarp`, `gdaldem`, `gdaladdo` on PATH with
GeoTIFF/PNG/MBTiles support. Default Java heap is6GiB; preflight requires at
least8GiB AVAILABLE physical RAM, including OS/native reserve. These are
conservative pipeline gates, not measured guarantees; output size and build
time depend on source revision and chosen zoom. Docker is optional, not used
by this entry point. GDAL runs as separate executables; Python GDAL bindings
are not needed in the application virtual environment.

Authoritative sources and prerequisites:

- [Geofabrik South-East Asia](https://download.geofabrik.de/asia/sea.html):
  `https://download.geofabrik.de/asia/sea-latest.osm.pbf` and its `.md5`.
  No Asia/planet extract is used. The observed listing in this checkpoint was
  about3.4GB; it changes over time. Each real build reads the replication
  timestamp and geographic bounds directly from the OSM PBF header.
- [Planetiler](https://github.com/onthegomap/planetiler): provision a released
  JAR from its official releases into the external tools folder. Keep that
  exact JAR for reproducibility. Its SHA256 and invocation are recorded.
  [Profile options](https://github.com/onthegomap/planetiler/blob/main/config-example.properties)
  document source cache paths, zooms and conservative layer exclusions.
- [GEBCO_2026 Grid](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid):
  obtain a user-defined data GeoTIFF subset through the
  [official subset application](https://download.gebco.net/). Select the2026
  grid and a rectangle covering the actual SEA extract bounds. No global
  GEBCO download is automated. Keep the original source/download metadata.
- [GDAL distribution information](https://gdal.org/en/stable/download.html):
  provision compatible command-line tools outside this application environment.

From the project directory:

```powershell
$buildRoot = Join-Path $env:LOCALAPPDATA 'GDS VTS\map-build'
$jarPath = Join-Path $buildRoot 'tools\planetiler.jar'
$gebcoPath = Join-Path $buildRoot 'sources\GEBCO_2026_SEA.tif'

# Read-only prerequisites and resource check. Nonzero means a blocked preflight.
powershell -NoProfile -File tools/maps/build_southeast_asia_offline_map.ps1 -Action preflight -PlanetilerJar $jarPath -Gebco $gebcoPath

# After provisioning prerequisites and obtaining the real GEBCO subset:
# explicit action permits the SEA OSM and Planetiler profile-dependency downloads.
powershell -NoProfile -File tools/maps/build_southeast_asia_offline_map.ps1 -Action build -PlanetilerJar $jarPath -Gebco $gebcoPath -DownloadOsm -Install

# Alternatively accept an existing SEA PBF, verifying an adjacent .md5 if present.
$osmPath = Join-Path $buildRoot 'sources\sea-latest.osm.pbf'
powershell -NoProfile -File tools/maps/build_southeast_asia_offline_map.ps1 -Action build -PlanetilerJar $jarPath -Gebco $gebcoPath -Osm $osmPath -Install
```

Use `-Java 'C:\path\to\jdk-25\bin\java.exe'` if Java25 is not on PATH.
Pass `-MaxZoom 14` only after reviewing resource impact.
Default SEA vector zoom is4–13; overview is0–5;
bathymetry is0–8, about611m per Web Mercator pixel at the equator, appropriate
for contextual rendering of the15-arc-second source. `-BathymetryMaxZoom 9`
is supported when justified, never extreme artificial high-detail bathymetry.

The build runs the bundled OpenMapTiles profile, excluding building and
housenumber layers. Other POIs remain in tile data; the maritime style displays
only relevant ports/harbours and major place/road classes. Natural Earth,
water polygons and lake-centerline dependencies are cached outside the repo.
A second low-zoom build uses genuine global dependencies with SEA OSM detail;
its world geometry is not extrapolated from regional GIS. Actual layer metadata,
bounds, native zooms, tile counts, SHA256 and low/middle/high sample reads are
inspected after export. Output metadata is completed in new build databases;
inputs and installed databases are never edited.

GEBCO is checked for georeferencing and coverage before vector building, cropped
to the requested geographic bounds, color-relieved with restrained depth blues
and transparent land, reprojected to EPSG:3857 PNG MBTiles, then given downsampled
overviews. Source depths are never invented. Its actual source bounds, requested
crop, source checksum, GEBCO release and resulting tile metadata are recorded.

Storage layout:

```text
%LOCALAPPDATA%/GDS VTS/map-build/
  tools/planetiler.jar
  sources/                  original sources and dependency cache
  runs/<uuid>/              retained logs, scratch files and built assets
    southeast_asia_basemap.mbtiles
    global_overview.mbtiles
    southeast_asia_bathymetry.mbtiles
    package/manifest.json
    package/build-record.json
  imports/<uuid>/           composition from existing real MBTiles
%LOCALAPPDATA%/GDS VTS/maps/revisions/<uuid>/  installed immutable revisions
```

The manifest records per-asset role, format, actual bounds/native zooms, tile
counts, metadata, SHA256, source/build provenance and style revision. Malaysia
GIS remains separate. Directory installation avoids a second multi-GB ZIP;
the existing `.gdsmap` importer remains available for transported archives.

To compose assets built on another machine, provide their genuine provenance
JSON: `revision`, `osm.timestamp`, `gebco.release` (`GEBCO_2026`) plus source URLs,
checksums, tool versions and build record. Do not use an example timestamp as
source provenance. Input MBTiles must already satisfy the documented metadata
contract. The importer does not rewrite them.

```powershell
powershell -NoProfile -File tools/maps/build_southeast_asia_offline_map.ps1 -Action package -Basemap 'D:\map-build\southeast_asia_basemap.mbtiles' -Bathymetry 'D:\map-build\southeast_asia_bathymetry.mbtiles' -Overview 'D:\map-build\global_overview.mbtiles' -Provenance 'D:\map-build\build-record.json' -Install

# The build/import command prints the exact package path.
.\.venv\Scripts\python.exe tools/maps/maps.py validate 'D:\map-build\package'
.\.venv\Scripts\python.exe tools/maps/maps.py install 'D:\map-build\package'
.\.venv\Scripts\python.exe tools/maps/maps.py rollback
```

`-Detail` accepts additional compatible regional/site vector MBTiles, including a
future Bangladesh/Bay of Bengal package. Do not assume the SEA extract covers
Bangladesh. Sources remain independent databases: MapLibre draws the genuine
overview first, regional data above it, then overlapping details by native
maxzoom and smaller coverage. This is bounded-source compositing, not runtime
database merging. Outside real detailed coverage only overview context is
available; above native zoom MapLibre overzooms existing data without new detail.
Global overview geographic/style acceptance still requires the first real build.

Update by retaining the old cache/revision, obtaining a newer SEA source in a
new path, and repeating build → validate → install → atomic activate. The
timestamp changes from the real header, not the PC date. Existing verified
downloads are reused; unverified or damaged caches/partials are retained and
reported rather than silently overwritten. Previous installed revisions remain
available through rollback. No automatic cleanup runs. After acceptance and
archiving, manually remove only explicitly selected obsolete scratch directories
under `map-build/runs/<uuid>/`; never remove `maps/revisions` as scratch cleanup.

Offline visual acceptance after a real installation:

```powershell
.\.venv\Scripts\python.exe tools/maps/validate_runtime.py --seconds 65 --output docs/diagnostics/real-sea-offline-runtime.json
```

This blocks WebEngine HTTP and cycles diagnostic-only fixed UTC states. Require
`asset_installed=true`, visible real coast/labels/depth/GIS, zero remote style/
tile/glyph/sprite requests, stable sources/layers/camera on palette changes,
correct controls, outside-SEA overview and sensible overzoom. Operational
providers have independent network behavior; disable them through their existing
configuration when conducting a fully disconnected test. Do not mistake the
no-asset background for a successful production map acceptance.

Attribution: © OpenStreetMap contributors/ODbL; OpenMapTiles/CC BY4.0;
Planetiler/Apache-2.0; Natural Earth public-domain context; GEBCO Bathymetric
Compilation Group2026 and DOI10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa.
These are contextual maps, not official ENC, ECDIS, SOLAS or certified charts.

NAV now starts from a local MapLibre style. Its map background has no mandatory
network dependency. Malaysia GIS, project GIS, own vessel, tracks, AIS and Squall
keep their existing services and sources. This is a situational-awareness map,
not an official ENC, ECDIS product or claim of SOLAS chart compliance.

**Current delivery: Malaysia / Singapore / Brunei Shortbread vector pack installed.**
No global overview, complete SEA pack, GEBCO MBTiles or satellite package is
installed. Outside installed coverage the plain background is a safe fallback;
it does not claim mapped land or water.
Tests create tiny, temporary, explicitly labelled test-only tile databases.
They are never installed as production map data.

## Package layout and coverage

One folder contains `manifest.json` and extracted MBTiles files. Schema version
1 uses these fields:

```json
{
  "schema_version": 1,
  "package_id": "sea-maritime",
  "name": "Southeast Asia Maritime",
  "revision": "2026-11",
  "created_at": "2026-11-08T00:00:00Z",
  "region": "Southeast Asia",
  "bounds": [92, -15, 142, 30],
  "minzoom": 4,
  "maxzoom": 13,
  "overview_file": "overview.mbtiles",
  "basemap_file": "sea.mbtiles",
  "bathymetry_file": "gebco.mbtiles",
  "detail_files": ["site.mbtiles"],
  "optional_satellite_files": [],
  "asset_files": [],
  "style_revision": "gds-maritime-1",
  "attribution": "Replace with the actual data and licence attribution",
  "checksums": {"overview.mbtiles": "SHA256", "sea.mbtiles": "SHA256", "gebco.mbtiles": "SHA256", "site.mbtiles": "SHA256"}
}
```

The example bounds describe a build decision, not a rendering constraint.
Use the actual basemap metadata bounds/zoom in each real manifest. Every source
uses its own database metadata for coverage. Rebuild this manifest with the CLI
to calculate real checksums. `overview_file` and `bathymetry_file` are optional
until available; their absence does not invent those datasets.

Suggested independent components:

| Role | Build coverage | Zoom strategy | Schema |
|---|---|---|---|
| Global overview | World, Mercator latitude limits | z0–5 | Natural Earth derived, mapped into the documented vector subset |
| Regional basemap | Agreed SEA operational bounds | z4–12/13 | OpenMapTiles vector |
| Detail | Selected ports/country/site | z12–15/16 | Same vector subset |
| Bathymetry | Regional operational waters | Independently chosen | GEBCO-derived PNG/JPEG/WEBP raster |
| Satellite | Only licensed actual imagery coverage | Independently chosen | PNG/JPEG/WEBP raster |

The local style consumes `landcover`, `water`, `waterway`, `boundary`,
`transportation`, `place`, `poi`. Vector packages require `water` and
`landcover` metadata; optional layers are omitted when absent. `class` filters
retain major roads, cities/towns/countries and ports/harbours, with no dense POI
presentation. Labels use `name:en`, falling back to `name`. Each metadata
`json.vector_layers` entry must identify its source layer. Other schemas need
an explicit exporter mapping, not guessed runtime layer names. No Malaysia GIS
features are baked into these tile databases.

## Preparing real assets

Use an established offline build system such as
[Planetiler](https://github.com/onthegomap/planetiler) with its
[OpenMapTiles profile](https://github.com/openmaptiles/planetiler-openmaptiles),
or the [OpenMapTiles build project](https://github.com/openmaptiles/openmaptiles).
Pin tool/profile/data revisions in the build record. Obtain an appropriately
licensed OSM regional extract, clip to the operational extent, set build zooms
and generate indexed MBTiles. Budget disk/RAM before running an external build.
Use Natural Earth for the independently generated global overview and the
actual GEBCO gridded dataset for a separately colour-relieved bathymetry raster.
Export raster MBTiles in TMS storage order with indexed coordinates and metadata.
No map download or tile build runs on app startup or during normal tests.

Required metadata: `name`, `description`, `version`, `type` (`baselayer` or
`overlay`), `format`, `bounds`, `center`, `minzoom`, `maxzoom`, `attribution`.
`scheme`, if present, must be `tms`. Supported formats: `pbf`, `mvt`, `png`,
`jpg`, `jpeg`, `webp`. This deliberately stricter delivery contract extends the
[MBTiles 1.3 minimum](https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md).
At least one readable tile and an indexed coordinate lookup are required.

Record actual OSM/ODbL, OpenMapTiles, Natural Earth, GEBCO and imagery licence
terms/attributions in the package/build record. Attributions are escaped and
passed to MapLibre's attribution control. Never call OSM or GEBCO an official ENC.

## CLI workflow (project virtual environment)

```powershell
.\.venv\Scripts\python.exe tools/maps/maps.py inspect C:\map-build\sea.mbtiles
.\.venv\Scripts\python.exe tools/maps/maps.py validate C:\map-build\sea.mbtiles
.\.venv\Scripts\python.exe tools/maps/maps.py build-manifest C:\map-build --id sea-maritime --name "SEA Maritime" --revision 2026-11 --region SEA --basemap sea.mbtiles --overview overview.mbtiles --bathymetry gebco.mbtiles --attribution "Actual source and licence notices"
.\.venv\Scripts\python.exe tools/maps/maps.py validate C:\map-build
.\.venv\Scripts\python.exe tools/maps/maps.py install C:\map-build
.\.venv\Scripts\python.exe tools/maps/maps.py rollback
```

Repeat `--detail`, `--satellite` or `--asset` for extra files. To transport a
`.gdsmap`, ZIP the folder's contents with `manifest.json` at the archive root,
rename the ZIP extension, then use the same `install` command. Runtime never
reads tile SQLite files from inside ZIP. Archives reject traversal, links,
duplicates, Windows device/alias names and excessive entry/size counts.

Default installed storage is `%LOCALAPPDATA%\GDS VTS\maps`. Install validates
the source, copies/extracts into same-filesystem staging, validates all SHA256
checksums again, renames to an immutable revision directory, and atomically
replaces `active.json`. The previous revision remains available to rollback.
A failed validation leaves the active pointer intact. An interrupted install
may leave an unreferenced revision, which is harmless; nothing automatically
deletes retained maps. Restart NAV to load the activated revision, preserving
the current running session's sources and camera until then.

Development/bundled resolution: active installed package, folders in
`GDS_MAP_PACKAGE_PATH` (Windows `;` separated), then `data/maps/default`.
`GDS_MAP_DEFAULT_PACKAGE` selects a discovered package ID; otherwise the last
package ID is stored under `nav/map_package` in existing GDS/VTS QSettings.
`GDS_MAP_TILE_CACHE_SIZE` bounds per-reader LRU tile count (default128, max4096),
also capped at32MiB per reader. SQLite page cache is2MiB; tile payload and
decompression limit16MiB. Worker reads use two threads with at most64 pending
requests, synchronized connections, cancellation-safe replies and shutdown.

`GDS_MAP_ALLOW_ONLINE_FALLBACK=true` explicitly permits the existing online
development basemap only when no offline package is installed. It is labelled
ONLINE DEVELOPMENT FALLBACK. Default false makes no map style/tile HTTP calls.
Online operational providers retain their independent existing configuration.
The existing Bathymetry checkbox also controls the local bathymetry raster;
Satellite shows installed real imagery only, Marine hides it.

## Local resources and palette

MapLibre JS/CSS, operational SDF icons, style generation and font glyphs are
local. Bundled **KlokanTech Noto Sans Regular** includes Latin, Latin Extended,
Vietnamese, Thai, Myanmar, Khmer and punctuation ranges, with source README
and SIL OFL in its glyph directory. Source:
[KlokanTech glyph repository](https://github.com/klokantech/klokantech-gl-fonts),
[Noto licence](https://github.com/openmaptiles/fonts/blob/master/noto-sans/LICENSE).
Preserve the credited font name. Additional required scripts/ranges may be
delivered as manifest `asset_files` under `glyphs/{fontstack}/{range}.pbf`;
that package then supplies the complete glyph set via `gds://package/`.
Missing unsupported glyphs fail locally without fetching a font service.
Operational icons are generated in code; this style needs no external sprite.

AUTO (default), DAY and NIGHT are persisted at `nav/palette`. Only NAV's map
palette changes. AUTO uses the deterministic offline
[NOAA fractional-year solar equations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)
for geometric elevation: DAY >=0°, TWILIGHT 0 to−6°, NIGHT <−6°, with0.25°
exit hysteresis. This is an approximate display palette, not an astronomical
navigation instrument. It handles leap years and normalizes aware dates to UTC.

Fresh LIVE canonical telemetry with valid Date+UTC has priority: ISO date,
DD/MM/YYYY or NMEA DDMMYY, and HH:MM:SS or HHMMSS with optional fractional
seconds/Z. Reception must be less than3s old and GNSS clock within24h of system
UTC. Otherwise SYSTEM_UTC is explicit. Follow ON with a valid LIVE own position
uses OWN_VESSEL; Follow OFF or NO SOURCE uses settled MAP_CENTER. An absent or
invalid center uses the explicit deterministic (0°,0°) FALLBACK until the map
reports its center. No vessel is fabricated. Camera center reports settle for
700ms; movement of at least0.01 degrees from the last calculated reference and UTC minute changes recompute, with one
shared60s timer. No transient solar state is persisted.
Follow changes update the palette service immediately. Hysteresis resets when
reference type changes, a reference moves at least1 degree, or the user changes
mode. Each diagnostic payload includes an explicit UTC ISO timestamp.

`offline.js` owns a registry for basemap, bathymetry, satellite, operational,
GIS and fixed layers. Palette updates only owned paint values, including
raster brightness/saturation; they preserve visibility, severity expressions,
selection colours, camera, source identities and operational GeoJSON. Night
satellite is the same truthful imagery dimmed. Palette code never calls
`setStyle`, `addSource`, `setData`, camera fit or camera movement.
Registry roles are WATER, LAND, COAST, ROAD, BOUNDARY, LABEL, BATHYMETRY,
SATELLITE, REFERENCE_GIS and OPERATIONAL. Registry state is scoped to each map;
unowned and selection layers retain their styles. Short250ms paint transitions
soften palette changes. Repeated updates with the same effective palette do not
repaint existing layers. DAY restores each raster's original brightness and
saturation; night treatment preserves raster opacity and source data.

## Validation

Use `.\.venv\Scripts\python.exe -m pytest -q --tb=short`. Tests include the real
Qt scheme with HTTP blocked, compressed MVT and raster responses, local glyphs,
package rejection/rollback, solar UTC/reference behavior and real JS regression.

For visible Malaysia GIS and deterministic AUTO palette checks:

```powershell
.\.venv\Scripts\python.exe tools/maps/validate_runtime.py --seconds 90
```

This diagnostic alone fits Malaysia and injects fixed solar UTC instants.
Production startup does neither. It blocks WebEngine HTTP and writes actual
errors, layer/source counts, camera and rendered GIS counts to
`docs/diagnostics/offline-map-runtime.json`. Real regional background, global
context, bathymetry and satellite visual acceptance remains pending actual
licensed map assets. See `offline-maps-validation.md` for the delivery checks.
