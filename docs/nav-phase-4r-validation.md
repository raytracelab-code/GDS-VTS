# NAV Phase 4R continuation validation

Date: 2 November 2026 (Asia/Dhaka).

## Inherited work and audit

Inspected git status, diff statistics, tracked diffs, the existing maritime
architecture, all real-provider adapters, map integration, tests and documentation
before making changes. The inherited tree passed **199 tests in 0.90s**.
The 148-test pre-4R baseline was supplied by the user; the working tree already
contained later changes. Untracked files contain both Phase 4 architecture and
Phase 4R work, so git cannot independently separate those earlier sessions.

| Piece | Initial audit | Continuation result |
|---|---|---|
| Canonical store, area controller, source health, cache, lifecycle, bridge, MapLibre layers and inspector | COMPLETE | Preserved; cache failure handling hardened |
| AISStream transport and Class A/B/static/AtoN normalization | COMPLETE | Existing offline tests pass; credentials absent |
| Overpass geometry/tag normalization and area cache | COMPLETE | Actual bounded response normalized successfully |
| Open Waters, OpenSeaMap and GEBCO references | COMPLETE | Public network checks pass |
| Copernicus Toolbox surface subsets and CF normalization | COMPLETE | Offline contracts pass; credentials/datasets absent |
| GFW license gates and canonical normalization | PARTIAL | Corrected JSON transport to the documented binary MVT response |
| BOEM/BSEE and EMODnet regional discovery/query/normalization | COMPLETE | Live region-specific diagnostics pass |
| NAVAREA VIII boundary | COMPLETE | Explicit NO_STABLE_MACHINE_API retained; no API invented |
| Final continuation validation/report | PARTIAL | Completed below |
| Requested provider adapters not started | NONE | None |

The GFW correction follows the provider's [fixed infrastructure contract](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/v3/datasets/fixed-infra-context-layer).
The existing endpoint was correct, but `request_json` could never read its MVT
response. The adapter now requests bytes and decodes them with the optional
`mapbox-vector-tile` package. Tile-local geometry is discarded in favor of actual
provider WGS84 latitude/longitude attributes. All enable/license/token gates execute
before importing the optional decoder or issuing a request.

An independent failure-path defect was also fixed: cache file inspection could
raise outside its exception handler, and a failed worker's fallback cache read
could then raise without emitting completion. That left the source busy forever.
Cache inspection now treats unreadable files as a miss, and worker fallback reads
cannot prevent completion, ERROR health, or later retries. No raw error text or
credentials are exposed. Two regression tests exercise these failures.

## Current real-network observations

These diagnostics operate outside the canonical runtime and never insert their
objects into NAV. Regional tests use public U.S./European coordinates. Production
provider flags and credentials were not changed.

| Provider | This session's result |
|---|---|
| Overpass | PASS at 22.25 N, 91.8 E, 1 NM: one actual AtoN/navigation light. The inherited 10 NM query returned an incomplete/error response and was rejected; this remains an upstream availability limitation, not an empty-data success. |
| GEBCO | PASS: GetCapabilities advertised GEBCO_LATEST; Web Mercator GetMap returned a 4,774-byte PNG. |
| BOEM/BSEE | PASS at 28.5 N, 90 W, 2 NM: 19 objects, comprising 2 wellheads and 17 pipelines. |
| EMODnet | PASS at 55 N, 2 E, 5 NM: 18 objects, comprising 1 wellhead, 2 wind farms, 5 pipelines, 7 cables and 3 wrecks. |
| Open Waters | PASS: public MapLibre style validation. This supersedes the inherited HTTP 403 observation; full style/tile rendering was not revalidated this session. |
| OpenSeaMap | PASS: HTTPS PNG validation. Production flag remains disabled; no browser security changes. |
| AISStream | NOT CONFIGURED: no enabled flag or API key in local environment. No live connection attempted. |
| Copernicus wave/current/SST/sea level | NOT CONFIGURED: username, password and all four dataset IDs absent. Toolbox not installed; credential-dependent requests skipped. |
| GFW | LICENSE DISABLED: enable/license acknowledgement/token absent. No live request attempted. Actual binary encode/decode integration passes offline. |
| NAVAREA VIII | NO_STABLE_MACHINE_API boundary retained. No structured warning feed or fabricated warning claimed. |

