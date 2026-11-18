# Last Containment Loss acceptance

Added the optional historical date at `hse.containment_loss`, independently of `hse.incd` (Last Recordable Incident). Section 01 places it beside Last Recordable Incident in HSE Performance, using the existing custom GDS calendar and standard edit/store path.

The new-report default is empty. Existing normalization fills the missing key for older saved reports and PDF records. Existing rollover preserves it with the other historical HSE dates while resetting the daily incident text. It remains optional during finalization and follows the existing finalized date-field lock. The existing Perfect Days calculation includes it through the same historical HSE date enumeration; no special calculation was introduced.

The PDF HSE table gains one row. Its embedded report state already serializes the whole normalized report, so both current and legacy PDF import paths remain compatible. No Excel writer was added.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline | PASS | 598 passed in 186.01s; Git status/stat/diff captured before edits. |
| 2. Model field | PASS | Dedicated hse.containment_loss; no existing key overloaded. |
| 3. UI field | PASS | Section 01, HSE Performance, beside Last Recordable Incident. |
| 4. Date picker | PASS | Existing VdrDatePicker: optional, clearable, ISO storage, dd MMM yyyy display. |
| 5. Default empty | PASS | New and normalized legacy reports default to empty; no fake date. |
| 6. Autosave | PASS | Existing edit/save timer; automatic saved/reloaded value tested and desktop Saved status observed. |
| 7. Undo | PASS | Automated and desktop checks restore cleared date. |
| 8. Redo | PASS | Automated and desktop checks reapply clear. |
| 9. Backward compatibility | PASS | Legacy saved JSON and original jsPDF state packet tested; actual pre-change exported PDF imported with empty new field. |
| 10. Rollover | PASS | Historical date preserved across next-day selection, identically to LTI/injury/incident. |
| 11. Finalization | PASS | Empty and valid values both permitted; finalized picker locks. |
| 12. PDF export | PASS | Added one HSE row; two rendered pages visually inspected; branding/layout retained. |
| 13. PDF import | PASS | New values round-trip; older metadata without key imports empty. |
| 14. Serialization | PASS | Stable ISO string in existing HSE object; save/reload and PDF metadata tested. |
| 15. Excel-readiness key | PASS | hse.containment_loss maps to FLEET MANAGEMENT / Date of Last Containment Loss. |
| 16. GDS theme | PASS | Shared theme, VDR stylesheet and calendar source unchanged; 100 protected files match pre-task hashes. |
| 17. py_compile | PASS | model.py, pdf.py, sections.py, test_vdr_containment_loss.py. |
| 18. compileall | PASS | python -m compileall -q app main.py. |
| 19. Exact pytest | PASS | .\.venv\Scripts\python.exe -m pytest -q --tb=short: 608 passed in 175.51s. |
| 20. Total tests | PASS | 598 existing plus 10 new = 608; no existing tests weakened. |
| 21. Normal runtime | PASS | Normal main.py, NO SOURCE, 19 Nov 2026; calendar selected 12 Nov, Clear, Undo, Redo, Saved all observed. |
| 22. Files modified | PASS | app/vdr/model.py, app/vdr/pdf.py, app/ui/pages/vdr/sections.py, new tests/test_vdr_containment_loss.py, this report and evidence. |
| 23. Remaining issues | NONE CONFIRMED | Full regression run passed. No commit. NAV/map/VJR and other VDR sections unchanged. |

Focused check: 68 passed in 14.03s (10 new containment cases, 20 existing calendar cases, 38 existing VDR cases).

Baseline and final pytest command:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR='C:\Users\rayha\GDS-VTS\build\vdr-native-test-fonts'
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

The existing offscreen/native-font-alias setup avoids monitor clamping and platform font differences in the regression suite. Desktop verification used normal `.\.venv\Scripts\python.exe -u main.py`. The temporary test selection was cleared and saved, leaving the report's containment-loss value empty.

Evidence:

- [Selected calendar and separate incident field](diagnostics/vdr-containment-loss/selected-calendar.png)
- [Undo restores 12 Nov 2026](diagnostics/vdr-containment-loss/undo-restored-date.png)
- [Redo clears the date](diagnostics/vdr-containment-loss/redo-cleared-date.png)
- [Final empty value saved](diagnostics/vdr-containment-loss/hse-final-empty-saved.png)
- [PDF page 1 with new HSE row](diagnostics/vdr-containment-loss/pdf-page-1.png), [PDF page 2](diagnostics/vdr-containment-loss/pdf-page-2.png)
- [Protected-file scope check](diagnostics/vdr-containment-loss/scope-check.json)

A. LAST CONTAINMENT LOSS FIELD ACCEPTED
