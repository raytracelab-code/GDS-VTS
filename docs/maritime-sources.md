# NAV Phase 4 maritime sources

The general-purpose development basemap is not an ENC or certified ECDIS display.
Project `.gdsspatial` packages and Squall events remain separate from maritime-world data.
No external targets are generated at production startup. A restored TEST project
package remains explicitly named TEST and is not chart content.

## Ownership and threading

MainWindow owns one MaritimeRuntime and its one MaritimeObjectService. AISService,
MaritimeChartService and the offshore/AtoN/infrastructure/warning/metocean facades
all ingest into that canonical store. Own vessel continues through TelemetryStateService.
The runtime's bounded worker pool performs I/O and normalization. A queued Qt signal
applies results on the GUI thread. One 250 ms timer batches changes and ages targets;
there are no per-target timers or widgets. Shared GeoJSON collections feed the map.
Provider responses for superseded areas are discarded. Provider refreshes never move
the map camera. Only explicit operator camera actions and existing Follow do that.

## Configuration

Set environment variables before launching `python -u main.py`:

| Variable | Meaning / default |
|---|---|
| `GDS_AIS_ENDPOINT` | HTTP(S) normalized AIS JSON endpoint; empty = NOT CONFIGURED |
| `GDS_CHART_SOURCE` | Local GeoJSON file or HTTP(S) endpoint |
| `GDS_OFFSHORE_SOURCE` | Local GeoJSON file or HTTP(S) endpoint |
| `GDS_WARNINGS_SOURCE` | Local GeoJSON file or HTTP(S) endpoint |
| `GDS_METOCEAN_SOURCE` | Local GeoJSON file or HTTP(S) endpoint |
| `GDS_<AIS/CHART/OFFSHORE/WARNINGS/METOCEAN>_ENDPOINT` | Alternative source endpoint name |
| `GDS_<source>_API_KEY` | Optional Authorization Bearer token, never sent to JS |
| `GDS_<source>_POLL_SECONDS` | AIS: 10 s; others: 300 s |
| `GDS_AIS_STALE_SECONDS` | 120 s |
| `GDS_AIS_EXPIRE_SECONDS` | 600 s, must exceed stale threshold |
| `GDS_OWN_MMSI` | Suppress the matching AIS target only when own identity is known |
| `GDS_MARITIME_RADIUS_NM` | 50 NM; bounded 1–250 NM |
| `GDS_MARITIME_MOVE_NM` | 10 NM, capped at radius |
| `GDS_MARITIME_DEBOUNCE_SECONDS` | 3 s |
| `GDS_MARITIME_CACHE_DIR` | Local application-data maritime-cache directory |

`<source>` is uppercase. Never put secrets in source code or endpoint URLs.
Public Overpass and GEBCO are selected by default; no commercial API key is bundled.
Credentials are omitted from config representations and source errors expose exception
classes, not response bodies, URLs or tokens. Configure a provider-side gateway when
a vendor uses another authentication scheme or message format.

## AIS JSON contract

HTTP requests receive `latitude`, `longitude`, `radius_nm` query parameters.
The response is a JSON array or `{"vessels": [...]}`. Example schema:

```json
{"mmsi":"123456789","latitude":22.1,"longitude":91.7,
 "position_timestamp":"2026-11-01T12:00:00Z",
 "name":"Example","ship_type":"cargo","heading":45,"cog":48,"sog":8}
```

Only MMSI and valid position are required. Optional fields: IMO, name, call_sign,
ship_type, navigation_status, draught, destination, eta, sog, cog, heading.
Timestamp aliases: observed_at and last_update. Missing values remain unavailable.
AIS sentinel heading 511, COG 360 and SOG 102.3 mean unavailable. Timestamp must
include timezone; future offsets greater than five minutes are rejected.

MMSI is the stable cross-source identity. New observations update the same record;
known metadata survives partial dynamic updates. Older observations are ignored,
identical observations do not produce duplicate objects. Source timestamp determines
stale/expiry; receive time is the fallback only when no source timestamp exists,
and displayed source age remains unknown. Stale targets stay muted; expired targets
and their selection disappear. AIS is not persisted across restarts.

