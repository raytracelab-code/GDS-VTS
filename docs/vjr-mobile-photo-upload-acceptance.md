# VJR mobile photo acceptance record

Date: 2026-11-19. No commit was created. Existing VJR/UI changes and unrelated
working-tree edits were preserved. No VDR, NAV/map, PDF, serial or BLE implementation
was edited for this feature.

## Results

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline | Recorded | Native-display baseline: 722 passed, 4 failed; existing VDR wide-grid display assertions. |
| 2. Departure photo model | Pass | Independent optional relative attachment reference. |
| 3. Arrival photo model | Pass | Independent optional relative attachment reference. |
| 4. Local upload server | Pass | On demand, bounded standard-library HTTP; no cloud. |
| 5. LAN IP selection | Pass | Qt5/Qt6 adapters; physical LAN preferred; selectable network. Host Wi-Fi detected at 192.168.0.225. |
| 6. QR generation | Pass | Local QR PNG; fresh session on every generation. |
| 7. Token security | Pass | Random 256-bit bearer token; report/slot bound; excluded from logs. |
| 8. Token expiration | Pass | Ten-minute monotonic expiry; cancel, regenerate, single-use and attempt cap tested. |
| 9. Mobile upload page | Implemented | Responsive 480px maximum, viewport meta and 50px touch controls; live browser visual check unavailable because browser host is unavailable. |
| 10. Camera/gallery input | Implemented | Separate rear-camera capture and gallery controls; physical phone pending. |
| 11. File-type validation | Pass | JPEG/JPG/PNG only; extension and MIME checked. |
| 12. Image-content validation | Pass | Actual format verified and fully decoded; malformed/mismatched data rejected. |
| 13. File-size validation | Pass | 15 MiB limit; oversize rejected before storage. |
| 14. Orientation correction | Pass | EXIF rotation test; derived preview/export omit rotation metadata. |
| 15. Photo storage | Pass | Writable app-local immutable attachments; original retained. |
| 16. Autosave | Pass | Atomic report save before phone receives success. |
| 17. Restart recovery | Pass | Both slots persist; missing images handled explicitly. |
| 18. Desktop live update | Pass | Queued Qt signal; test records mutations on GUI thread. |
| 19. Preview | Pass | Generated screenshots for landscape Departure and portrait Arrival. |
| 20. Replace | Pass | Old attachment retained through failed/cancelled replacement and undo. |
| 21. Delete | Pass | Confirmation, autosave, undo retention and safe cleanup. |
| 22. Server cleanup | Pass | Five start/stop cycles, partial requests, worker/port release, delivery abort. |
| 23. Wrong-token handling | Pass | Friendly invalid/expired/used/cancelled responses; no stack trace. |
| 24. Session isolation | Pass | Independent slot uploads; stale report delivery rejected. |
| 25. Excel Departure image | Automated pass | Correct original sheet/region, aspect, centering, bounds and logo retention; native visual review pending firewall prompt. |
| 26. Excel Arrival image | Automated pass | Correct original sheet/region, aspect, centering, bounds and logo retention; native visual review pending firewall prompt. |
| 27. Excel no-photo case | Pass | No-photo, Departure-only, Arrival-only and both-photo cases. |
| 28. Source template unchanged | Pass | Immutable template hash and unrelated OOXML parts checked. |
| 29. Mobile manual test | Pending | GDS VTS launched with `python -u main.py`; no physical mobile upload claimed. |
| 30. Firewall behavior | Pass / handoff | Native Windows security prompt observed; no firewall changes made or automated. User must handle it. |
| 31. Normal pytest | Pass | 754 passed in 243.06s. |
| 32. Legacy pytest | Pass | 753 passed, 1 skipped in 307.26s. |
| 33. Compileall | Pass | Both environments, app/tools/tests, exit 0. |
| 34. Packaged-build compatibility | Legacy built | Controlled Python 3.8/PySide2 PyInstaller build completed. Both specs updated. Modern rebuild not performed: PyInstaller is absent in modern environment. Physical Win7 not tested. |
| 35. Documentation | Complete | Architecture, usage, storage, LAN/firewall, security, dependencies, export and limitations documented. |
| 36. Files modified | Recorded | Task files and complete final working-tree inventory below. |
| 37. Remaining limitations | Explicit | Physical phone/browser, native Excel visual review and physical Win7 validation pending; modern package not rebuilt. Trusted LAN HTTP; JPEG/PNG only. |

## Commands and evidence

