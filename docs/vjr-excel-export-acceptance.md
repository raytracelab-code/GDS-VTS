# VJR implementation and Excel export acceptance

Validation date: 19 November 2026 (Asia/Dhaka). No commit was created.

## Scope and source

The source was located at `C:\Users\rayha\Downloads\Untitled spreadsheet.xlsx`.
The bundled `app/resources/templates/vjr_template.xlsx` is an exact binary copy.
Both retain SHA-256 `04e1ad4b53066f05475c962f05ac39f918e579ac1ee5b1bb0dd5f7634961d4e8` after export and read-only Excel review.
The existing `.saropa/diagnostics/history.json` change was present before this task and was preserved.

The baseline normal command, `.venv/Scripts/python.exe -m pytest -q --tb=short`,
returned **648 passed, 5 failed in 192.93s**. The five failures were existing VDR
wide-grid assertions: the native display capped a requested 2100-pixel window.
The initial legacy command returned **431 passed, 1 skipped, 221 errors in 103.81s**,
with temporary-directory access errors. Neither result was treated as a clean baseline.

Subsequent desktop regression runs encountered a Windows native Qt/COM exception
while setting up an existing VDR test window. Offscreen runs isolated this display
issue. Map-download tests require temporary directories outside Git; the existing
`build/prepare_vdr_test_fonts.py` supplies native font families to offscreen Qt.
No production map, VDR, font, compatibility or sensor code was changed to fix these
environment constraints.

## Implementation evidence

| Check | Result | Notes |
| --- | --- | --- |
| 1. Baseline | Recorded | Actual results above; user changes preserved |
| 2. Source template located | Pass | Exact Downloads workbook, eight expected sheets |
| 3. Template bundled | Pass | Original bytes and hash; both existing PyInstaller specs bundle app/resources |
| 4. Sheet structure preserved | Pass | Order, names, hidden state, layout, merges, dimensions, styles and validations |
| 5. GDS Meta | Pass | Explicit D7:D14, D26:D27 map; current identity; generated UTC timestamp |
| 6. Core Crew | Pass | Add/edit/remove, dates, sequential mapping, 200-row limit |
| 7. Crew Working Days | Pass | Arrival report date preferred, then departure; inclusive day count; materialized |
| 8. Contractors | Pass | Add/edit/remove, name/vendor/passport/nationality/remarks, 200-row limit |
| 9. Waypoint Plan | Pass | DMS components, direction, course, speed, remarks; 30 rows |
| 10. Departure General Information | Pass | Captain, preparer/checker, phones, drafts, requirements, linked identity and derived counts |
| 11. Departure Information | Pass | Calendar date, nullable 24-hour time, location and remarks |
| 12. Estimated Arrival | Pass | Calendar date, 24-hour time, destination and remarks |
| 13. Departure Deck Space | Pass | Five destinations, lifts, three area categories, cargo and remarks |
| 14. Departure Inventory | Pass | All 17 exact template products; normalized-name lookup |
| 15. Arrival General Information | Pass | Independent report date; other general information linked |
| 16. Departure reuse in Arrival | Pass | Linked general/departure values; destination follows original D26 link |
| 17. Actual Arrival | Pass | Independent actual date, time and remarks |
| 18. Arrival Deck Space | Pass | Five independent destination rows and totals |
| 19. Arrival Inventory | Pass | Independent arrival quantities and remarks |
| 20. Voyage Progress | Pass | Date, hour/minute, DMS, COG, speed, all six weather components, remarks; 100 rows |
| 21. Coordinate handling | Pass | Tested decimal-to-DMS helper; NAV representation unchanged |
| 22. Derived calculations | Pass | Shared helpers for UI/export; utilization blank at missing/zero capacity |
| 23. Autosave | Pass | Atomic JSON replacement, restart recovery, unreadable-store protection, save-error visibility |
| 24. Undo/redo | Pass | Fields and all row groups, departure/arrival, independent inventory; keyboard Ctrl+Z tested |
| 25. Validation | Pass | Invalid drafts survive autosave; path-specific issues block export without partial replacement |
| 26. Stale sample-data clearing | Pass | Every mapped unused destination cleared; blank report and cached-title checks |
| 27. Back Deck Photo preservation | Pass | Entire L9:U27 cell regions and drawing/media ZIP parts untouched; no new image |
| 28. Download Excel | Pass | Existing GDS styling; model-based export; sanitized Windows filename |
| 29. Save dialog | Pass | Real Windows dialog observed; blank native report saved and reopened |
| 30. Source template unchanged | Pass | Source and bundled SHA-256 remain equal to original |
| 31. Full fixture export | Pass | Multiple crew, contractors, waypoints, progress rows, all deck rows and products |
| 32. Acceptance workbook | Pass | docs/evidence/VJR_excel_export_acceptance.xlsx |
| 33. Visual comparison | Pass | Original opened in Protected View, export read-only; all export sheets inspected in Excel |
| 34. Normal pytest | Pass | 718 passed in 205.54s (3:25), final code and tests |
| 35. Legacy pytest | Pass | 717 passed, 1 skipped in 282.67s (4:42), final code and tests |
| 36. compileall | Pass | Both .venv and .venv-win7, app and main.py, exit 0 |
| 37. Manual runtime | Pass with scope noted | main.py opened VJR offline; sections/scrolling/reservation/download/native save/shutdown observed; edits/history/restart tested in isolated Qt stores |
| 38. Regression | Pass | Complete suites cover Configure, VDR Excel/PDF, NAV, compatibility, USB/serial, autosave/history; no unrelated implementation edits |
| 39. Files modified | Listed below | No auto-commit; diagnostics file belongs to pre-existing user changes |
| 40. Remaining limitations | Documented | No photo mechanism or automatic telemetry capture; one active journey; materialized Excel snapshot |