`SourceAdapter` supplies `fetch/start/update_area/stop` boundaries. Streaming
WebSocket/TCP/UDP or vendor decoders can deliver batches of canonical MaritimeObject
records through queued results without changing the map/store architecture. This
release implements normalized JSON polling, not those protocol decoders or raw AIS.

## Static/current GeoJSON contract

Responses must be FeatureCollections. Each Feature needs stable `id` (or
`properties.source_id`), `properties.category`, `properties.object_type`, valid geometry.
An optional top-level `dataset_at` supplies the dataset timestamp. Per-feature
`observed_at`, `dataset_at`, `expires_at` accept timezone-aware ISO timestamps.
Optional `canonical_id` provides deliberate cross-source identity; otherwise source
plus provider ID are distinct. No name/proximity guessing merges unrelated assets.

Canonical category values:
`vessels`, `offshore`, `aton`, `ports`, `anchorages`, `routes`, `restricted`, `subsea`,
`hazards`, `bathymetry`, `warnings`, `metocean`.

Use normalized object_type values such as oil_platform, gas_platform, drilling_rig,
production_platform, fpso, fso, spm, sbm, loading_terminal, wellhead, buoy, light_buoy,
beacon, lighthouse, daymark, cardinal_mark, lateral_mark, safe_water_mark,
isolated_danger_mark, special_mark, radar_beacon, anchorage, fairway,
navigation_channel, traffic_separation_scheme, traffic_lane, precautionary_area,
pilot_boarding_area, prohibited_area, safety_zone, port_limits, berth,
submarine_pipeline, submarine_cable, wreck, obstruction, rock, reef, shoal,
dredged_area, dumping_ground, depth_area, depth_contour, sounding, navigation_warning,
wind, gust, wave_height, wave_direction, swell, current, tide, visibility, rain, pressure.
Spaces/hyphens normalize to underscores; TSS, cable, pipeline, oil rig and RACON
aliases normalize at ingestion. Provider-specific decoding belongs in adapters.

Any category can carry supported Point, LineString, Polygon and Multi* geometry.
Polygon rings must close. NaN/Infinity, out-of-range positions, unbounded fields,
oversize responses and malformed records reject the batch atomically.
Descriptions render as plain text. Operator, characteristic, confidence, quality,
severity and timestamps are displayed only when supplied; no values are fabricated.

Chart/AtoN/installation/infrastructure features use static GeoJSON adapters. This
release does not decode raw S-57/S-101, vector tiles or PMTiles. A real converter
can feed the canonical contract; raw ENC compliance is not claimed. Bathymetry
and metocean render supplied geometries only, never inferred depths/weather.

## Area, cache and failure behavior

Own-vessel movement beyond the threshold requests a new operating area. Significant
settled viewport movement can load a remote area; minor vessel motion does not
override that view. Wide world views are ignored, bounded radius requests are used,
and local/static provider results are filtered conservatively by area intersection.
No source refresh changes Follow, bearing, pitch, center or zoom.

Chart/offshore cache entries include source, area, cache timestamp and feature
dataset timestamps. They are endpoint/area scoped, atomically replaced and capped
at 100 entries. On failure the matching cache is used with DEGRADED source health
and CACHED object freshness. In-memory static objects are retained during outages.
AIS/warnings/metocean dynamic configurations are not persisted as live state.
Source health distinguishes NOT_CONFIGURED, CONNECTING, LIVE, DEGRADED, STALE,
ERROR and recovers on successful fetch. Successful contact age differs from
individual target source age. No connection does not disable Phases 1–3.

## Development validation

```powershell
python tools/dev_maritime_feed.py --auto --telemetry --lifecycle-fast --quit-after 90
```

This explicit tool injects five TEST vessels, four TEST offshore installations,
buoy/beacon, anchorage, TSS, pipeline, cable, wreck, restricted area, warning,
contour, terminal and metocean point. Optional own telemetry enters the existing
canonical ingest path; it is never inserted as an AIS target. Lifecycle time is
advanced only in this tool's store. No synthetic provider is enabled by main.py.

Live external AIS, authoritative installations and real chart datasets require
user/provider data and credentials. **REAL PROVIDER VALIDATION PENDING DATA/CREDENTIALS.**

