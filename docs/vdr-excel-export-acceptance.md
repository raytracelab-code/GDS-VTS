# VDR Excel export acceptance

The current VDR can download a finalized report as an Excel snapshot in the exact supplied template. PDF export remains available. Workbook mapping is implemented in `app/vdr/excel.py`; shared domain calculations supply values, and the native UI only chooses the destination and reports success/failure.

The supplied file was found at `C:\Users\rayha\Downloads\16092026 VDR Executive Brilliance .xlsx`. It is 139111 bytes with SHA-256 `94b92a23932300dd7795cbe86a11fdec4ce3b6e2158df259994dea98d2521161`. Because Excel had the original open, it was read with read/write file sharing and read-only access. The source was never saved or replaced; its hash was verified again after export.

Full cell-level mapping, transformations, capacities, merged-cell receiver handling, and the explicit Fleet equipment-block decision are documented in [vdr-excel-cell-map.md](vdr-excel-cell-map.md).

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline tests | PASS | 608 passed in 159.90s; Git status/stat/diff recorded before editing. |
| 2. Exact template located | PASS | Original Downloads filename, not the duplicate .xlsx.xlsx. |
| 3. Template SHA-256 | PASS | Exact expected 94b92a…2521161, verified before and after. |
| 4. Template bundled | PASS | app/resources/templates/vdr_executive_brilliance_template.xlsx. |
| 5. Structure validation | PASS | Hash, size, sheet order/names/states, critical labels and mapped-cell existence. |
| 6. GDS Meta handling | PASS | C9/C10 authoritative configured identity; missing values blank; matching nonempty client name C11. |
| 7. VDR main mapping | PASS | Date, report number, identity, captain, location and drafts typed and materialized. |
| 8. HSE mapping | PASS | Perfect Days uses the extracted existing UI helper; dates and daily incident direct values. |
| 9. Last Containment Loss | PASS | hse.containment_loss to Fleet D6; visible VDR incident field remains separate. |
| 10. Endurance | PASS | H16:H19 current values; empty values cleared. |
| 11. Weather | PASS | All four rows, six fields; fixed time labels preserved. |
| 12. Activity mapping | PASS | W:AI rows 14:103, authoritative FROM/duration, four-digit clocks; unused rows cleared. |
| 13. Daily Duration at Location | PASS | Existing contiguous-period helper to AK:AN; exact DUYONG/JAMPUK 12:00 result tested. |
| 14. Running Hours | PASS | All 22 rows mapped by normalized equipment name, independent of app order. |
| 15. Equipment Consumption | PASS | Existing calculate().eqCons, direct numeric values. |
| 16. Total Daily Consumption | PASS | Existing calculate().totalCons to VDR T45/Fleet D74. |
| 17. Bulk Inventory | PASS | All 21 items, receipt/transfer/detail/remarks fields and current app closing values. |
| 18. NABM | PASS | Fixed row 76; receipt, transfer, closing and remarks tested. |
| 19. PREMIX | PASS | Fixed row 77; same full mapping. |
| 20. Fuel transfers | PASS | Two transfers in both sheets; unused six-slot VDR lines cleared; fixed # labels preserved. |
| 21. Activity Summary | PASS | Ten categories and DP/coverage totals from shared interval summary; unused K–R zeroed. |
| 22. Location Summary | PASS | First-seen unique locations aggregated from existing derived visits; return visits summed correctly. |
| 23. Core Crew | PASS | All nine columns, inclusive working days and nationality names; unused rows cleared. |
| 24. Contractors | PASS | All six columns; unused sample rows cleared. |
| 25. Fleet HSE | PASS | D3:D6 direct current data; containment loss not incident. |
| 26. Fleet block 1 | PASS | D8:D29 = FM @0000H; name mapping includes reversed stern order. |
| 27. Fleet block 2 | PASS | D30:D51 = FM @2400H; shortened Bow Thruster alias handled. |
| 28. Fleet block 3 | PASS | D52:D73 = consumption; same alias handling. |
| 29. Fleet fuel summary | PASS | D74:D82 consumption, receipt, two transfers, opening and closing. |
| 30. Fleet movement summary | PASS | D84:D93 including shortened towing label; same derived source as VDR. |
| 31. Stale sample clearing | PASS | Sparse fixture verifies mapped outputs empty/zero; no old operational cell values retained. |
| 32. No #REF outputs | PASS | Generated fixture scanned across every sheet/cell; Fleet formulas replaced with direct values. |
| 33. Download Excel UI | PASS | Existing GDS button styling beside PDF; enabled only when finalized. |
| 34. Save dialog | PASS | Native .xlsx dialog, sanitized default filename; cancellation has no state/output effect. |
| 35. Source unchanged | PASS | Bundled template byte identity tested; original Downloads hash rechecked unchanged. |
| 36. Packaged resources | PASS | Relative development and _MEIPASS paths tested; gds_vts.spec includes existing resource tree and openpyxl hooks. Executable build not run. |
| 37. Full fixture export | PASS | Test-only all-equipment/all-bulk fixture with two fuel transfers, crew, contractors and all HSE data. |
| 38. Acceptance path | PASS | C:\Users\rayha\GDS-VTS\docs\evidence\VDR_excel_export_acceptance.xlsx. |
| 39. Visual/template comparison | PASS | Opened in existing native Excel; VDR main/activity, crew and contractor layouts reviewed. Guide XML/styles/merges/dimensions/protection/print settings compared automatically. |
| 40. py_compile | PASS | Changed product and test Python files. |
| 41. compileall | PASS | python -m compileall -q app main.py. |
| 42. Exact pytest | PASS | .\.venv\Scripts\python.exe -m pytest -q --tb=short: 636 passed in 139.19s. |
| 43. Total tests | PASS | 608 baseline + 28 export cases = 636. Focused rerun: 66 passed in 41.45s (28 export + 38 existing VDR). No existing tests weakened. |
| 44. Manual runtime | PASS | Normal main.py, finalized test report imported through existing PDF route, Download Excel clicked, native destination selected, produced workbook independently reopened and verified. |
| 45. Files modified | PASS | Listed below; NAV/map/VJR/Configure/theme/calendar/PDF/store source unchanged. No commit. |
| 46. Remaining limitations | DOCUMENTED | Template limits are enforced with errors; absent configured vessel/hire values export blank. Frozen path/spec tested; packaged binary not built. |

