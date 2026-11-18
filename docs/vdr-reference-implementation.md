# VDR reference implementation

The user confirmed `C:\Users\rayha\Downloads\index (6).html` as authoritative.
Its complete document was loaded and its CSS/grid/sticky/print rules, embedded
country sprite, application render functions, custom lists/calendar, state
transitions, validation, rollover, calculations and PDF serializer/importer
were inspected. Bundled vendor/polyfill modules were identified separately.

The original checkout contained only a VDR placeholder. This implementation
adds a native Qt page, one Python model/store and one ReportLab/pypdf pipeline.
The reference HTML is never a runtime dependency. Data is saved atomically to
`QStandardPaths.AppLocalDataLocation/vdr/reports.json`; unreadable originals
are preserved with visible failure feedback. The existing telemetry gate stays
in force. The single VDR integration change in the shell hides the generic
header on VDR because this page supplies its own sticky topbar.

## New model fields

The reference-compatible schema is implemented in `app/vdr/model.py`:

| Group | Fields |
|---|---|
| meta | date, captain, loc24, fwd, aft |
| hse | inc24, lti, inj, incd |
| end | fuel, water, prov, nextProv |
| wx | t, wind, swell, sea, sky, vis, temp; four slots |
| acts | to, act, cat, dp, lifts, pob, loc; computed FROM/duration |
| eq | name, total, daily, fm0, fm24; computed consumption |
| bulk | name, open, rcvQty, rcvFrom, rcvB, rcvA, rcvTicket, cons, remarks, det, tr |
| transfer | to, qty, mb, ma, tk |
| crew | name, rank, age, nat, ic, signon, comments; computed inclusive days |
| ctr | name, vendor, age, nat, ic |
| lifecycle | finalized, finalizedAt |
| identity extension | vessel, client, hireDate snapshots |
| storage envelope | schemaVersion, reports, current, layout, customRanks |

Vessel name reads the application's existing in-memory `nav.config.name`.
Vessel/client/hire values can also be read from existing GDS/VTS QSettings keys
`vessel/name`, `vessel/client`, `vessel/date_of_hire`. This checkout has no
configured client/hire model, so absent values remain blank/dash. No Configure
fields or settings are created or redesigned.

## Compatibility and calculations

Flowmeter consumption = FM2400 minus FM0000. Only non-negative complete meter
pairs contribute to total fuel consumption. Bulk closing = opening + received
minus consumption minus transfers. Fuel uses the running-hours total. Crew tour
days include sign-on day. Rollover carries metadata/crew, adds daily hours to
total, advances meter readings and closing inventory, and clears daily entries.
These formulas follow the reference.

Export contains all seven sections and transaction details regardless of
Scroll/Steps or expanded detail state. Embedded UTF8 JSON, zlib, base64 and
`jspdf:metadata` XML preserve reference interchange. Missing older fields are
filled without invalidating imported finalization; older finalized dates are
supported. There were no pre-existing stored-report fixtures in this checkout.
Compatibility checks therefore use the exact reference metadata representation
and normalized older records, plus new PDF round trips.

## Reproduction and evidence

`python tools/validate_vdr.py --reference "C:\Users\rayha\Downloads\index (6).html" --shell`
creates deterministic evidence in `docs/diagnostics/vdr`. `--interactive` opens
the isolated fixture for review; it does not populate production reports or
change the telemetry gate. The shell option selects the real VDR page for
inspection without changing production module access rules.

Reference measured topbar: 61.5px; native: 62px. Reference sidebar: 257.6px
outer width (232px content plus padding/borders), native: 258px. Reference
sidebar height: 644.9px; native: 645px. Both use 20px workspace margins/gap,
24px section horizontal padding, light report surfaces and square 1px grids.
Exact table column sizes are kept with local horizontal scroll.

Intentional differences: GDS fonts and branding, configured production data,
numbered native navigation, native calendar/combo controls, local weather glyphs,
Qt scroll areas for sticky chrome, and native font/layout metrics. PDF styling
uses GDS branding and embeds the local fonts. QtPdf's renderer omits repeated
page chrome in its second-page raster; independent MuPDF rendering verifies the
header/footer are present in the actual PDF.

No NAV, map resource, Configure page or VJR source was edited. The main window's
header visibility change affects VDR only; pre-existing unrelated working-tree
changes remain. No commit was created.