`tests/test_vjr.py` and `tests/test_vjr_ui.py` pass **65 tests** after final layout
and keyboard-history checks. The fixture lives only in `tests/vjr_fixture.py` and
the requested evidence workbook; production reports are never seeded with demo data.

## Preservation and visual review

The exporter uses openpyxl for read-only structure inspection, then patches only
mapped cell values in the original ZIP archive. It does not save a reconstructed
openpyxl workbook. Tests compare **every ZIP member**: non-report parts are
byte-identical; for changed worksheets, all content outside mapped cell elements
is byte-identical. This covers guide content, existing images/drawings, row heights,
column widths, print settings, page setup, cell styles, merges and validations.
Mapped cell attributes, including style identifiers, remain intact.

Critical calculations, linked arrival data, report titles and date annotations
are materialized so cached sample client/date data cannot appear before Excel
recalculation. Unrelated reference/helper formulas remain unchanged.

Excel opened the generated workbook without a repair dialog. Metadata, guide,
crew, contractors, waypoint plan, departure, arrival and voyage progress were
viewed. Current identity, dates, working days and DMS values appeared within the
original layout. The original departure sheet was opened separately for comparison.
The source already contains an embedded deck photograph: it is intentionally
preserved, alongside the photo-region cells and labels. No photo was uploaded,
replaced, removed or inserted. Office's sign-in notice and original Protected View
were left in place; no security setting was changed.

The native application exported a blank working report through its real Windows
Save As dialog to ignored `build/vjr-native-empty.xlsx`. Reopening confirmed eight
sheets and blank operational values. The final native process explicitly returned
exit code **0**. `build/vjr-runtime-last.log` records
`STARTUP 9: app.exec returned` and `STARTUP 10: Qt objects destroyed before QApplication`.
No fixture or invented operational data was entered into the production workspace.

## Final validation commands

Run from the repository root. The offscreen setup addresses the baseline's display
and font assumptions; distinct outside-Git temporary roots avoid the original
legacy access error and map-download containment checks.

```powershell
.\.venv\Scripts\python.exe build/prepare_vdr_test_fonts.py
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR=(Resolve-Path build/vdr-native-test-fonts).Path
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-normal-final-5
.\.venv-win7\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-legacy-final-5
.\.venv\Scripts\python.exe -m compileall app main.py
.\.venv-win7\Scripts\python.exe -m compileall app main.py
.\.venv\Scripts\python.exe tools/verify_vjr_acceptance.py
```

## Files created or modified

Modified:

- `app/ui/components/top_tabs.py` — allow the implemented manual VJR without telemetry.
- `app/ui/pages/vjr_page.py` — replace the placeholder with the VJR workspace.
- `tests/test_nav_map_first.py` — update the intended VJR availability assertion.
- `tests/test_vdr_navigation.py` — update VJR availability and isolate its store in shell tests; VDR assertions preserved.

Created:

- `app/resources/templates/vjr_template.xlsx`
- `app/ui/pages/vjr_workspace.py`
- `app/vjr/__init__.py`
- `app/vjr/schema.py`
- `app/vjr/model.py`
- `app/vjr/calculations.py`
- `app/vjr/validation.py`
- `app/vjr/store.py`
- `app/vjr/excel.py`
- `tests/vjr_fixture.py`
- `tests/test_vjr.py`
- `tests/test_vjr_ui.py`
- `tools/verify_vjr_acceptance.py`
- `docs/vjr-excel-cell-map.md`
- `docs/vjr-excel-export-acceptance.md`
- `docs/evidence/VJR_excel_export_acceptance.xlsx`

Pre-existing user modification, preserved: `.saropa/diagnostics/history.json`.
Ignored `build/` test logs, native-export smoke artifact, temporary font copies and
compile caches are local validation support, not application deliverables.

## Limitations

- Photo transfer/import/insertion is intentionally absent. Existing source photo
  regions and media remain untouched until future requirements are provided.
- Manual Voyage Progress is implemented; automatic sensor capture is deferred.
  The VJR-specific decimal-to-DMS helper is ready for that integration.
- There is one persistent working journey. A journey archive/new-journey workflow
  was outside the requested scope.
- Excel is a materialized report snapshot for critical calculations and linked
  operational cells. Edit in GDS VTS and re-export to refresh them.
- Configure's existing name/client settings are reused when present; IMO/capacity
  remain VJR fields because no authoritative existing settings were found.
- The original workbook's embedded photograph and reference-sheet examples remain
  by explicit preservation requirements; mapped operational sample values are cleared.

A. VJR IMPLEMENTATION AND EXCEL EXPORT ACCEPTED
