# VDR GDS calendar acceptance — 19 November 2026

The implemented VDR is native PySide6, not a Chromium form. Optional HSE and crew dates previously used `QDateEdit` with an empty-value sentinel of `QDate(1752, 9, 14)`. Opening an empty input therefore opened September 1752. The native calendar also inherited platform styling. No timestamp conversion caused this defect.

The supplied attachment contains the written task, without the screenshot itself; the exact photographed field cannot be distinguished. The shared faulty initializer affected Last LTI, Last recordable injury, Last recordable incident, and crew sign-on dates. Report date also used a native picker and is replaced. Date of hire is a display label; next provision supply remains its existing free-text field; contractors have no date input.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Popup root cause | FIXED | Removed the 1752 empty-date sentinel and native platform calendar. |
| 2. Screenshot field | IDENTIFIED CLASS | Optional HSE/crew dates shared the faulty initializer; exact photographed field unavailable in supplied attachment. |
| 3. Native picker replaced | PASS | No QDateEdit/QCalendarWidget remains in VDR production code; runtime test also checks absence. |
| 4. Reusable DatePicker | PASS | VdrDatePicker and CalendarPopover in date_picker.py serve every editable VDR date. |
| 5. Font | PASS | Locally bundled Inter throughout popup; actual resolved family checked in tests. Surrounding GDS typography preserved. |
| 6. Theme | PASS | Shared navy/light GDS palette, 300px panel, 34px day buttons, 12px rounded corners; explicit opaque panel painting fixes Windows transparency. |
| 7. Initial month | PASS | Valid stored date, then selected report date, then current date. Empty values remain empty. |
| 8. Report date | PASS | Existing report selection route and limits preserved; visible dd MMM yyyy, persisted YYYY-MM-DD. Historical imported reports remain reachable. |
| 9. Selected day | PASS | Navy fill, white text; captured with 19 Nov selected in report-date screenshot. |
| 10. Today | PASS | Outlined day; Today action; no automatic value insertion merely by opening. |
| 11. Month navigation | PASS | Previous/next controls, disabled where out of allowed range. |
| 12. Year rollover | PASS | December/January and reverse rollover covered by tests; Shift+Page keys move a year. |
| 13. Positioning | PASS | Below input or above when needed; constrained to VDR/screen bounds. Desktop captures show both placements and an unclipped table popup. |
| 14. Layering | PASS | One Qt.Popup at a time, outside card/table clipping; closes when modal dialog appears and cannot open while a modal is active. |
| 15. Outside click | PASS | Dismissal and replacement covered in tests; outside desktop click dismissed popup. |
| 16. Escape | PASS | Automated and physical desktop checks. |
| 17. Keyboard | PASS | Space/Enter/Down open, arrows move focused date, Enter commits, Escape dismisses, Tab moves onward; PageUp/Down navigate. Existing table navigation retained. |
| 18. Autosave | PASS | ISO selection uses existing store mutation; saved/reloaded temporary store tested. Invalid manual date typing cannot corrupt value. |
| 19. Undo/redo | PASS | Selection and clear use existing history, tested through undo/redo. |
| 20. Finalized state | PASS | Date fields lock; report-date navigation remains usable. Existing normal draft edits restore editable date state. Store business rules unchanged. |
| 21. Scroll | PASS | Automated integration and normal-app report/HSE popup checks. |
| 22. Steps | PASS | Automated integration and normal-app crew popup checks. |
| 23. Exact pytest | PASS | Baseline 558 passed in 95.58s. Final 578 passed in 106.33s; same `-m pytest -q --tb=short` arguments. |
| 24. Startup | PASS | Normal `.\.venv\Scripts\python.exe -u main.py`; VDR opened with NO SOURCE. Existing NAV Chromium cache/provider diagnostics appeared, without blocking VDR. |
| 25. Screenshot evidence | PASS | Links below; report date, three HSE dates, and all five initial crew rows opened in November 2026. |
| 26. Files modified | PASS | Listed below; protected-file hash check reports 100 checked, zero changed. No auto-commit. |
| 27. Remaining issues | NONE CONFIRMED | No confirmed VDR calendar defect remains after desktop and regression checks. |

Validation commands:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR='C:\Users\rayha\GDS-VTS\build\vdr-native-test-fonts'
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\python.exe -m compileall app main.py
```

Offscreen mode avoids Windows monitor-size clamping in existing wide-layout tests. The ignored test font directory supplies Windows font aliases to Qt's offscreen font database. These environment settings apply only to testing. Normal manual verification used `.\.venv\Scripts\python.exe -u main.py` with the native desktop platform.

Evidence from normal startup on report date 19 Nov 2026:

- [Report date, selected day, below-input placement](diagnostics/vdr-calendar/report-date-0.png)
- [Empty LTI, November fallback, above-input placement](diagnostics/vdr-calendar/empty-lti-0.png)
- [Empty injury](diagnostics/vdr-calendar/empty-injury.png)
- [Empty incident](diagnostics/vdr-calendar/empty-incident.png)
- [Crew row 1 in Steps, popup outside table bounds](diagnostics/vdr-calendar/crew-signon-steps.png)
- [Crew row 2](diagnostics/vdr-calendar/crew-signon-row2.png), [row 3](diagnostics/vdr-calendar/crew-signon-row3.png), [row 4](diagnostics/vdr-calendar/crew-signon-row4.png), [row 5](diagnostics/vdr-calendar/crew-signon-row5.png)
- [Protected-file comparison](diagnostics/vdr-calendar/scope-check.json)

Task changes: `app/ui/pages/vdr/date_picker.py` (new), `sections.py` (all date creation), `workspace.py` (finalized date locking), `style.py` (input styles/native calendar rules removed), `tests/test_vdr_calendar.py` (20 new cases), `tests/test_vdr.py` (existing clear test adapted to replacement picker), this report, and its evidence directory. The model, store, PDF, calculation, navigation, shared theme, Configure, VJR, and NAV/map source files were not changed by this task. Earlier unrelated workspace changes remain present.

A. VDR GDS CALENDAR ACCEPTED
