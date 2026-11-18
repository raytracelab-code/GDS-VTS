# Online basemap transition acceptance — 2026-11-09

The inherited implementation was complete. This continuation reviewed the dirty
tree, re-ran the full suite and compilation, refreshed country/palette and blocked
HTTP captures, and inspected a normal `main.py` launch through the Windows UI.
No application code was changed, reverted, or committed in this continuation.
The reference-style NAV redesign remains a separate task.

## Inherited work classification

| Work | Inherited state | Continuation result |
|---|---|---|
| Online OpenFreeMap Liberty default and unrestricted camera | COMPLETE | Retained and verified |
| Removal of installed MBTiles and build/download assets | COMPLETE | Current filesystem independently verified |
| Empty active/regional registries and cleared package setting | COMPLETE | Independently verified |
| Local Malaysia GIS and existing professional palette/glow/UI | COMPLETE | Retained; visual and regression checks passed |
| Optional offline engine and regional tooling | COMPLETE | Retained; regression suite passed |
| Final runtime/visual acceptance and report | PARTIAL | Finished here |
| Acceptance document linked by `offline-maps.md` | NOT STARTED | Created here |
| Reference-style UI redesign | NOT STARTED | Deferred as requested |

The inherited tracked diff comprised 16 files, 472 insertions and 64 deletions,
plus untracked engine/tooling/tests/diagnostics. The larger count includes earlier
regional-engine and presentation work. It was not treated as new work to redo.
The final file inventory is in
[`diagnostics/online-map-continuation.json`](diagnostics/online-map-continuation.json).
The obsolete Map regions sidebar instructions in `offline-regions.md` were corrected.

## Storage and state

Before values come from the inherited measured
[`online-map-cleanup-storage.json`](diagnostics/online-map-cleanup-storage.json);
they are not estimates reconstructed from package sizes.

| Location | Before (bytes) | After (bytes) |
|---|---:|---:|
| `%LOCALAPPDATA%\GDS VTS\maps` | 37,747,727,610 | 8 |
| `%LOCALAPPDATA%\GDS VTS\map-build` | 84,247,389,911 | 0 |
| Total reclaimed | **121,995,117,513 (113.62 GiB)** | |

Only `active.json` and `regions.json` remain in the map store; both parse as `{}`.
Installed packages = 0; active packages = 0; `nav/map_package` is unset.
No further deletion was necessary. WebEngine's normal online cache and unrelated
application data were retained. The Malaysia GIS directory contains 41 files,
65,410,569 bytes, with no Git changes. Its existing audit reports 10,268 local
features across 18 GIS layers, including 13 invalid features and 2 null geometries;
those pre-existing input warnings are unrelated to the basemap transition.

## Runtime and visual results

[`online-map-runtime.json`](diagnostics/online-map-runtime.json) was refreshed by
`tools/maps/validate_online.py`. All nine scenes reported `ready`, `loaded`,
`tiles_loaded`, and `MAP / ONLINE / READY`. The diagnostic's combined
renderer/GIS readiness gate completed in 15.00 seconds; this is not a claim about
time to the first tile. It created zero MBTiles readers. No package switching or
geographic clipping was used. The seven country captures were visually inspected.

| Scene | Result | Rendered basemap features |
|---|---|---:|
| [Bangladesh](diagnostics/online-map-bangladesh.png) | PASS | 409 |
| [Myanmar](diagnostics/online-map-myanmar.png) | PASS | 348 |
| [Thailand](diagnostics/online-map-thailand.png) | PASS | 292 |
| [Malaysia / DAY](diagnostics/online-map-malaysia-day.png) | PASS | 37 |
| [Malaysia / TWILIGHT](diagnostics/online-map-malaysia-twilight.png) | PASS | 37 |
| [Malaysia / NIGHT](diagnostics/online-map-malaysia-night.png) | PASS | 37 |
| [Vietnam](diagnostics/online-map-vietnam.png) | PASS | 320 |
| [Philippines](diagnostics/online-map-philippines.png) | PASS | 144 |
| [Indonesia](diagnostics/online-map-indonesia.png) | PASS | 311 |

Each Malaysia scene rendered 390 local GIS features, including 29 platform symbols,
127 pipeline features and 87 field boundaries. Counts are rendered features in
this viewport, not unique dataset totals. Coastline and offshore geometry show no
visible coordinate swap, CRS offset, or ordering regression. Pipeline glow opacity
was 0 in DAY, 0.0532 in TWILIGHT, and 0.19 in NIGHT. Existing tests also cover field,
producing-area, track, heading, COG, squall, selection, platform and AtoN effects,
their ordering, visibility, and source identity across palette changes.

The refreshed [blocked-HTTP report](diagnostics/online-map-fallback-runtime.json)
and [capture](diagnostics/online-map-local-fallback.png) show safe startup with
`MAP / ONLINE UNAVAILABLE / LOCAL OVERLAYS ACTIVE`, zero readers, and the same
390 GIS features / 29 platforms / 127 pipelines / 87 fields. Blocking was applied
to WebEngine HTTP(S) requests in the diagnostic process, not to the computer's
network connection. Operational sources for vessel/track/project/AIS/squall remain
present; live sensor and authenticated AIS feeds were not available for a live
data acceptance test.

Normal `.\.venv\Scripts\python.exe -u main.py` startup was separately inspected:
Configure opened, NAV loaded the Bangladesh online map, the sidebar reported
`MAP / ONLINE / READY`, and AUTO selected TWILIGHT using the unchanged controller.
Sidebar, toolbar, legend and Malaysia layer controls remain intact. Satellite has
no configured imagery asset/provider; clicking it safely reports
`Offline satellite imagery is not installed`. Clicking Marine restores online READY.
No new satellite provider was added. The normal application was left open on NAV.

The online script contract exercises fetch success, failure, invalid style and
timeout, retained local sources and deduplicated provider-error warnings. Existing
provider backoff was preserved. Runtime logs contain no stale MBTiles/database/
active-revision errors or Python traceback. Optional Overpass timeout/HTTP errors
and the pre-existing GIS input warnings can still occur independently. The
PowerShell `*>` capture wrappers returned status 1 for native stderr logging;
their complete scene reports and screenshots were written, without a traceback.
That wrapper result is not recorded as a clean diagnostic-command exit.

## Required checks

| Check | Result | Notes |
|---|---|---|
| Full suite | PASS | `476 passed in 78.84s (0:01:18)` |
| Total tests | PASS | 476; unchanged from the inherited baseline |
| `python -m py_compile app\ui\pages\nav\nav_page.py` | PASS | Exit 0 |
| `python -m compileall app main.py` | PASS | Exit 0 |
| `git diff --check` | PASS | No whitespace errors |
| Offline engine | PASS | MBTiles reader, gds scheme, manager, Shortbread and manifest code retained |
| Own Vessel / Track | PASS (regression) | State, vectors, segmentation, controls and render sources; live sensor unavailable |
| AIS / Squall / project spatial | PASS (regression) | Existing service/render/selection tests; no live AIS feed configured |
| AUTO / UTC / solar / Follow | PASS | Existing tests; algorithms untouched; normal AUTO observed |
| Online UI and local GIS | PASS | Fresh captures plus live normal-app inspection |
| Satellite | NOT CONFIGURED | Safe status and Marine return verified |
| Remaining issues | NONE blocking | External feed availability and pre-existing GIS warnings documented above |

ONLINE BANGLADESH + SOUTHEAST ASIA MAP ACCEPTED — HEAVY OFFLINE ASSETS REMOVED