For the Bangladesh operating area, BOEM/BSEE and EMODnet are geographically out of
coverage; existing guards are tested to reject that area before issuing requests.
Their production flags are also unset locally. Network successes above refer only
to their separate in-coverage diagnostic areas.

The diagnostic tool now honors endpoint environment overrides, supports explicit
public Open Waters/OpenSeaMap checks, and allows a bounded Overpass diagnostic
radius without altering production configuration:

```powershell
python tools/check_maritime_providers.py overpass gebco boem emodnet
python tools/check_maritime_providers.py overpass openwaters openseamap --overpass-radius-nm 1
```

## Verification and runtime limits

- `python -m py_compile app/ui/pages/nav/nav_page.py`: PASS.
- `python -m compileall app main.py`: PASS.
- Final `python -m pytest -q --tb=short`: **202 passed in 3.13s**; no skips.
- This includes existing MapLibre JavaScript runtime tests, license/coverage gates,
  actual binary GFW tile encode/decode, and cache failure/retry regression tests.
- A sandboxed intermediate pytest run encountered temporary-directory/cache access
  denials. The full suite was rerun outside that sandbox and passed as shown above.
- `python -u main.py`: MainWindow constructed, shown, event loop entered;
  NAV loadFinished=True, operational JS sources initialized.
- Used the Computer Use skill to inspect the running NAV window: actual basemap,
  navigation controls and source-health readout render, with no generated targets.
- WebEngine logged nonfatal access-denied GPU/disk-cache warnings in the existing
  local profile. They did not prevent map rendering. That local profile was not
  deleted or reset. The development basemap also logged null numeric-expression
  warnings and missing POI sprite images (office, lift_gate, atm, sports_centre,
  gate). Basemap rendering continued; those underlying basemap issues remain
  outside this provider continuation. No confirmed remaining provider implementation
  defect was observed after the fixes; live credential-dependent paths remain unverified.
- Closed the validation window normally; `app.exec` returned and the process exited 0.
- This session did not repeat full manual rendering/selection/toggle validation for
  each optional provider; the inherited GEBCO visual validation remains historical.

## Files changed in this continuation

- `app/nav/maritime/adapters/base.py`: unreadable static cache handling.
- `app/nav/maritime/runtime.py`: protect fallback cache reads and deliver completion.
- `app/nav/maritime/adapters/gfw.py`: binary MVT transport and normalization bridge.
- `app/nav/maritime/requirements-providers.txt`: optional MVT decoder dependency.
- `tests/test_maritime_providers.py`: three regressions and updated license-gate mock.
- `tools/check_maritime_providers.py`: environment overrides and public diagnostics.
- `docs/maritime-sources.md`: corrected GFW transport and current report link.
- `docs/nav-phase-4r-validation.md`: this report.

All previously dirty/untracked files were preserved. No auto-commit, credentials,
synthetic production feeds, Configure/VDR/VJR edits, new maritime store or UI redesign.
The optional decoder and its dependencies were installed in the existing virtual
environment so the binary regression ran rather than skipped.

Remaining work is deployment configuration and validation: supply AISStream and
Copernicus settings (and its optional Toolbox), enable references/regionals as
appropriate, and perform live authenticated and full visual checks. GFW requires
explicit license acknowledgement and a token before any live test. NAVAREA VIII
requires a legitimate stable structured source before automatic warning ingestion.

B. NAV PHASE 4R CODE-COMPLETE — SOME PROVIDERS NOT CONFIGURED
