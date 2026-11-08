# Malaysia / Singapore / Brunei offline Shortbread acceptance

Date: 2026-11-08. Continued the existing workspace and retained all inherited
edits. No tile rebuild, Planetiler invocation, Java installation or commit.
Configure, VDR and VJR were not modified.

## Inherited work classification

| Work | At continuation | Final |
|---|---|---|
| Official asset discovery/download/receipt | COMPLETE | Retained; no duplicate download |
| Read-only MBTiles validation, schema detection and style | COMPLETE | Retained |
| Package manifest, checksum, staged installation, activation | COMPLETE | Retained; no duplicate installation |
| Local gds tile/glyph routing and HTTP-blocked audit | COMPLETE | Retained |
| DAY/TWILIGHT/NIGHT real-tile audit and GIS overlays | COMPLETE | Retained |
| Hidden-NAV canvas resize correction | COMPLETE in code and delayed-tab diagnostic | Normal startup verified |
| Final manual override/startup verification | PARTIAL | COMPLETE |
| Consolidated acceptance report | NOT STARTED | COMPLETE (this document) |
| Bathymetry/global overview/additional regions | NOT STARTED | Intentionally deferred |

The continuation completed review, final compilation/tests, normal-launch visual
checks, manual DAY/NIGHT/AUTO checks and this report. No duplicate schema,
package-selection, bounds-routing or style-registry implementation was added.

## Genuine source asset

- Official source page:
  https://download.geofabrik.de/asia/malaysia-singapore-brunei.html
- Actual link discovered on that page:
  https://download.geofabrik.de/asia/malaysia-singapore-brunei-shortbread-1.0.mbtiles
- Downloaded outside the repository:
  `%LOCALAPPDATA%\GDS VTS\map-build\sources\malaysia-singapore-brunei-shortbread-1.0.mbtiles`
- Size: **294,547,456 bytes**; download duration **60.95 seconds**.
- Source package HTTP Last-Modified: **2026-11-08T03:54:19Z**. This is the
  package publication timestamp, not an asserted OSM replication timestamp.
- SHA256 of downloaded and installed database:
  `5acc0e97f0d5b68289c4bc03ceef1aa72ffdae48dc4849a984ccc340588fbc86`

Original bytes remain unchanged. Geofabrik supplies author and license rather
than the optional attribution metadata key. The existing reader now derives
attribution in memory from those fields; no source database metadata or tile
data were edited. The manifest supplies visible © OpenStreetMap contributors,
Geofabrik GmbH and Open Database License 1.0 attribution.

## Actual MBTiles inspection

| Field | Actual value |
|---|---|
| name | Shortbread |
| version | 1.0 |
| type | baselayer |
| description | Tile config for a simple vector tiles schema |
| format | pbf / MVT |
| bounds W,S,E,N | 99.25611, 0.830813, 119.6683, 7.736849 |
| center lon,lat,zoom | 109.46220500000001, 4.283831, 7 |
| native minzoom / maxzoom | 0 / 14 |
| scheme | Metadata absent; standard TMS storage, handled by the reader |
| tiles | 390,078 |
| low/middle/high sample reads | z0, z7, z14 passed through existing reader |
| vector layer count | 26 |

Actual vector layers:

```text
place_labels, boundaries, boundary_labels, addresses,
water_lines, water_lines_labels, dam_lines, dam_polygons,
pier_lines, pier_polygons, bridges, street_polygons,
streets_polygons_labels, ferries, streets, street_labels,
street_labels_points, aerialways, public_transport, buildings,
water_polygons, ocean, water_polygons_labels, land, sites, pois
```

Actual fields were inspected, including `kind`, `name`, `name_en`, `name_de`,
`population`, `admin_level`, `maritime`, and road/POI source attributes. The
adapter maps the Shortbread fields and layer names directly. It does not impose
OpenMapTiles water/transportation/place names on these tiles. Layer-level zoom
metadata is not treated as proof of missing low-zoom content: actual sample
tiles contain ocean and road geometry below some reported layer minzooms.

## Package and runtime

Package ID: `malaysia_singapore_brunei`.

Revision: `shortbread-1.0-20261108T035419Z-5acc0e97f0d5`.

Installed directory:

```text
%LOCALAPPDATA%\GDS VTS\maps\revisions\e95f3d5dc1f844b4a3942d008f04246b
```

The directory contains the unchanged `basemap.mbtiles`, `manifest.json` and
source receipt. Existing PackageManager validation/checksums/staging/atomic
activation were used. Current/previous revision registry behavior is retained;
this first production install had no previous production revision to roll back
to. Future installations retain their previous revision normally.

The active source requests:

```text
gds://tiles/malaysia_singapore_brunei/basemap/{z}/{x}/{y}.pbf
```

