# VDR GDS theme restyle

Presentation-only checkpoint, 19 November 2026 (Asia/Dhaka).

The native application theme is `app/ui/theme.py`. VDR now imports its `COLORS`,
`FONT_DISPLAY`, `FONT_BODY`, and `FONT_DATA` rather than maintaining a separate
black/white reference palette and foreign UI font assignments. The shared native
faces are Segoe UI Semibold, Segoe UI and Cascadia Mono. The shared theme itself,
Configure, NAV/map, VJR, routing and the offline VDR gate were not changed.

## Presentation changes

- Light GDS workspace; white toolbar, sidebar and content surfaces; navy headings
  and primary actions; existing native green finalized-state treatment.
- Rounded 14px outer panels, 10px internal panels and compact 6–8px controls;
  subtle shared borders, clear hover/focus/disabled/selected states, no shadows.
- Native 18px page heading, 14px section headings, 13px body/forms, native mono
  dates/numeric inputs/computed values. Density and existing dimensions retained.
- Computed cells have shaded backgrounds and navy values; invalid calculations
  retain the same conditions but use a visible danger edge and readable dark text.
- Validation dialog typography/surfaces/actions match GDS. Required-field checks,
  issue navigation, validation decisions and finalization workflow are unchanged.
- Draft-profile drawing uses GDS colors and the shared body font; geometry and
  draft/trim calculations are unchanged.

Modified source files:

1. `app/ui/pages/vdr/style.py`: scoped QSS generated from shared tokens/constants.
2. `app/ui/pages/vdr/workspace.py`: presentation imports, button object names,
   finalized badge property, validation title/style and computed error styles.
3. `app/ui/pages/vdr/sections.py`: removed the gray weather reading style override
   so the shared-token VDR stylesheet controls it.
4. `app/ui/pages/vdr/widgets.py`: native palette/font for the draft-profile paint.
5. `tests/test_vdr.py`: strict rendered-font assertions now expect the current
   shared native font constants instead of the superseded reference font names.

No fields, sections, table base widths, date navigation, layout modes, signal
connections, autosave, undo/redo, validation rules, finalization decisions or PDF
import/export behavior were removed or changed. No commits were made.

## Verification

- Relevant py_compile and `python -m compileall app main.py`: passed.
- Full `.\.venv\Scripts\python.exe -m pytest -q --tb=short`: **558 passed in
  104.55s (0:01:44)**, offscreen Qt with installed native fonts loaded. Test count
  unchanged; no disabled/removed tests.
- Normal `.\.venv\Scripts\python.exe -u main.py` launched successfully; VDR was
  opened using the real left rail with NO SOURCE. The native shell chrome and
  active rail styling remain. Scroll and Steps/table sections were inspected.
- Supplemental deterministic renders cover all seven sections, expanded bulk
  detail, finalized state, invalid computed values, validation dialog and
  1440×820 / 1000×750 widths. See `docs/diagnostics/vdr-gds-theme/`.
- Protected source hash comparison confirms domain/PDF, NAV/map, Configure,
  VJR, shared theme, main window, page entry point and navigation gate unchanged.

For headless regression checks, Qt uses `QT_QPA_PLATFORM=offscreen`. Windows'
native GDS font faces were read into ignored temporary test files under `build/`
and made available through `QT_QPA_FONTDIR`. The Semibold family alias was exposed
to FreeType in the temporary copy; glyph data/metrics and production fonts were
not modified. This permits the strict actual-family assertions to remain in
force. No proprietary font copies were added to application resources or Git.
Normal application verification uses installed Windows fonts directly.

The sandbox denied access to pytest temporary/cache directories; checks were
retried outside the sandbox. No tests were disabled, removed, or marked xfail.

Remaining visual issues: none observed in the checked views.

**A. VDR GDS THEME RESTYLE ACCEPTED**