## Phase 4R real providers

The existing store, operating-area controller, selection, bridge and operational
layers are reused. Provider I/O runs on the existing worker pool; AISStream uses
one long-lived WebSocket thread and drains into the same GUI-thread batch path.
Provider arrivals never change camera position, zoom, bearing, pitch or Follow.
No fallback provider ever generates synthetic targets.

Install optional SDKs in the project virtual environment when enabling their feeds:

```powershell
python -m pip install -r app/nav/maritime/requirements-providers.txt
```

The generic Phase 4 JSON/GeoJSON contracts above remain available. An explicitly
supplied legacy-only configuration still supports offline tests/deployments. Normal
production configuration registers the real providers below. Overpass is the default
community feature provider and GEBCO is enabled by default. AISStream starts when a
key exists unless explicitly disabled; other feeds follow their flags/credentials.
No request occurs until a valid own position or an operator-driven viewport establishes
an area. A restored TEST project package is never used as a provider operating position.

| Provider | Categories, coverage and semantics | Authentication / activation | Cache and health |
|---|---|---|---|
| AISStream | Global upstream AIS coverage; live Class A/B position, static/voyage metadata, AIS AtoN reports | `AISSTREAM_ENABLED`, `AISSTREAM_API_KEY`; Python-only WSS subscription | Never persisted. CONNECTING/LIVE/STALE/DEGRADED/ERROR. Complete subscription replacement on meaningful area changes; at least one second between replacements. Reconnect backoff capped at 30 seconds plus jitter; clean cancellation on shutdown. |
| OSM/Overpass | Real community seamarks, offshore installations, marine routes, areas, subsea infrastructure, hazards and ports where mapped | `GDS_OVERPASS_ENDPOINT`; default `https://overpass-api.de/api/interpreter`; no credential | Existing area cache, 24-hour refresh, one consolidated query, minimum 60 seconds between requests, bounded retries. READY after success, CACHED/DEGRADED on outage. Community data is not official chart data. |
| Open Waters Seamap | Optional global reference style with seamarks, bathymetry and chart symbology; no duplicate canonical targets | `GDS_OPENWATERS_ENABLED`, `GDS_OPENWATERS_STYLE_URL`; default `https://tiles.openwaters.io/seamap/style.json` | Validate the published style before applying it. Uses MapLibre tile caching and provider attribution. DISABLED unless enabled; HTTP failures remain provider errors. |
| OpenSeaMap | Optional legacy seamark reference raster | `GDS_OPENSEAMAP_ENABLED`; HTTPS tiles only | DISABLED by default. Never enables mixed content or weakens WebEngine security. |
| GEBCO | Global bathymetric context, not official ENC/ECDIS/SOLAS chart data | `GDS_GEBCO_ENABLED`, `GDS_GEBCO_WMS_ENDPOINT`; default `https://wms.gebco.net/mapserv?` | Discover current `GEBCO_LATEST` from GetCapabilities, validate Web Mercator, construct WMS 1.1.1 GetMap tiles. Existing Bathymetry control; raster below operational layers. Capabilities cached per adapter, browser caches tiles. READY/DEGRADED/ERROR. |
| Copernicus Marine | Configured global/regional model products: wave, current, SST, sea level; coverage follows selected dataset | `COPERNICUSMARINE_USERNAME`, `COPERNICUSMARINE_PASSWORD`, and the corresponding `GDS_CMEMS_*_DATASET` | Official Toolbox `open_dataset`, bounded bbox, two-hour time window, upper metre, at most 16×16 actual grid-cell samples per bbox. No global downloads or invented dataset IDs. NOT_CONFIGURED per missing product. One-hour refresh; model timestamps/units retained. Dynamic model samples are not reused as live restart state. |
| Global Fishing Watch | Global satellite-derived fixed infrastructure, classified oil/wind/unknown; observation lag applies | `GDS_GFW_ENABLED` **and** `GDS_GFW_LICENSE_ACK` **and** `GDS_GFW_API_TOKEN` | DISABLED_LICENSE unless both gates are true. No requests through a disabled gate. Dataset `public-fixed-infrastructure-filtered:latest`; bounded binary MVT context tiles decoded with optional `mapbox-vector-tile`, using provider WGS84 lat/lon attributes; existing static cache. READY, never labelled live AIS. |
| BOEM/BSEE | Official U.S. offshore platforms, wells and pipelines; Gulf, Atlantic, Pacific and Alaska service families | `GDS_BOEM_ENABLED`, `GDS_BOEM_BASE_URL`; default `https://gis.boem.gov/server/rest/services/BOEM_BSEE/` | OUT_OF_COVERAGE outside applicable U.S. regions. Discover advertised layers; ArcGIS envelope/intersects GeoJSON queries with bounded pagination. Existing static cache; READY/DEGRADED. |
| EMODnet Human Activities | European regional installations, wells, cables, pipelines, wrecks, ports and supported human-activity layers | `GDS_EMODNET_ENABLED`, `GDS_EMODNET_WFS_ENDPOINT`; default `https://ows.emodnet-humanactivities.eu/wfs?` | Discover feature types through WFS GetCapabilities. Independent bbox queries avoid this GeoServer's multi-type join limitation; omit zero-offset pagination for keyless views. Existing static cache. OUT_OF_COVERAGE outside Europe. OSM-derived marina layers are omitted to avoid duplicating community data as official. |
| NAVAREA VIII / HydroBharat | Official warning boundary; no documented stable structured feed found during inspection | `GDS_NAVAREA8_ENABLED`, `GDS_NAVAREA8_SOURCE_URL`; default official warning page | NO_STABLE_MACHINE_API when enabled. No HTML/PDF scraper, inferred coordinates or fake warnings. Existing normalized warning import remains usable for legitimate structured feeds/local imports; raw S-124 decoding is not claimed. |

