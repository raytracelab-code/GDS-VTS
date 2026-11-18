# VDR reference implementation checklist

Authoritative input confirmed by user: `C:\Users\rayha\Downloads\index (6).html`.
Baseline: **510 passed in 121.77s**, `python -m pytest -q --tb=short`.
The existing VDR is a two-line QLabel placeholder; no report model, database,
PDF exporter, importer, or fixtures exist. Existing unrelated working changes
(including NAV and the shell) must be preserved. No commits are authorized.

## Inspection / implementation plan (before editing)

- Inspect the full HTML envelope, stylesheet (including embedded flag sprite),
  bundled script modules, application render methods, domain functions, custom
  list/date widgets, PDF serializer and import metadata format.
- Native Qt workspace; one Python report dictionary/store, reference-compatible
  field names. No WebEngine implementation or duplicate browser state.
- Fixed topbar: 22px heading, 11px subtitle, hire date, compact status, saved
  text, Undo/Redo, disabled-until-finalized Download, Import, Finalize.
- Dark outer background; light #F5F5F5 report, white manual cells, gray computed
  cells, 1px borders, square controls; blue active navigation/toggles.
- 20px workspace margins/gap, 232px sidebar (plus reference padding), 24px
  section horizontal padding, 20px vertical padding, 14px header gap.
- Sidebar report date / previous / next, Scroll/Steps, seven ordered numbered
  sections, keyboard instructions, manual/computed field legend.
- Report/HSE: metadata beside draft profile; HSE/endurance beneath.
- Four weather slots, selectable sky/sea/visibility, copy previous, readings.
- Wide grid columns matching reference: activities 60/60/64/240+/225/52/56/60/
  185/30; equipment 190+/120/120/150/150/130/30; bulk 200/104/104/104/110/
  110/150+/76/30; crew 36/200+/150/56/130/160/140/70/120+/30;
  contractors 36/200+/170/56/140/180/30. Local horizontal scrolling.
- Activity FROM/duration automatic, normalize TO, auto-add, cap at 2400 / 50.
- Equipment flowmeter subtraction; fuel consumption links to total; bulk
  opening + received - consumption - transfers; inline received/transfer detail.
- Crew countries/flags, custom ranks, inclusive tour days / 90-day validation;
  contractor and all table add/remove controls.
- Reference rollover: carry crew/metadata, hours and closing inventory forward;
  clear daily readings/activity/transactions. No demo values or hire date.
- Autosave atomically; visible success/failure; date-scoped undo/redo snapshots;
  edits invalidate finalization, history includes finalization/import.
- Validation dialog lists section and Go action. Export all seven sections
  independent of view. Legacy compressed jspdf metadata import/export support.
- Convert bundled OFL webfonts into local native TTFs: Manrope headings,
  Inter form/UI, JetBrains Mono numeric fields. No shared theme changes.
- Deterministic model/UI/PDF tests, reference and native renders at equivalent
  desktop dimensions, narrow-width check, real main.py startup/manual checks.

## Model additions

All VDR model fields are new to this checkout, and retain the reference schema:
`meta`, `hse`, `end`, `wx`, `acts`, `eq`, `bulk` (including `tr` detail records),
`crew`, `ctr`, `finalized`, `finalizedAt`. `identity` adds configured vessel,
client and hire date snapshots for stable report export. Storage envelope adds
schema version, reports by date, current date, layout, and custom ranks.
No Configure, NAV, or VJR domain fields are modified.
