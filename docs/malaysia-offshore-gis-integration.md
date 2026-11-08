# Malaysia offshore GIS integration validation

Validated 8 November 2026. No commit created. The supplied local directory remains the data source, with optional GDS_MALAYSIA_GIS_PATH override.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Inherited work | PRESERVED | Phase 1?4/4R complete/in progress as inherited. Malaysia integration was NOT STARTED: no provider or manifest existed. Baseline 226 passed. |
| 2. Files inspected | PASS | Maritime modules/adapters, MapBridge, NAV page/map assets, tests, provider docs, all supplied GIS files; git status and diff inspected before edits. |
| 3. GeoJSON file count | 18 | 14 regional datasets and 4 supplemental facility files; macOS metadata excluded. |
| 4. Valid feature count | 10,313 | 10,268 retained after suppressing 45 duplicate labels. 10,326 source records total. |
| 5. Invalid feature count | 13 rejected | 11 invalid/degenerate geometries and 2 null well geometries. Other records/layers continue loading. |
| 6. CRS | PASS | 15 files declare CRS84; platforms_134/3/34 omit CRS and use RFC 7946 WGS84 semantics. Finite/range/topology checks applied; projected declarations rejected. |
| 7. Combined bounds | PASS | [98.022889, 1.263626, 120.264806, 9.030622], west/south/east/north. |
| 8. Platforms | 477 regional | Five platform-related files total: 707 raw records, 662 retained including 185 optional facility details, not wells. |
| 9. Pipelines | 742 retained / 745 raw | Three degenerate source lines rejected. Two dense map copies simplified; full geometry retained in index. |
| 10. Wells | 6,967 retained / 6,969 raw | Two null geometries rejected; dedicated offshore_wells category, separate from installations. |
| 11. Oil/gas fields | 491 | Restrained polygons; separate from PSC/development semantics. |
| 12. Production areas | 132 | Separate PRODUCTION subtype and toggle. |
| 13. Pre-development areas | 235 | Separate PRE_DEVELOPMENT subtype and toggle. |
| 14. Abandoned areas | 9 | Separate ABANDONED subtype and toggle. |
| 15. Ceased areas | 6 | Separate CEASED subtype and toggle. Additional development dataset contains 2 features. |
| 16. Awarded blocks | 111 retained / 116 raw | Five invalid polygons rejected; petroleum contracts, not navigation restrictions. |
| 17. Open blocks | 26 retained / 28 raw | Two invalid polygons rejected; separate petroleum block subtype. |
| 18. Basins | 26 | Petroleum basin reference polygons; default off. |
| 19. Seismic | 829 | Reference survey coverage; default off. Nine dense map copies simplified. |
| 20. FTG/geophysical | 30 retained / 31 raw | One self-intersecting polygon rejected. Actual survey metadata supports geophysical coverage classification. |
| 21. Duplicate files/features | PASS | Four supplemental files are layouts/crane coverage/reference zones/labels. Suppressed 45 matching point labels; preserved 384 intentional native-ID overlaps between field/status views. |
| 22. Provider implementation | PASS | Dedicated MalaysiaOffshoreGISProvider -> canonical normalization -> MaritimeObjectService -> maritimeStateChanged -> MapBridge -> MapLibre. No second operational state system. |
| 23. Spatial index | PASS | Shapely 2 STRtree; exact intersects predicate. Worker loads/validates/indexes once, checks file/manifest signatures for reload. |
| 24. Viewport filtering | PASS | Existing settled/debounced area controller and stale-generation protection. Indexed queries use current local reference bounds; online provider extents stay bounded. |
| 25. NO SOURCE behavior | PASS | Observed own_marker=false. Peninsular view 3,637 in area; Sabah view 57 in area. No vessel position was fabricated. |
| 26. Platform rendering | PASS | 33 installation symbols in final normal offshore view. Optional close-zoom names share icon collision placement; no emoji. |
| 27. Pipeline rendering | PASS | 181 unique pipelines drawn in final peninsular view. Restrained dashed brown styling; distinct from track, project pipelines and cables. |
| 28. Well rendering | PASS | Initially off, hidden at low zoom even when enabled, 213 individual points drawn at zoom 11.219. Metadata selection verified; original off preference restored. |
| 29. Field rendering | PASS | 156 field polygons in final peninsular view; six in Sabah view. Transparent fills and zoom-gated names. |
| 30. Block rendering | PASS | Awarded/open toggles checked manually; four awarded and one open block rendered in close view. |
| 31. Basin rendering | PASS | Toggle checked manually; one subtle basin polygon rendered in test area. |
| 32. Survey rendering | PASS | 29 seismic areas rendered when enabled; separate Sabah view rendered six FTG coverages. Final survey styling is subdued, without long identifier labels. |
| 33. Layer controls | PASS | 18 manifest-driven controls in MALAYSIA OFFSHORE GIS; operational controls first. Existing QSettings persistence; temporary validation changes restored. |
| 34. Default visibility | PASS | Platforms, pipelines, fields and producing areas ON. Wells, other status areas, blocks, basins, surveys and facility details OFF. |
| 35. Source-status panel | PASS | MALAYSIA GIS READY / LOCAL GIS, total and current-area counts, rejected/null counts. Never labelled LIVE or official. |
| 36. Inspectors | PASS | Actual platform, pipeline and well clicks verified. Readable available attribute rows and category headings; absent/null placeholders hidden. Field/PSC/basin/survey mappings covered by tests. |
| 37. Show Object | PASS | Actual selected pipeline fit verified without enabling Follow; point/geometry behavior also covered by map tests. |
| 38. Performance | PASS | One index; no feature widgets/timers/sources/layers. 18 GIS sources, final 82 style layers. Hidden dense geometry omitted from Qt payload. Representative query about 4 ms; full audit load 56 s during concurrent validation, recorded without a timing assertion. |
| 39. AIS coexistence | TESTS PASS | No configured AISStream key during manual run; successful live AIS transport was not claimed. Existing normalization/lifecycle/map tests pass. |
| 40. Overpass coexistence | TESTS PASS | Adapter remains enabled; external timeout/backoff/HTTP 502 observed. Successful live retrieval was not demonstrated. Conservative display-only duplicate preference retains both source records. |
| 41. GEBCO coexistence | PASS | Actual READY response and bathymetry visible. Late raster arrivals remain below customer GIS, covered by regression test. |
| 42. Squall coexistence | TESTS PASS | Existing event/map click priority, cross-selection, ETA/trajectory/impact regression tests preserved. No synthetic production event inserted. |
| 43. Phase 1 regression | TESTS PASS | Own vessel/track/heading/follow/camera controls preserved. Live telemetry unavailable for manual vessel validation. |
| 44. Phase 2 regression | PASS | TEST Jampuk .gdsspatial package remains separate and active/out of view; package/selection tests unchanged and passing. |
| 45. Phase 3 regression | TESTS PASS | Squall event/selection/map tests unchanged and passing. |
| 46. Phase 4R regression | TESTS PASS | Existing online providers, source health, cache, generation handling and bridges preserved; all tests pass. |
| 47. py_compile | PASS | .venv/Scripts/python.exe -m py_compile app/ui/pages/nav/nav_page.py |
| 48. compileall | PASS | .venv/Scripts/python.exe -m compileall app main.py |
| 49. pytest exact result | PASS | 263 passed in 41.19s. Command: .venv/Scripts/python.exe -m pytest -q --tb=short. Normal Windows temp/cache access used after sandbox ACL restrictions. |
| 50. Total tests | 263 | Inherited 226 + 37 net additional parametrized cases. No existing tests deleted or weakened. |
| 51. Startup | PASS | Actual python -u main.py startup checked. Final real-app diagnostics ended cleanly with exit 0. |
| 52. Manual visual validation | PASS | Peninsular/Dulang offshore scene plus actual Dent/Sabah FTG extent. Platform/pipeline/well metadata, Show Object, zoom and reference toggles inspected. GIS renderer errors: none. |
| 53. Files created | 14 | See complete list below; source GeoJSON was not rewritten. |
| 54. Files modified | 13 | See complete list below. Inherited unrelated edits were preserved; Configure, VDR and VJR were not edited. |
| 55. Licence/provenance | NOT YET RECORDED | LICENCE / AUTHORITY: NOT YET RECORDED. Classified LOCAL_GIS, static/reference customer data. |
| 56. Remaining issues | RECORDED | 13 malformed/null source records excluded; licence/authority unknown. AIS credentials missing and Overpass external failures limit live-provider manual evidence. No confirmed remaining Malaysia GIS runtime defect. |

