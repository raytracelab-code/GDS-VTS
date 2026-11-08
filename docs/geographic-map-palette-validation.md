# Geographic AUTO map palette

Continued the inherited uncommitted palette/controller/toolbar implementation.
The offline MBTiles reader, package manager, tile routes and validation were not
modified. Configure, VDR and VJR were not modified. No assets were downloaded,
no vessel feed was fabricated, and no commit was made.

## Implementation

- `app/nav/offline_maps/palette.py`: deterministic NOAA fractional-year solar
  equations, leap-year handling, geometric elevation and UTC normalization.
  Source: https://gml.noaa.gov/grad/solcalc/solareqns.PDF
  DAY >=0 degrees; TWILIGHT >=-6 and <0; NIGHT <-6 on first calculation.
  Existing symmetric0.25-degree hysteresis retained around both thresholds.
- `app/nav/offline_maps/controller.py`: one repeating60s timer plus one700ms
  single-shot map-settle debounce. Fresh valid LIVE GNSS Date+UTC has priority,
  otherwise system UTC. GNSS_UTC is the internal GNSS source label. Follow ON
  with a valid LIVE position uses OWN_VESSEL; all other cases use MAP_CENTER.
  Before a center is available, FALLBACK(0,0) is explicit and is never an own
  vessel. Sub0.01-degree movement is ignored relative to the last calculation.
  Reference changes over1 degree reset hysteresis. UTC timestamps are included
  in diagnostics. Logs are DEBUG-only and emitted on mode/state/reference-type
  changes. Only requested mode is persisted under nav/palette.
- `app/ui/pages/nav/nav_page.py`: existing compact AUTO/DAY/NIGHT toolbar retained;
  Follow changes now notify the authoritative controller immediately.
- `app/resources/map/offline.js`: explicit role registry per map; paint-only
  updates and250ms transitions; repeated effective-state updates skip repaint.
  Basemap water/land/coast/roads/boundaries/labels have separate palette colors.
  GIS point/line colors lighten without increasing polygon fills/opacity.
  Severity expressions and selections remain unchanged. Raster brightness,
  saturation and contrast change without changing opacity/source data; DAY
  restores original raster brightness/saturation. Own Vessel's CSS color lightens.

## Automated checks

Baseline before edits: **367 passed in24.59s**.

Final full suite: **411 passed in25.94s** (+44 tests; no removals).

Both requested compilation commands and git diff --check passed.

`tests/test_map_palette.py` adds44 deterministic cases covering Malaysia,
Bangladesh, longitude-dependent states, twilight/hysteresis boundaries, invalid
references, Follow transitions, NO SOURCE/stale/lost/waiting modes, GNSS/system
UTC, UTC offset normalization, persistence, manual overrides, debounced map
centers, movement throttling, repeating timer ownership, polar/date-line values
and immediate Follow toolbar dispatch.

`tests/nav_offline_runtime.cjs` extends the existing real-JS behavior checks for
all ten roles, independent map registries, unowned layers, selection/severity,
source and layer identities, camera, visibility, raster opacity and restoration,
late layer registration and suppression of same-state paint writes. Its doubles
throw if palette code invokes style reload, source creation or camera movement.

The complete suite also exercises Phase1 vessel/track/Follow/camera controls,
Phase2 spatial packages and selections, Phase3 Squall geometry/selection,
Malaysia GIS layers/visibility/selection, and the offline engine including real
Qt WebEngine gzip-vector/raster tile requests.

## Runtime and visual checks

Launched the requested `.\.venv\Scripts\python.exe -u main.py`: window shown,
local resources loaded and NAV ready. Visually exercised manual DAY, manual
NIGHT and return to AUTO with NO SOURCE. The application shell stayed unchanged.

Ran `tools/maps/validate_runtime.py --seconds65` with diagnostic-only fixed UTC
for AUTO DAY, TWILIGHT and NIGHT, using actual local Malaysia GIS. Observed all
three toolbar states and palettes. WebEngine HTTP was blocked. The runtime
report records real source/layer identities, error events, rendered GIS and
before/after camera/layer-visibility/source checks around palette applications.
This instrumentation distinguishes deliberate/operator camera movement from
palette side effects.

Evidence: `docs/diagnostics/geographic-palette-runtime.json`.
The final diagnostic exited successfully:12 snapshots,55 sources,241 layers,
up to759 rendered local GIS features,11 palette applications with camera/source/
layer-visibility preservation checks all true, and zero MapLibre errors. The
camera_matches_initial field may be false after map movement; camera_preserved
measures directly across each palette application and remained true.

Remaining visual acceptance: real basemap/bathymetry/satellite assets are absent;
no live Own Vessel/AIS/Squall feed was available. Those visual cases remain
pending; their state-preservation paths are covered by automated tests. Runtime
provider warnings (e.g. Overpass backoff and rejected existing GIS records) are
independent of the palette and their implementations were not changed.

## Files in this continuation

Created: this report; `tests/test_map_palette.py`;
`docs/diagnostics/geographic-palette-runtime.json`.

Modified: `app/nav/offline_maps/palette.py`,
`app/nav/offline_maps/controller.py`, `app/resources/map/offline.js`,
`app/ui/pages/nav/nav_page.py`, `tests/nav_offline_runtime.cjs`,
`tools/maps/validate_runtime.py`, `docs/offline-maps.md`.

All other uncommitted workspace changes were inherited and preserved.
