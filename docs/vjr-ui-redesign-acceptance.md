# VJR UI redesign acceptance

Review date: 19 November 2026 (Asia/Dhaka).

This change refines the VJR presentation using the accepted VDR palette, fonts,
card treatment, section navigator, inputs, buttons and calendar. The application
shell, VDR and NAV are unchanged. No commit was created.

## Scope boundary

`app/ui/pages/vjr_workspace.py` contains the layout and UI rendering changes.
`app/ui/pages/vjr_widgets.py` contains presentation-only layout, table-header and
scrolling helpers. `VdrDatePicker` is imported and reused without modifying VDR.

SHA-256 verification confirms **77 protected files remain byte-identical** to the
state at the start of this task. These include every VJR domain module, the
original bundled VJR workbook, all VDR UI modules and NAV Python modules.
See [scope verification](evidence/vjr-ui-redesign/scope-verification.json).
The accepted Excel regression file `tests/test_vjr.py` was not edited. The only
change to the existing UI test file updates the intentionally revised photo
placeholder wording. Autosave, history, validation rules and calculations retain
their accepted implementation.

## Design and behavior

- A VDR-style header shows VJR, Voyage Journey Report, the current vessel when
  available, a report status, actual autosave state, undo/redo and Download Excel.
  The primary export action stays visible at the requested desktop sizes.
- A numbered left navigator switches the same seven report sections. Clicking
  the active section preserves its selected appearance.
- Form cards use labels above fields, 36-pixel controls and a responsive three,
  two or one-column grid. Resizing rearranges existing editors rather than
  recreating them. Departure/arrival separate identity, general information,
  departure reference, arrival, draft/requirements, deck, inventory and photos.
- Dates use the accepted VDR calendar. Time controls display HH:MM in a compact
  field; the existing nullable-time behavior is preserved. Linked arrival values
  have a calm tinted treatment, including the departure-time field.
- Editable tables use numbered rows, compact headers, numeric alignment,
  consistent row heights, alternating backgrounds, row actions and capacity-aware
  Add buttons. Waypoint and progress headers group related columns. Horizontal
  scrolling preserves access to all fields at smaller widths.
- Deck-space tables show the existing helper results in a read-only TOTAL row.
  Inventory keeps its exact fixed product names and units.
- Validation rules are unchanged. Subtle field borders, inline messages and cell
  outlines identify issues. Download Excel remains blocked for invalid reports.
- Photo cards are informative reserved areas without an upload, camera, file,
  clipboard, drag/drop, path-storage or Excel-image feature.

The native review identified two presentation issues during implementation:
active-navigation deselection and a linked time editor omitted from its layout.
Both were corrected and covered by UI tests. Final screenshot review also caught
a Qt styled-spin-box issue that collapsed time-text width. The corrected style
and a minimum usable text-width regression check pass in both Qt6 and Qt5.

## Verification

| Check | Result | Notes |
| --- | --- | --- |
| 1. Baseline | Recorded | Requested normal command: 718 passed in 220.74s; native Windows Qt/COM diagnostic also emitted; process exited 0 |
| 2. VJR header | Pass | Real vessel/status/autosave values; export action kept primary |
| 3. General Information | Pass | Compact responsive cards and aligned labels |
| 4. Crew UI | Pass | Numbering, date picker, working days, row actions; 200-row capacity unchanged |
| 5. Contractor UI | Pass | Matching grid and actions; capacity unchanged |
| 6. Waypoint UI | Pass | Grouped DMS and navigation headers; compact widths |
| 7. Departure UI | Pass | Clear subsection cards, compact controls and scrolling |
| 8. Arrival UI | Pass | Matching structure; linked departure time visible and updating |
| 9. Deck Space UI | Pass | Read-only derived fields and aggregate TOTAL row |
| 10. Inventory UI | Pass | Fixed products/units, numeric alignment and full row access |
| 11. Voyage Progress UI | Pass | Grouped date/time, coordinates, navigation, weather and remarks |
| 12. Photo placeholders | Pass | Two noninteractive reserved cards; no image feature |
| 13. Validation styling | Pass | Inline field messages, cell outlines, export blocking retained |
| 14. Responsive layout | Pass | 1920×1080, 1600×900 and 1366×768 snapshots and geometry assertions |
| 15. Scrolling | Pass | Native vertical page and horizontal progress scrolling checked; tables pass wheel events onward at boundaries |
| 16. Autosave | Pass | Existing isolated-store persistence/restart tests; implementation unchanged |
| 17. Undo/redo | Pass | Existing field/table/keyboard checks and row-action undo |
| 18. Excel export regression | Pass | Existing Excel tests unchanged; mappings/template/backend hashes preserved |
| 19. Normal pytest | Pass | 726 passed in 189.57s (3:09), final styling and checks |
| 20. Legacy pytest | Pass | 725 passed, 1 skipped in 236.90s (3:56), final styling and checks |
| 21. compileall | Pass | app and main.py in both environments, exit 0 |
| 22. Manual runtime | Pass | Normal main.py opened VJR; isolated native profiles reviewed all sections and scrolling; review processes exited 0 |
| 23. Screenshots/evidence | Pass | 22 PNGs, VDR comparison, responsive views, validation and full-capacity view |
| 24. Files modified | Listed below | Scope is UI, tests, evidence tooling and documentation |
| 25. Remaining limitations | Intentional | Dense grids require horizontal scrolling; photo workflow remains deferred |