Additional provider variables, with no secret values in this repository:

| Variables | Safe default |
|---|---|
| `GDS_CMEMS_WAVE_DATASET`, `GDS_CMEMS_CURRENT_DATASET`, `GDS_CMEMS_SST_DATASET`, `GDS_CMEMS_SEALEVEL_DATASET` | Unset; no guessed IDs |
| `GDS_GFW_ENABLED`, `GDS_GFW_LICENSE_ACK` | false |
| `AISSTREAM_ENABLED` | Auto with a key; explicit false disables; missing key = NOT_CONFIGURED |
| `GDS_GEBCO_ENABLED` | true unless explicitly disabled |
| `GDS_OVERPASS_FALLBACK_ENDPOINTS` | `https://overpass.private.coffee/api/interpreter`; comma-separated, at most two configured fallbacks |
| `GDS_OPENWATERS_ENABLED`, `GDS_OPENSEAMAP_ENABLED`, `GDS_BOEM_ENABLED`, `GDS_EMODNET_ENABLED` | false |
| `GDS_NAVAREA8_ENABLED` | true; boundary reports no stable machine API |
| `GDS_MARITIME_RADIUS_NM`, `GDS_OWN_MMSI` | Existing 50 NM radius / optional known own MMSI |

`.env.example` contains names and safe defaults only; it is not loaded automatically.
Secrets are read from the process environment and never passed to MapLibre, cached
as feature metadata, printed by diagnostics or included in error messages.

### Provenance and rendering

Objects retain provider identity, provider feature ID, source tier, available source
timestamps, dataset version and attribution. Government/service/satellite/community
priority applies only to explicit shared canonical identities; unrelated nearby
features are never merged by guessed names/proximity. Offshore attribution is never
inferred from an onshore petroleum well or underground pipeline alone.

AIS static messages enrich an existing target without refreshing its position age.
Position reports preserve known static metadata. AIS unavailable heading falls back
to COG; missing both produces a neutral target. Own MMSI suppression remains in the
existing canonical store. AtoN source flags are retained only when supplied.

Copernicus output uses actual returned CF variables and explicit units. Height,
direction and current units are converted only when recognized. Unknown units fail
normalization rather than fabricate measurements. Waves/SST/sea-level render sampled
points with actual value/unit labels; current components additionally derive direction
vectors through the existing shared metocean line layer. No interpolated raster or
official tide/chart datum is claimed.

Open Waters retains its published attribution. GEBCO and OpenSeaMap sources carry
their attribution into MapLibre. A reference-tile failure degrades that provider and
does not delete operational objects or change the map camera.

