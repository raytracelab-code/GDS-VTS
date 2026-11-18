# GDS VTS map-first NAV checkpoint — 2026-11-09

NAV now fills its workspace from a 60 px application rail to the right and bottom
edges. The application header remains on Configure and is hidden on NAV. Four
floating control capsules, a compact palette/status capsule, and loaded-data search
replace the permanent toolbar and sidebar. Layers and the selected-object inspector
float temporarily over the map. The existing inspector's full information remains
available through DETAILS. Escape dismisses overlays without clearing selection.

The attachment supplied a detailed written visual direction but no image files.
The comparison below is against that direction, not an exact screenshot comparison.
GDS branding and original line icons are used throughout.

## Scope and compatibility

No provider, canonical data service, telemetry service, TrackManager, solar
calculation, palette-reference logic, offline engine, package manager, or Malaysia
GIS file was edited in this checkpoint. Existing uncommitted backend edits from
the accepted online-basemap checkpoint remain untouched. OpenFreeMap Liberty is
still the provider; no new basemap, satellite, geocoder, or bathymetry provider was
introduced. Existing optional reference overlays remain available as before.

The shell changes are in `app/ui/main_window.py` and `components/top_tabs.py`;
these are needed to replace the horizontal tabs/header with the requested narrow
rail on NAV. Configure retains its page and header, and the VDR/VJR telemetry gates
remain intact. NAV controls still dispatch the original commands.

One confirmed presentation compatibility defect was corrected: the inherited
operational font `KlokanTech Noto Sans Regular` returns HTTP 404 from the existing
online provider's glyph endpoint. `Noto Sans Regular` returns HTTP 200. Online
operational labels now use the supported font; offline mode keeps the old font.
This changes label layout only, without changing the provider or reloading styles.
The [high-zoom capture](diagnostics/nav-map-first-malaysia-platform-labels.png)
visibly confirms platform and field labels. Native Qt retains the project's
existing system-font fallbacks for its WOFF2-based type system.

Infrastructure paint changes stay in the existing NAV renderer/palette module:
amber rig cores and controlled halos, muted teal pipelines, subdued field polygons,
warmer producing-area outlines and a seafoam own-vessel symbol. The existing glow
companion creation, layer ordering, zoom thresholds and collision controls remain.
No gas/oil pipeline color classification is fabricated: the current map payload
does not expose pipeline contents, so pipeline styling remains neutral teal.

## Interaction and evidence

Search reads the existing visible, loaded canonical records; it matches names,
field names, pipeline endpoints and MMSI. Results are capped at 12. It also accepts
`latitude, longitude`, validates ranges, and navigates through the existing camera
helper. It does not fetch locations or load countries through a new search backend.
Move into Malaysia before searching Malaysia objects that are not currently loaded.
No saved visibility preference is silently enabled by search.

Manual normal-app checks covered Configure → NAV, loaded-data search, coordinate
navigation to Malaysia, a Resak platform result, CENTER/DETAILS, Layers, and Escape
dismissal while the selected map object remained highlighted. VDR/VJR were visibly
locked with no telemetry, as before. Satellite is disabled with a clear Not configured
tooltip until existing configuration supplies an imagery layer.

The [runtime report](diagnostics/nav-map-first-runtime.json) contains 13 full-window
captures: the seven-country route, three Malaysia palettes, high-zoom labels, Layers,
selection card and 800 × 600 layout. Every scene reports `ready`, `loaded`,
`tiles_loaded`, HUD present and canvas filling NAV, with zero offline readers.
The final combined renderer/GIS readiness gate took 17.00 seconds; this is not a
time-to-first-tile benchmark. In the wide Malaysia scene, 50 platform symbols,
218 pipeline features and 169 field boundaries rendered. Counts reflect the
viewport and feature fragments, not unique dataset totals.

Pipeline glow opacity remains DAY 0, TWILIGHT 0.0532, NIGHT 0.19. Platform halo
opacity remains DAY 0.05, TWILIGHT 0.132, NIGHT 0.24. Source/camera identity and
palette stability are checked by the existing real-script contracts; HUD tests
also check repeated initialization, coordinates, bearing and nautical scale without
camera or source mutation.