Style: **GDS Shortbread Maritime**. Ocean/inland water, coastline edges, land,
major roads, country/state boundaries, city/town labels and piers use explicit
palette roles. Dense buildings/addresses/retail are omitted from the style.
Ports/harbours are shown only when relevant attributes exist in the source.
Labels use `name_en` with a nonempty `name` fallback. Local font glyphs and
application icons are retained; there is no remote style, sprite or tile server.

Source bounds and safe outside-coverage status are retained. Future regional
and site databases can be composed as independent bounded detail sources in an
active bundle; source-priority ordering remains overview → region → details.
No database merge is performed. No other regional assets were downloaded.

## Real offline validation

Evidence files:

- `docs/diagnostics/shortbread-download.json`
- `docs/diagnostics/shortbread-mbtiles.json`
- `docs/diagnostics/shortbread-reader.json`
- `docs/diagnostics/shortbread-install.json`
- `docs/diagnostics/shortbread-runtime.json`
- `docs/diagnostics/shortbread-hidden-tab-runtime.json`

The offline diagnostic disabled online operational adapters before their first
Qt tick, blocked WebEngine HTTP, and used the real installed database and real
local Malaysia GIS. Production online-provider settings were not changed.

The delayed-tab audit recorded:

| Check | Result |
|---|---|
| Installed asset | true |
| Observed effective palettes | DAY, TWILIGHT, NIGHT |
| Sources | 56, stable |
| Layers | 253, stable |
| Maximum rendered basemap features | 400 |
| Maximum rendered Malaysia GIS features | 760 |
| Canvas fits visible container | true for every ready snapshot |
| MapLibre errors | 0 |
| HTTP/HTTPS map requests | 0 |
| Local map tiles/glyphs | gds routes recorded |
| Palette camera/source/visibility checks | all true |

Reviewed actual coastline, labels, land/water, offshore platforms, pipelines and
subtle field polygons around eastern Peninsular Malaysia. Pipeline landfalls
meet the visible coast and platforms lie offshore; no visible lat/lon swap or
CRS offset. This is visual/contextual alignment verification, not a survey-grade
position accuracy certification.

Normal `.\.venv\Scripts\python.exe -u main.py` startup succeeded. Opening NAV
resizes its formerly hidden canvas and frames the regional source once; returning
to NAV preserves later operator camera choices. Manual NIGHT, DAY and return to
AUTO were observed on the genuine map without camera jumps or missing sources.
The final normal window remains on NAV in AUTO · NIGHT.

The earlier diagnostic's deterministic clock changed the effective palette while
the toolbar retained a previously persisted manual item. Its instrumentation
recorded the effective state correctly. The diagnostic now synchronizes the
toolbar to AUTO before its fixed-clock checks; this was a diagnostic UI issue,
not a production manual-override defect.

## Regression validation

Before Shortbread integration: **420 passed in 26.58s**.
At continuation: the inherited suite already contained431 tests.
Latest final result: **431 passed in 53.66s**.

Both requested compilation commands passed. The complete suite preserves
Phase1 vessel/track/camera/Follow, Phase2 spatial packages/selection, Phase3
Squall, Malaysia GIS, MBTiles tile handling/package activation and geographic
palette behavior. No tests were removed or weakened, and pytest does not
download production assets.

Eleven inherited Shortbread tests cover metadata fallback without database
mutation, required schema signatures, declared schema mismatch, actual layer/
field/role mapping, bounds, activation without bathymetry, local tile URLs,
outside-coverage fallback, future overlapping sources, regional startup framing
and hidden-NAV resize without repeated camera framing.

## Shortbread integration file inventory

Created during the integration (inherited by the final continuation):

- `app/nav/offline_maps/schemas.py`
- `tools/maps/import_shortbread.py`
- `tests/test_shortbread_maps.py`
- `tests/nav_shortbread_runtime.cjs`
- the six diagnostic JSON evidence files listed above

Modified during the integration (preserved in the final continuation):

- `app/nav/offline_maps/mbtiles.py` (in-memory author/license attribution fallback)
- `app/nav/offline_maps/manager.py` (schema-aware validation)
- `app/nav/offline_maps/render_config.py` (schema adapter, coverage and initial view)
- `app/resources/map/nav.js` (coverage status and one-time framing/resize)
- `app/ui/pages/nav/nav_page.py` (status/source date and NAV show-time resize)
- `tools/maps/validate_runtime.py` (offline audit and delayed-tab diagnostics)
- `docs/offline-maps.md` (prebuilt asset strategy and commands)

Created in this final continuation: this acceptance report. No new application
implementation was needed after inherited work inspection.

## Remaining work

**BATHYMETRY ASSET PENDING**. Global overview, additional regional packs and
satellite imagery are separate future asset work. No live Own Vessel/AIS/Squall
feed was available for a new live-data visual exercise; existing automated
regressions remain green. These do not block acceptance of the genuine offline
Malaysia/Singapore/Brunei basemap checkpoint.

**A. MALAYSIA OFFLINE SHORTBREAD MAP ACCEPTED**
