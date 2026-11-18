# VDR reference acceptance

Verified 19 November 2026 (Asia/Dhaka). Reference path confirmed by the user.
Detailed architecture/model notes: `vdr-reference-implementation.md`.
Visual evidence: `diagnostics/vdr/`.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Baseline tests | PASS | 510 passed in 121.77s before edits. |
| 2. Complete reference inspection | PASS | HTML/CSS, seven render sections, lists/calendar, state, validation, formulas, PDF and print inspected. |
| 3. Architecture | PASS | Qt native widgets; one Python model/store; one PDF pipeline. Original VDR was a placeholder. |
| 4. Topbar | PASS | 62px native vs 61.5px reference; same action order; sticky outside report scroll. |
| 5. Sidebar | PASS | 258px outer width vs 257.6px reference; 645px vs 644.9px height. |
| 6. Date navigation | PASS | Previous/next, future blocking, date records, daily rollover. |
| 7. Scroll/Steps | PASS | Continuous document or one section; selected states and step footer. |
| 8. Section navigation | PASS | Seven ordered numbered sections; smooth scroll or step selection. |
| 9. Report & HSE | PASS | Metadata, draft profile, HSE and endurance fields; optional calendars clearable. |
| 10. Weather | PASS | Four slots, sky/sea/visibility toggles, readings, temperature controls, copy previous, wrapping. |
| 11. Activity Log | PASS | Automatic FROM/duration, full category list, TO normalization/auto-add, 2400 cap, 50-row cap. |
| 12. Running Hours | PASS | Total/daily hours, flowmeters, consumed amounts and linked fuel total. |
| 13. Bulk Inventory | PASS | Closing formula; received/transfer details; ticket/meter fields; six-transfer cap. |
| 14. Core Crew | PASS | Nationality flags/search, custom ranks, inclusive tour days, 90-day validation. |
| 15. Contractors | PASS | Name/vendor/age/nationality/ID fields, local flags, add/remove. |
| 16. Add/remove | PASS | Activities, equipment, bulk, crew, contractors and transfers checked. |
| 17. Undo | PASS | Report snapshots, including edits, finalization/import; Ctrl+Z from focused editor tested. |
| 18. Redo | PASS | Ctrl+Shift+Z and redo button; date-scoped history tested. |
| 19. Save | PASS | 300ms autosave; atomic replace; subtle feedback; corrupted originals preserved. |
| 20. Validation | PASS | Required fields/numbers/coverage/tours; section-specific issue dialog with Go action. |
| 21. Finalization | PASS | Validation required; FINALIZED state; edits clear finalization and disable download. |
| 22. PDF export | PASS | Seven sections, transaction details, GDS/configured identity, embedded local fonts; two-page fixture visually inspected. |
| 23. PDF import | PASS | Download/import UI actions and compressed jsPDF metadata round trips tested. |
| 24. Existing-report compatibility | PASS with scope | No original VDR reports/fixtures existed; exact reference metadata format and older finalized records tested. |
| 25. Manrope headings | PASS | Local converted font; actual Qt family checked. |
| 26. Inter body/UI | PASS | Local converted font; actual editor family checked. |
| 27. JetBrains Mono numeric/time | PASS | Numeric inputs, times, counters and dates; actual family checked. |
| 28. Reference spacing | PASS with native differences | 20px workspace margins/gap; 24px horizontal/20px vertical section padding; native font metrics differ. |
| 29. Table dimensions | PASS | Reference base widths; flexible columns fill wide viewports; readable columns retain horizontal scroll. |
| 30. Responsive behavior | PASS | 1440×800 and 1000×750 captures; tables do not collapse; topbar horizontal scroll when needed. |
| 31. Print behavior | PASS | PDF pipeline exports all sections independent of view; no navigation/actions in output. |
| 32. Configure regression | PASS | Configure source unchanged; full regression suite passes. |
| 33. NAV regression | PASS | NAV/map source untouched by this task; full regression suite passes. |
| 34. VJR regression | PASS | VJR placeholder/source unchanged; module access gate preserved. |
| 35. compileall | PASS | `python -m compileall app main.py` and explicit VDR py_compile completed. |
| 36. Exact pytest command | PASS | `.\.venv\Scripts\python.exe -m pytest -q --tb=short`: **548 passed in 96.34s**; offscreen Qt. |
| 37. Total tests | PASS | **548 total**, baseline 510; **38 added VDR cases**. Focused run: 38 passed in 11.74s. |
| 38. Startup | PASS with device limitation | `python -u main.py` started normally. No connected telemetry device: production VDR button remains locked. Isolated real-shell VDR render passes. |
| 39. Visual comparison | REVIEW PENDING | Desktop reference/native, full Scroll, all Steps, bulk detail, finalized, narrow and real-shell captures saved and inspected. Final user visual acceptance pending. |
| 40. Files created | RECORDED | See inventory below. |
| 41. Files modified | RECORDED | VDR entry point, requirements and one VDR-only header-visibility condition in existing main window. |
| 42. Intentional differences | RECORDED | GDS fonts/branding/data, native Qt calendar/combo/list/scroll behavior, numbered navigation and local weather glyphs. |
| 43. Remaining issues | REVIEW PENDING | Final visual approval and live-device acceptance pending. No confirmed VDR runtime defects after fixes. |

## Verification environment

Baseline ran with normal desktop Qt. Native UI tests also passed on desktop Qt;
Windows accessibility callback diagnostics appeared during later desktop pytest
runs while UI automation was connected, although pytest exited successfully.
Final full suite uses `QT_QPA_PLATFORM=offscreen`, with the requested pytest
arguments unchanged. Windows temp-folder sandbox permission errors were handled
by rerunning outside the sandbox. The real desktop UI and normal shell were
rendered separately. Shared NAV WebEngine cache warnings occurred when the
normal app and diagnostic shell were open concurrently; NAV code was unchanged.

## Task file inventory

Created source:

- `app/vdr/{__init__,model,store,pdf}.py`
- `app/ui/pages/vdr/{__init__,workspace,sections,widgets,style}.py`
- `tests/test_vdr.py`
- `tools/build_vdr_assets.py`, `tools/validate_vdr.py`
- `app/resources/vdr/`: three native TTFs, three OFL notices, catalogs JSON,
  local flag sprite/offsets and README.
- `docs/vdr-reference-checklist.md`, `docs/vdr-reference-implementation.md`,
  this acceptance report, and `docs/diagnostics/vdr/` evidence.

Modified source:

- `app/ui/pages/vdr_page.py`: placeholder replaced with the native page factory.
- `app/ui/main_window.py`: hide the generic header on VDR; pre-existing unrelated
  shell changes preserved.
- `requirements.txt`: ReportLab and pypdf runtime dependencies.

No commits created.

**B. VDR REFERENCE UI CODE-COMPLETE — FINAL VISUAL ACCEPTANCE PENDING**