The final blocked-HTTP run also exited 0: NAV reached LOCAL ONLY with the same
718 GIS feature fragments, 50 platform symbols, 218 pipeline features and 169 field
boundaries, plus the HUD and floating controls. It created no MBTiles readers.
This blocks WebEngine HTTP(S) requests in the diagnostic process; it does not
disconnect the host network or claim live external-feed availability.

| Evidence | File |
|---|---|
| Hero NIGHT | [Malaysia NIGHT](diagnostics/nav-map-first-malaysia-night.png) |
| DAY / TWILIGHT | [DAY](diagnostics/nav-map-first-malaysia-day.png), [TWILIGHT](diagnostics/nav-map-first-malaysia-twilight.png) |
| Layers | [Temporary panel](diagnostics/nav-map-first-malaysia-layers.png) |
| Selection | [Selected platform](diagnostics/nav-map-first-malaysia-selection.png) |
| Compact layout | [800 × 600](diagnostics/nav-map-first-compact-layout.png) |
| Bangladesh | [Full map](diagnostics/nav-map-first-bangladesh.png) |
| Remaining route | [Myanmar](diagnostics/nav-map-first-myanmar.png), [Thailand](diagnostics/nav-map-first-thailand.png), [Vietnam](diagnostics/nav-map-first-vietnam.png), [Philippines](diagnostics/nav-map-first-philippines.png), [Indonesia](diagnostics/nav-map-first-indonesia.png) |
| Blocked WebEngine HTTP(S) | [Report](diagnostics/nav-map-first-fallback-runtime.json), [capture](diagnostics/nav-map-first-local-fallback.png) |

## Requested acceptance checks

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline pytest | PASS | 476 passed in 73.37s (0:01:13) |
| 2. Backend preserved | PASS | Frozen systems and GIS assets untouched in this checkpoint |
| 3. Map canvas | PASS | Fills the NAV workspace |
| 4. Left rail | PASS | 60 px, GDS mark, tooltips, active state, original gates |
| 5. Search | PASS | Existing loaded records and validated coordinates |
| 6. Capsules | PASS | Four compact original icon groups |
| 7. Navigation group | PASS | Original Center / Follow / North commands |
| 8. Map mode group | PASS | Marine and unconfigured Satellite |
| 9. Layers button | PASS | Opens a temporary panel |
| 10. Layers popover | PASS | Hidden initially; toggle / outside click / Escape / close |
| 11. Layer persistence | PASS | Existing settings and defaults retained |
| 12. Permanent sidebar | REMOVED | Panel floats over the existing canvas |
| 13. Platforms | PASS | Industrial rig symbol with restrained amber core |
| 14. Platform labels | PASS | Online font compatibility fixed; zoom/collision behavior retained |
| 15. Pipelines | PASS | Teal core, original glow; no invented type classification |
| 16. Fields | PASS | Secondary boundaries and transparent fill |
| 17. Producing areas | PASS | Warmer, stronger than generic fields; below infrastructure |
| 18. Wells | PASS | Original off/high-zoom/clustering preferences retained |
| 19. AIS | PASS (regression) | White/seafoam hierarchy; no live AIS feed configured |
| 20. Own Vessel | PASS (regression) | Seafoam presentation; no live sensor acceptance |
| 21. Squall | PASS (regression) | Severity colors, events and trajectories unchanged |
| 22. Selected card | PASS | Floating right, CENTER and full DETAILS |
| 23. Selection glow | PASS | Existing emphasis retained; dismissing card keeps selection |
| 24. Bottom-right HUD | PASS | Geographic information and bearing |
| 25. Coordinates | PASS | Normalized decimal degrees, four places |
| 26. Zoom | PASS | Two decimal places |
| 27. Nautical scale | PASS | Existing MapLibre nautical scale, NM styling |
| 28. Compass | PASS | Event-driven bearing; existing North Up command |
| 29. Palette control | PASS | AUTO / DAY / NIGHT; computed twilight labels |
| 30. DAY | PASS | Restrained palette and readable dark controls |
| 31. TWILIGHT | PASS | Original palette behavior preserved |
| 32. NIGHT | PASS | Dark marine hero state; readable infrastructure |
| 33. Night glow | PASS | Existing category companions and ordering retained |
| 34. Marine | PASS | Same accepted provider/style integration |
| 35. Satellite | NOT CONFIGURED | Disabled, explicit tooltip, layout intact |
| 36. Bangladesh | PASS | Fresh full-window capture inspected |
| 37. Malaysia | PASS | GIS/labels/selection captures inspected |
| 38. Online regression | PASS | All seven country scenes loaded |
| 39. Malaysia GIS regression | PASS | Existing source data and regression suite preserved |
| 40. Phase 1 | PASS (regression) | Telemetry / vessel / track tests |
| 41. Phase 2 | PASS (regression) | Project spatial and interaction tests |
| 42. Phase 3 | PASS (regression) | Squall / event / selection tests |
| 43. Phase 4 | PASS (regression) | Maritime / GIS / provider contracts |
| 44. Palette regression | PASS | Solar/UTC/reference logic untouched |
| 45. Source preservation | PASS | Real-script identity contracts |
| 46. Camera preservation | PASS | Panels/HUD/palettes do not move the camera |
| 47. MapLibre errors | PASS | No map errors in final visual run |
| 48. UI performance | PASS (structural) | Event-driven HUD; debounced search; no feature widgets/layers or repaint timer |
| 49. py_compile | PASS | Exit 0 |
| 50. compileall | PASS | Exit 0 |
| 51. Final pytest | PASS | 488 passed in 68.59s (0:01:08) |
| 52. Total tests | 488 | 476 preserved + 12 presentation tests |
| 53. Startup | PASS | Normal main.py startup and NAV manually inspected |
| 54. Created files | RECORDED | See inventory below |
| 55. Modified files | RECORDED | See inventory below; inherited edits retained |
| 56. Remaining visual issues | NONE blocking | Original reference images were not attached; live feed limits noted |
| 57. Reference direction | PASS | Written direction comparison below |