## Files created

- `app/nav/maritime/malaysia_config.py`
- `app/nav/maritime/adapters/malaysia.py`
- `app/nav/maritime/inspector.py`
- `data/maritime/malaysia/manifest.json`
- `tests/test_malaysia_gis.py`
- `tests/nav_malaysia_runtime.cjs`
- `tools/audit_malaysia_gis.py`
- `tools/validate_malaysia_nav.py`
- `docs/diagnostics/malaysia-gis-audit.json`
- `docs/diagnostics/malaysia-nav-runtime.json`
- `docs/diagnostics/malaysia-nav-acceptance.json`
- `docs/diagnostics/malaysia-nav-final.json`
- `docs/diagnostics/malaysia-nav-ftg.json`
- `docs/malaysia-offshore-gis-integration.md`

## Files modified in this task

- `app/nav/maritime/models.py`
- `app/nav/maritime/service.py`
- `app/nav/maritime/render_state.py`
- `app/nav/maritime/source_health.py`
- `app/nav/maritime/config.py`
- `app/nav/maritime/providers.py`
- `app/nav/maritime/runtime.py`
- `app/nav/maritime/area_controller.py`
- `app/resources/map/nav.js`
- `app/ui/pages/nav/nav_page.py`
- `requirements.txt`
- `.env.example`
- `docs/maritime-sources.md`

The inherited worktree already contained changes to main.py, MapBridge, MainWindow, .gitignore, provider modules/tests and other documentation. Those edits were not discarded or committed.

## Evidence

- [Full file/property/CRS/bounds audit](diagnostics/malaysia-gis-audit.json)
- [Acceptance summary](diagnostics/malaysia-nav-acceptance.json)
- [Final peninsular runtime](diagnostics/malaysia-nav-final.json)
- [Sabah FTG runtime](diagnostics/malaysia-nav-ftg.json)
- [Source and operation documentation](maritime-sources.md)

A. MALAYSIA OFFSHORE GIS INTEGRATION ACCEPTED
