# Regional expansion file audit

No commit was created. Existing professional NAV edits were retained.

## Created for this expansion

| File | Purpose |
|---|---|
| `app/nav/offline_maps/regions.py` | Official catalog discovery, profiles, resumable downloads and disk planning |
| `app/nav/offline_maps/regional.py` | Viewport resolution, bounded reader pool and shared regional render configuration |
| `app/resources/map/regions.js` | Settled-view source activation, overlap ordering, cleanup and overview fallback |
| `app/ui/pages/nav/map_regions_dialog.py` | Compact NAV package management dialog |
| `tools/maps/install_geofabrik_regions.py` | List, dry-run, install, resume and explicit update tooling |
| `tests/test_map_regions.py` | Catalog, registry, reader, download and viewport regressions |
| `tests/test_map_regions_ui.py` | Package-management UI behavior |
| `tests/nav_regions_runtime.cjs` | Repeated real-script source lifecycle and operational-state contracts |
| `docs/offline-regions.md` | Operation, installation and resource-limit documentation |

New JSON audits in this directory record the official catalog, initial/full
download plans, the first and resumed installation passes, preflight/inventory,
and real Malaysia/Thailand/Bangladesh/PNG/Australia runtime routes. These are
metadata and diagnostics, not production map databases. Runtime logs are ignored
by Git.

## Extended existing files

| File | Expansion change |
|---|---|
| `app/nav/offline_maps/manager.py` | Independent regional pointers, atomic registry, locking, enable/disable, rollback and protected removal |
| `app/nav/web_scheme.py` | Route existing tile paths to installed packages; bounded readers and safe reload |
| `app/nav/map_bridge.py` | Regional status, reader retention and configuration signals |
| `app/resources/map/index.html` | Load the regional lifecycle module |
| `app/resources/map/nav.js` | Reuse settled-map reporting and accept package configuration updates |
| `app/resources/map/offline.js` | Release palette registry entries when regional layers are removed |
| `app/ui/pages/nav/nav_page.py` | NAV-only management entry and status/configuration wiring |
| `tools/maps/import_shortbread.py` | Independent regional installation and staging guards; source bytes unchanged |
| `tools/maps/validate_runtime.py` | Regional routes, fixed diagnostic palettes, source/reader and HTTP audits |

## Inherited work preserved

The existing uncommitted platform, pipeline, glow, inspector and legend changes
remain in `nav.css`, `nav.js`, `offline.js`, `nav_page.py`,
`presentation_widgets.py`, `tests/test_nav_presentation.py`,
`tests/nav_visual_runtime.cjs`, `tests/test_nav_visual.py`, and the earlier
professional-UI diagnostic. Those presentation changes were not restarted or
reverted.

The MBTiles reader, shared Shortbread style adapter, solar controller/calculation,
Malaysia GIS provider, AIS/Squall/telemetry services, Configure, VDR and VJR were
not changed by this expansion. Production MBTiles remain under LOCALAPPDATA.
