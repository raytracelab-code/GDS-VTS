# Offline map and AUTO palette delivery checks

Validated 2026-11-08 using the project `.venv`. Inherited baseline:
**269 passed in22.89s**. Final suite: **342 passed in26.56s**, no skips or
failures;73 added tests. Existing tests were not removed or weakened.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Inherited workspace | PASS | Existing NAV/provider/UI/GIS changes retained; no commit/reset |
| 2. Offline module | PASS | Six files under `app/nav/offline_maps/` |
| 3. MBTiles reader | PASS | Indexed bounded SQL, synchronized read-only connections |
| 4. XYZ/TMS | PASS | Row=(2^z−1)−y; coordinate limits tested |
| 5. Gzip PBF | PASS | Bounded decompression; actual WebEngine response verified |
| 6. Raster MBTiles | PASS | PNG/JPEG/WEBP reader tests; real PNG scheme response |
| 7. gds tile serving | PASS | Two worker threads, bounded queue, Qt-owned reply buffers |
| 8. Global overview | ENGINE READY | Independent Natural Earth/OpenMapTiles-compatible role; real asset pending |
| 9. SEA basemap | ENGINE READY | Metadata coverage and OpenMapTiles subset; real asset pending |
| 10. Detail packs | PASS | Independent detail sources/metadata coverage tested |
| 11. Bathymetry | ENGINE READY | Separate raster role; actual GEBCO package pending |
| 12. Satellite | ENGINE READY | Optional real raster role; no imagery fabricated |
| 13. Manifest | PASS | Version1, identifiers, revisions, dates, coverage, roles, attribution, checksums |
| 14. Validator | PASS | Metadata, indexed SQL, readable sample, binary format, safe paths, SHA256 |
| 15. Staging/activation | PASS | Same-filesystem staging; atomic revision/pointer replacement |
| 16. Rollback | PASS | Prior revision retained; checksum and activation-failure tests |
| 17. Storage | PASS | `%LOCALAPPDATA%\GDS VTS\maps`; env/development/bundled discovery |
| 18. Online fallback | PASS | Default false; optional online development map explicitly labelled |
| 19. Package status UI | PASS | Compact sidebar status and explanatory tooltip |
| 20. DAY | PASS | Actual running NAV and supplied Malaysia GIS visually checked |
| 21. TWILIGHT | PASS | Deterministic diagnostic UTC; actual running NAV checked |
| 22. NIGHT | PASS | Low-glare background and readable supplied GIS checked |
| 23. Solar calculation | PASS | NOAA geometric elevation, leap years, civil twilight, hysteresis |
| 24. UTC priority | PASS | Fresh canonical Date+UTC, otherwise explicit SYSTEM_UTC |
| 25. Own Vessel reference | PASS | Follow+valid LIVE own position tested |
| 26. Map Center reference | PASS | Settled actual center; geographic unit and runtime checks |
| 27. NO SOURCE AUTO | PASS | SYSTEM_UTC/MAP_CENTER, no fabricated vessel |
| 28. Follow ON | PASS | Own position if valid; otherwise center |
| 29. Follow OFF | PASS | Center even when own position elsewhere |
| 30. Manual DAY | PASS | Actual dropdown/keyboard override, runtime effective DAY while solar NIGHT |
| 31. Manual NIGHT | PASS | Actual override and dark map verified |
| 32. AUTO restore | PASS | Recorded requested AUTO/effective NIGHT after manual overrides |
| 33. Persistence | PASS | Existing QSettings; transient computed state not persisted |
| 34. No style reload | PASS | Real palette JS test throws on setStyle/addSource/camera calls |
| 35. Camera preservation | PASS | JS identity/value assertions; stable runtime across palette changes |
| 36. AIS | PASS | Existing architecture/tests retained; credentials/live vessel feed unavailable |
| 37. Squall | PASS | Existing tests plus severity/selection colour preservation |
| 38. Malaysia GIS | PASS | Same local directory/service; all18 GIS sources retained |
| 39. Project GIS | PASS | Existing spatial sources, feature selection and tests retained |
| 40. Bathymetry night | CODE VERIFIED | Brightness/saturation JS assertions; real asset visual check pending |
| 41. Satellite night | CODE VERIFIED | Truthful-image dimming/restore tested; real imagery visual check pending |
| 42. Attribution | PASS | Per-database attribution; local font licence/credits; no ENC claim |
| 43. No-internet map | PASS WITH LIMIT | HTTP-blocked WebEngine probe and35 UI snapshots; no real SEA package |
| 44. Asset availability | NOT INSTALLED | No production MBTiles found; no large map download attempted |
| 45. Installed package | ENGINE READY | Actual map store resolves no package; test packages isolated/temporary |
| 46. Tooling | PASS | CLI inspect/build-manifest/validate/install/reinstall/rollback all exit0 |
| 47. Documentation | PASS | `docs/offline-maps.md`, source links, schema/build/import/licensing/rollback |
| 48. Phase1 regression | PASS | Existing vessel/track/heading/COG/camera/follow tests |
| 49. Phase2 regression | PASS | Existing .gdsspatial/render/selection/fit tests |
| 50. Phase3 regression | PASS | Existing Squall trajectory/ETA/zones/selection/lifecycle tests |
| 51. Phase4/Malaysia regression | PASS | Existing provider/index/viewport/normalization/render tests |
| 52. py_compile | PASS | `app/ui/pages/nav/nav_page.py` |
| 53. compileall | PASS | `app main.py` |
| 54. Exact pytest | PASS |342 passed in26.56s |
| 55. Test total |342 |269 baseline+73 added |
| 56. Startup | PASS | Normal `python -u main.py`; local resources served; loadFinished True |
| 57. Visual validation | PARTIAL ACCEPTANCE | DAY/TWILIGHT/NIGHT, overrides, AUTO and supplied GIS checked; real tiled context pending |
| 58. Files created | PASS | Domain6; offline.js; glyph ranges/licences; tools/maps; tests; docs |
| 59. Files modified | PASS | NAV bridge/scheme/page, nav.js/css/index.html, .env.example only for this task |
| 60. Remaining work | ASSETS | Build/import licensed overview/SEA/bathymetry; imagery optional; validate real tiles visually |

