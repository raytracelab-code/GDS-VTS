# Empty NAV maritime layers: diagnosis and verification

2 November 2026, Asia/Dhaka. Existing Phase 4/4R changes were inspected and preserved.
No Configure/VDR/VJR changes, synthetic production objects, UI redesign or commit.

## Findings and narrow fixes

The original running Malaysia window showed `NO SOURCE`, `OVERPASS ERROR`, and
`CURRENT VIEW 70 NM`. Its external maritime checkboxes were ON. Therefore telemetry
was not blocking provider loading in that instance: it had already established a
viewport area and attempted Overpass. Other providers were disabled/unconfigured.

Three confirmed issues were addressed:

1. `nav.js` required `moveend.originalEvent` and never submitted the initial map
   viewport. Startup and programmatic operator moves could leave providers with no
   area. Initial bounded views now submit automatically; moves without an original
   mouse event also submit. Automatic own-vessel Follow remains excluded.
2. A harbour-scale view was expanded to the minimum 50 NM own-vessel radius, and
   zooming in could not replace that broad area. Before the fix, the reproduced
   Malaysia viewport produced a query envelope of
   `[99.6701638771, 3.1972234168, 101.3398361229, 4.8627669316]`.
   Exact bounded viewport coordinates now travel with the existing OperatingArea,
   are used by existing provider bbox helpers, and participate in cache identity.
   A significantly smaller view can replace a broad query. Own-vessel radius
   behavior, dateline splitting, debounce and provider rate limits remain intact.
3. The source panel showed only `ERROR`, without the safe recorded error reason.
   It now appends the existing sanitized error identifier. No raw exception text,
   endpoint credentials or tokens are displayed.

The public Overpass endpoint is also intermittent: requests returned timeouts and
HTTP 502. An exact-bbox GET diagnostic succeeded, and a live controlled HTTP run
returned the same 22 elements and rendered real features. Subsequent GET/header
comparisons also failed, so neither HTTP method nor the Accept header was proven
to be the cause. **Speculative transport/header changes were removed.** Production
retains the original form POST transport and default endpoint. No automatic
alternate-server fallback or global provider enabling was introduced.

## Viewport provenance

The existing uninstrumented process exposes its source states and radius, but no
inspection endpoint for its exact internal map bounds. Its visible region was
Pangkor/Lumut through Bagan Datuk. A separate actual-MainWindow diagnostic instance
reproduced that region. These are measured bounds from that diagnostic map, not a
claim to have recovered the old process's exact hidden camera coordinates:

| Coordinate order | Value |
|---|---|
| Map bounds W/S/E/N | `[100.12000000000245, 3.8020716142080886, 100.89000000000249, 4.257918734151801]` |
| Final provider bbox W/S/E/N | `[100.12000000000239, 3.8020716142080886, 100.89000000000249, 4.257918734151801]` |
| Center latitude/longitude | `4.029995174179945, 100.50500000000244` |
| Own vessel | NO SOURCE, position null, no own-vessel marker |
| Origin | viewport |

The difference in west longitude is floating-point normalization only. Radius
metadata remains 50 NM; provider bbox requests now use the exact bounded view.
Very broad views remain capped by the existing 250 NM area limit.

## Actual environment and provider inventory

The following were checked **inside the launched Python diagnostic process**.
Every requested variable was **NOT SET**. No secret values were printed.
The original process's visible source states matched this configuration; its raw
environment was not extracted from process memory.