| REFERENCE DIRECTION | RESULT | NOTES |
|---|---|---|
| Map-first composition | PASS | Canvas extends behind all temporary UI |
| Floating controls | PASS | Compact groups; no duplicate Qt/web action toolbar |
| Dark maritime feel | PASS | Deep Current surfaces and restrained marine palette |
| Infrastructure prominence | PASS | Amber rigs, distinct pipelines, secondary fields |
| Low UI clutter | PASS | Narrow rail; panels, details and legend are temporary |

## File inventory for this checkpoint

Created source/test files:

- `app/ui/components/nav_icons.py`
- `app/ui/pages/nav/floating_controls.py`
- `app/resources/map/presentation.js`
- `tests/test_nav_map_first.py`
- `tests/nav_hud_runtime.cjs`
- `docs/nav-map-first.md`

Modified files:

- `app/ui/main_window.py` — rail and NAV header visibility only.
- `app/ui/components/top_tabs.py` — compact rail; same navigation/gating API.
- `app/ui/pages/nav/nav_page.py` — floating integration and original command wiring.
- `app/ui/pages/nav/presentation_widgets.py` — dark surfaces and compact inspector rows.
- `app/resources/map/index.html`, `nav.css`, `nav.js`, `offline.js` — HUD, label font and paint presentation.
- `tests/test_nav_presentation.py`, `tests/nav_online_runtime.cjs` — preference and online-font contracts.
- `tools/maps/validate_online.py` — opt-in full-window/panel/label diagnostic scenes.

New `docs/diagnostics/nav-map-first-*` reports, screenshots and ignored runtime logs
hold the evidence. The first diagnostic pass also refreshed the inherited
`online-map-*` runtime reports/captures. No production MBTiles were downloaded,
no GIS files were removed, and no commit was created.

A. REFERENCE-STYLE NAV UI ACCEPTED