Full suites used the established offscreen font setup to avoid the native-display
baseline's VDR grid width limitation. Test data was outside the Git tree because
the repository hygiene test detects fixture files inside it. Sandbox runs without
temporary-folder access encountered access-denied errors; final runs had that access.

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR=(Resolve-Path build/vdr-native-test-fonts).Path
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-photo-modern-final-3
.\.venv-win7\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-photo-legacy-final-3
.\.venv\Scripts\python.exe -m compileall -q app tools tests
.\.venv-win7\Scripts\python.exe -m compileall -q app tools tests
.\.venv-win7\Scripts\python.exe -m PyInstaller --noconfirm --distpath build/vjr-photo-package-legacy --workpath build/vjr-photo-pyi-legacy gds_vts_win7.spec
```

Final full-suite logs: `build/vjr-photo-normal-final.log` and
`build/vjr-photo-legacy-final.log`. After the final bounded socket-drain deadline
adjustment, focused photo tests passed again: modern **28 passed in 19.07s**,
legacy **28 passed in 21.42s**. Both compileall runs were then repeated successfully.
The Windows socket cleanup fixes early-close resets when rejecting unread POST
bodies; response cleanup is bounded by both 64 KiB and a 0.2-second total deadline.

Legacy package: `build/vjr-photo-package-legacy/GDS VTS/`. Preserve the full onedir
folder. Build log: `build/vjr-photo-package-legacy.log`. Existing Shapely dependency
warnings are emitted during analysis; the controlled spec separately includes its
DLLs. This is a build check, not a packaged-runtime or Windows 7 hardware acceptance.

Workbook: [VJR_excel_photo_acceptance.xlsx](evidence/VJR_excel_photo_acceptance.xlsx).
Evidence: [Departure preview](evidence/vjr-mobile-photo/departure_preview.png),
[Arrival preview](evidence/vjr-mobile-photo/arrival_preview.png),
[QR waiting card](evidence/vjr-mobile-photo/qr_waiting.png).
The pictures are synthetic test patterns. Pictured QR tokens are invalidated.

Native Excel opened the workbook read-only, with no repair prompt observed, but a
Windows Firewall security prompt overlaid it before photo-sheet visual inspection.
That check remains pending. The first sandboxed app-launch attempt also produced
a Python breakpoint dialog; the normal-context launch reached GDS VTS successfully.
No Windows security settings or permissions were changed. No browser or physical
camera success is inferred from automated HTTP/Qt tests.

## Task file inventory

Created:

- `app/vjr/photo_storage.py`
- `app/vjr/photo_server.py`
- `app/vjr/photo_network.py`
- `app/vjr/photo_excel.py`
- `app/ui/pages/vjr_photos.py`
- `app/resources/vjr/mobile_photo.html`
- `tests/test_vjr_photos.py`
- `tests/test_vjr_photo_ui.py`
- `tools/verify_vjr_photo_acceptance.py`
- `docs/vjr-mobile-photo-upload.md`
- `docs/vjr-mobile-photo-upload-acceptance.md`
- `docs/evidence/VJR_excel_photo_acceptance.xlsx`
- `docs/evidence/vjr-mobile-photo/arrival_preview.png`
- `docs/evidence/vjr-mobile-photo/arrival_test.jpg`
- `docs/evidence/vjr-mobile-photo/departure_preview.png`
- `docs/evidence/vjr-mobile-photo/departure_test.jpg`
- `docs/evidence/vjr-mobile-photo/qr_example.png`
- `docs/evidence/vjr-mobile-photo/qr_waiting.png`

Extended existing work, including files that were already untracked:

- `app/vjr/model.py`
- `app/vjr/excel.py`
- `app/ui/pages/vjr_workspace.py`
- `app/ui/pages/vjr_widgets.py`
- `tests/test_vjr_ui.py`
- `tests/test_vjr_redesign.py`
- `docs/vjr-excel-cell-map.md`
- `requirements.txt`
- `requirements-win7.txt`
- `gds_vts.spec`
- `gds_vts_win7.spec`

The following working-tree inventory also includes earlier task/user changes;
`git diff --stat` omits untracked files and therefore is not the complete feature
diff. No automatic commit, reset or cleanup of earlier work was performed.

```text
 M .saropa/diagnostics/history.json
 M app/ui/components/top_tabs.py
 M app/ui/pages/vjr_page.py
 M gds_vts.spec
 M gds_vts_win7.spec
 M requirements-win7.txt
 M requirements.txt
 M tests/test_nav_map_first.py
 M tests/test_vdr_navigation.py
