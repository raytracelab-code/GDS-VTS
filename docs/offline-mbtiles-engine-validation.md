# Offline MBTiles engine continuation

Scope: engine only. Inspected `git status`, `git diff --stat`, `git diff`,
untracked offline modules, package tooling, NAV source integration and tests.
Continued the inherited workspace without reverting or restarting implementation.
Existing palette/UI/provider changes were preserved and not edited in this pass.
Configure, VDR, VJR, Malaysia GIS, AIS, Overpass and Copernicus were not modified.
No commit, asset download or production map generation was performed.

## Engine status

| Check | Result | Evidence / implementation |
|---|---|---|
| Local MBTiles reader | PASS | Indexed on-disk queries; bounded tile payloads/cache; synchronized connections |
| Vector PBF/MVT | PASS | Raw vector bytes and structural validation; real Qt response tested |
| Raster tiles | PASS | PNG, JPG/JPEG, WEBP decode validation; maximum 4096 pixels per dimension; real Qt PNG response tested |
| XYZ to TMS | PASS | `tms_y = (2**z - 1) - xyz_y`; limits and known values tested |
| gzip | PASS | Magic-byte detection; bounded decompression; truncated/oversized input rejected |
| Metadata | PASS | Required metadata, bounds, center, zoom, format, scheme and vector layer metadata |
| Missing/corrupt data | PASS | Missing DB/tile, bad SQLite, malformed vectors, gzip and metadata tests |
| SQLite access | PASS | URI `mode=ro`, `query_only`, indexed lookup and bounded SQLite work/cache |
| gds local serving | PASS | `gds://tiles/{package_id}/{role}/{z}/{x}/{y}.{format}`; worker reads, Qt reply buffers |
| Missing-tile serving | PASS | Finite JSON error body avoids inherited Qt Fetch error-body hang |
| MapLibre sources | PASS | Local vector/raster source templates, metadata bounds/zoom, separate raster role |
| Manifest / validation | PASS | Version1 contract; SHA256; file/role/coverage checks; safe paths |
| Package storage / registry | PASS | `%LOCALAPPDATA%\GDS VTS\maps`; staged install; atomic active pointer; retained revision / rollback |
| Registry damage | FIXED | Non-object JSON, invalid fields, invalid encoding/JSON and oversized registry fall back safely |
| No installed package | PASS | Actual discovery returns no package; explicit OFFLINE MAP NOT INSTALLED state; package disappearing during style setup also falls back safely |
| Online fallback | PASS | Existing default disabled; explicit environment opt-in only |

The basemap and bathymetry routes include the selected package ID, for example:

```text
gds://tiles/sea-maritime/basemap/{z}/{x}/{y}.pbf
gds://tiles/sea-maritime/bathymetry/{z}/{x}/{y}.png
```

Existing `tools/maps/maps.py` supplies inspect, validate, build-manifest, install
and rollback commands. Existing `GDS_MAP_PACKAGE_PATH`, `GDS_MAP_DEFAULT_PACKAGE`,
`GDS_MAP_TILE_CACHE_SIZE` and `GDS_MAP_ALLOW_ONLINE_FALLBACK` support local discovery
and configuration. See `offline-maps.md` for the inherited package contract and
import instructions.

## Inherited work

- `app/nav/offline_maps/manager.py`: bounded registry reads to64KiB; reject
  non-object JSON and malformed revision values without a startup exception;
  preserve a valid current revision when the previous field is damaged; reject
  Windows-invalid filename characters; reject boolean manifest schema versions.
- `tests/test_offline_maps.py`:17 additional engine cases covering those failures,
  including fallback to a valid configured local package.
- This engine-specific validation report originally recorded 359 passing tests.

The many other changes shown by Git were inherited. No tests were deleted or weakened.
The inherited suite includes isolated temporary tile fixtures and an actual Qt
WebEngine integration subprocess with HTTP blocked. These fixtures are test data,
not installed or represented as real map assets.

## Latest continuation changes

- `app/nav/offline_maps/mbtiles.py`: raster validation now decodes images with
  the same Qt codecs as NAV, checks stream completion markers/container length,
  and checks dimensions before decoding. Signature-only truncated images no
  longer pass. Supported raster dimensions are 1 through 4096 per axis.
- `app/nav/web_scheme.py`: a package that disappears or becomes invalid between
  discovery and render configuration falls back to the empty local style.
- `tests/test_offline_maps.py`: eight added regression cases cover truncated
  PNG/JPG/JPEG/WebP at opening and during later tile reads, bounded raster
  dimensions, corrupt PNG image data, and package removal/corruption at startup.
- This report was updated. Palette, NAV presentation, Configure, VDR, VJR and
  external provider implementations were not edited during this continuation.

## Exact verification

Latest inherited baseline: **359 passed in 24.42s**.

```powershell
.\.venv\Scripts\python.exe -m py_compile app\ui\pages\nav\nav_page.py
.\.venv\Scripts\python.exe -m compileall app main.py
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

Both compilation commands passed. Exact final pytest: **367 passed in 24.71s**.
The test count increased by eight from the inherited baseline; no tests were removed.
`git diff --check` passed. Package discovery checked the installed storage and
configured fallback paths and returned `NONE`.

Remaining work: obtain/build and import a genuine licensed map package, then
validate its real geographic coverage and appearance. No large map assets were
downloaded or generated. Palette development is outside this continuation.

**OFFLINE MAP ENGINE READY**  
**OFFLINE MAP ASSET NOT INSTALLED**

**B. OFFLINE MBTILES ENGINE CODE-COMPLETE — MAP ASSET PENDING**