| Variables | Result |
|---|---|
| AISSTREAM_ENABLED, AISSTREAM_API_KEY | NOT SET |
| GDS_MARITIME_RADIUS_NM, GDS_OWN_MMSI | NOT SET |
| GDS_OVERPASS_ENDPOINT | NOT SET |
| GDS_OPENSEAMAP_ENABLED | NOT SET |
| GDS_OPENWATERS_ENABLED, GDS_OPENWATERS_STYLE_URL | NOT SET |
| GDS_GEBCO_ENABLED, GDS_GEBCO_WMS_ENDPOINT | NOT SET |
| COPERNICUSMARINE_USERNAME, COPERNICUSMARINE_PASSWORD | NOT SET |
| GDS_CMEMS_WAVE_DATASET, GDS_CMEMS_CURRENT_DATASET | NOT SET |
| GDS_CMEMS_SST_DATASET, GDS_CMEMS_SEALEVEL_DATASET | NOT SET |
| GDS_GFW_ENABLED, GDS_GFW_API_TOKEN, GDS_GFW_LICENSE_ACK | NOT SET |
| GDS_BOEM_ENABLED, GDS_BOEM_BASE_URL | NOT SET |
| GDS_EMODNET_ENABLED, GDS_EMODNET_WFS_ENDPOINT | NOT SET |
| GDS_NAVAREA8_ENABLED, GDS_NAVAREA8_SOURCE_URL | NOT SET |

| Provider | Implementation | Effective startup / reason |
|---|---|---|
| AISStream | IMPLEMENTED | DISABLED; enabled defaults FALSE and key NOT SET. Credential configuration is missing; no WSS connection attempted. |
| Overpass | IMPLEMENTED | Instantiated, CONNECTING until viewport; requests independent of telemetry. READY on success, ERROR on empty-cache failure, DEGRADED/CACHED on failure with real cache. |
| Open Waters / OpenSeaMap | IMPLEMENTED | DISABLED, effective flags FALSE. |
| GEBCO | IMPLEMENTED | DISABLED, effective flag FALSE. Public smoke test separately passed. |
| Copernicus wave/current/SST/sea level | IMPLEMENTED | All NOT_CONFIGURED; credentials and dataset IDs absent. |
| GFW | IMPLEMENTED | DISABLED_LICENSE; effective enable/ack FALSE, token absent. No request. |
| BOEM/BSEE | IMPLEMENTED | DISABLED, effective flag FALSE; Malaysia OUT_OF_COVERAGE if enabled. |
| EMODnet | IMPLEMENTED | DISABLED, effective flag FALSE; Malaysia OUT_OF_COVERAGE if enabled. |
| NAVAREA VIII | PARTIAL, explicit boundary | NO_STABLE_MACHINE_API. Effective enabled default TRUE; no invented API, scraper or automatic warning feed. |

No requested provider is NOT STARTED. NAVAREA's boundary is intentional, not a claim
that automatic official-warning ingestion has been implemented.

## Network and end-to-end counts

Default endpoint: `https://overpass-api.de/api/interpreter`.

| Stage | Successful live diagnostic | Later normal-cache verification |
|---|---:|---:|
| HTTP | 200, 34,951 bytes | No HTTP required for fresh area cache |
| Raw OSM elements | 22 | Previously fetched real response |
| Adapter normalization | 17 | 17 restored canonical objects |
| Service active | 17 | 17 |
| Render payload | 17 | 17 |
| MapBridge.getMaritimeState | 17 | 17 |
| maritimeStateChanged | Published 17 | Published 17 |
| JS latest state | 17 | 17 |
| MapLibre source data | 17 | 17 |
| Distinct rendered objects in viewport | 6 | 6 |

The live controlled run omitted the generic Accept header and used a read-only
GET query to compare with the successful standalone diagnostic. It still used the
existing adapter normalizer, runtime worker completion, service, bridge and actual
MapLibre view. It did not inject fixture objects. The final-code cache verification
used **no transport override** and loaded the real response through the existing
StaticCache. A separate fresh recheck encountered 502 and correctly recovered 17
cached objects as DEGRADED/CACHED. No failed request was counted as live success.

Initially, counts became zero at HTTP failure, before normalization. After a
successful response, no count was lost across normalization/store/bridge/JS/setData.
The 22-to-17 normalization difference is unmapped/unsupported raw elements, not a
rendering loss. All 17 records remain in the sources. Geometry inspection found
5 points (3 AtoN, 1 port and 1 hazard), 11 hazard polygons and 1 hazard MultiPolygon.
Thus the 13 hazards are mostly area footprints, not 13 point markers. At the
measured zoom MapLibre reported 6 distinct rendered objects, including one hazard
point and one hazard footprint. Small area footprints need not produce separately
discernible symbols at this scale; no polygon-filter exclusion was observed.