?? app/resources/templates/vjr_template.xlsx
?? app/resources/vjr/mobile_photo.html
?? app/ui/pages/vjr_photos.py
?? app/ui/pages/vjr_widgets.py
?? app/ui/pages/vjr_workspace.py
?? app/vjr/__init__.py
?? app/vjr/calculations.py
?? app/vjr/excel.py
?? app/vjr/model.py
?? app/vjr/photo_excel.py
?? app/vjr/photo_network.py
?? app/vjr/photo_server.py
?? app/vjr/photo_storage.py
?? app/vjr/schema.py
?? app/vjr/store.py
?? app/vjr/validation.py
?? docs/evidence/VJR_excel_export_acceptance.xlsx
?? docs/evidence/VJR_excel_photo_acceptance.xlsx
?? docs/evidence/vjr-mobile-photo/arrival_preview.png
?? docs/evidence/vjr-mobile-photo/arrival_test.jpg
?? docs/evidence/vjr-mobile-photo/departure_preview.png
?? docs/evidence/vjr-mobile-photo/departure_test.jpg
?? docs/evidence/vjr-mobile-photo/qr_example.png
?? docs/evidence/vjr-mobile-photo/qr_waiting.png
?? docs/evidence/vjr-ui-redesign/01_overview_header.png
?? docs/evidence/vjr-ui-redesign/02_general_information.png
?? docs/evidence/vjr-ui-redesign/03_core_crew.png
?? docs/evidence/vjr-ui-redesign/04_contractors.png
?? docs/evidence/vjr-ui-redesign/05_waypoint_plan.png
?? docs/evidence/vjr-ui-redesign/06_departure_report.png
?? docs/evidence/vjr-ui-redesign/07_departure_deck_space.png
?? docs/evidence/vjr-ui-redesign/08_departure_inventory.png
?? docs/evidence/vjr-ui-redesign/09_arrival_report.png
?? docs/evidence/vjr-ui-redesign/09b_arrival_departure_reference.png
?? docs/evidence/vjr-ui-redesign/10_voyage_progress.png
?? docs/evidence/vjr-ui-redesign/10b_voyage_weather_and_remarks.png
?? docs/evidence/vjr-ui-redesign/11_departure_photo_reserved.png
?? docs/evidence/vjr-ui-redesign/12_arrival_photo_reserved.png
?? docs/evidence/vjr-ui-redesign/13_responsive_1920.png
?? docs/evidence/vjr-ui-redesign/14_responsive_1600.png
?? docs/evidence/vjr-ui-redesign/15_responsive_1366.png
?? docs/evidence/vjr-ui-redesign/16_vjr_comparison.png
?? docs/evidence/vjr-ui-redesign/17_vdr_reference.png
?? docs/evidence/vjr-ui-redesign/18_vdr_vjr_side_by_side.png
?? docs/evidence/vjr-ui-redesign/19_inline_validation.png
?? docs/evidence/vjr-ui-redesign/20_full_capacity_crew.png
?? docs/evidence/vjr-ui-redesign/README.md
?? docs/evidence/vjr-ui-redesign/manifest.json
?? docs/evidence/vjr-ui-redesign/scope-verification.json
?? docs/vjr-excel-cell-map.md
?? docs/vjr-excel-export-acceptance.md
?? docs/vjr-mobile-photo-upload-acceptance.md
?? docs/vjr-mobile-photo-upload.md
?? docs/vjr-ui-redesign-acceptance.md
?? tests/test_vjr.py
?? tests/test_vjr_photo_ui.py
?? tests/test_vjr_photos.py
?? tests/test_vjr_redesign.py
?? tests/test_vjr_ui.py
?? tests/vjr_fixture.py
?? tools/capture_vjr_ui_evidence.py
?? tools/verify_vjr_acceptance.py
?? tools/verify_vjr_photo_acceptance.py

 .saropa/diagnostics/history.json | 10 ++++++++++
 app/ui/components/top_tabs.py    |  5 ++---
 app/ui/pages/vjr_page.py         |  7 +++++--
 gds_vts.spec                     |  2 +-
 gds_vts_win7.spec                |  2 +-
 requirements-win7.txt            |  3 +++
 requirements.txt                 |  4 ++++
 tests/test_nav_map_first.py      |  4 ++--
 tests/test_vdr_navigation.py     |  9 ++++++---
 9 files changed, 34 insertions(+), 12 deletions(-)
```