Runtime evidence: `docs/diagnostics/offline-map-runtime.json` contains35 samples,
all with55 sources and241 layers, no map errors and zero HTTP requests intercepted.
At the diagnostic's initial fixed view,703 supplied GIS features rendered in all
three solar palettes. Subsequent window/camera interaction changed the viewport
and rendered feature count; palette updates retained the sources/layers. Own
marker stayed absent under NO SOURCE. Manual DAY, NIGHT and AUTO each appear in
the recorded payloads. The diagnostic uses a fixed UTC clock only in that tool;
normal `main.py` uses trustworthy telemetry/system UTC and does not auto-fit GIS.

The real Qt probe uncovered a missing-tile Fetch completion issue with
`QWebEngineUrlRequestJob.fail()`. Missing tile requests now return a finite
`application/json` error body (custom schemes have no HTTP status API), avoiding
an indefinitely pending body. MapLibre reports unavailable local tiles while
retaining operational overlays. Valid gzip MVT, PNG and local glyphs are tested
through the actual scheme with HTTP blocked. No error response contains fake
geography or imagery.

Created implementation files:
`app/nav/offline_maps/{__init__,mbtiles,manager,render_config,palette,controller}.py`,
`app/resources/map/offline.js`,
`app/resources/map/assets/glyphs/KlokanTech Noto Sans Regular/` (eight PBF ranges,
upstream README and OFL), `tools/maps/{maps,validate_runtime}.py`,
`tests/test_offline_maps.py`, `tests/nav_offline_runtime.cjs`,
`tests/offline_webengine_probe.py`, the two documentation files and diagnostics.

The build guidance references the primary MBTiles specification, NOAA equations,
Planetiler/OpenMapTiles projects and font repositories in `offline-maps.md`.
All live-provider credential/licence limitations from Phase4R remain unchanged.
Configure, VDR and VJR were not edited in this task. No auto-commit was made.

**B. OFFLINE MAP ENGINE CODE-COMPLETE — OFFLINE MAP ASSET PACKAGE PENDING**