The final full-suite runs use the previously established offscreen font setup and
separate temporary folders outside Git. This avoids native display/font assumptions
and preserves the map-download tests' repository containment rule:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QPA_FONTDIR=(Resolve-Path build/vdr-native-test-fonts).Path
.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-ui-normal-final-3
.\.venv-win7\Scripts\python.exe -m pytest -q --tb=short --basetemp=C:/Users/rayha/AppData/Local/Temp/gds-vjr-ui-legacy-final-3
.\.venv\Scripts\python.exe -m compileall app main.py
.\.venv-win7\Scripts\python.exe -m compileall app main.py
```

Local logs are under ignored `build/vjr-ui-*.log`. No dependency or Windows
compatibility layer changes were needed.

## Visual and runtime evidence

The [screenshot gallery](evidence/vjr-ui-redesign/README.md) covers every requested
section and both photo cards. A [side-by-side comparison](evidence/vjr-ui-redesign/18_vdr_vjr_side_by_side.png)
shows the unchanged VDR reference beside the redesigned VJR, using the same
typography, navy/seafoam palette, white cards, field labels and spacing rhythm.
All populated screenshots use the existing test-only fixtures in isolated stores;
no sample data was added to production reports.

The capture tool tests 200 crew, 200 contractors, 30 waypoints and 100 progress
rows together. It asserts that a field edit keeps the existing table widgets.
The measured local edit duration is recorded in [manifest.json](evidence/vjr-ui-redesign/manifest.json),
approximately 15–20 ms in the reviewed runs. This is a local measurement, not a
cross-hardware performance guarantee.

The ordinary `main.py` runtime opened the new VJR header and General page. That
window was later minimized; desktop control refused restoration after detecting
user input, so it was left untouched. The remaining checks used the application's
existing isolated validation profile, including native crew, contractor,
waypoint, departure, arrival and progress rendering, vertical scrolling and
horizontal access to weather/remarks. The isolated review processes returned
exit code 0 and logged their normal Qt cleanup. The original minimized runtime
may need a normal restart to load the final source changes.

## Files changed for this redesign

Modified:

- `app/ui/pages/vjr_workspace.py`
- `tests/test_vjr_ui.py` — revised placeholder wording only

Created:

- `app/ui/pages/vjr_widgets.py`
- `tests/test_vjr_redesign.py`
- `tools/capture_vjr_ui_evidence.py`
- `docs/vjr-ui-redesign-acceptance.md`
- `docs/evidence/vjr-ui-redesign/README.md`
- `docs/evidence/vjr-ui-redesign/manifest.json`
- `docs/evidence/vjr-ui-redesign/scope-verification.json`
- The 22 PNGs individually listed in the screenshot gallery.

All other dirty/untracked files reported by Git belonged to the accepted VJR
implementation or existing diagnostics changes at the start of this task and
were preserved. No commit, staging, reset or cleanup of user changes occurred.

A. VJR UI REDESIGN ACCEPTED
