# VDR Excel-sheet gaps acceptance

NABM and PREMIX are standard selectable Bulk Inventory items, appended after BASE OIL. The existing five initial default rows remain unchanged. Both additions use the same bulk row, received details, transfers, validation, persistence, closing calculation, and PDF interchange as every other standard item.

Section 03 now contains A. Daily Operation Activity Log and B. Daily Duration at Location. The summary is calculated on every existing refresh from the authoritative activity interval helper. It never enters the report schema or creates history entries. There are still exactly seven main sections.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline tests | PASS | 578 passed in 101.04s; status/stat/diff captured before edits. |
| 2. NABM added | PASS | Standard Add item option: NABM (bbls). |
| 3. PREMIX added | PASS | Standard Add item option: PREMIX (bbls). |
| 4. Bulk ordering | PASS | Tail: SBM, FOAM, BASE OIL, NABM, PREMIX; existing order/default rows preserved. |
| 5. NABM details | PASS | Received From/meters/ticket and transfer To/quantity/meters/ticket tested; desktop details verified. |
| 6. PREMIX details | PASS | Same existing workflow; both closing examples: 100 + 20 - 5 - 12 = 103. |
| 7. Duration helper | PASS | Pure derive_location_durations(activity_rows); shared activity_intervals with calculate(). |
| 8. Activity integration | PASS | Both tables belong to section 03; no section 08. |
| 9. Contiguous grouping | PASS | Exact requested five activities produce DUYONG 0000–1200 and JAMPUK 1200–2400. |
| 10. Non-contiguous grouping | PASS | Return visits remain separate; row order preserved. |
| 11. Duration calculation | PASS | Existing minutes()/hhmm() and derived FROM reused; HH:MM including 00:45, 12:30 and 24:00 tested. |
| 12. Invalid rows | PASS | Invalid TO/chronology and empty locations omitted; omitted rows break grouping. Subsequent intervals follow existing activity rules. |
| 13. Read-only presentation | PASS | Non-editable items, calculated-value background, subtle shared border, AUTO-CALCULATED label; existing GDS body/data font constants. |
| 14. Scroll | PASS | Summary immediately below activity table; automated and normal-app screenshot checks. |
| 15. Steps | PASS | Both activity tables in same step; automated and normal-app screenshot checks. |
| 16. Undo/redo | PASS | Derived refresh adds no history; edit/undo/redo tested. Desktop undo restored exact 12:00/12:00 scenario. |
| 17. Autosave | PASS | Only original activity records persisted; saved/reloaded derivation tested. Both bulk item details persist. |
| 18. Excel-ready structure | PASS | List of dictionaries with from, to, duration, location strings; no Excel exporter added. |
| 19. Existing VDR regression | PASS | All existing tests retained; finalization and both PDF round trips also tested with new inventory items. |
| 20. GDS theme regression | PASS | Shared theme, VDR stylesheet, and date picker hashes unchanged. NAV/map/VJR/routing/PDF/store protected sources unchanged. |
| 21. py_compile | PASS | model.py, sections.py, workspace.py, test_vdr_excel_gaps.py. |
| 22. compileall | PASS | python -m compileall -q app main.py. |
| 23. Exact pytest | PASS | .\.venv\Scripts\python.exe -m pytest -q --tb=short; final 598 passed in 110.93s. |
| 24. Total tests | PASS | 578 baseline + 20 new = 598; no existing test weakened. Focused gap/existing VDR run: 58 passed in 13.73s. |
| 25. Manual runtime | PASS | Normal main.py, NO SOURCE, existing PDF import, persisted scenario on 17 Nov 2026, Steps/Scroll and both bulk details verified. |
| 26. Files modified | PASS | model.py, sections.py, workspace.py, new test_vdr_excel_gaps.py, this report and diagnostic evidence. |
| 27. Remaining issues | NONE CONFIRMED | No confirmed gap-field defect. No auto-commit. Earlier unrelated workspace changes preserved. |

Tests ran with `QT_QPA_PLATFORM=offscreen` and `QT_QPA_FONTDIR=C:\Users\rayha\GDS-VTS\build\vdr-native-test-fonts` to retain the existing wide-layout test setup and native font aliases. Manual checks used normal `.\.venv\Scripts\python.exe -u main.py` on the Windows desktop.

Manual scenario was prepared with existing VDR model/PDF export and opened through the existing Import dialog. On the normal application, changing third TO from 1200 to 1300 immediately produced DUYONG 13:00 and JAMPUK 11:00. Toolbar Undo restored both 12:00 values. The acceptance scenario uses report date 17 Nov 2026 and vessel name VDR GAP ACCEPTANCE SCENARIO.

Evidence:

- [Exact scenario in Steps](diagnostics/vdr-excel-gaps/activity-steps.png)
- [Live TO edit and immediate derived update](diagnostics/vdr-excel-gaps/activity-live-edit.png)
- [Exact scenario restored in Scroll](diagnostics/vdr-excel-gaps/activity-scroll.png)
- [NABM and PREMIX inventory rows and calculated closings](diagnostics/vdr-excel-gaps/bulk-nabm-premix.png)
- [Both received/transfer detail panels](diagnostics/vdr-excel-gaps/bulk-details.png)
- [Protected source comparison: 100 files, zero changed](diagnostics/vdr-excel-gaps/scope-check.json)

A. VDR EXCEL-SHEET GAP FIELDS ACCEPTED