| Category | Normalized/source records | Distinct rendered in measured view |
|---|---:|---:|
| AtoN/navigation lights | 3 | 3 |
| Ports/harbours | 1 | 1 |
| Hazards: 12 rocks, 1 reef | 13 | 2 |
| Platforms, anchorages, routes/TSS, pipelines, cables | 0 | 0 |

## Map visibility, source panel and GEBCO

All 13 maritime GeoJSON sources exist, including selection. AtoN has 3 features,
ports 1 and hazards 13. Maritime point/line/fill/outline layers are visible. There
are no min/max zoom restrictions on those operational layers. Point icons have
nonzero opacity and all five generated maritime icon images exist. Labels begin
at zoom 10; diagnostic zoom was 9.7144, so label suppression is expected and does
not suppress the symbols.

The existing filters use the MapLibre GL simple geometry types Point, LineString
and Polygon. These cover the corresponding Multi* inputs; this follows the
[MapLibre expression specification](https://maplibre.org/maplibre-style-spec/expressions/).
No geometry-filter rewrite was needed or made.

Expanded MARITIME in the running original UI. Offshore Installations, Aids to
Navigation, Routes/TSS, Anchorages, Ports/Harbours, Restricted Areas, Subsea
Infrastructure, Hazards and Bathymetry were all ON. Pipelines and cables share
the existing Subsea Infrastructure control; PROJECT Pipelines is a separate local
overlay. Collapsing MARITIME hides its controls, not its map layers.

DATA SOURCES is below the initial right-panel viewport but reachable by scrolling.
It is plain text, wraps and can be read. No panel redesign was needed. The original
running Python process must be restarted to load the Python/controller changes;
it was preserved rather than silently replaced.

GEBCO remained DISABLED in production. Its separate actual GetCapabilities/GetMap
smoke test passed: GEBCO_LATEST discovered, valid Web Mercator PNG, 4,774 bytes.
No reference raster source was expected in the disabled production snapshot.
AISStream key was absent, so connection/messages/MMSI/target tests were skipped.

## Verification and files

- `python -m py_compile app/ui/pages/nav/nav_page.py`: PASS.
- `python -m compileall app main.py`: PASS.
- Final `python -m pytest -q --tb=short`: **205 passed in 1.87s**.
- Plain `python -u main.py`: MainWindow constructed, shown, event loop entered,
  NAV loadFinished=True and MapLibre operational sources initialized.
- Used the Computer Use skill for original UI controls/status inspection and visual
  confirmation of actual maritime symbols in the diagnostic map.
- Nonfatal existing WebEngine disk/GPU cache access warnings and development-basemap
  null numeric-expression warnings remain. They did not prevent maritime rendering.
- No confirmed remaining maritime implementation defect was observed. Public
  Overpass availability, missing provider configuration and NAVAREA's unsupported
  feed remain limitations. No assertion of uninterrupted fresh data is made.

Changed production files in this diagnosis:

- `app/resources/map/nav.js`: initial/programmatic viewport reporting.
- `app/nav/maritime/area_controller.py`: bounded viewport metadata, query-area shrinking and cache identity.
- `app/nav/maritime/adapters/provider_common.py`: exact viewport bbox/dateline helper.
- `app/nav/maritime/adapters/overpass.py`: optional explicit bbox input for diagnostics; original production transport preserved.
- `app/ui/pages/nav/nav_page.py`: sanitized source error reason in existing label.

Tests/tools/report:

- `tests/nav_event_runtime.cjs`: initial/no-own-vessel viewport regression; exact Python payload through JS/setData.
- `tests/test_maritime_providers.py`: NO SOURCE worker/bridge regression, viewport bbox/shrink/dateline regression, Python-to-JS payload regression.
- `tools/check_overpass_viewport.py`: real exact-bbox raw/normalized diagnostic, HTTP GET/POST comparison.
- `tools/trace_maritime_runtime.py`: opt-in real application trace, safe environment status, counts, source/layer inspection and stable first-rendered snapshot.
- `docs/nav-empty-maritime-diagnosis.md` and `docs/diagnostics/`: report and captured evidence.

A. REAL MARITIME DATA NOW VISIBLE
