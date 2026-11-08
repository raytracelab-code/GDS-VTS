# Real maritime deployment defaults and acceptance

2 November 2026, Asia/Dhaka. Continues the existing uncommitted Phase 4R work.
The inherited tree had 205 passing tests; final validation has 226. No existing
work was discarded and no commit was made.

## Delivered behavior

Public Overpass and GEBCO now register automatically. AISStream activates when
`AISSTREAM_API_KEY` exists unless `AISSTREAM_ENABLED` is explicitly false/0/no/off.
Missing AIS credentials report NOT_CONFIGURED. Explicit GEBCO disablement and
persisted layer visibility remain respected. `.env.example` is a template only;
the application continues to use the process environment.

Overpass uses a Python-worker form POST (`urlencode({'data': query})`), JSON Accept,
and a clear GDS-VTS User-Agent. The consolidated nwr query includes seamarks,
offshore platforms, pipelines, harbour tags, underwater objects and the existing
mapped hazards/infrastructure selectors. It requests full metadata/geometry,
including relation-member geometry. The inappropriate 16 MB **server RAM** setting
was removed; the **client response** limit remains 16 MB.

The default primary is `https://overpass-api.de/api/interpreter`. The default
fallback is `https://overpass.private.coffee/api/interpreter`, an instance listed by
the [OSM project](https://wiki.openstreetmap.org/wiki/Overpass_API). Override the
primary with `GDS_OVERPASS_ENDPOINT` and the comma-separated fallback list with
`GDS_OVERPASS_FALLBACK_ENDPOINTS`; an explicitly empty fallback list disables it.
At most two configured fallbacks are retained and at most two endpoints are
attempted in a fetch. There is no parallel host fan-out. Failed endpoints cool
down for at least 120 seconds and successful endpoints remain preferred. 429 does
not trigger host hopping. Retry-After is respected across area changes; network
requests remain separated by at least 60 seconds. No UI thread sleeps or I/O.

Transport errors expose bounded reason codes such as HTTP 429, HTTP 502, TIMEOUT,
DNS ERROR, TLS ERROR or INVALID RESPONSE. Logs include sanitized endpoint (without
query), status/reason, bytes, elapsed time and a small response-header whitelist.
Credentials, raw response bodies and raw exception messages are not printed.

The existing static cache is reused. Fresh, fully covering snapshots can serve
contained views and camera floating-point jitter, with TTL and endpoint identity
checks. Minor overlapping viewport movements preserve the active query/cache
identity. A significantly smaller or displaced view still refreshes. Cache reads
are allowed during provider backoff, so panning to already cached data does not
wait for a network retry. Successful empty responses show READY | 0 objects.

GEBCO discovers the current layer and advertises a valid Web Mercator WMS raster
through the existing shared bridge. Bathymetry controls it at opacity 0.4, below
operational objects. There is no camera operation in provider-data application.

Open Waters remains optional and requires an explicitly configured style URL.
Its validated nautical layers are imported as overlays; the basemap is not
replaced. Remote sprite-dependent reference symbols get geometry-based circles.
Canonical maritime points also have an independent circle core. Icon registration
failure is contained and cannot hide the point or abort operational-layer setup.
All six GeoJSON geometry variants are covered by the filter regression checks.

## Measured network results and limits

The controlled current-region check used these actual MapLibre bounds, W/S/E/N:

`[100.12000000000245, 3.8020716142080886, 100.89000000000249, 4.257918734151801]`

This is the reproduced Pangkor/Lumut–Bagan Datuk view used in the preceding
diagnosis, not a claim that an uninstrumented older process's hidden bounds were
extracted. The ordinary app's camera is now operator-controlled.

Fresh POST acceptance attempts in this run did **not** establish a successful live
Overpass response. Primary timed out after 35.50 s; the configured fallback was
tried once and timed out after 37.87 s. A later plain `python -u main.py` launch
received HTTP 502 from the primary in 0.65 s: 534 bytes, Content-Type text/plain,
Content-Length 534, Server nginx; its fallback timed out after 35.47 s. These are
public-provider/gateway availability failures, not a generic Python HTTPError.
There is no evidence here to attribute the gateway's internal failure specifically
to a local proxy, DNS, TLS, or malformed query. No proxy/security settings changed.

The normal-cache Malaysia check returned OVERPASS READY | CACHED | 17 objects and
GEBCO READY. Those 17 objects were genuinely fetched and normalized during the
preceding live acceptance, originating from 22 raw OSM elements; no fixtures or
synthetic targets were injected. The original raw-response count is provenance,
**not** a fresh successful request count for this run.

| Pipeline stage, normal-cache Malaysia acceptance | Count |
|---|---:|
| Raw elements in the genuine cached response's originating fetch | 22 |
| Canonical objects restored | 17 |
| MaritimeObjectService | 17 |
| Render features | 17 |
| MapBridge objects | 17 |
| JS received | 17 |
| MapLibre GeoJSON features, excluding selection | 17 |
| Distinct rendered objects at measured zoom | 6 |

Categories: 3 AtoN/navigation lights, 1 harbour and 13 hazards (12 rocks, 1 reef).
Offshore, routes/TSS, anchorages, pipelines and cables were zero in that snapshot.
There are 5 Point, 11 Polygon and 1 MultiPolygon records. MapLibre rendered 3 AtoN,
1 harbour and 2 distinct hazards at the measured view/zoom; small hazard footprints
are not all separately discernible. No count was lost across store/bridge/setData.

GEBCO GetCapabilities succeeded: HTTP 200, 24,420 bytes, XML, Server Apache;
GEBCO_LATEST was selected. The actual map visibly rendered its bathymetry. Manual
Bathymetry OFF removed it and ON restored it; recorded bounds were identical:
the raster layer changed from visibility none to visible at opacity 0.4 while
the same 17 source objects and 6 rendered objects remained. No security downgrade,
fatal JS exception or provider-induced camera jump was observed.

Evidence: [fresh attempts](diagnostics/maritime-defaults-live.json) and
[normal defaults/cache/GEBCO rendering](diagnostics/maritime-defaults-final.json).
The separate ordinary `python -u main.py` process was also started, NAV opened,
and actual GEBCO terrain/bathymetry and attribution observed. It was left running;
UI input was stopped when operator input was detected. The diagnostic instances
closed normally.

## Configuration and source states

All requested credential/configuration variables, including the new fallback-list
override, were NOT SET in the diagnostic Python process. Consequently the new
defaults, rather than a test-only enablement override, produced the acceptance.
No AIS, Copernicus or GFW secret value was printed or placed in JavaScript/cache.

| Source | Actual/effective state |
|---|---|
| Overpass | Enabled by default. READY/CACHED for the measured covered view; explicit availability errors/backoff for uncached failed views. |
| GEBCO | Enabled by default, READY, visibly rendered. Explicit false still disables. |
| AISStream | NOT_CONFIGURED; API key NOT SET, enabled flag NOT SET. A key would auto-activate without UI clicks unless explicitly disabled. |
| Copernicus wave/current/SST/sea level | NOT_CONFIGURED; credentials and all dataset IDs absent; no live request. |
| GFW | DISABLED_LICENSE; gates/token absent; no request or auto-enablement. |
| BOEM/BSEE | DISABLED locally; enabled Malaysia requests are OUT_OF_COVERAGE before I/O. |
| EMODnet | DISABLED locally; enabled Malaysia requests are OUT_OF_COVERAGE before I/O. |
| NAVAREA VIII | NO_STABLE_MACHINE_API; intentional adapter boundary, no scraper. |
| Open Waters | NOT_CONFIGURED; optional flag/style URL absent; does not block core feeds. |
| OpenSeaMap | DISABLED; optional, not a defect. |

## Required acceptance checklist

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Empty-map root cause | Addressed in app | Optional public GEBCO was off; public Overpass was failing; defaults and operational error/cache behavior now explicit. |
| 2. Overpass HTTPError cause | Identified to available evidence | HTTP 502 gateway response and actual timeouts. Internal gateway/proxy cause not proven. |
| 3. Endpoint | Primary + bounded fallback | Defaults listed above; no manual setup required. |
| 4. HTTP result | Availability failure this run | Primary timeout/502; one configured fallback timeout. No fresh success claimed. |
| 5. Viewport bbox | Captured | Exact Malaysia bounds above. |
| 6. Raw OSM elements | 22 originating cached response | Fresh failed requests have no valid element count. |
| 7. Normalized count | 17 | Genuine cache. |
| 8. AtoN | 3 | Navigation lights. |
| 9. Offshore | 0 | No presence claimed. |
| 10. Routes/TSS | 0 | No presence claimed. |
| 11. Anchorages | 0 | No presence claimed. |
| 12. Ports | 1 | Harbour. |
| 13. Pipelines | 0 | No presence claimed. |
| 14. Cables | 0 | No presence claimed. |
| 15. Hazards | 13 | 12 rocks, 1 reef. |
| 16. Service objects | 17 | Existing canonical store. |
| 17. MapBridge | 17 | Existing signal/state path. |
| 18. MapLibre | 17 source features | 6 distinct rendered objects at measured view/zoom. |
| 19. GEBCO capabilities | PASS | HTTP 200, XML parsed. |
| 20. GEBCO layer | GEBCO_LATEST | Discovered, no obsolete year. |
| 21. GEBCO visible | PASS | Live raster, OFF/ON verified. |
| 22. AIS enabled | Auto with key | Explicit false remains a disable. |
| 23. AIS key | NOT SET | No value exposed. |
| 24. AIS connection | Not attempted | NOT_CONFIGURED. |
| 25. AIS messages | 0 | No configured connection; not an empty upstream-feed claim. |
| 26. Unique MMSIs | 0 | No configured connection. |
| 27. Visible AIS | 0 | No fake ships. |
| 28. Copernicus | NOT_CONFIGURED | Missing credentials/datasets. |
| 29. GFW | DISABLED_LICENSE | Correct, unchanged gate. |
| 30. BOEM | DISABLED | OUT_OF_COVERAGE if enabled for Malaysia. |
| 31. EMODnet | DISABLED | OUT_OF_COVERAGE if enabled for Malaysia. |
| 32. NAVAREA VIII | NO_STABLE_MACHINE_API | Acceptable boundary. |
| 33. Open Waters | NOT_CONFIGURED | Optional safe-overlay implementation. |
| 34. OpenSeaMap | DISABLED | Optional. |
| 35. NO SOURCE fallback | PASS | Viewport area loads independent of telemetry. |
| 36. Layer defaults | ON unless persisted otherwise | Existing user preferences respected; no force-enable on each startup. |
| 37. Source UI | PASS | States/counts/CACHED/errors; empty success displays READY with 0 objects. |
| 38. Camera | PASS | Identical bounds through Bathymetry toggle/data arrival. |
| 39. Phase 1 | Automated PASS | Existing telemetry, track, heading/COG, controls/Follow checks retained. |
| 40. Phase 2 | Automated PASS | Spatial package, geometry, selection/inspector checks retained. |
| 41. Phase 3 | Automated PASS | Squall lifecycle, ETA, selection/cache/JS checks retained. |
| 42. py_compile | PASS | Requested NAV module. |
| 43. compileall | PASS | app and main.py. |
| 44. Exact pytest | 226 passed in 1.38s | No skips reported. |
| 45. Total tests | 226 | 21 more cases than inherited 205; foundation 148 preserved. |
| 46. Startup | PASS | Plain python -u main.py, NAV loadFinished=True. |
| 47. Manual visual | PASS, scoped | Real cached OSM + live GEBCO, toggles, no fake own vessel; no live AIS without key. |
| 48. Created files | Report + evidence | This file and two diagnostics JSON files. |
| 49. Modified files | Listed below | Existing architecture preserved. |
| 50. Remaining defects/limits | No confirmed new core rendering defect | Public Overpass freshness unavailable this run, missing credentials, existing nonfatal basemap/WebEngine warnings. |

## Files changed in this task

- `.env.example`: current defaults and fallback configuration.
- `main.py`: maritime-only operational logging; no credential-bearing debug logs enabled.
- `app/nav/maritime/providers.py`: GEBCO/AIS/optional-source registration policy and Overpass fallbacks.
- `app/nav/maritime/runtime.py`: retry deadlines across viewport changes, cache availability during backoff, source/count logs.
- `app/nav/maritime/area_controller.py`: minor-movement overlap hysteresis.
- `app/nav/maritime/adapters/provider_common.py`: safe HTTP/network diagnostics and retry metadata.
- `app/nav/maritime/adapters/overpass.py`: form POST, query selectors, category aliases and bounded sticky fallback.
- `app/nav/maritime/adapters/base.py`: fresh covering-area cache reuse.
- `app/nav/maritime/adapters/reference.py`: nautical overlay import for optional Open Waters.
- `app/resources/map/nav.js`: independent circle fallbacks and namespaced reference overlays/error routing.
- `app/ui/pages/nav/nav_page.py`: explicit successful zero-object state.
- `tests/test_maritime_providers.py`: defaults, POST/fallback/rate limit, redaction, cache, source UI, AIS runtime, aliases and viewport regressions.
- `tests/nav_event_runtime.cjs`: all six geometry variants, missing icons, overlays/visibility/no camera jump.
- `tools/check_overpass_viewport.py`: endpoint/status/headers/bytes/elapsed diagnostics without body dumps.
- `tools/trace_maritime_runtime.py`: safe headers, stable raster snapshot and atomic evidence writes.
- `docs/maritime-sources.md`: current defaults and behavior documentation.

Created: this report, `docs/diagnostics/maritime-defaults-live.json`, and
`docs/diagnostics/maritime-defaults-final.json`.

No Configure, VDR or VJR implementation was changed. No second maritime state
store, production fixture, embedded credential, security downgrade or commit.

B. CORE REAL DATA FIX COMPLETE — AIS CREDENTIALS NOT CONFIGURED