### Usage and licence caveats

The [AISStream documentation](https://www.aisstream.io/documentation/) defines the
current message schemas, subscription limits and lack of an SLA. Coverage depends on
upstream reception; an empty area is not an adapter failure.

The [OSM Overpass instance policy](https://wiki.openstreetmap.org/wiki/Overpass_API)
describes shared-server limits and recommends self-hosted/paid infrastructure for
commercial use. Production fleet-scale deployments must configure a suitable endpoint;
the default public instance may time out. Cache and meaningful area changes reduce load.

[Open Waters](https://openwaters.io/charts/seamap/) publishes reference tiles/styles
with attribution and source-specific licence requirements; it is not an official ENC.
GEBCO is bathymetric context, not a navigation chart. Copernicus data remains model
information with dataset-specific credits and conditions. GFW's explicit licence
acknowledgement does not grant a licence; the operator must have appropriate rights.
BOEM and EMODnet retain their source/dataset usage terms and regional coverage.

### Real-network validation in this implementation run

Run diagnostics separately from the active map:

```powershell
python tools/check_maritime_providers.py overpass gebco boem emodnet
```

These diagnostic bboxes never inject U.S./European objects into a Bangladesh map.

| Provider | Validation state and exact observations |
|---|---|
| AISStream | IMPLEMENTED — NOT CONFIGURED; no local key; no live AIS/MMSI count claimed. |
| Overpass | IMPLEMENTED; default endpoint returned HTTP 502/timeouts for the bounded Chattogram diagnostic. An OSM-listed alternate also timed out. Real categories remain UNVERIFIED, not zero. No automatic endpoint fallback was added. |
| GEBCO | REAL NETWORK + VISUAL VALIDATED: actual GetCapabilities advertised `GEBCO_LATEST`; GetMap returned a valid 4,774-byte PNG. Normal NAV rendered the real layer and attribution; Bathymetry OFF/ON removed/restored it with unchanged camera and no fatal CORS/WebEngine/MapLibre issue. |
| BOEM/BSEE | REAL NETWORK VALIDATED for a 2 NM diagnostic at 28.5°N, 90°W: 19 normalized objects — 2 wells/offshore objects and 17 subsea pipelines. A larger first diagnostic timed out; no platform presence claimed. |
| EMODnet | REAL NETWORK VALIDATED for a 5 NM diagnostic at 55°N, 2°E: 18 objects — 1 well, 2 offshore wind farms, 5 pipelines, 7 cables and 3 wrecks. Live-discovered WFS compatibility defects were fixed and tested. |
| Open Waters | Optional; public style request returned HTTP 403 from this environment. Not visually validated. |
| OpenSeaMap | DISABLED; no security downgrade attempted. |
| Copernicus | IMPLEMENTED — NOT CONFIGURED; no credentials/dataset IDs available. Normalization/subset contracts tested offline. |
| GFW | IMPLEMENTED — LICENSE DISABLED; no API requests made. |
| NAVAREA VIII | NO_STABLE_MACHINE_API found in official published sources; no scraper added. |

### Continuation validation, 2 November 2026

The preceding observations are inherited session history. Current observations and
the continuation audit are recorded in [nav-phase-4r-validation.md](nav-phase-4r-validation.md).

### Current deployment defaults and acceptance

The latest task supersedes earlier disabled-by-default GEBCO/AIS policies and
full-style Open Waters behavior in this document's historical tables. See
[maritime-real-data-completion.md](maritime-real-data-completion.md) for current
configuration, fallback/backoff policy and measured acceptance results.

Overpass uses Python-worker form POST with `[out:json][timeout:25]` and full
node/way/relation geometry. The erroneous 16 MB server-RAM setting was removed;
the client response cap remains 16 MB. On transient failure, at most one configured
fallback is tried per fetch; failed endpoints cool down for at least 120 seconds.
A working endpoint is preferred thereafter. HTTP 429 never triggers host hopping,
and Retry-After applies across viewport changes. Cache reads remain available
during network backoff. Existing TTL, bounded cache, viewport debounce and minimum
60-second network interval apply. Recent fully covering cache entries can satisfy
contained views and floating-point camera jitter; partial coverage is never labelled fresh.

Open Waters now requires an explicit configured style URL and imports nautical
sources/layers as overlays. It never replaces the primary basemap. Optional source
failure cannot block Overpass, GEBCO or AIS. Generated point icons also have an
independent circle core, so sprite failure cannot silently hide maritime points.

## MALAYSIA OFFSHORE GIS
Provider: `MalaysiaOffshoreGISProvider`, source key `malaysia_gis`, tier `LOCAL_GIS`. This is static/reference customer GIS. **LICENCE / AUTHORITY: NOT YET RECORDED**. Attribute names and coverage are not evidence of official status. No source timestamps or version were supplied.
Default directory: `data/maritime/malaysia`, resolved relative to the application, including its extracted subdirectories. `GDS_MALAYSIA_GIS_PATH` optionally selects an external directory. It may contain its own `manifest.json`; otherwise it uses the bundled contract with the same relative filenames. No ZIP or Downloads path is required. macOS `__MACOSX`, `._*` and `.DS_Store` files are ignored.
`data/maritime/malaysia/manifest.json` defines all 18 layers: mapping, source tier, geometry types, display names, defaults, minimum/label zoom, style and inspector headings. Python passes this contract to JavaScript; JavaScript has no parallel Malaysia category/filename mapping. Visibility persists in existing `QSettings` keys.
### Inventory
All 14 regional files explicitly declare `urn:ogc:def:crs:OGC:1.3:CRS84`. `platforms_496.geojson` also explicitly declares CRS84. The other three supplemental files omit CRS, so RFC 7946 longitude/latitude WGS84 is assumed and all coordinates are range checked. Unknown/projected CRS declarations are rejected with a source-health error. There is no silent reprojection or coordinate swap.
Combined retained bounds, `[west, south, east, north]`: `[98.022889, 1.263626, 120.264806, 9.030622]`.
10,326 source records: **10,268 retained + 45 duplicate labels suppressed + 13 rejected**. Of the rejected records, 2 have null geometry; the other 11 have self intersections or degenerate geometry. Raw source files are untouched.
| File | Source records | Retained | Rejected (null) | Duplicate labels | Geometry | Category / subtype | Default |
|---|---:|---:|---:|---:|---|---|---|
| `malaysia_abandoned_psc_wgs84.geojson` | 9 | 9 | 0 (0) | 0 | Polygon | development_areas / abandoned | OFF |
| `malaysia_awarded_block_wgs84.geojson` | 116 | 111 | 5 (0) | 0 | MultiPolygon, Polygon | petroleum_blocks / psc_awarded_block | OFF |
| `malaysia_basin_wgs84.geojson` | 26 | 26 | 0 (0) | 0 | Polygon | basins / petroleum_basin | OFF |
| `malaysia_ceased_psc_wgs84.geojson` | 6 | 6 | 0 (0) | 0 | Polygon | development_areas / ceased | OFF |
| `malaysia_development_psc_wgs84.geojson` | 2 | 2 | 0 (0) | 0 | Polygon | development_areas / development | OFF |
| `malaysia_fields_all_wgs84.geojson` | 491 | 491 | 0 (0) | 0 | Polygon, MultiPolygon | oil_gas_fields / oil_gas_field | ON |
| `malaysia_ftg_wgs84.geojson` | 31 | 30 | 1 (0) | 0 | Polygon, MultiPolygon | geophysical_surveys / geophysical_survey_area | OFF |
| `malaysia_open_block_wgs84.geojson` | 28 | 26 | 2 (0) | 0 | Polygon, MultiPolygon | petroleum_blocks / psc_open_block | OFF |
| `malaysia_pipeline_wgs84.geojson` | 745 | 742 | 3 (0) | 0 | LineString, MultiLineString | subsea / pipeline | ON |
| `malaysia_platform_wgs84.geojson` | 477 | 477 | 0 (0) | 0 | Point | offshore / other_offshore_installation | ON |
| `malaysia_pre_development_psc_wgs84.geojson` | 235 | 235 | 0 (0) | 0 | Polygon, MultiPolygon | development_areas / pre_development | OFF |
| `malaysia_production_within_psc_area_wgs84.geojson` | 132 | 132 | 0 (0) | 0 | Polygon, MultiPolygon | development_areas / production | ON |
| `malaysia_seismic_3d_wgs84.geojson` | 829 | 829 | 0 (0) | 0 | Polygon, MultiPolygon | seismic_surveys / seismic_survey_area | OFF |
| `malaysia_well_location_wgs84.geojson` | 6969 | 6967 | 2 (2) | 0 | Point | offshore_wells / offshore_well | OFF |
| `platforms_134.geojson` | 53 | 44 | 0 (0) | 9 | MultiLineString, LineString, Point, Polygon | offshore / offshore_facility_detail | OFF |
| `platforms_3.geojson` | 87 | 87 | 0 (0) | 0 | MultiLineString, Polygon, Point | offshore / offshore_facility_detail | OFF |
| `platforms_34.geojson` | 73 | 50 | 0 (0) | 23 | MultiLineString, Point | offshore / offshore_facility_detail | OFF |
| `platforms_496.geojson` | 17 | 4 | 0 (0) | 13 | Point | offshore / offshore_facility_detail | OFF |

The machine-readable [audit](diagnostics/malaysia-gis-audit.json) records each file's CRS, bounds, all important attribute names, errors and simplification counts. Reproduce with `.\.venv\Scripts\python.exe tools/audit_malaysia_gis.py`.
### Validation and overlap handling
Each FeatureCollection is validated per feature: finite WGS84 coordinates, geometry structure/topology, properties and deterministic identity. Bad features are counted and skipped, while a bad/missing layer is reported as ERROR without stopping other layers/providers. Source data remains unchanged. Native IDs are scoped by dataset; missing IDs use a deterministic SHA-256 content hash. Conflicting repeated native IDs receive a content suffix independent of array order.
The four supplemental `platforms_*` files contain facility layouts, label/reference points, crane coverage and reference zones. They are **not** navigation restrictions. Their 45 point labels are suppressed only where a matching name/abbreviation and position (within 0.0005 degrees, about 55 m here) identifies a main platform. Distinct drawings, crane coverage and unmatched facilities remain inspectable as optional facility details at zoom 14+. The detailed multiline drawings keep their valid segments even when they exceed the usual per-object vertex limit (bounded to 200,000 coordinates).
The 384 shared native IDs between field and development-status overlays are intentional alternate status views and remain in separate layers. They are not separate platform duplicates.
Cross-provider platform deduplication is display-only: `GDS_OFFSHORE_SOURCE_PRIORITY=malaysia_gis,overpass` prefers the richer local platform record only on matching names/abbreviations and positions. Both original records and provenance remain in the canonical service; unrelated nearby installations remain distinct. Change or empty this setting to disable that preference. No authority ranking is inferred.
### Runtime, spatial filtering and reload
The existing bounded worker pool loads/validates the source and builds a Shapely 2 STRtree once. Queries use exact geometric intersection against the settled local viewport bbox, or the own-vessel operating bbox. Longitude wrapping is supported. `MaritimeAreaController` retains separate local reference bounds for views up to 30 degrees while online requests keep their existing bounded extents. Whole-world views remain ignored. Movement thresholds, settle reports, debounce and stale-generation rejection remain in the existing controller/runtime. No telemetry is needed: NO SOURCE uses the settled viewport.
The worker checks file size/mtime and manifest changes every 30 seconds and on area changes. Unchanged files are not reparsed or reindexed. A new load replaces the index as one snapshot; source removal clears affected objects on the next refresh. Valid dense regional geometry exceeding 20,000 vertices is simplified only for the map copy, starting at 0.000001 degree tolerance and increasing only as necessary; the spatial index keeps full source geometry. Eleven regional features currently use this rendering copy.
Only current-area records enter `MaritimeObjectService`; visible GIS features cross `maritimeStateChanged` / `MapBridge` into one MapLibre source per dataset. Hidden features remain in the service and index, but their coordinates are omitted from QWebChannel payloads until enabled. No per-feature widgets, sources, layers or timers exist. Static GIS alone does not trigger one-second age publications. The audit records measured load/query times as informational diagnostics, without timing-based test assertions.
### Map and inspection
Platforms use the established offshore installation symbol; pipelines use restrained brown dashed lines; well points appear only at zoom 11+ and labels at 14+. Wells are off by default and use zoom gating rather than clustering. Field/status polygons use transparent fills; blocks, basins and surveys remain subtle and off by default. Supplemental facility drawings are off at startup. Regional platforms, pipelines, fields and production areas are on by default.
GIS layers sit below project overlays and live maritime/event overlays. Hit priority favors Squall/AIS, platforms, AtoN, wells and pipelines over project features, then field/block/reference polygons. Existing cross-selection and blank-map clear remain in use. Inspectors show mapped available attributes only, with source MALAYSIA OFFSHORE GIS; absent/null/placeholder fields are hidden. Pipeline pressure is explicitly marked source units because no pressure units were supplied.
SHOW OBJECT fits the selected point/line/polygon without enabling Follow. FIT MALAYSIA GIS is an explicit diagnostic extent command and never runs at startup; zoom closer to see regional offshore symbols. Configure, VDR, VJR, TEST Jampuk and online adapters remain separate.

### Validation evidence (8 November 2026)

The inherited baseline was 226 passing tests. Final suite: `263 passed in 41.19s`; `py_compile` and `compileall app main.py` passed. The Python-to-MapLibre test uses `QJsonDocument.fromVariant`, so it exercises the real Qt JSON boundary as well as the JavaScript map contract. In particular, Shapely tuple coordinates are converted into nested lists before QVariant serialization.

Actual application startup and WebEngine rendering were checked with NO SOURCE. The peninsular test extent drew 33 installation symbols, 181 pipelines, 156 fields and 51 production areas; the close view drew 213 individual wells at zoom 11.219. Platform, pipeline and well selection/inspectors and Show Object were checked manually. Blocks, basin and seismic toggles rendered optional coverage; a separate actual Dent/Sabah extent rendered six FTG/geophysical coverages. Final GIS renderer errors: none. GEBCO remained available. Overpass returned external timeout/backoff/HTTP 502 responses during this run; AISStream had no configured key. Live AIS transport and successful live Overpass retrieval therefore were not manually demonstrated; their existing adapter tests passed.

See [manual acceptance evidence](diagnostics/malaysia-nav-acceptance.json), [final peninsular runtime](diagnostics/malaysia-nav-final.json), and [Sabah FTG runtime](diagnostics/malaysia-nav-ftg.json). Run `tools/validate_malaysia_nav.py` for an opt-in real-app diagnostic; `--focus-layer malaysia_ftg` derives an extent from actual source geometry and restores the temporary visibility preference on exit. These diagnostic cameras never create telemetry or change normal startup behavior.

Field-status overlay labels are suppressed in the manifest to avoid repeating the main field names. Seismic/FTG coverage labels are suppressed to avoid clutter from long source survey identifiers. Installation icons and optional close-zoom names share a single MapLibre symbol placement.

## Phase 4R continuation status ? 8 November 2026

The inherited adapters were retained and revalidated; no provider/service architecture was recreated. The existing optional Copernicus SDK requirement is now installed in the project virtual environment (2.5.1). Actual installed-SDK signature and real xarray normalization tests pass without authentication. Final suite: **269 passed in 66.52s**; py_compile, compileall and pip check pass.

Fresh public checks validated GEBCO capabilities/PNG, OpenSeaMap raster, BOEM/BSEE (19 Gulf objects) and EMODnet (11 North Sea objects). Overpass returned HTTP 502. AISStream/Copernicus remain NOT_CONFIGURED; GFW remains DISABLED_LICENSE. BOEM/EMODnet remain disabled by default and reject Malaysia before I/O if queried. NAVAREA VIII retains NO_STABLE_MACHINE_API; no API or scraper was invented.

`tools/check_maritime_providers.py --output <path>` saves only bounded results/counts and sanitized reason codes; it skips Open Waters if its style URL is absent. Credentials remain process-environment-only. See the [continuation report](nav-phase4r-continuation.md), [fresh network results](diagnostics/phase4r-continuation-network.json) and [configuration/coverage evidence](diagnostics/phase4r-continuation-configuration.json).