Manual runtime output: `docs/evidence/VDR_excel_runtime_2026-11-16.xlsx`. This separate workbook contains the report selected in the normal app, including current HSE, NABM, crew, contractors, location periods and Fleet values. Configure identity was absent, so its vessel/hire cells are blank rather than using imported or template sample identity. The acceptance workbook uses explicit test identity to verify populated identity mapping. No test fixture is imported or hardcoded by production code.

The manually imported runtime fixture was removed after verification, following an exact match against the test fixture and a local backup. Only the validation process launched for this task was stopped; preexisting reports were preserved. The native automation tool could not restore its minimized window, so cleanup used the verified validation process handle and an atomic saved-state update. Both evidence workbooks remain available.

A Windows shell file-open attempt encountered an Excel installation startup error (0xc0000142). Opening the same generated file through the already-running Excel instance succeeded without a repair prompt. Final snapshot outputs do not require formula recalculation; unrelated template metadata formulas remain preserved.

Intentional limits: 90 activity rows, 200 crew, 200 contractors, 22 unique location totals, at most two fuel transfers for all-sheet export, and one non-fuel transfer per item. Unknown/duplicate equipment or bulk names, unknown movement categories, invalid typed values, wrong/missing templates, and locked/unwritable destinations fail without publishing partial output. Fuel case/whitespace variants in imported names use a shared domain/UI predicate so the UI closing and exported consumption cannot diverge.

Product/source changes:

- `app/vdr/excel.py` (new service and cell map).
- `app/vdr/model.py` (shared report number, Perfect Days, activity summary, normalized fuel predicate).
- `app/ui/pages/vdr/workspace.py` (Excel action/gate/dialog; shared Perfect Days helper).
- `app/ui/pages/vdr/sections.py` (same fuel predicate as domain/export).
- `app/resources/templates/vdr_executive_brilliance_template.xlsx` (pristine bundled original).
- `requirements.txt` (openpyxl), `gds_vts.spec` (packaging).
- `tests/test_vdr_excel_export.py`, mapping/acceptance docs, workbook and screenshot evidence.

Test command uses the existing wide-layout/font-alias setup:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR='C:\Users\rayha\GDS-VTS\build\vdr-native-test-fonts'
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

Evidence: [machine checks](diagnostics/vdr-excel-export/checks.json), [enabled toolbar](diagnostics/vdr-excel-export/download-excel-enabled.png), [native save completed](diagnostics/vdr-excel-export/native-excel-export-complete.png), [Excel VDR](diagnostics/vdr-excel-export/excel-vdr-main.png), [Excel activities](diagnostics/vdr-excel-export/excel-activities.png), [Excel crew](diagnostics/vdr-excel-export/excel-core-crew.png), [Excel contractors](diagnostics/vdr-excel-export/excel-contractors.png).

A. VDR EXCEL EXPORT ACCEPTED
