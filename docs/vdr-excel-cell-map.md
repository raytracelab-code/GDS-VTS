# VDR Excel snapshot cell map

Source: `16092026 VDR Executive Brilliance .xlsx`, 139111 bytes, SHA-256 `94b92a23932300dd7795cbe86a11fdec4ce3b6e2158df259994dea98d2521161`.
Bundled immutable copy: `app/resources/templates/vdr_executive_brilliance_template.xlsx`.
Service: `app/vdr/excel.py::VdrExcelExporter`. UI uses domain/store data, never label scraping.

Every export opens fresh verified template bytes. openpyxl validates names/order, visibility, and critical labels. The exporter patches only mapped worksheet cell values in the original OOXML ZIP. It retains cell styles, formats, merges, dimensions, protection, print setup, drawings, relationships, namespaces/extensions, workbook metadata, and all unrelated ZIP parts. `VDR GUIDE` remains byte-for-byte unchanged. No sheet is added, removed, reordered, or unhidden. Text is written as literal inline strings, including leading `=`, and cannot become an Excel formula. Dates are real Excel serial dates using the workbook epoch and existing template date formats; numeric data are numbers; durations are fractional days in existing `[h]:mm` cells. Clock values are four-character strings, including `0000` and `2400`.

## Identity and main report

The UI passes its existing configured identity provider (`QSettings('GDS','VTS')`: `vessel/name`, `vessel/date_of_hire`, `vessel/client`). An explicit empty provider does not fall back to imported identity or template samples. The current Configure page has no additional vessel/hire input controls; unavailable configuration exports blank as requested. Direct service callers may supply authoritative identity explicitly; otherwise the report's identity snapshot is used. Existing report state is never modified by export.

| Source / helper | Destination | Type / transformation |
|---|---|---|
| configured identity.vessel | GDS Meta!C9, VDR!E12 | Text; blank when absent |
| configured identity.hireDate | GDS Meta!C10, VDR!I12 | Excel date; blank when absent |
| identity.client, when nonempty | GDS Meta!C11 | Existing matching client name; other template client metadata retained |
| meta.date | VDR!B12 | Excel date |
| report_number(report, identity) | VDR!C12 | Integer, hire-date day one (`tour_days`); blank without hire date |
| meta.captain, meta.loc24 | VDR!J12, L12 | Text |
| meta.fwd, meta.aft | VDR!P12, T12 | Number |
| hse_perfect_days(report, identity) | VDR!E15 | Existing UI calculation extracted to shared domain helper; report date minus latest HSE/hire date, floor zero |
| hse.inc24 | VDR!E16, FLEET MANAGEMENT!D3 | Text or blank |
| hse.lti | VDR!E17, FLEET MANAGEMENT!D4 | Excel date or blank |
| hse.inj | VDR!E18, FLEET MANAGEMENT!D5 | Excel date or blank |
| hse.incd | VDR!E19 | Excel date or blank; never substituted for containment loss |
| hse.containment_loss | FLEET MANAGEMENT!D6 | Excel date or blank; no visible VDR row inserted |
| end.fuel, end.water, end.prov | VDR!H16, H17, H18 | Number or blank |
| end.nextProv | VDR!H19 | Existing free-text supply field |
| wx[0:4].wind, swell, sea, sky, vis, temp | VDR!L16:L19, N16:N19, P16:P19, R16:R19, T16:T19, U16:U19 respectively | Numeric wind/swell/visibility/temperature; text sea/sky. Fixed K16:K19 labels unchanged |

No existing report-number helper was present. `report_number` therefore uses existing `tour_days` to reproduce the template's report date minus hire date plus one. The UI Perfect Days expression was moved unchanged into `hse_perfect_days`; both UI and export use it.

## Activity and locations

