# Hybrid satellite marine acceptance — 9 November 2026

The existing capsule switches between Marine and the hybrid offshore view without a style reload. No commits were made. Existing uncommitted workspace changes were preserved.

NASA metadata: https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml

GEBCO metadata: https://wms.gebco.net/mapserv?SERVICE=WMS&REQUEST=GetCapabilities

The preferred Suomi NPP daily product advertises 2026-11-02 as its latest date. Live probes of November 9–6 found no valid regional imagery and correctly retained Marine. NOAA-20 is the current equivalent VIIRS product, advertises November 9, and loaded that date in the acceptance scene. The selected date is global to the source; no tile has an independent date fallback.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline tests | PASS | 505 passed in 83.96s; actual baseline exceeded the expected 488. |
| 2. NASA GIBS layer | PASS | VIIRS_NOAA20_CorrectedReflectance_TrueColor; current equivalent to the unavailable recent SNPP product. |
| 3. Exact official endpoint | PASS | https://gibs.earthdata.nasa.gov/wmts/epsg3857/best ; GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpeg, EPSG:3857. |
| 4. Imagery date | PASS | 2026-11-09 selected in live Malaysia scene. |
| 5. Date fallback | PASS | UTC today, -1, -2, -3; bounded probes, blank-image rejection, one global date. Simulated third-date selection and actual SNPP four-date exhaustion verified. |
| 6. Satellite button | PASS | Enabled with no key; existing capsule and checked states preserved. |
| 7. Dark ocean layer | PASS | hybrid-marine-sea-water clones OpenFreeMap water geometry/filter; no full-screen dark rectangle. |
| 8. GEBCO WMS | PASS | https://wms.gebco.net/mapserv? ; WMS 1.3.0, EPSG:3857. |
| 9. Bathymetry layer | PASS | GEBCO_LATEST, current GEBCO_2026 shaded relief. Existing Bathymetry checkbox controls visibility. |
| 10. Contour availability | UNAVAILABLE | DEPTH CONTOUR VECTOR SOURCE NOT AVAILABLE. No invented contours or depth labels. |
| 11. NASA attribution | PASS | NASA GIBS / EOSDIS and VIIRS NOAA-20 attribution shown. |
| 12. GEBCO attribution | PASS | GEBCO_2026, Compilation Group (2026), DOI and context-only warning. |
| 13. Marine default | PASS | No NASA requests or sources until Satellite is selected. |
| 14. Marine → Satellite | PASS | Live DAY/TWILIGHT/NIGHT and automated checks. |
| 15. Satellite → Marine | PASS | Original visibility restored, including intentionally hidden POIs. |
| 16. No-style-reload | PASS | Mode switch only changes layer visibility and paint; test stub rejects setStyle. |
| 17. Camera preservation | PASS | Center 104E/5.5N, zoom 8, bearing 17° retained; 55° pitch retained on return. |
| 18. Source preservation | PASS | All original source objects retain identity in every live scene; hybrid/NASA sources reused across switches. |
| 19. Selection preservation | PASS | Resak Drilling Platform-A retained across mode changes; network test later deliberately changes operating area. |
| 20. Search preservation | PASS | Resak text and UI results state retained; automated checks cover open results. |
| 21. Layers panel preservation | PASS | Open panel retained on Marine/Satellite return. |
| 22. HUD preservation | PASS | Latitude, longitude, zoom, compass and NM scale unchanged. |
| 23. Platform rendering | PASS | 51 rendered platform features at primary 2D scene; accepted industrial symbol and amber halo retained. |
| 24. Pipeline rendering | PASS | 219 rendered pipeline features above imagery; accepted category styling/glow retained. No metadata classifications invented. |
| 25. Field rendering | PASS | 173 rendered field-boundary features; restrained fills and outlines retained. |
| 26. Producing-area rendering | PASS | Existing local production layers and hierarchy retained; tested below pipelines/platforms. |
| 27. DAY | PASS | NASA brightness 1, saturation 0; navy water; relief opacity .16. |
| 28. TWILIGHT | PASS | Brightness .68, saturation -.25; deeper water; relief opacity .12. |
| 29. NIGHT | PASS | Brightness .32, saturation -.45; charcoal navy; relief opacity .08; accepted operational glows. |
| 30. AUTO | PASS (automated) | Existing solar logic unchanged; hybrid follows effective_state. Live scenes force effective palettes for comparison. |
| 31. Dark marine sea result | PASS | Geometry-based water-only darkening; operational infrastructure dominates. |
| 32. Bathymetry result | PARTIAL (visual) | Service loaded; relief deliberately subtle in the shallow Malaysia scene. WMS is a low-opacity regional raster, not an ocean-clipped depth dataset; land imagery remains visible beneath it. |
| 33. Labels | PASS | Country, state, city, town and water labels retained; village/other/POI and roads omitted from hybrid. |
| 34. Geographic alignment | PASS (contextual) | XYZ NASA and WMS EPSG:3857; coastal context and real GIS inspected together. No survey-grade accuracy claim. |
| 35. NASA failure | PASS | Simulated errors/timeouts and live blocked requests restore Marine without losing operational sources. |
| 36. GEBCO failure | PASS (automated) | Only optional source removed; Satellite remains active; UNAVAILABLE reported; no repeated notifications. |
| 37. Network failure | PASS | Live blocked NASA and all-network scenes remain responsive with local GIS. Existing upstream provider warnings remain. |
| 38. Marine fallback | PASS | Live TILE_ERROR and actual SNPP NO_RECENT_IMAGERY retained Marine. |
| 39. Online-map regression | PASS | Full suite includes online map contracts. |
| 40. Malaysia GIS regression | PASS | Full suite and real Malaysia visual scene; backend unchanged. |
| 41. Night-glow regression | PASS | Pipeline, field, production, track, vectors, squall, selection, platform/AtoN effects reused unchanged. |
| 42. Phase 1 regression | PASS (automated) | Telemetry, own-vessel, track, heading/COG and Follow tests; no live vessel hardware available. |
| 43. Phase 2 regression | PASS (automated) | Spatial package, geometry and selection tests. |
| 44. Phase 3 regression | PASS (automated) | Squall/event lifecycle, bridge and map tests. |
| 45. Phase 4 regression | PASS (automated) | Maritime/provider and Malaysia GIS contracts. Unconfigured external providers remain unconfigured. |
| 46. py_compile | PASS | .\\.venv\\Scripts\\python.exe -m py_compile app\\ui\\pages\\nav\\nav_page.py |
| 47. compileall | PASS | .\\.venv\\Scripts\\python.exe -m compileall app main.py |
| 48. Exact pytest | PASS | .\\.venv\\Scripts\\python.exe -m pytest -q --tb=short ; final 510 passed in 214.96s (0:03:34). An earlier repeat had 135 setup errors from sandbox access to pytest's shared Windows temp directory; rerunning outside the sandbox resolved them. Earlier full run: 510 passed in 138.31s. Final satellite-only run: 22 passed in 22.83s. |
| 49. Total tests | 510 | Five new checks, no decrease. |
| 50. Startup | PASS | .\\.venv\\Scripts\\python.exe -u main.py ; window and NAV loaded. Acceptance script also completed 10 real-WebEngine scenes. |
| 51. Reference comparison | PENDING | No reference screenshot accompanies this request. Direction assessed below; no pixel-perfect claim. |
| 52. Resolution limitations | DOCUMENTED | Level 9 VIIRS is regional Earth-observation context, affected by clouds/swath gaps; rigs/buildings come from GIS, not satellite pixels. GEBCO is not ENC/ECDIS or safety-at-sea data. |
| 53. Files created | DONE | This report, hybrid-provider-metadata.json, hybrid runtime logs/JSON/screenshots and preserved SNPP-unavailable evidence. Existing untracked satellite implementation files were extended. |
| 54. Files modified | DONE | app/nav/satellite_map.py; app/resources/map/{satellite.js,nav.js,offline.js,nav.css}; tests/{test_satellite_maps.py,nav_satellite_runtime.cjs}; tools/maps/validate_satellite.py. |
| 55. Remaining issues | VISUAL ACCEPTANCE | Reference comparison pending; bathymetry subtle and not ocean-clipped. Existing provider warnings, rejected input GIS features and unavailable live integrations are inherited. No new confirmed hybrid runtime defect. |