| Source / helper | Destination | Type / transformation |
|---|---|---|
| calculate(report).actD[i].fromM | VDR!W14:W103 | Four-digit clock string |
| acts[i].to, interpreted through actD.toM | VDR!X14:X103 | Four-digit clock string |
| calculate(report).actD[i].min | VDR!Y14:Y103 | Minute count / 1440, `[h]:mm` |
| acts[i].act, cat, dp, lifts, pob | VDR!Z, AE, AG, AH, AI rows 14:103 | Text, text, text, number, number |
| acts[i].loc through derive_location_durations | VDR!AK14:AN103 | FROM, TO, duration, location; existing contiguous-visit helper reused |
| activity_summary(report).locations | VDR!R82:R103 and T82:T103 | First-seen unique location; aggregate minutes from derived visits / 1440 |
| activity_summary(report).movement | VDR!I82, I83, I84, I86, I87, I89:I93 | Categories below; sum authoritative valid interval minutes / 1440 |
| unused categories K–R | VDR!I94:I101 | Explicit zero duration |
| activity_summary(report).total, .dp | VDR!I102, I103 | Coverage and Y-mode duration / 1440 |

Capacity: 90 activity rows; 90 contiguous periods; 22 unique location totals. Overflow blocks export. All unused activity/location-log slots through row 103 and location totals through row 103 are blanked. The shared activity-summary helper consumes existing `calculate().actD` and `derive_location_durations`, preserving their timing, invalid-row and grouping rules.

| Movement category | VDR duration | Fleet duration |
|---|---|---|
| Maneuvering at Supply Base | I82 | D84 |
| Alongside berth at Supply Base | I83 | D85 |
| Anchorage at Supply Base | I84 | D86 |
| En-route: full speed | I86 | D87 |
| En-route: economical speed | I87 | D88 |
| Inter-rig/ Maneuvering offshore | I89 | D89 |
| Standby steaming offshore | I90 | D90 |
| Cargo works within 500m zone | I91 | D91 |
| Towing/ Static Towing/ Rigmove/ Hose Handling | I92 | D92 |
| Mooring to buoy/platform offshore | I93 | D93 |

Fleet's shorter `Towing/ Static Tow/ Rigmove` label is retained; its value uses the current full category above. Unknown categories block export.

## Equipment

All equipment is matched by trimmed, whitespace-normalized, case-insensitive name, not list position. Duplicate or unknown names block export. Absent equipment outputs are blanked.

| Canonical equipment | VDR row |
|---|---|
| PORT ME / PORT ME OUTLET FLOWMETER | 23 / 24 |
| CENTER ME (P) / CENTER ME (P) OUTLET FLOWMETER | 25 / 26 |
| CENTER ME (STBD) / CENTER ME (STBD) OUTLET FLOWMETER | 27 / 28 |
| STBD ME / STBD ME OUTLET FLOWMETER | 29 / 30 |
| BOW THRUSTER 1 / 2 / 3 | 31 / 32 / 33 |
| STERN THRUSTER 1 / 2 | 34 / 35 |
| SHAFT GENERATOR 1 / 2 | 36 / 37 |
| GENERATOR 1–6 | 38–43 |
| EMERGENCY GENERATOR | 44 |

`eq.total → H`, `eq.daily → J`, `eq.fm0 → L`, `eq.fm24 → P`, `calculate().eqCons[index] → T` on the matching VDR row, all numeric. `calculate().totalCons → VDR!T45` and `FLEET MANAGEMENT!D74`.

**Explicit application mapping decision:** Fleet's original references are broken and its three block headings are absent. This exporter implements the requested meaning:

- D8:D29: Flowmeter @0000H (`eq.fm0`).
- D30:D51: Flowmeter @2400H (`eq.fm24`).
- D52:D73: calculated equipment consumption (`calculate().eqCons`).

For each block, the original B-column label determines the equipment. Port/Stbd Main Engine and Port/Stbd Center Main Engine names map to the corresponding ME names above; Outlet maps to OUTLET FLOWMETER. `(L)` unit suffix is ignored. `Bow Thruster (L)` in rows 38 and 60 means BOW THRUSTER 1. Stern Thruster **2** precedes Stern Thruster **1** in each Fleet block; this order is explicitly respected by name. Other thrusters and generators match their canonical names. No broken Fleet formula is retained in an output cell.

## Bulk inventory

| Item | VDR row |
|---|---|
| FUEL (ltrs) | 52 (six transfer slots 52–57) |
| FRESH WATER (ltrs) / LUB. OIL (ltrs) / GEAR OIL (ltrs) / DISPERSANT (ltrs) | 58 / 59 / 60 / 61 |
| DRILL WATER (ltrs) / CEMENT (Slag) (mt) / CEMENT (mt) / BARITE (mt) | 62 / 63 / 64 / 65 |
| SARAPAR (bbls) / BENTONITE (mt) / New OBM (bbls) / Used OBM (bbls) | 66 / 67 / 68 / 69 |
| VERSAPRO 9.3PPG (bbls) / OBM 7,5 PPG (bbls) / OBM 7,8 PPG (bbls) | 70 / 71 / 72 |
| SBM (bbls) / FOAM / BASE OIL (bbls) / NABM (bbls) / PREMIX (bbls) | 73 / 74 / 75 / 76 / 77 |