| VISUAL DIRECTION | RESULT | NOTES |
|---|---|---|
| Land satellite look | PARTIAL | Actual VIIRS, but regional/cloud-limited and visibly subdued at night. |
| Dark marine ocean | PASS | Distinct navy water treatment, land not covered by the sea fill. |
| Bathymetry context | PARTIAL | Loaded shaded relief; restrained and shallow-water structure is slight. |
| Rig prominence | PASS | Industrial amber rigs and controlled halos above all background layers. |
| Pipeline prominence | PASS | Crisp network and restrained accepted night glow. |
| Field visibility | PASS | Outline/fill hierarchy remains readable. |
| Night operations look | PASS | Dark water and subordinate imagery with operational infrastructure dominant. |

Evidence: `docs/diagnostics/hybrid-satellite-runtime.json`, `hybrid-satellite-{day,twilight,night}.png`, `hybrid-{marine-return,satellite-return,network-loss,all-network-loss}.png`, `hybrid-snpp-unavailable-runtime.json`, `hybrid-provider-metadata.json`.

Final automated runtime-capture assertions: all ten checks in `hybrid-acceptance-checks.json` passed. Final test output is in `hybrid-final-pytest-elevated.log`; compilation output is in `hybrid-compileall.log`. The saved live captures precede the final small bathymetry status refinement (hiding it now reports OFF and re-enabling loaded relief reports READY); final automated tests cover that refinement.

B. HYBRID SATELLITE MARINE VIEW CODE-COMPLETE — FINAL VISUAL ACCEPTANCE PENDING