Names use the same normalization as equipment. Unknown or duplicate names block export; missing item destinations are cleared.

The shared domain/UI fuel predicate accepts case and surrounding whitespace in imported names, matching exporter name normalization. Fuel still uses the existing total equipment consumption and closing arithmetic; no alternate exporter calculation is used.

| Source | Destination on item row | Type |
|---|---|---|
| bulk.open | C | Number |
| bulk.rcvFrom | D | Text |
| bulk.rcvQty, rcvB, rcvA | E, F, G | Number |
| bulk.rcvTicket | H | Text |
| bulk.cons | I | Number; FUEL uses calculate().totalCons |
| bulk.tr[].to | K (fuel), merged J:K anchor J (non-fuel) | Text |
| bulk.tr[].qty, mb, ma | L, N, P | Number |
| bulk.tr[].tk | R | Text |
| calculate().bulkClose[index] | T | Number; existing two-decimal app result, not template formula rounding |
| bulk.remarks | U | Text |

The requested logical K receiver destination is physically merged J:K for non-fuel rows 58–77. The exporter writes the merge anchor J, retaining the original merge. Fuel J52:J57 fixed #1–#6 labels are never overwritten. Fuel transfer slots 52–57 are all cleared, but all-sheet export blocks above **two** transfers because Fleet supports only two. Non-fuel capacity is **one** transfer per item; overflow blocks with item/count/capacity. `bulk.det` is a UI disclosure flag and is not an Excel data field.

| Fuel source | FLEET MANAGEMENT |
|---|---|
| calculate().totalCons | D74 |
| fuel.rcvQty / rcvFrom | D75 / D76 |
| fuel.tr[0].qty / to | D77 / D78 |
| fuel.tr[1].qty / to | D79 / D80 |
| fuel.open / calculate().bulkClose[fuel index] | D81 / D82 |

## People

All mapped cells in rows 6–205 are cleared first, including old numbering and working-day formulas. Completely blank form rows are omitted. Populated records retain source order and get sequential numeric numbering. More than 200 rows in either input list blocks export.

| Source | CORE-CREW | Type / transformation |
|---|---|---|
| ordinal | B6:B205 | Number |
| crew.name / rank / age / nat / ic | C / D / E / F / G | Text, text, number, country name, text |
| crew.signon | H | Excel date |
| tour_days(signon, meta.date) | I | Integer, same inclusive working days as VDR |
| crew.comments | J | Text |

`CONTRACTORS` B:G rows 6:205 receive ordinal, `ctr.name`, `vendor`, numeric `age`, nationality name, and `ic`. Country codes use the existing bundled `countryCodes` mapping, matching VDR/PDF nationality names; already textual values remain text. Unmapped production identity fields do not exist in the domain; no values are invented.

## Export policy, failures, and packaging

Finalized state is required, like PDF download. Existing domain validation is checked again to avoid publishing inconsistent imported state. Invalid numeric/date/text values, mapping failures, capacity excess, unknown/duplicate equipment/bulk names, missing or wrong template, or write/lock failures abort. An in-memory completed ZIP is written to a temporary sibling file, flushed, then atomically replaced; existing output survives failed export. The original/bundled template path and hard links to it cannot be destinations.

Only the normal native save dialog chooses the output. Windows-safe default: `VDR_<configured vessel or Vessel>_<YYYY-MM-DD>.xlsx`. PDF download remains available separately. No report mutation, new undo entry, autosave schema change, or Excel recalculation is needed for report outputs. Existing unrelated template metadata/formulas remain intact.

Development resources resolve relative to the module. Frozen resources resolve below `sys._MEIPASS/app/resources`. `gds_vts.spec` includes the entire existing app resource tree (including template, catalogs and fonts) and openpyxl hooks. With PyInstaller and the project dependencies installed, build with `pyinstaller gds_vts.spec`; an executable build itself is not part of the source/test validation.
