# GDS VTS Full Application Audit

| | |
|---|---|
| **Audit date** | 19 November 2026 |
| **Branch** | `feature/nav-squall-phase3` (HEAD `99302a2`) plus uncommitted VJR work, listed in [Environment](#environment) |
| **Audit type** | End-user / product audit. No fixes were applied and nothing was committed. |
| **Evidence folder** | [`docs/evidence/application-audit/`](evidence/application-audit/), with subfolders `shell/`, `vdr/`, `vjr/`, `nav/`, `platform/` and `pytest-summary.txt` |

---

## Executive Summary

### Overall state

GDS VTS is a well-engineered application with a strong design language. The two reporting modules (VDR, VJR) do the hardest thing right: they write into the original Excel templates without breaking them. Saving is careful in several ways. Files are written atomically, a damaged file is never overwritten, and the Excel template is checked before export. The NAV map has a deep provider and offline-map stack, and its network work runs off the screen-drawing thread (the GUI thread).

From a real operator's point of view, though, the application is **not yet ready for production**. Problems fall into four groups:

1. **Identity data cannot be entered.** No screen in the app lets the user enter the vessel name, client or Date of Hire. VDR's Report No. and HSE "perfect days" are calculated from the Date of Hire. So on a clean install every VDR Excel export has a blank vessel name, a blank Date of Hire and a blank Report No.
2. **Report data can silently become wrong or unrecoverable.**
   - **Stale carry-forward:** opening stock, flowmeter readings and run hours carried into the next day do not update when the previous day is corrected.
   - **Store lockout:** one bad or over-long field makes the whole VDR store unreadable, and every later save is refused. The only warning is small grey text.
   - **Silent reopen:** a single keystroke turns a finalized report back into a draft, with no prompt.
3. **Connectivity is not finished as a user feature.**
   - **Live data never shown:** the "Live Telemetry" panel on Configure never shows data; nothing in the code calls its update method.
   - **Silent errors:** every connection error is thrown away, so the user never sees it.
   - **No disconnect, stale status:** there is no Disconnect button. The USB status keeps saying CONNECTED after the cable is pulled.
   - **BLE:** BLE data delivery is very likely broken.
4. **NAV can mislead.**
   - **Zero shown as missing:** speed 0 and heading 000° are displayed as "—" (no data).
   - **Invented heading:** a missing heading is drawn as an arrow pointing north.
   - **No stale or lost state:** the vessel marker never shows that telemetry is stale or lost.
   - **No internet at startup:** if the app starts without internet, the basemap stays blank with no retry. The offline map regions dialog cannot be opened from the UI.

### Strongest areas
- **Excel export (VDR and VJR):**
  - The exporter edits the template's own internal files directly, so merged cells, formatting and the template's drop-down rules survive.
  - Capacity overflow is reported instead of silently cutting data off.
  - Unicode, `&`, `<`, `=` and long text are written safely.
- **Safe storage writes.** Each save writes a temp file, flushes it to disk, then swaps it in. An unreadable store is never overwritten.
- **VJR mobile photo upload.** Security is well designed: random single-use tokens with expiry, private-network-only binding, Host/Origin checks, file-type sniffing and size caps.
- **Visual design** of VDR and VJR: consistent, modern and clean.
- **Test coverage:** 754 automated tests. 751 pass; the 3 that fail are listed in [Environment](#environment).

### Weakest areas
- **Connectivity** (Configure page, USB, BLE): about a third of the visible UI is unconnected to the code behind it.
- **Settings:** there is no Settings page.
- **Release engineering:**
  - The `dist/` build is stale and does not contain VJR.
  - There is no installer and no code signing.
  - The Windows 7 and Windows 10/11 builds both produce the same `GDS VTS.exe` with version `0.0.0.0`.
  - A crash in the packaged app is invisible to the user.
- **Consistency between modules:**
  - VDR and VJR use different validation, autosave and undo models.
  - The screen, the PDF and the Excel export use different sources for the hire date.

### Major risks
1. A wrong or blank daily report is sent to the client: no identity fields, stale opening stock, export rules that differ from finalize rules.
2. A day's work is lost. One bad field locks the store, and the only indication is faint text.
3. Operators trust a live-looking display that is actually stale: USB still "CONNECTED", NAV marker still full-colour, health tiles still "LIVE".
4. The vessel position is sent to public third-party Overpass servers by default, without disclosure.
5. The Windows 7/8 build can crash (an access violation in shapely, seen in stress logs). The packaged build in `dist/` is out of date.

### Production-ready?
**No.** Verdict **D. NOT YET PRODUCTION READY**; see the [final section](#production-readiness-verdict). Most fixes are low to medium complexity. The architecture is sound, so roughly 4–6 focused weeks could plausibly reach verdict C or B.

### Recommended next priorities
1. Vessel identity in Configure, used as the single source for VDR, VJR and exports.
2. Data-integrity hardening: store recovery, live carry-forward, one rule set shared by finalize and export, read-only finalized reports.
3. Connectivity wiring: telemetry panel, error and state reporting, Disconnect, reconnect, BLE event loop.
4. NAV truthfulness: zero values, no-heading marker, stale/lost marker, offline and WebGL messaging.
5. Release engineering: rebuild, versioning, installer, crash dialog and log access.

---

## Audit Scope

Covered:

| Area | How it was audited |
|---|---|
| Startup, shell, navigation rail, header | Headless launch of the real `MainWindow` (Qt test-mode paths, so real user data was untouched). Screenshots at 1366×768, 1600×900 and 1920×1080. Startup and shutdown timing. |
| Configure, USB/Serial, BLE, telemetry | Code review. Probes using a fake serial port and crafted JSON. Offscreen UI probes. No real hardware was present: `list_ports.comports()` returned `[]`. |
| VDR (all 7 sections, finalize, undo/redo, autosave, PDF import/export, Excel) | Drove the model, store and UI headlessly with temporary stores. Generated real PDF and XLSX files from dense and edge-case data and compared them with the template. |
| VJR (all 7 sections, photo workflow, Excel) | Same approach as VDR. Tested the photo server with real HTTP requests on the LAN interface. |
| NAV / Map | Headless launch of `NavPage`. Provider timeout and shutdown probes. Track and render-state growth measurement. Analysis of the stress logs under `build/`. |
| Settings, Camera | Searched the code. Neither exists as a feature; see the module reviews. |
| Windows compatibility, packaging, distribution | Spec files, requirements, preflight script, manifest. Launched the packaged `dist\GDS VTS\GDS VTS.exe` with `--validation-profile`. |

**Not covered or limited:**
- No physical Patroller-I, FTDI, CDC or BLE device.
- No physical Windows 7/8/8.1 machine. Legacy behaviour was judged from the `.venv-win7` runtime and the stress logs.
- No real phone upload over Wi-Fi. HTTP requests were made from the PC.
- WebGL does not render offscreen, so the NAV visuals were judged from code, the controls layout and logs.
- PDFs were checked by text extraction; no rasteriser was available.
- Exports were inspected with openpyxl, not opened in Microsoft Excel.

Items that depend on these are marked **(unverified)**.

---

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| Modern runtime | `.venv`: Python 3.13.15, PySide6 6.12.0, bleak 3.0.2 |
| Legacy runtime | `.venv-win7`: Python 3.8.10, PySide2 5.15.2.1, bleak 0.22.3 |
| Packaged build present | `dist\GDS VTS\` is a **legacy (PySide2) build** from 2026-11-19 08:36, 1,778 files, ~394 MB |
| Branch / HEAD | `feature/nav-squall-phase3` / `99302a2 Finalize Windows compatibility build candidate` |

**Uncommitted changes at audit start:**
- **Modified:**
  - `.saropa/diagnostics/history.json`
  - `app/ui/components/top_tabs.py`: VJR no longer locked behind live telemetry
  - `app/ui/pages/vjr_page.py`
  - `gds_vts.spec`, `gds_vts_win7.spec`: qrcode/PIL/QtNetwork hidden imports
  - `requirements.txt`, `requirements-win7.txt`: Pillow, qrcode, pypng, colorama
  - `tests/test_nav_map_first.py`, `tests/test_vdr_navigation.py`
- **Untracked:**
  - the whole VJR module: `app/vjr/`, `app/ui/pages/vjr_*.py`, `app/resources/vjr/`, `vjr_template.xlsx`
  - VJR tests, tools and docs
  - VJR evidence

So **the VJR feature, including the photo workflow, is not committed yet.**

**Test suite** (`.venv`, `pytest -q`): **751 passed, 3 failed** in 4 min 51 s.
- All 3 failures are `tests/test_vdr.py::test_wide_grids_fill_available_width_without_compressing_columns[bulk|crew|ctr]`. In each, the column widths add up to 1310 px against a 1169 px viewport.
- The log also contains a non-fatal `Windows fatal exception: code 0x8001010d` (a COM re-entrancy error) dump.
- See `evidence/application-audit/pytest-summary.txt`.

Passing tests only show that the code matches its own tests. They say little about usability.

---

## Severity summary

| Priority | Count |
|---|---|
| **P0 — Critical** | **3** |
| **P1 — High** | **22** |
| **P2 — Medium** | **25** |
| **P3 — Low** | **11** |
| **Total** | **61** (related issues grouped) |

### Master summary table

| ID | PRIORITY | MODULE | ISSUE | USER IMPACT | RECOMMENDED ACTION |
|---|---|---|---|---|---|
| GDS-AUDIT-001 | P0 | Configure / VDR / VJR / Exports | Vessel name, client and Date of Hire cannot be entered anywhere. Excel uses a different hire-date source than the screen and the PDF. | Every VDR export from a clean install has blank vessel name, Date of Hire and Report No. Screen, PDF and Excel can disagree. | Add a Vessel Identity section to Configure as the single source for all modules and exports. |
| GDS-AUDIT-002 | P0 | VDR | Carried-forward opening stock, flowmeter readings and run hours do not update when the previous day is corrected | Wrong ROB and meter readings in exported reports, with no warning | Link carried values to the previous day, or re-derive them; warn when they don't match |
| GDS-AUDIT-003 | P0 | VDR / VJR storage | One malformed record or over-long field makes the whole store unreadable; every later save is refused | All history inaccessible; new work silently not saved | Quarantine bad records per day, cap input lengths, keep backups, show a recovery banner |
| GDS-AUDIT-004 | P1 | VDR | Report finalizes successfully but Excel export then fails (finalize and export use different rules) | User can't produce the deliverable; must un-finalize to fix | Run the exporter checks as a dry run at Finalize; limit the UI to template capacity |
| GDS-AUDIT-005 | P1 | VDR | A finalized report silently returns to draft on a single keystroke | A sent report can be altered by accident; the audit trail is lost | Read-only when finalized; explicit "Reopen" with confirmation |
| GDS-AUDIT-006 | P1 | VDR | Typing TO = 2400 on an earlier activity row deletes every later row without asking | Activity log lost by accident | Never delete on a time edit; confirm; one undo step |
| GDS-AUDIT-007 | P1 | VDR | A comma decimal ("2,5") is read as 25 | Drafts and quantities off by ×10 or ×1000 | Strict number parsing plus plausibility ranges |
| GDS-AUDIT-008 | P1 | VDR | A missed day (weekend, shore leave) gives a completely blank next report | Whole crew list and opening stock re-keyed; error-prone | Roll over from the most recent earlier report |
| GDS-AUDIT-009 | P1 | VDR / PDF | PDF export crashes on a long activity cell or on an imported invalid report, showing a raw error | No PDF; confusing technical message | Allow long cells to split across pages; re-validate imports; friendly errors |
| GDS-AUDIT-010 | P1 | VJR | No required fields and no date-order checks; a blank or illogical VJR exports without complaint | Wrong voyage reports sent to the client | Required-field and cross-field rules (departure ≤ ETA, etc.) |
| GDS-AUDIT-011 | P1 | VJR | Only one VJR file exists and there is no "New voyage" action | Each new voyage means manually clearing up to hundreds of rows | New/Archive voyage, one file per voyage |
| GDS-AUDIT-012 | P1 | Configure | The Live Telemetry panel never updates (nothing calls `update_frame`) | 26 fields always show "—" while the header says LIVE | Wire the panel into the refresh loop |
| GDS-AUDIT-013 | P1 | Connectivity | Transport errors and disconnect events never reach the UI; unplugging still shows CONNECTED | Silent failures; stale status trusted | Send errors and state changes to the UI as Qt signals; show plain-language messages |
| GDS-AUDIT-014 | P1 | Connectivity | No Disconnect button; reconnecting leaks the open COM port; app close does not disconnect | Port stays locked; needs an app restart | Add Disconnect; make connect idempotent; disconnect in `closeEvent` |
| GDS-AUDIT-015 | P1 | Connectivity / BLE | The BLE event loop closes right after connect, so notifications are very likely lost; scan and connect freeze the UI | BLE shows connected but no data arrives (unverified on hardware) | Run one long-lived event loop for BLE in a background thread; make scan and connect asynchronous |
| GDS-AUDIT-016 | P1 | NAV | Speed or heading of 0 is shown as "—"; a missing heading is drawn as an arrow pointing north | Stationary vessel looks like it has no data; bow direction is made up | `is None` checks; a marker with no direction when heading is missing |
| GDS-AUDIT-017 | P1 | NAV | Vessel marker never indicates stale or lost telemetry; track still says RECORDING | Operator trusts an old position | Pass telemetry status to the map; grey the marker; show a LOST banner |
| GDS-AUDIT-018 | P1 | NAV | No internet at startup gives a blank basemap with no retry; the offline regions dialog cannot be opened from the UI | Featureless map until restart; offline charts unusable | Retry with backoff; fall back to installed regions automatically; expose "Map regions" |
| GDS-AUDIT-019 | P1 | NAV / Platform | WebGL, renderer or WebEngine failure is not detected; status still says READY | Blank map that claims to be ready; on legacy, the whole app may fail to start | Detect and report failures; software-GL fallback; load WebEngine lazily |
| GDS-AUDIT-020 | P1 | NAV | Track history is unbounded and the whole track is rebuilt and re-sent on every frame | UI gets progressively sluggish over days at sea | Thin out old track points, send only new points, keep a running distance total |
| GDS-AUDIT-021 | P1 | NAV / Squall | No production squall feed; impact is not judged against the vessel; ETA does not count down | "No active events" read as an all-clear | Show feed status; evaluate against own position; top-level alert |
| GDS-AUDIT-022 | P1 | NAV / Privacy | Exact vessel position is sent to public Overpass servers by default, without disclosure | Third parties can reconstruct the vessel's track | Opt-in; quantise query areas; disclose |
| GDS-AUDIT-023 | P1 | NAV / Shutdown | Shutdown waits for in-flight provider requests: 32 s measured, and no limit if Copernicus is configured | Invisible process keeps running after close; relaunch problems | Time-limited shutdown; cancel open network requests; timeouts everywhere |
| GDS-AUDIT-024 | P1 | Windows 7/8 build | Access violation in shapely during Malaysia GIS load (2 of 3 non-default stress runs) | Crash of the whole app on legacy PCs | Reproduce, isolate the GIS work on one thread or pre-validate, re-pin shapely |
| GDS-AUDIT-025 | P1 | Packaging | `dist/` is stale (no VJR); both builds produce an identical `GDS VTS.exe` with version 0.0.0.0 | Wrong build shipped; support cannot tell builds apart | Rebuild from a committed tree; distinct names; real version and git SHA |
| GDS-AUDIT-026 | P2 | VJR | Hourly Voyage Progress entry is slow: blank rows only, calendar-only date entry, full page rebuild on each add | ~1,440 entries plus 72 calendar picks for a 3-day voyage | "Add next hour" copying the previous row; dates you can type |
| GDS-AUDIT-027 | P2 | VDR / VJR | Validation feedback is inconsistent: VDR never marks the field, VJR shows only the first error | Users can't find what to fix | Inline field marking plus an issue list in both modules |
| GDS-AUDIT-028 | P2 | VDR | Missing domain checks (run hours > 24, total < daily, unnamed crew rows, duplicates, etc.) | Implausible data accepted | Add domain rules |
| GDS-AUDIT-029 | P2 | VDR / PDF | PDF drops non-Latin characters and leaves out location summary, Report No., HSE perfect days and crew comments | PDF differs from Excel | Font with fallback glyphs; parity with Excel content |
| GDS-AUDIT-030 | P2 | VDR | Location names differ by case; the UI never shows the exported location summary; the 22-location cap is found only at export | Duplicate locations in the report | Normalise names; show "as exported" summary |
| GDS-AUDIT-031 | P2 | VDR / VJR | Undo per keystroke, 100-step cap, focus lost on undo; VJR writes to disk on every keystroke | Undo unusable for real edits; heavy disk I/O | Group undo by field; debounce saving |
| GDS-AUDIT-032 | P2 | VDR | Weather: no wind direction; 21 Tab presses between slots | Template content can't be entered; slow entry | Direction field; tab order skips chip buttons |
| GDS-AUDIT-033 | P2 | VDR / VJR | At 1366×768, tables need horizontal scrolling with hidden delete/comment columns; VJR progress has nested scrollbars; 3 layout tests fail | Hidden controls; context lost while scrolling | Frozen key columns; full-height tables; fix the failing tests |
| GDS-AUDIT-034 | P2 | VJR | No upper limits on speed, visibility, wind, wave | Typos accepted (999 kn) | Template ranges |
| GDS-AUDIT-035 | P2 | VJR / Excel | "N days ago" cells are frozen at export time; hour/minute exported as numbers instead of text | Stale annotations; Excel flags the cells as invalid | Keep the formulas; zero-padded text |
| GDS-AUDIT-036 | P2 | VJR | The template's drop-down lists (Sky, Rank, Locations, Countries) are not offered | Free-text values that the template rejects | Editable combo boxes with the template lists |
| GDS-AUDIT-037 | P2 | VJR | Arrival drafts, requirements and personnel are locked to the departure values | Real arrival drafts can't be recorded | Product decision; arrival-specific fields |
| GDS-AUDIT-038 | P2 | VJR / Photo | Photo server keeps listening after the session; 4 idle connections block uploads; changing network card cancels the other QR code | Needless LAN exposure; confusing failures | Stop when idle; per-IP limits; one server per card |
| GDS-AUDIT-039 | P2 | VJR | Voyage Progress is capped at 100 rows (~4 days hourly) | Long voyages can't be logged hourly | Template overflow strategy |
| GDS-AUDIT-040 | P2 | Shell | Global header shown on Configure/VJR but hidden on VDR/NAV: double header on VJR, telemetry status invisible on VDR/NAV | Lost space; inconsistent status visibility | One shell header policy; status indicator in the rail |
| GDS-AUDIT-041 | P2 | Configure / Telemetry | No units on values; health tiles stay "LIVE" when stale; STALE/LOST can never be reached; diagnostics fields hard-coded "—" | Unfinished look; misleading health | Units, freshness-aware tiles, real diagnostics |
| GDS-AUDIT-042 | P2 | Telemetry | Validator accepts any JSON; coordinate heuristic misreads values; one malformed line kills the stream; unbounded buffer | Garbage goes "LIVE"; silent stream death | Strict validation; per-line error isolation; capped buffer |
| GDS-AUDIT-043 | P2 | Configure / USB | Device details always show the first port; last port not remembered; connection mode not saved | Wrong port chosen; repeated setup | Follow the selection; remember the last device |
| GDS-AUDIT-044 | P2 | Settings | No Settings page; validation profile writes to the real registry settings | No customisation; test runs pollute user settings | Minimal Settings page; isolate the validation profile |
| GDS-AUDIT-045 | P2 | NAV | 11 of 13 map tools icon-only; Centre/Fit do nothing silently without position; map opens over Bangladesh; very long Layers panel | Ambiguous controls; confusing start | Labels, a no-position overlay, a sensible default view |
| GDS-AUDIT-046 | P2 | NAV | Status badge, status text and provider states contradict each other; full maritime state (6.5 MB) rebuilt on the GUI thread every ~30 s | Mixed signals; CPU spikes | Status from one source; send only changes |
| GDS-AUDIT-047 | P2 | Distribution | No installer, unsigned exe and script, preflight blocked by default execution policy, firewall prompt not documented | Needs technical knowledge to install | Signed installer with prerequisites and firewall rule |
| GDS-AUDIT-048 | P2 | Reliability / Support | Packaged crash invisible; log has no timestamps and its location is not discoverable; false "fatal exception" lines; debug prints | Support can't diagnose | Crash dialog with log path; timestamps; "Open logs" |
| GDS-AUDIT-049 | P2 | All | Terminology: SETUP vs Configure, VDR/VJR never spelt out, POB vs NON-CREW POB, "Reader revision", "Patroller-I", "PID", ROB/FW/DW/NABM unexplained, "WEATHER" button opens squall list | Confusion for new crew | Glossary, tooltips, consistent labels |
| GDS-AUDIT-050 | P2 | Build | Modern requirements not locked; PyInstaller and 2 runtime packages missing from `requirements.txt` | Builds not reproducible | Lock file for the modern build |
| GDS-AUDIT-051 | P3 | VDR | Browsing past dates creates and saves empty stub reports | Clutter; confusing history | Create only on first edit |
| GDS-AUDIT-052 | P3 | VDR | Carried-forward numbers show as "5650.0" or "1.23e+16" | Untidy; precision loss | Number formatting |
| GDS-AUDIT-053 | P3 | VDR | Slow with large crew lists (2 s per added row at 120 crew) | Sluggish entry | Update the affected row only |
| GDS-AUDIT-054 | P3 | VJR | Filenames collide (`VJR_Vessel_Undated.xlsx`); raw timestamp with microseconds | Overwrites; ugly metadata | Better default names; local time |
| GDS-AUDIT-055 | P3 | VJR | "Delete row" button silently does nothing; per-row × deletes with no confirmation | Confusion | Fix selection; undo toast |
| GDS-AUDIT-056 | P3 | VJR | Visual polish gaps compared with VDR: raw ISO dates, inconsistent heading case, no required markers, no keyboard legend, no issue badge | Feels less finished than VDR | Align with VDR conventions |
| GDS-AUDIT-057 | P3 | NAV | Placeholder text with corrupted characters ("Position ?", "COG ??"); debug output printed in production | Looks broken | Fix the text; gate debug logging |
| GDS-AUDIT-058 | P3 | NAV | Legacy Copernicus shown as "NOT CONFIGURED" instead of "UNAVAILABLE"; satellite layer blurry at harbour scale | Minor confusion | Wording; cap zoom with a note |
| GDS-AUDIT-059 | P3 | VJR / Photo | Original uploaded photo keeps GPS location data on disk | Minor privacy | Strip location data from the original too, or delete it |
| GDS-AUDIT-060 | P3 | Packaging | 394 MB bundle includes unused Qt modules (3D, Charts, Multimedia, etc.) | Large download | Excludes and pruning |
| GDS-AUDIT-061 | P3 | Repository | Junk files committed; dead code (`sidebar.py`, NAV stub page, module gate, `Settings`, recorder); 601 MB `build/` | Maintainability; confusion | Clean up |

---

## Critical Findings

### GDS-AUDIT-001: Vessel identity (name, client, Date of Hire) cannot be entered; exports use inconsistent identity sources
- **Module:** Configure / VDR / VJR / Exports
- **Severity:** P0
- **Category:** Data integrity / incorrect exported report / missing functionality

**Observed behaviour**
- VDR and VJR both read the vessel identity from the saved settings keys `vessel/name`, `vessel/client` and `vessel/date_of_hire`. Nothing in the application ever writes these keys. A code search finds only readers.
- The Configure page has no identity fields: it contains only connection, telemetry and diagnostics. There is no Settings page.
- On a clean install:
  - VDR shows **"UNNAMED VESSEL"** and **"DATE OF HIRE —"**.
  - VDR **Report No.** and **HSE Perfect Days** are calculated from the hire date, so they are blank or wrong.
  - The Excel exporter writes the vessel name and hire date from these settings, which are blank, into `GDS Meta!C9:C10` and `E12/I12`.
- In addition, the screen and the PDF use the identity copied into each report at rollover, while Excel uses the current settings. With a hire date present in settings, the screen showed Report No. 322 / perfect days 321, but the exported Excel showed **171 / 170**.

**Expected behaviour:** The user enters vessel name, IMO, client, Date of Hire and master once, in Configure. Every module, display and export uses this one source.

**User impact:**
- Every daily report exported from a fresh installation lacks the vessel name, Date of Hire and Report No.
- The only workarounds are editing the Windows registry by hand or importing an old PDF.
- When identity data exists, the PDF and the Excel copy of the same day can disagree.
- VJR has the same gap: vessel name, IMO, deck space and captain must be retyped, and the captain is entered separately in VDR too.

**Reproduction steps:**
1. Fresh profile (no `HKCU\Software\GDS\VTS\vessel` keys).
2. Open VDR. The header shows "UNNAMED VESSEL" and "DATE OF HIRE —".
3. Look for a field to set either. None exists.
4. Fill in the day, finalize and download Excel. Vessel name, Date of Hire and Report No. cells are empty.

**Evidence:**
- `app/ui/pages/vdr/workspace.py:50-53`, `:156-157` and `:399-401` (comment: "Configure is authoritative for vessel/hire identity").
- `app/ui/pages/vjr_workspace.py:152-155`.
- `app/vdr/model.py:121-135` (Report No. and perfect days come from `hireDate`).
- `app/vdr/excel.py:192-196`.
- No writer: a search for `vessel/` and `hire` in `app/` finds readers only.
- Screenshot `evidence/application-audit/shell/vdr-1366x768.png` ("UNNAMED VESSEL", "DATE OF HIRE —").
- `evidence/application-audit/vdr/identity_mismatch.xlsx` and `excel_audit_output.txt` (322 vs 171).

**Likely root cause:** The Configure identity section was planned (the code comments call it authoritative) but never built. Rollover deep-copies the identity into each report, and Excel reads settings directly, so there are two sources of truth.

**Recommended fix direction:**
- Add a "Vessel & Contract" card to Configure: vessel name, IMO, client, Date of Hire, master, deck capacity. Validate the fields and save them in QSettings.
- Show the identity read-only in VDR and VJR, with a "Change in Configure" link.
- Use one function for identity in the display, the PDF and Excel. Snapshot the identity into the report only at Finalize.

**Regression risk:** Low to medium. Existing reports carry copied identity, so decide whether finalized reports keep their snapshot (recommended).

---

### GDS-AUDIT-002: VDR carried-forward values go stale when the previous day is corrected
- **Module:** VDR
- **Severity:** P0
- **Category:** Data integrity / incorrect exported data

**Observed behaviour:**
- A day's opening stock, the flowmeter reading at 0000H and total run hours are copied from the previous day once, the first time the new day is opened. Startup opens today, so that is usually at launch.
- Later edits to the previous day are never carried forward. In testing, day 17's Fresh Water closing was changed to 4000. Day 18's opening stayed at **5000.0**.

**Expected behaviour:** Opening values follow the previous day's final closing figures. At minimum, the user is warned "Opening ≠ yesterday's closing".

**User impact:**
- The normal workflow is: open the app in the morning (today is created), then correct and finalize yesterday.
- That workflow produces a wrong opening ROB, wrong flowmeter readings and wrong run hours in today's report.
- Every later day inherits the error. Nothing on screen indicates it.

**Reproduction steps:**
1. Report for the 17th with FW closing 5000.
2. Open the app on the 18th; it rolls over 5000.
3. Go back to the 17th and change Consumed so that closing = 4000.
4. Return to the 18th. FW opening still shows 5000.

**Evidence:**
- `app/vdr/store.py:49-51` and `app/vdr/model.py:205-223` (`rollover()` is a one-time snapshot).
- `evidence/application-audit/vdr/model_audit2_output.txt` ("day 18 FW opening still 5000.0").

**Likely root cause:** Carry-forward is implemented as copy-on-create instead of a derived link.

**Recommended fix direction:**
- Store carried fields as "linked to previous day" until the user overrides them.
- Re-derive them when the previous day changes or is finalized.
- Show a visible mismatch warning, and block Finalize unless the user confirms the mismatch.

**Regression risk:** Medium. This touches rollover persistence and existing stored reports.

---

### GDS-AUDIT-003: One bad record locks the whole report store; later saves are silently refused
- **Module:** VDR storage, and the same pattern in VJR
- **Severity:** P0
- **Category:** Data loss / unrecoverable workflow

**Observed behaviour:**
- **VDR:** if any single report in `reports.json` is malformed, or any field is longer than the 20,000-character limit, the entire load fails.
  - The UI allows such a field: a single-line text box accepts up to 32,767 characters by default.
  - After restart, every day is inaccessible. The page runs on an empty in-memory report, and every save is refused ("original file preserved").
  - The only indicators are small grey "Load error" and "SAVE FAILED" text in the top bar.
- **VJR:** a corrupt `report.json` shows "Could not load VJR; original file preserved…". Every edit then shows "Not saved", and Excel is disabled. There is no way out inside the app.

**Expected behaviour:**
- Input is limited to what the store accepts.
- A bad day is quarantined, not the whole history.
- Rotating backups exist.
- A prominent, blocking banner offers recovery: restore a backup, or open a fresh file and keep the damaged one.

**User impact:** The operator can keep typing for hours believing the work is saved, when none of it is. All history appears to have vanished, and a support call is needed to recover it.

**Reproduction steps:**
1. In a VDR remark, paste 20,001 characters.
2. Close and relaunch. All days fail to load.
3. Type into any field. "SAVE FAILED".

**Evidence:**
- `app/vdr/store.py:23-37` and `:95-98`; `app/vdr/model.py:251`; `app/ui/pages/vdr/workspace.py:46-47` and `:346`.
- `evidence/application-audit/vdr/pdf_threshold_output.txt` ("reload with 20001-char remark … load_error").
- `model_audit_output.txt` ("one bad report -> all lost").
- Screenshot `vdr/07_load_error_save_failed.png`.
- VJR: `app/ui/pages/vjr_workspace.py:98` (single file); `vjr/scripts/ui_audit.py`.

**Likely root cause:** The whole file is validated all-or-nothing. There is no limit on input length and no backup rotation. The error state is shown only in a subtle label.

**Recommended fix direction:**
- `setMaxLength` on every editor, matching the normalisation limits.
- Load per report, quarantining invalid entries.
- Keep the last N backups (`reports.json.1..5`).
- On any load or save error, show a red modal or banner that names the file location and offers choices.

**Regression risk:** Medium.

---

## High-Priority Findings

### GDS-AUDIT-004: VDR report can be finalized and then fail Excel export
- **Module / Severity / Category:** VDR · P1 · Validation consistency
- **Observed:** Finalize uses `validate()`, which is much weaker than the Excel exporter's checks. Each of these finalized successfully and then failed at Excel export:
  - Lifts "abc", POB text, crew age "forty", fuel endurance "12 days"
  - 2 transfers on Fresh Water: the template holds 1, while the UI allows up to 6
  - 3 fuel transfers
  - 23 locations: the template holds 22
  - 201 contractors
  - an unknown bulk item from a PDF import

  The export error dialog shows only the first error.
- **Expected:** If Finalize succeeds, Excel export succeeds. The UI never allows more rows than the template holds.
- **Impact:** The user cannot produce the deliverable. To fix the data they must edit the report, which silently un-finalizes it (005). Then they fix one error at a time.
- **Repro:** Enter Lifts "abc", finalize, then Download Excel.
- **Evidence:** `app/vdr/model.py:153-202` vs `app/vdr/excel.py:155-179`, `:204-212`, `:249`; `app/ui/pages/vdr/workspace.py:255`; `evidence/application-audit/vdr/excel_audit_output.txt`.
- **Root cause:** Two separate rule sets.
- **Fix direction:** Run the exporter's checks in dry-run mode as part of `validate()`. Limit transfer, location and contractor counts in the UI. List all errors.
- **Regression risk:** Low to medium. Some existing finalized reports may become "invalid".

### GDS-AUDIT-005: Typing in a finalized VDR silently returns it to draft
- **Module / Severity / Category:** VDR · P1 · Workflow / audit trail
- **Observed:** After finalizing, editors stay editable; only the date pickers lock. One keystroke in Captain changes the badge from FINALIZED to "READY TO FINALIZE" and disables both download buttons. There is no prompt and no "Reopen" concept. `finalizedAt` is lost.
- **Expected:** The form is read-only when finalized. An explicit "Reopen report" action asks for confirmation and records who reopened it and when.
- **Impact:** An accidental keystroke changes a report that has already been sent. It is unclear to the user what "Finalized" protects.
- **Repro:** Finalize, then click into Captain and type a character.
- **Evidence:** `app/vdr/store.py:58-59`; `app/ui/pages/vdr/workspace.py:168-170`; `evidence/application-audit/vdr/05_finalized_then_typed.png`.
- **Root cause:** Finalization is a flag that is cleared on any change.
- **Fix direction:** Lock the editors, add a Reopen flow, and keep a revision number in exports (e.g. "Rev 2").
- **Regression risk:** Medium.

### GDS-AUDIT-006: Setting TO = 2400 on an earlier activity row deletes all later rows
- **Module / Severity / Category:** VDR Activity Log · P1 · Data loss
- **Observed:** With rows 0600, 1200 and 1800, typing 2400 into row 2's TO and pressing Tab deletes rows 3 and later. There is no confirmation. It takes two separate undo steps, and undoing only one leaves an invalid row.
- **Expected:** A time edit never deletes data. Later rows are flagged as "after 2400", or the user is asked to confirm, and the change is a single undo step.
- **Impact:** Silent loss of logged activity.
- **Repro:** As described above.
- **Evidence:** `app/ui/pages/vdr/workspace.py:231-234`; `evidence/application-audit/vdr/ui_audit_output.txt`.
- **Root cause:** The rule "end of day closes the log" is applied destructively.
- **Fix direction:** Mark the rows instead of deleting them, or confirm first; group the change into one undo step.
- **Regression risk:** Low.

### GDS-AUDIT-007: Comma decimal separator is misread (×10 or ×1000)
- **Module / Severity / Category:** VDR (all numeric fields) · P1 · Incorrect data
- **Observed:** `number('2,5')` returns 25.0, so a draft of "2,5" passes as 25 m. `'1.000,5'` returns 1.0005. In VJR, a comma is rejected but with a raw message: "could not convert string to float".
- **Expected:** An ambiguous comma is rejected with a clear message. Plausibility ranges apply, e.g. draft 0–15 m.
- **Impact:** Crew on European-locale PCs, or crew used to the comma decimal, enter values that are wrong by a factor of 10 or 1000, with no warning.
- **Repro:** Enter Draft FWD "2,5". It validates as 25.
- **Evidence:** `app/vdr/model.py:11-16`; `evidence/application-audit/vdr/model_audit2_output.txt`.
- **Root cause:** Commas are stripped as thousands separators.
- **Fix direction:** Accept a comma only in a strict thousands pattern; add ranges; give friendly messages in both modules.
- **Regression risk:** Low.

### GDS-AUDIT-008: Missed day produces a completely blank VDR
- **Module / Severity / Category:** VDR · P1 · Workflow / data quality
- **Observed:** Rollover copies only from the calendar day immediately before. With a report on the 15th and the app opened on the 17th, crew, ROB, captain and equipment are all empty.
- **Expected:** Roll over from the most recent earlier report and show "Carried from 15 Nov".
- **Impact:** The whole crew list and every opening stock must be re-typed after weekends or shore days, which invites errors.
- **Repro:** Report on day N, open the app on day N+2.
- **Evidence:** `app/vdr/store.py:50-51`; `evidence/application-audit/vdr/model_audit2_output.txt` ("opened 2 days later: ('', '', '')").
- **Root cause:** Exact date−1 lookup.
- **Fix direction:** Search backwards for the most recent report.
- **Regression risk:** Low.

### GDS-AUDIT-009: VDR PDF export crashes on realistic content and shows a raw error
- **Module / Severity / Category:** VDR PDF · P1 · Crash / error message
- **Observed:**
  - An activity cell longer than about 2,660 characters raises the PDF library's `LayoutError`, and the internal message is shown in a warning box. Excel handles the same report.
  - An imported report that is already finalized but has transfer quantity "ten" crashes with `ValueError: could not convert string to float`. Imports keep `finalized=True` without re-validating.
  - The PDF file is written in place, not atomically.
- **Expected:** Long cells split across pages. Imports are re-validated. Errors explain what to do.
- **Impact:** No PDF for the manager, and a message the user cannot act on.
- **Repro:** Paste a 3,000-character activity description, then Download Report.
- **Evidence:** `app/vdr/pdf.py:81-83`, `:118`, `:167`; `app/vdr/model.py:267`; `evidence/application-audit/vdr/pdf_audit_output.txt` and `pdf_threshold_output.txt`.
- **Root cause:** Tables cannot split across pages, and the PDF code bypasses the normal number parser.
- **Fix direction:** Allow table rows to split across pages; parse numbers safely; validate on import; write atomically.
- **Regression risk:** Low.

### GDS-AUDIT-010: VJR has no required fields or date-order checks
- **Module / Severity / Category:** VJR · P1 · Validation
- **Observed:** `validate(new_report())` returns no errors, and a completely blank VJR exports. All of these are accepted:
  - ETA before departure
  - actual arrival before departure
  - arrival report date before departure
  - progress rows dated a year earlier
  - duplicate or out-of-order hours
  - deck use over 100 %
  - crew working days over 300 (the template's header says "max 90 days")
- **Expected:** Required markers as in VDR (`*`). Date-order and plausibility rules, with "warn" vs "block" levels.
- **Impact:** Illogical voyage reports reach the client.
- **Repro:** New VJR, then Download Excel. It succeeds with everything blank.
- **Evidence:** `app/vjr/validation.py:43-102`; `evidence/application-audit/vjr/scripts/model_audit.py`.
- **Root cause:** Validation checks only types and ranges.
- **Fix direction:** A required-field schema plus cross-field rules.
- **Regression risk:** Low to medium.

### GDS-AUDIT-011: VJR has no "New voyage"; there is only ever one report
- **Module / Severity / Category:** VJR · P1 · Workflow
- **Observed:** VJR is a single file (`AppLocalData/vjr/report.json`). There is no New, Archive or Reset action. After voyage 1, the master must delete up to 200 crew rows, 100 progress rows and 2×17 inventory items by hand.
- **Expected:** "Start new voyage", with the previous voyage archived and crew optionally carried over. A list of past voyages.
- **Impact:** Each voyage begins with tedious manual clearing, with a high risk of leaving old data in the new report.
- **Evidence:** `app/ui/pages/vjr_workspace.py:98`; no new/archive actions in `vjr_*.py`.
- **Root cause:** Single-document design.
- **Fix direction:** Store one file per voyage, with an archive list. Photo references are already tied to `photo_report_id`.
- **Regression risk:** Medium.

### GDS-AUDIT-012: Configure "Live Telemetry" panel never shows data
- **Module / Severity / Category:** Configure · P1 · Broken functionality
- **Observed:** `TelemetryPanel.update_frame()` has no caller, and `ConfigurePage.refresh()` refreshes only the connection and diagnostics panels. All 26 values (position, navigation, weather, attitude and power) always show "—", even while the header says LIVE.
- **Expected:** Values update with each frame and show units.
- **Impact:** The main screen for checking that the sensor works never shows a reading. Users will report it as "telemetry not working".
- **Repro:** Feed a valid frame (`evidence/application-audit/platform/probe_configure_ui.py`).
- **Evidence:** `app/ui/pages/configure/telemetry_panel.py:13`; `configure_page.py:8`; `evidence/application-audit/platform/probe_ui.txt`; the code search for `update_frame` finds only the definition.
- **Root cause:** Not wired.
- **Fix direction:** Call `self.telemetry.update_frame(state.latest_frame)` in `refresh`. Format the values and blank them when not LIVE.
- **Regression risk:** Low.

### GDS-AUDIT-013: Transport errors and disconnects never reach the user
- **Module / Severity / Category:** Connectivity · P1 · Error handling / misleading status
- **Observed:**
  - `on_error` and `on_state` are never assigned outside the transport layer. Every error is dropped: busy port, access denied, missing device, read failure, BLE scan failure.
  - When the cable is pulled, the read thread exits but the port is not closed. `is_connected()` stays True, and the USB card keeps "● CONNECTED" forever, while the Diagnostics tile says "NO DEVICE".
  - The transport messages would be raw Python exceptions anyway, e.g. `FileNotFoundError(2, 'The system cannot find the file specified.'…)`.
  - There is no auto-reconnect.
- **Expected:** Clear status changes ("Disconnected: device removed"), plain-language errors ("COM5 is in use by another program") and automatic reconnect.
- **Impact:** Silent failures. The operator trusts a connection that is dead, and support calls follow.
- **Repro:** Connect to a port that is in use, or unplug during streaming (simulated in `probe_usb.py`).
- **Evidence:** `app/transports/base_transport.py:24`; `usb_transport.py:30-37`; `app/ui/main_window.py:16`; `app/ui/pages/configure/connection_panel.py:34-38`; `evidence/application-audit/platform/probe_usb.txt` ("states [False, True] is_connected() True").
- **Root cause:** Callbacks are defined but never connected, and the card status is set only on success.
- **Fix direction:** Emit errors and state changes as Qt signals, which carry them safely from the worker thread to the UI. Show an inline message area on each card, call `state.mark_disconnected`, and reconnect with backoff.
- **Regression risk:** Medium (threading).

### GDS-AUDIT-014: No Disconnect; reconnecting leaks the COM port
- **Module / Severity / Category:** Connectivity · P1 · Workflow / resource leak
- **Observed:** Only the Scan and Connect buttons exist. CONNECT stays enabled after connecting. A second connect replaces the serial handle without closing the old one, so the old thread and port stay open. `closeEvent` never disconnects USB or BLE.
- **Expected:** A Connect/Disconnect toggle. Connecting first disconnects the previous connection.
- **Impact:** Changing port requires restarting the app. A retry on the same port fails silently because the port is held by the app itself.
- **Evidence:** `connection_panel.py:19`, `:37-42`; `usb_transport.py:20-24`; `main_window.py:30`; `probe_usb.txt` ("double connect: old thread alive True old serial open True").
- **Fix direction:** As described above.
- **Regression risk:** Low to medium.

### GDS-AUDIT-015: BLE notifications very likely lost; scan and connect freeze the UI
- **Module / Severity / Category:** Connectivity / BLE · P1 · Broken functionality (code-verified, **hardware-unverified**)
- **Observed:**
  - `_run()` starts `asyncio.run(...)` in a temporary thread and waits for it (`join()`). The event loop closes as soon as connect and `start_notify` return.
  - Bleak's Windows backend delivers notifications by scheduling them on that loop (`loop.call_soon_threadsafe`), so data should never arrive.
  - Disconnect runs on yet another new loop.
  - The `join()` blocks the GUI for the whole 4 s scan, and for the full connect timeout.
- **Expected:** One persistent event loop thread for BLE. Scan and connect run asynchronously with a "Scanning…" state.
- **Impact:** BLE appears connected but no telemetry flows, and the window freezes ("Not responding") during scans.
- **Evidence:** `app/transports/ble_transport.py:28-50`; bleak `backends/winrt/client.py:1022,1028` (3.0.2) and `:968,974` (0.22.3).
- **Fix direction:** Run the loop with `loop.run_forever()` in a dedicated thread and submit work with `run_coroutine_threadsafe`. Deliver results to the UI as Qt signals.
- **Regression risk:** Medium. Must be tested on real hardware.

### GDS-AUDIT-016: NAV shows zero as "no data" and draws an invented heading
- **Module / Severity / Category:** NAV · P1 · Incorrect operational display
- **Observed:**
  - The readout uses `{f.speed_knots or "—"}`, `{f.cog or "—"}` and `{f.heading or "—"}`. SOG 0.0 and heading 000° therefore display "—".
  - The marker receives `heading: self.vessel.heading or 0` and `setRotation(data.heading||0)`, so with no heading the arrow points north as if that were real.
- **Expected:** Show 0.0 kn and 000°. Without a heading, show a marker with no direction plus a "No heading" badge.
- **Impact:** A vessel on DP or alongside looks like it has no data, and the bow direction is fabricated.
- **Evidence:** `app/ui/pages/nav/nav_page.py:323` and `:326`; `app/resources/map/nav.js:102`.
- **Fix direction:** Explicit `is None` checks; pass `null` for heading and switch the marker shape.
- **Regression risk:** Low.

### GDS-AUDIT-017: NAV vessel marker never indicates stale or lost telemetry
- **Module / Severity / Category:** NAV · P1 · Misleading data
- **Observed:**
  - Only latitude, longitude and heading are sent to the map, and the marker style is fixed.
  - The last frame is kept forever, so after a connection loss the marker stays full-colour at the old position.
  - The track bar keeps saying "TRACK RECORDING".
  - The only stale cue is an age line inside a collapsed section of the Layers panel.
- **Expected:** A greyed or hatched marker, a "TELEMETRY LOST — last fix 12 min ago" banner, and the track shown as PAUSED.
- **Impact:** The operator reads an old position as the current one.
- **Evidence:** `nav_page.py:323`; `nav.js:102`; `app/nav/presentation.py` (`track_metrics`); `app/telemetry/telemetry_state.py`.
- **Fix direction:** Include the telemetry status in the map update; style the marker by status.
- **Regression risk:** Low.

### GDS-AUDIT-018: No internet at startup gives a blank map with no recovery; offline regions not reachable
- **Module / Severity / Category:** NAV · P1 · Offline workflow
- **Observed:**
  - `startMap` fetches the online style once, with a 5 s timeout. On failure it permanently uses a background-only style and never retries.
  - `onlineUnavailable` is only ever set to true, so one error latches "ONLINE UNAVAILABLE / LOCAL ONLY" for the whole session.
  - Offline map packages are used only if the `GDS_MAP_SOURCE=offline` environment variable is set.
  - `NavPage._map_regions` (the Offline Regions dialog) has no caller, so users cannot open it.
- **Expected:**
  - Retry with backoff, and when the network comes back.
  - Fall back automatically to installed offline regions.
  - A visible "Map regions…" entry.
  - Clear "Offline: showing installed region X" messaging.
- **Impact:** A vessel that starts the app out of coverage gets a featureless canvas until restart, and the offline-map investment cannot be used.
- **Evidence:** `app/resources/map/nav.js:30-46`, `:43`, `:97`; `app/nav/web_scheme.py:31`; `app/ui/pages/nav/nav_page.py:117` (no callers). Code path only; the offline simulation was defeated by the WebEngine cache.
- **Fix direction:** As described above.
- **Regression risk:** Medium.

### GDS-AUDIT-019: WebGL, renderer or WebEngine failures are undetected; status still says READY
- **Module / Severity / Category:** NAV / Platform · P1 · Reliability / messaging
- **Observed:**
  - No `webglcontextlost` handling.
  - The headless run logged `CONTEXT_LOST_WEBGL`, yet the status read `MAP / ONLINE / READY` with the badge "ONLINE".
  - `build/stress-source-software-1.txt` shows MapLibre failing to create WebGL, with no UI notice.
  - There is no `renderProcessTerminated` handler.
  - In the legacy build, QtWebEngine is initialised when the app starts (`app/qt/__init__.py:25-26`). A broken WebEngine therefore aborts startup before any window appears, even though Configure, VDR and VJR do not need it.
- **Expected:** "Map renderer unavailable" with a Reload button, a software-rendering fallback, and the rest of the app still working.
- **Impact:** A blank map that claims to be ready on older or virtual-machine GPUs. On legacy PCs the whole application may fail to start.
- **Evidence:** As above; `app/ui/pages/nav/nav_page.py:168`.
- **Fix direction:** Handle the context and renderer events; set `QTWEBENGINE_CHROMIUM_FLAGS` for a SwiftShader fallback on legacy; import WebEngine lazily.
- **Regression risk:** Low to medium.

### GDS-AUDIT-020: Track history is unbounded and fully rebuilt each frame
- **Module / Severity / Category:** NAV · P1 · Performance over long runtime
- **Observed:** `TrackManager` never trims. On every frame the full track geometry is rebuilt and sent to the map, and the total distance is re-summed every 500 ms even when NAV is hidden. Measured at 1 Hz:

  | Run time | Points | Payload per frame | Cost |
  |---|---|---|---|
  | 24 h | 86,400 | **2.1 MB** | 40 ms per metrics tick |
  | 7 days | 604,800 | **14.6 MB** | ~580 ms build plus serialisation; 278 ms per tick |

- **Expected:** Steady memory and CPU use over weeks of operation.
- **Impact:** The app gets progressively slower during a voyage; it is very likely unusable after about a week.
- **Evidence:** `app/nav/track_manager.py`; `nav_page.py:324`; `main_window.py` (500 ms timer); `evidence/application-audit/nav/scripts/measure.py`.
- **Fix direction:** Thin out old track points (decimation or a ring buffer), send only appended points, keep a running distance total, and pause the work while the tab is hidden.
- **Regression risk:** Low to medium.

### GDS-AUDIT-021: Squall events: no production feed; "No active events" looks like an all-clear
- **Module / Severity / Category:** NAV Squall · P1 · Misleading safety information
- **Observed:**
  - `ingest_squall_event` and `ingest_squall_json` are called only from `tools/dev_*.py`; no transport feeds them.
  - Impact is evaluated only against project site polygons, never against the vessel's own position. With no spatial package, every event is `NONE`.
  - ETA is measured from `observed_at` and does not count down.
  - There is no top-level alert. The "WEATHER" button opens the Layers panel.
- **Expected:** "Squall feed: NOT CONNECTED" when there is no source; evaluation against the vessel; a live ETA countdown; a prominent alert banner for IMPACT.
- **Impact:** Crew may read "No active events" as "no weather threat".
- **Evidence:** `app/ui/main_window.py:34-35`; `app/nav/events/impact.py`; `app/nav/events/render_state.py`; `app/ui/pages/nav/floating_controls.py` (`toggle_weather`).
- **Fix direction:** As described above.
- **Regression risk:** Low to medium.

### GDS-AUDIT-022: Vessel position sent to public Overpass servers by default
- **Module / Severity / Category:** NAV / Privacy · P1 · Privacy exposure
- **Observed:**
  - Overpass is on by default (`overpass-api.de`, fallback `overpass.private.coffee`).
  - The query box is centred **exactly** on the vessel. Verified to 6 decimals.
  - A new query is sent every 10 NM of movement, with User-Agent `GDS-VTS-Maritime/4R`.
  - There is no opt-in and no disclosure in the UI or the docs.
- **Expected:** Opt-in, query areas snapped to a coarse grid, and a disclosure.
- **Impact:** Third parties can reconstruct the vessel's track at about 10 NM resolution.
- **Why P1 rather than P0:** Vessel positions are often public through AIS. However, client contracts for offshore operations may forbid this; confirm with management and legal.
- **Evidence:** `app/nav/maritime/providers.py:25-32`; `app/nav/maritime/runtime.py:53-69`; `app/nav/maritime/config.py` (`movement_nm`).
- **Fix direction:** Turn it off by default or snap queries to a 0.5° grid; add a "Data sources & privacy" note.
- **Regression risk:** Low to medium (cache keys change).

### GDS-AUDIT-023: Shutdown blocks on in-flight provider requests
- **Module / Severity / Category:** NAV / Shutdown · P1 · Hang
- **Observed:**
  - `main.py` calls `maritime_runtime.close(wait=True)`, which waits for the worker threads.
  - Overpass and GEBCO requests use a 35 s timeout. With a stalled server, closing took **32.3 s**.
  - Copernicus `open_dataset` has no timeout at all.
  - With a healthy network, shutdown measured about 0.3 s, which is good.
- **Expected:** The process exits within about 2 s.
- **Impact:** An invisible process lingers after the window closes. A relaunch may find the COM port still held (unverified).
- **Evidence:** `main.py:49`; `app/nav/maritime/runtime.py:219`; `provider_common.py:91,98`; `copernicus.py:40-46`; `evidence/application-audit/nav/scripts/shutdown_probe.py`.
- **Fix direction:** Limit how long close waits; cancel open network requests; give every remote call a timeout.
- **Regression risk:** Medium.

### GDS-AUDIT-024: Legacy build crashes (access violation) during Malaysia GIS load
- **Module / Severity / Category:** Windows 7/8 build · P1 · Crash
- **Observed:**
  - `build/stress-source-gpu-disabled-1.txt:46` and `build/stress-source-software-2.txt:46` both show `Windows fatal exception: access violation` in shapely `is_valid`.
  - The call comes from `malaysia.py:170` and `runtime.py:161`, on a worker thread under Python 3.8.
  - That is 2 of the 3 non-default stress runs; the 10 default runs did not crash.
- **Expected:** No crash on any rendering mode. Software rendering is exactly the mode older PCs will use.
- **Impact:** The whole app closes on legacy PCs. Data is safe thanks to atomic saves, but unsaved typing within the save delay may be lost.
- **Root cause:** Unverified. Possibly the GEOS library inside the Python 3.8 shapely wheel is not thread-safe, or it interacts with the legacy garbage collector running on the GUI thread.
- **Fix direction:**
  - Reproduce with crash tracing (faulthandler) on.
  - Run all GIS work on one dedicated thread.
  - Validate the dataset at build time so `is_valid` is skipped at runtime.
  - Evaluate another shapely/GEOS pin.
- **Regression risk:** Medium.

### GDS-AUDIT-025: Packaged build is stale and builds are indistinguishable
- **Module / Severity / Category:** Packaging · P1 · Release integrity
- **Observed:**
  - `dist\GDS VTS` is the legacy build from 08:36. The VJR sources were changed later the same day and are uncommitted.
  - The exe contains `app.ui.pages.vjr_page` but none of `app.vjr.*`, `vjr_workspace`, `vjr_photos` or `vjr_widgets`. Resources lack `vjr/` and `vjr_template.xlsx`.
  - Both spec files output the same `dist\GDS VTS\GDS VTS.exe` with FileVersion 0.0.0.0.
  - No modern build exists in `dist/`.
- **Expected:** Builds made from a committed tree, with distinct names (e.g. "GDS VTS (Win7)"), a real version number and the git commit SHA in the version info and the startup log.
- **Impact:** Distributing `dist/` today would ship the old placeholder VJR. Support cannot tell which build a user has.
- **Evidence:** `gds_vts.spec`, `gds_vts_win7.spec`; `packaging/version_info.txt`; `evidence/application-audit/platform/packaged_legacy_startup.log`.
- **Fix direction:** As described above.
- **Regression risk:** Low.

---

## Medium-Priority Findings

Each item gives what was observed, what was expected, the impact, how to reproduce it, the evidence, the cause, the fix direction and the regression risk.

### GDS-AUDIT-026: VJR hourly Voyage Progress entry is slow (P2, efficiency)
- **Observed:**
  - "Add row" adds a completely blank row and rebuilds the page each time (0.10–0.18 s per click; 10.1 s for 72 rows).
  - There is no way to duplicate a row or to add the next hour automatically.
  - The Date cell is read-only, and typing a date ("2026-11-18") stores nothing, so every row needs a calendar pick.
- **Expected:** "Add next hour", which copies date, position and weather from the previous row with hour+1 and rolls the date over at midnight. Dates you can type. Optionally, position pre-filled from live telemetry.
- **Impact:** About 1,440 entries and 72 calendar picks for a 3-day voyage.
- **Evidence:** `evidence/application-audit/vjr/scripts/ui_audit.py`, `kbd2.py`; `app/ui/pages/vdr/date_picker.py:51,136`; `vjr_07_voyage_1366x768.png`.
- **Regression risk:** Low.

### GDS-AUDIT-027: Validation feedback is hard to find and inconsistent between modules (P2, validation clarity)
- **Observed in VDR:**
  - No field is ever outlined as invalid (draft −3, wind "abc").
  - Errors appear only as counts in the sidebar, the "DRAFT · N ISSUES" badge and a modal list at Finalize.
  - An invalid activity row shows grey "INVALID", cut off to "INVALI" at 1440 px.
  - Negative calculated values get only a 2 px red line.
- **Observed in VJR:** fields are tinted inline, but the banner shows only the first error "(+N more)", with the rest in a tooltip.
- **Expected:** Both modules outline the field, show an icon and text (not colour alone), and list all issues with a click-to-jump.
- **Evidence:** `app/ui/pages/vdr/workspace.py:180-193`; `vdr/06b_activity_invalid_row_scrolled.png`; `vjr/vjr_04_waypoints_invalid_1366x768.png`.
- **Regression risk:** Low.

### GDS-AUDIT-028: VDR missing domain checks (P2, data quality)
- **Observed:** All of these pass validation:
  - daily run hours of 30
  - total hours less than daily hours
  - received quantity larger than the meter difference
  - a transfer meter running backwards
  - a transfer quantity with no recipient
  - duplicate crew members
  - crew rows with no name; Excel exports these, but the PDF drops them

  In addition, fuel consumed comes only from flowmeters. A negative meter difference is silently left out of the total, and inlet and outlet meters are added together. This matches the template's `T45 =SUM(T23:T44)`; confirm that this is intended.
- **Evidence:** `app/vdr/model.py:103-109`, `:153-202`; `vdr/model_audit_output.txt`.
- **Fix direction:** Add the rules, at warning or blocking level.
- **Regression risk:** Low.

### GDS-AUDIT-029: VDR PDF loses characters and sections (P2, export parity)
- **Observed:**
  - Chinese characters and ✓ disappear, because the bundled Inter, Manrope and JetBrains Mono fonts lack the glyphs.
  - The PDF leaves out the daily duration at location, the location summary, movement-category and DP totals, Report No., HSE perfect days, hire date and crew comments.
- **Expected:** Content parity with Excel and a font with broad character coverage.
- **Impact:** A manager reading the PDF sees a different report from the Excel file, and non-Latin crew names are lost.
- **Evidence:** `app/vdr/pdf.py:67-69`, `:96-138`; `vdr/pdf_audit_output.txt`; `vdr/unicode_small.pdf`.
- **Regression risk:** Low.

### GDS-AUDIT-030: Location names and summaries (P2, data quality / clarity)
- **Observed:**
  - "LABUAN", "labuan " and "Labuan" become three locations, both on screen and in the Excel R82 summary.
  - The UI shows only contiguous visits (A→B→A gives 3 rows). Excel aggregates by place (2 rows), and that aggregated view is never shown in the app, so users cannot see the difference before export.
  - The 22-location capacity is discovered only at export.
- **Fix direction:** Trim and case-fold names to the catalogue spelling; add a read-only "Location summary (as exported)" table with a capacity counter.
- **Evidence:** `app/vdr/model.py:82-98`, `:147-149`; `vdr/09_location_durations.png`.
- **Regression risk:** Low.

### GDS-AUDIT-031: Undo and autosave granularity (P2, usability / I/O)
- **Observed:**
  - Undo works per keystroke in both modules. Typing "Capt Ahmad" makes 10 steps.
  - The 100-step cap means typing about 100 characters wipes earlier structural history, such as row deletes.
  - Undo rebuilds the page and keyboard focus is lost. VDR undo can switch the report date without telling the user.
  - VJR writes to disk on every keystroke: two deep copies, JSON serialisation and a forced disk flush, plus full validation. VDR uses a save timer instead (inconsistent).
- **Expected:** One undo step per field edit, focus restored after undo, and debounced saving in both modules.
- **Evidence:**
  - VDR: `app/ui/pages/vdr/sections.py:59`; `app/vdr/store.py:54-80`.
  - VJR: `app/vjr/store.py:21-30`; `vjr/scripts/ui_audit.py`.
- **Regression risk:** Medium. Existing tests assert the per-keystroke behaviour.

### GDS-AUDIT-032: VDR weather entry (P2, efficiency / template fit)
- **Observed:**
  - Wind accepts numbers only. The template's own example is "NW 11-16", so wind direction cannot be entered.
  - Moving from one time slot's wind field to the next takes 21 Tab presses, because every sky, sea and visibility chip button takes focus.
  - Temperature and visibility are optional. "<1 NM" is stored as 0.5.
- **Evidence:** `app/ui/pages/vdr/sections.py:128-149`; `app/vdr/model.py:162-168`; `vdr/08_weather.png`.
- **Fix direction:** Direction plus speed fields; arrow keys within chip groups so Tab moves between groups; a "copy previous slot" action.
- **Regression risk:** Low.

### GDS-AUDIT-033: Layout at 1366×768 (P2, layout)
- **Observed:**
  - Inside the shell, VDR gets about 1306×728.
  - The activity table (1032 px of columns) and the crew table (1092 px) scroll horizontally, which hides the delete × and Comments columns. Only about 5 rows are visible.
  - The VJR progress table is limited to 520 px inside a scrolling page, giving two vertical scrollbars. Its content is 1688 px wide in a 984 px viewport, with no frozen Date/Hour columns.
  - The weather chips are clipped.
  - The test suite agrees: 3 VDR layout tests fail (column sum 1310 > viewport 1169).
- **Fix direction:** Freeze the key columns; let tables fill the available height; make columns respond to width; fix the failing tests.
- **Evidence:** `shell/vdr-1366x768.png`; `vdr/03_activity_1306x728.png`; `vdr/04_crew_1306x728.png`; `vjr/vjr_07_voyage_1366x768.png`; `app/ui/pages/vjr_workspace.py:362-369`; `pytest-summary.txt`.
- **Regression risk:** Low to medium.

### GDS-AUDIT-034: VJR missing upper bounds (P2, validation)
- **Observed:** Planned speed 999, visibility 500 NM, wind 400 kn and wave 60 m are accepted. The template itself limits speed to 0–300.
- **Evidence:** `app/vjr/validation.py:32`.
- **Fix direction:** Ranges for each kind of value.
- **Regression risk:** Low.

### GDS-AUDIT-035: VJR Excel frozen relative dates and hour/minute types (P2, export fidelity)
- **Observed:**
  - J10, J18 and J24 originally hold `TODAY()`-based formulas. The exporter replaces them with fixed text such as "1 DAY(S) AGO", which is permanently wrong a week later.
  - Voyage Progress hours and minutes export as numbers (0.0), while the template and the Departure sheet use text ('09'), and the template's drop-down rules expect '00'–'23'.
- **Evidence:** `app/vjr/excel.py:47-50`, `:113-118`; `vjr/scripts/tpl.py`.
- **Fix direction:** Keep the formulas, or leave the cells blank; export zero-padded text.
- **Regression risk:** Low.

### GDS-AUDIT-036: VJR ignores the template's drop-down lists (P2, data quality / consistency)
- **Observed:** The template defines lists for Sky (5 values), Rank (18), Locations (28) and Countries (250). The app uses free text, so "Rainy" is stored where the template expects one of its own values.
- **Fix direction:** Editable combo boxes populated from the template lists. VJR already does this for compass and N/S fields.
- **Evidence:** `app/vjr/schema.py`; `vjr/scripts/lists.py`.
- **Regression risk:** Low.

### GDS-AUDIT-037: VJR arrival values locked to departure (P2, workflow; product decision)
- **Observed:**
  - Arrival drafts, Fuel/FW/DW requirements, captain, prepared-by and checked-by are read-only and copied from Departure. This mirrors the template (`Arrival E13 ='4. Departure Report'!E13`).
  - There is no accidental overwrite: estimated and actual arrival are stored separately.
  - However, the actual arrival draft cannot be recorded.
- **Fix direction:** Confirm with operations, then add arrival-specific draft fields.
- **Evidence:** `app/vjr/model.py:63-68`; `vjr/vjr_06_arrival_1366x768.png`.
- **Regression risk:** Low to medium.

### GDS-AUDIT-038: VJR photo server lifecycle (P2, security hygiene / robustness)
- **Observed:**
  - After an upload finishes, the server keeps listening on the LAN until the app quits.
  - Holding 4 idle connections makes a genuine phone upload receive a 503 error.
  - Generating the Arrival QR code on a different network card cancels the live Departure QR code.
  - The photo upload uses plain HTTP, so the short-lived token is visible on the LAN. That is acceptable, but should be documented.
- **Fix direction:** Stop the server when no session is pending; add a short timeout for reading the request header and a per-IP limit; manage sessions per card.
- **Evidence:** `app/vjr/photo_server.py:140-160`, `:229-231`; `app/ui/pages/vjr_photos.py:44,109`; `vjr/scripts/photo_audit.py`.
- **Regression risk:** Low.

### GDS-AUDIT-039: VJR Voyage Progress capacity of 100 rows (P2, workflow limit)
- **Observed:**
  - The template range `B8:B107` limits the log to about 4 days at one row per hour.
  - Add is disabled at 100 rows, and export is blocked at 101. Data is never silently cut off, which is good.
- **Fix direction:** Decide with the client: a template extension, an overflow sheet, or a documented 2-hourly interval for long voyages.
- **Regression risk:** Low.

### GDS-AUDIT-040: Shell header inconsistency (P2, consistency / space)
- **Observed:**
  - `navigate()` hides the global "GDS VTS" header only for NAV and VDR. VJR therefore shows two headers (global plus the VJR title bar) and loses about 70 px of height at 1366×768. VDR does not.
  - The telemetry status pill ("● NO SOURCE"/"LIVE") is visible only on Configure and VJR.
  - The pill always uses the neutral style, never the "live" colour.
- **Fix direction:**
  - Drop the global header everywhere.
  - Move the telemetry status into the navigation rail so it is visible on every page.
  - Colour the pill by state.
- **Evidence:** `app/ui/main_window.py:27-29`; `app/ui/components/top_header.py`; `shell/vjr-1366x768.png` vs `shell/vdr-1366x768.png`.
- **Regression risk:** Low.

### GDS-AUDIT-041: Telemetry display and health tiles (P2, unfinished / misleading)
- **Observed:**
  - Telemetry values have no units (speed, COG, wind, temperature, pressure, voltage).
  - Health tiles (GPS, Heading, IMU, Power) stay "● LIVE" after 15 s without data, because they check whether a frame exists, not how old it is.
  - The STALE and LOST states can never be reached: after 3 s `tick()` drops the source and the status goes straight to NO SOURCE.
  - "Frame Rate", "Reconnect Count" and "Active Source Since" are hard-coded "—".
  - The summary strip is cramped ("ACTIVE SOURCE STANDBY TELEMETRY" have no spacing).
  - "PATROLLER-I", "PID" and "Canonical vessel data" are jargon.
- **Evidence:** `app/ui/pages/configure/diagnostics_panel.py:17-19`; `telemetry_panel.py:13-15`; `app/telemetry/telemetry_state.py:30-46`; `platform/probe_ui.txt`; `shell/configure-1920x1080.png`.
- **Regression risk:** Medium (state-model tests).

### GDS-AUDIT-042: Telemetry ingest robustness (P2, data integrity / reliability)
- **Observed:**
  - The validator accepts any JSON object (`{}`, `{"hello":"world"}`), NaN or Infinity, and latitude 999999. Any JSON-sending device therefore goes LIVE.
  - Coordinates are treated as DDMM whenever the absolute value is greater than 90, so 101.5° decimal degrees becomes 1.025°, and `0030.0` becomes 30.0. This is correct for Patroller-I in Malaysian waters, but fragile.
  - One deeply nested line raises `RecursionError` and kills the USB read thread permanently, while the status still says CONNECTED.
  - The stream buffer has no limit and its cost grows quadratically: 52 MB after 800×64 KB without a newline.
- **Strength:** parsing throughput is about 78k frames/s, far above need.
- **Evidence:** `app/telemetry/validator.py`; `normalizer.py:12-19`; `parser.py:8`; `stream_assembler.py:5`; `platform/probe_modern.txt`, `probe_legacy.txt`, `probe_usb.txt`.
- **Fix direction:** Required keys, finite range checks, coordinate format chosen per protocol, catch errors per line, cap line and buffer length.
- **Regression risk:** Medium. Check against real device frames first.

### GDS-AUDIT-043: COM port selection UX (P2, usability)
- **Observed:**
  - The details grid always shows the first scanned device, whatever is selected (COM7 selected, COM3 shown).
  - FTDI and CDC devices are not distinguished from Bluetooth virtual COM ports.
  - The last used port is not remembered, and devices are not rescanned when plugged in.
  - Connection Mode resets to AUTO each launch.
  - The baud rate is fixed at 115200.
  - The DTR/RTS default may reset some CDC boards (unverified).
- **Evidence:** `app/ui/pages/configure/connection_panel.py:29-31`; `platform/probe_ui.txt`.
- **Regression risk:** Low.

### GDS-AUDIT-044: No Settings page; validation profile pollutes real settings (P2, missing feature / test isolation)
- **Observed:**
  - There is no Settings page: no app name, logo or font options, and no reset.
  - `app/core/settings.py` is dead code.
  - `--validation-profile` redirects file paths but not QSettings, which are stored in the registry. Acceptance runs therefore read and write the user's real vessel and NAV preferences (verified with a probe key).
- **Note:** The prompt lists app name, logo and font customisation as audit items. None exist. Whether they are required is a product decision.
- **Fix direction:** A minimal Settings page (identity per 001, units, data folder, "Open logs", reset); use INI-format QSettings in validation mode.
- **Regression risk:** Low.

### GDS-AUDIT-045: NAV controls usability (P2, usability)
- **Observed:**
  - 11 of the 13 floating tools are 36 px icon-only buttons, labelled only by tooltip.
  - "WEATHER" opens the squall list.
  - "CENTER VESSEL" and "FIT TRACK" do nothing, silently, when there is no position.
  - With no telemetry the map opens over Bangladesh (`center:[90.36,22.36]`) with no "No own-vessel position" message.
  - The Layers panel has more than 30 toggles in nested sections.
- **Evidence:** `nav.js:97`, `:102`; `app/ui/pages/nav/floating_controls.py`; `nav/nav_default_offscreen.png`, `nav_layers_panel_offscreen.png`.
- **Fix direction:**
  - Text labels, or expanded labels on hover.
  - A no-position overlay.
  - Default to the operating area (Malaysia) or the last known position.
  - Group layers into presets.
- **Regression risk:** Low.

### GDS-AUDIT-046: NAV status contradictions and render cost (P2, consistency / CPU)
- **Observed:**
  - With every maritime provider in ERROR and WebGL lost, the badge still said ONLINE and the status said READY.
  - The badge is derived by matching words in free text, and provider errors appear only in tooltips.
  - The full maritime render state (6.5 MB in a Malaysia view, with geometry duplicated) is rebuilt and sent every ~30 s even when unchanged: average 89 ms, worst 304 ms on the GUI thread; every 1 s when AIS data is present.
  - A single pool of 3 worker threads is shared by remote providers and local GIS.
- **Evidence:** `app/nav/maritime/service.py`, `render_state.py`, `runtime.py:28`; `floating_controls.py`; `nav/scripts/publish_rate.py`.
- **Fix direction:** Status from one structured source; send only changes; a separate worker pool for local GIS.
- **Regression risk:** Medium.

### GDS-AUDIT-047: Installation and distribution need technical knowledge (P2, deployment)
- **Observed:**
  - The app is a portable folder: no installer, shortcuts, uninstaller or upgrade flow.
  - The exe and `Check-WindowsPrerequisites.ps1` are unsigned. SmartScreen will warn, and downloaded zips carry the "from the internet" mark.
  - Stock PowerShell execution policy (Restricted) blocks the preflight script, and the docs say not to bypass it.
  - The preflight requires the system-wide VC++ 2015–2019 redistributable even though those DLLs are bundled, which may block users wrongly (unverified on Windows 7).
  - Windows Firewall will prompt when the photo server first listens; allowing it may need admin rights.
  - FTDI driver installation is not covered.
- **Evidence:** `docs/windows-compatibility.md:36-40`; `scripts/Check-WindowsPrerequisites.ps1`; `Get-AuthenticodeSignature` reports NotSigned.
- **Fix direction:** A signed installer (Inno Setup or MSI) that installs prerequisites, adds a firewall rule, creates shortcuts and keeps `%LOCALAPPDATA%` on upgrade.
- **Regression risk:** Low.

### GDS-AUDIT-048: Diagnosability of the packaged app (P2, supportability)
- **Observed:**
  - With no console window, a startup exception exits with no dialog.
  - The log (`%LOCALAPPDATA%\GDS VTS\logs\startup.log`) has no timestamps, records only file:line for exceptions, and its location is not shown anywhere in the app.
  - Clean runs log a frightening `Windows fatal exception: code 0x8001010d`, a harmless COM exception that the crash tracer reports anyway. It appears in both the packaged log and the pytest output.
  - Production prints verbose debug lines: `WEB PATH`, one `GDS REQUEST/SERVED` line per resource, every JavaScript console message.
- **Positive:** STARTUP 1–10 markers, log rotation and redaction.
- **Evidence:** `packaging/startup_log.py`; `platform/packaged_legacy_startup.log`; `pytest-summary.txt`.
- **Fix direction:** Timestamps; a fatal-error dialog that names the log path; "Open log folder" in the app; filter the harmless exception codes; debug output off by default.
- **Regression risk:** Low.

### GDS-AUDIT-049: Terminology and abbreviations (P2, clarity)
- **Observed:**
  - The rail says "SETUP" while the tooltip, page and docs say "Configure".
  - "NAV" vs "Nav".
  - "VDR" and "VJR" are never spelt out except in VJR's subtitle.
  - The activity table's "POB" exports as "NON-CREW POB", while the crew section's "CREW POB" just counts rows.
  - "Drinking water" (UI) vs "Water endurance" (PDF).
  - VJR exposes technical fields: "Reader version", "Reader revision", "Client ID", "Generated timestamp".
  - "Patroller-I", "PID" and "Canonical" appear on Configure.
  - ROB, FW, DW, NABM, PREMIX and DP are unexplained.
  - "Download Report" (PDF) vs "Download Excel": the format is not named consistently.
  - "Last LTI (empty = none)" exports a blank, not "None".
  - The "WEATHER" button opens squall events.
- **Fix direction:** A glossary of tooltips on abbreviations; consistent labels ("Download PDF" / "Download Excel"); hide or relabel technical metadata.
- **Regression risk:** Low.

### GDS-AUDIT-050: Modern build not reproducible (P2, build engineering)
- **Observed:**
  - `requirements.txt` mixes `>=` ranges (PySide6≥6.8, installed 6.12.0; bleak≥0.22, installed 3.0.2) with exact pins (Pillow==13.0.0).
  - PyInstaller is not in `.venv`.
  - `websockets` and `mapbox-vector-tile` are imported by the code but not listed.
  - There is no lock file. By contrast, the Windows 7 environment is fully pinned and checked.
- **Fix direction:** A pip-compile lock file for the modern build, including PyInstaller.
- **Regression risk:** Low.

---

## Low-Priority Findings

| ID | Module | Category | Observed → Expected | Evidence | Fix direction (risk) |
|---|---|---|---|---|---|
| GDS-AUDIT-051 | VDR | File/data hygiene | Browsing back 5 days creates and saves 5 empty stub reports → create a report only on first edit | `app/vdr/store.py:49-51`; `vdr/model_audit_output.txt` | Lazy creation (Low) |
| GDS-AUDIT-052 | VDR | Formatting | Carried-forward openings read "5650.0"; very large values become "1.2345678901234568e+16" → plain numbers | `app/vdr/model.py:213,217` | Format with fixed decimals (Low) |
| GDS-AUDIT-053 | VDR | Performance | 120 crew: page build 1.6 s, adding a row 2.1 s (whole page rebuilt), ~46 ms per keystroke → update only the changed row | `vdr/ui_audit_output.txt` | Row-level updates (Medium) |
| GDS-AUDIT-054 | VJR | Files | A blank vessel or date gives `VJR_Vessel_Undated.xlsx`, so files collide; the timestamp is UTC with microseconds → vessel, voyage ID and date in the name; local time to the second | `app/vjr/excel.py`; `vjr/scripts/model_audit.py` | (Low) |
| GDS-AUDIT-055 | VJR | Interaction | The toolbar "Delete row" does nothing after a page rebuild (no row is selected); the per-row × deletes with no confirmation → keep the selection; "Row deleted — Undo" notice | `app/ui/pages/vjr_workspace.py:391-400` | (Low) |
| GDS-AUDIT-056 | VJR | Visual consistency | Departure-reference dates show raw ISO `2026-11-18`; photo card titles are in title case; no `*` required markers; no keyboard legend; no issue-count badge; "Vessel not set" in monospace → match VDR conventions | `vjr/vjr_06_arrival_1366x768.png`; `shell/vjr-1366x768.png` | (Low) |
| GDS-AUDIT-057 | NAV | Visual / logging | Readout placeholder `'Position ?\nSOG ? kn   COG ??'` and `Features N ? Status`: the dash and degree characters were lost; debug prints in production → correct text; logging off by default | `app/ui/pages/nav/nav_page.py:243,291`; `app/nav/web_scheme.py` | (Low) |
| GDS-AUDIT-058 | NAV | Wording | Legacy Copernicus shows "NOT CONFIGURED" instead of "UNAVAILABLE (Windows 7/8 build)"; the NASA GIBS satellite layer stops at zoom 9, so it is blurry at harbour scale → explicit message | `app/nav/maritime/providers.py:47-51` | (Low) |
| GDS-AUDIT-059 | VJR Photo | Privacy | `original.jpg` keeps the phone's GPS location data; the exported copy is correctly stripped → strip the original too, or don't keep it | `app/vjr/photo_storage.py:105` | (Low) |
| GDS-AUDIT-060 | Packaging | Size | 394 MB, 1,778 files, including unused Qt modules: 3D, Quick3D, Charts, DataVisualization, VirtualKeyboard, Multimedia, Location, etc. → exclude them | `dist\GDS VTS\` | Spec excludes (Low) |
| GDS-AUDIT-061 | Repository | Maintainability | Junk files committed at the root: `ersrayhaGDS-VTS` (captured git output), `ffline-engine-palette` (captured `less` help text). Dead code: `app/ui/components/sidebar.py`, `app/ui/pages/nav_page.py` stub, the `AppState` module gate (now a no-op), `TopTabs.set_locked(unlocked)` ignores its argument, `core/settings.py`, `storage/telemetry_recorder.py`. 601 MB `build/` scratch area. 3 failing tests (033). | `git ls-files` | Clean up; get the test suite to green (Low) |

---

## Module Reviews

### Configure
Configure is really a **connection console**. It has no identity or configuration fields at all (001).
- **Layout:** the two transport cards, the summary strip and the System Health tiles look professional.
- **Behind the layout:**
  - The live telemetry cards never update (012).
  - Connection errors and disconnects are invisible (013), and there is no Disconnect button (014).
  - Device details ignore the selection, and nothing is remembered between sessions (043).
  - Health tiles can show LIVE for stale data (041).
- **Startup:** with nothing connected, the user sees a page full of "—" and "NO DEVICE", with no guidance on what to do first.
- **Recommendation:** Configure should become the place where the vessel is set up once (identity, contract, units) and where the connection is clearly controlled.

### VDR
VDR is the most complete module and visually the strongest.
- **What works well:** the day-picker rail, chip-based weather entry, HHMM shorthand, FROM times filled in automatically, the draft profile illustration, atomic saving and template-faithful Excel.
- **Main problems are integrity, not looks:**
  - Stale or skipped carry-forward (002, 008).
  - The store lockout (003).
  - Finalize and export rules disagree (004).
  - Finalize can be undone silently (005).
  - The destructive 2400 rule (006).
  - Comma parsing (007).
  - PDF fragility and missing content (009, 029).
- **Usability:** errors are not shown at the field (027); undo works per keystroke (031); weather has 21 tab stops per slot (032); tables need horizontal scrolling at 1366×768 (033).
- **Location duration:** the difference between contiguous visits (shown in the app) and per-location totals (exported) is not explained, and the exported view is never shown (030). This confirms the concern in the brief.

### VJR
VJR is a credible redesign that matches VDR's design language, and its validation for coordinates is better than VDR's.
- **Waypoint DMS entry:** invalid values (lat 91, lon 181, minute 60, second 60, course 360) are flagged inline and block export.
- **Photo workflow:** implemented and the most security-conscious part of the codebase (038, 059 are hygiene items).
- **Weaknesses:**
  - No required fields or date-order checks (010).
  - No new-voyage concept (011).
  - Slow hourly log entry (026) and a 100-row cap (039).
  - Template drop-down lists not offered (036).
  - Arrival values locked to departure (037).
- **Shell:** VJR carries a duplicated header, while VDR does not (040).
- **Compared with VDR:** VJR is slightly more "spreadsheet-like" on Voyage Progress, with nested scrolling and no frozen columns, and lacks VDR's issue badge and keyboard legend (056).

### NAV / Map
NAV has a deep and well-engineered data layer:
- provider back-off and caching
- bounded responses
- off-GUI-thread networking
- hardened offline tile serving
- local-only search
- 311 passing tests

What reaches the operator is less reliable:
- **Display:** zero values shown as missing and an invented heading (016); no stale or lost state (017).
- **Offline and failure handling:** no offline recovery (018); undetected renderer failure (019).
- **Long voyages:** performance degrades over days of tracking (020).
- **Squall alerting:** looks like an all-clear when no feed exists (021).
- **Privacy:** the vessel position is sent to public servers by default (022).
- **Shutdown and legacy stability:** shutdown can block for 32 s or more (023), and the legacy build can crash during GIS load (024).
- **Controls:** mostly icon-only, and the Layers panel is long (045).

### Settings
No Settings page exists (044). The application's persisted preferences are limited to NAV map view, palette and layers, stored invisibly in the registry. The brief's list (app name, logo, fonts, reset) has no implementation.

### Connectivity (USB / Serial / BLE)
Serial reading correctly runs on a background thread, and parsing is fast and handles split and CRLF-terminated frames. BLE is correctly disabled before Windows 10 1709 with a clear message ("Bluetooth LE is not supported on this Windows version."), which satisfies the accepted legacy limitation.

Otherwise the user experience is unfinished:
- **Hidden failures:** silent errors (013).
- **Connection control:** no Disconnect and port leaks (014).
- **BLE:** data very likely never delivered, and scans freeze the UI (015).
- **Garbage input:** malformed or arbitrary JSON is accepted, and one bad line kills the stream (042).
- **Status:** reconnect and status logic is incomplete (041).

Not tested with real FTDI, CDC or BLE hardware.

### Camera
**No camera feature exists in the desktop application.** There is no QCamera, OpenCV or recording code, and `docs/windows-compatibility.md:97` confirms this. The only camera use is the phone's browser camera in the VJR photo upload page (`capture="environment"`). The camera audit items (open, record, stop, filename, close during recording) are not applicable. If camera recording is on the roadmap, it is not started.

### Exports
**Excel (VDR and VJR):** the strongest part of the product.
- The template's internal sheet files are patched directly, so formatting and validation survive.
- The template is checked by hash and structure.
- Inline strings prevent formula injection; Unicode and long text are preserved.
- Writing is atomic, and capacity overflow is reported instead of silently truncated.
- Filenames are made safe.
- **Weaknesses:**
  - Identity is blank or inconsistent (001).
  - Finalize and export rules differ (004).
  - VJR "days ago" cells are frozen and hour/minute types are wrong (035).
  - Filenames collide (054).

**PDF (VDR):**
- **Strengths:** the import round-trip is exact, and truncated files are rejected.
- **Weaknesses:**
  - Crashes on long cells (009).
  - Loses non-Latin characters and leaves out several sections that the Excel has (029).
  - Not written atomically.
- **Readability:** judged by text extraction only. The layout is a clean tabular style, and a manager could read it.
- **Gap:** VJR has no PDF export. That is not in scope per the brief, but it differs from VDR.

### Windows Compatibility
- **Good practice:**
  - The legacy track is carefully controlled: fully pinned, Python version guard, path-length check, SHA-256 manifest, `asInvoker` manifest with supportedOS entries for Windows 7 to 10.
  - WebEngine profiles are separated per Qt major version.
  - BLE is cleanly disabled on old Windows.
- **Problems:**
  - Legacy Copernicus is labelled "NOT CONFIGURED" rather than "UNAVAILABLE" (058).
  - The legacy build initialises WebEngine at startup, which makes the whole app depend on it (019).
  - The legacy GIS crash (024) is the main compatibility risk.
  - The modern and legacy builds cannot be told apart (025).
- Not tested on real Windows 7, 8 or 8.1.

### Packaging / Deployment
- **Packaged legacy exe:**
  - Launched successfully: window shown about 4.0 s after launch, map loaded, exit code 0, about 2.5 s shutdown.
  - Memory peak about 713 MB in the main process and about 805 MB including child processes.
  - The bundle is stale (025), large (060) and unsigned (047), and crashes are hard to diagnose (048).
- **User data:**
  - Stored correctly under `%LOCALAPPDATA%\GDS VTS\` and `HKCU\Software\GDS\VTS`, so replacing the folder keeps data.
  - Data storage is scattered across `GDS VTS\`, `GDS\VTS\maritime-cache` and the registry. That is worth consolidating, but it is not a defect.

---

## UX Consistency Review

| Aspect | Configure | VDR | VJR | NAV | Verdict |
|---|---|---|---|---|---|
| Global header | Shown | Hidden | Shown, plus its own header | Hidden | **Inconsistent** (040) |
| Telemetry status visible | Yes | No | Yes | Badge (different) | **Inconsistent** |
| Visual language | Deep Current light cards | Deep Current light | Deep Current light | Dark map overlay | Coherent; NAV dark is appropriate |
| Validation display | n/a | Counts, badge, modal; no field marking | Inline tint plus first-error banner | n/a | **Inconsistent** (027) |
| Required markers | n/a | `*` | none | n/a | Inconsistent (056) |
| Autosave | none needed | Debounced timer | Every keystroke written to disk | Settings save immediately | Inconsistent (031) |
| Undo | n/a | Per keystroke, page rebuild | Per keystroke, page rebuild | n/a | Consistently weak |
| Date display | n/a | "19 Nov 2026" | Mixed "18 Nov 2026" and raw ISO | n/a | Minor (056) |
| Export naming | n/a | "Download Report" / "Download Excel" | "Download Excel" | n/a | Name the formats |
| Keyboard help | n/a | Legend in sidebar | None | Tooltips | Inconsistent |
| Navigation labels | "SETUP" in rail, "Configure" elsewhere | VDR | VJR | NAV | Minor (049) |

The modules look like one product. The differences are in **behaviour**: how errors are shown, when data is saved and what headers appear. These are the inconsistencies operators will notice.

---

## Data Integrity Review

Ranked by likelihood × harm:
1. **Identity missing or inconsistent across exports** (001): certain on every clean install.
2. **Stale carry-forward of ROB, flowmeters and run hours** (002): likely under the normal morning routine.
3. **Comma-decimal ×10 errors** (007): likely for some crews.
4. **Store lockout, with work silently not saved** (003): low probability, catastrophic outcome.
5. **Finalized reports silently changed** (005); **2400 row deletion** (006).
6. **Missing plausibility rules** (010, 028, 034): illogical data accepted.
7. **Telemetry accepts arbitrary JSON; coordinate heuristic** (042): wrong positions possible on the map.
8. **Zero values shown as missing; invented heading** (016).

**Safeguards that work:**
- Atomic writes; an unreadable store is never overwritten.
- The Excel template is hash-checked; Excel capacity overflow is reported instead of truncated.
- VJR coordinate validation; VJR departure and arrival data are stored separately.
- The photo path is safe.

---

## Performance Review

| Measurement | Result | Assessment |
|---|---|---|
| Startup, source (Py3.13), to window shown | ~4.4 s (imports 0.84 s, MainWindow 2.16 s) | Acceptable; no splash screen, so ~4 s with nothing on screen |
| Startup, packaged legacy exe | ~4.0 s to window shown | Acceptable |
| Malaysia GIS load (worker thread) | ~17 s | Fine off the GUI thread; causes crashes on legacy (024) |
| Shutdown, healthy network | ~0.3 s (source), ~2.5 s (packaged) | Good |
| Shutdown, stalled provider | **32.3 s** | Poor (023) |
| Memory, process tree after startup | ~805–814 MB | High but mostly WebEngine; watch on 4 GB legacy PCs |
| VDR, 120 crew | 1.6 s build, 2.1 s per row add, 46 ms per keystroke | Sluggish (053) |
| VJR, dense (200 crew, 100 progress rows) | 0.26 s build, 18 ms per cell edit, 0.1–0.18 s per row add | OK; progressive rebuild cost (026) |
| VJR Excel export, dense | ~0.6 s | Good |
| Telemetry parsing | ~78k frames/s (Py3.13), 57k (Py3.8) | Excellent |
| NAV track after 24 h / 7 days at 1 Hz | 2.1 MB / 14.6 MB per frame | **Degrades over days** (020) |
| Maritime render publish | ~89 ms average, 304 ms worst, on the GUI thread every ~30 s | Noticeable stutter (046) |
| BLE scan | 4 s UI freeze | Poor (015) |

---

## Reliability Review

**Strengths:**
- Storage is atomic.
- Shutdown order is explicit; 10 out of 10 default stress runs exited cleanly.
- Provider back-off and timeouts mean the UI thread never does network work.
- Caches and response sizes are bounded.

**Weaknesses:**
- **Silent failure paths:** transport errors (013), the dead read thread (042), the store's "SAVE FAILED" text (003), WebGL loss (019) and packaged crashes (048) are all invisible to the user.
- **Long-runtime growth:** the NAV track grows without limit (020) and the maritime state is re-sent constantly (046).
- **Legacy crash:** the shapely access violation (024).
- **Shutdown:** can block on network requests (023).
- **Recovery:** no backups and no recovery UI (003); no reconnect for USB (013).

---

## User Workflow Review

**First run (new vessel):**
1. The user opens the app and lands on a Configure page that is entirely "—".
2. There is nowhere to enter vessel, client or hire date.
3. They scan USB, pick a port and press CONNECT. If it fails, nothing happens.
4. If it succeeds, the Live Telemetry cards still show "—" (012).
5. They open VDR: "UNNAMED VESSEL".

Each step creates a support call.

**Daily VDR routine:**
1. Open the app; today is created from yesterday.
2. Correct yesterday, which leaves today's opening values stale (002).
3. Finalize yesterday, then Download Excel. Export may fail if a value violates an export-only rule (004). Fixing it un-finalizes the report (005).
4. Today: the activity log is fast with the HHMM shorthand, but setting 2400 early deletes rows (006). Weather needs many Tab presses (032).

**Voyage (VJR):**
- Fill in identity again (001/013).
- Waypoints: good validation.
- Departure, then Departure photo by QR code: works well.
- Hourly progress: very slow (026), capped at 100 rows (039).
- Arrival: arrival drafts can't be changed (037).
- Export: works even if blank (010).
- Next voyage: manually clear everything (011).

**At sea with NAV:**
- With no internet at startup the basemap is blank until restart (018).
- A stopped vessel shows "—" (016).
- After a sensor drop the marker looks current (017).
- After several days the UI slows (020).

---

## Module Scorecard

Scores are 1–10 (10 = excellent). They are not inflated.

| Module | Functionality | Usability | Visual Quality | Reliability | Consistency |
|---|---|---|---|---|---|
| Configure | 3 | 4 | 6 | 3 | 4 |
| VDR | 6 | 5 | 7 | 5 | 4 |
| VJR | 6 | 5 | 7 | 6 | 6 |
| NAV | 6 | 5 | 6 | 4 | 5 |
| Connectivity | 3 | 3 | 6 | 3 | 4 |
| Settings | 2 | 2 | n/a (no UI) | 6 | 4 |
| Exports | 7 | 6 | 7 | 5 | 4 |
| **Overall Application** | **5** | **5** | **7** | **4** | **5** |

### Configure
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 3 | Telemetry panel dead; no identity fields; no Disconnect. |
| Usability | 4 | Clear card layout, but no guidance and silent failures. |
| Visual | 6 | Professional cards; cramped summary strip; no units. |
| Reliability | 3 | Status can show CONNECTED and LIVE for a dead link. |
| Consistency | 4 | The card, health tile and header disagree. |

### VDR
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 6 | Every section works; carry-forward stale or skipped; finalize does not guarantee export. |
| Usability | 5 | Smart shorthands, but no field-level errors, per-keystroke undo, many tab stops, horizontal scroll at 1366. |
| Visual | 7 | Best-looking module; faint error states, some truncation. |
| Reliability | 5 | Atomic saves, but one bad field locks everything, PDF crashes on long text, finalized reports change silently. |
| Consistency | 4 | Validate, Excel and PDF use three different rule sets; two hire-date sources; label drift. |

### VJR
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 6 | Full template coverage and photo workflow; no new voyage, no date-order checks. |
| Usability | 5 | Hourly log is laborious; identity re-entered; nested scroll. |
| Visual | 7 | Consistent with VDR; double header and small polish gaps. |
| Reliability | 6 | Atomic saves and a hardened photo server; corrupt store is a dead end; writes on every keystroke. |
| Consistency | 6 | Same look as VDR, but a different validation and autosave model. |

### NAV
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 6 | Rich provider and GIS stack; no offline fallback in the UI; no squall feed. |
| Usability | 5 | Icon-only tools; long Layers panel; silent no-op commands. |
| Visual | 6 | Coherent dark theme; corrupted placeholder text; no stale visuals. |
| Reliability | 4 | Legacy crash, shutdown block, WebGL loss undetected, unbounded track. |
| Consistency | 5 | Badge, status text and provider states disagree. |

### Connectivity
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 3 | Scan and connect exist; BLE data very likely broken; no Disconnect; no reconnect. |
| Usability | 3 | Errors silent; details ignore the selection. |
| Visual | 6 | Clean cards and tiles. |
| Reliability | 3 | Dead reader undetected; port leak; arbitrary JSON goes LIVE. |
| Consistency | 4 | Contradictory status indicators. |

### Settings
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 2 | No page; preferences implicit; connection mode not saved. |
| Usability | 2 | Nothing to use. |
| Visual | n/a | No UI. |
| Reliability | 6 | The preferences that exist are validated, with safe fallbacks. |
| Consistency | 4 | One settings namespace, but the validation profile leaks into it. |

### Exports
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 7 | Exact-template Excel for both modules; VDR PDF with import. |
| Usability | 6 | One click; filename collisions; the first error only. |
| Visual | 7 | Template fidelity is excellent; PDF clean but incomplete. |
| Reliability | 5 | Excel atomic and robust; PDF crashes on long text and is not atomic. |
| Consistency | 4 | Identity and content differ between screen, PDF and Excel. |

### Overall application
| Dimension | Score | Reason |
|---|---|---|
| Functionality | 5 | Strong reporting core, with gaps in identity, connectivity and settings. |
| Usability | 5 | Good ideas, undermined by silent failures and inefficient repetitive entry. |
| Visual | 7 | A genuinely consistent, modern design system. |
| Reliability | 4 | Several silent-failure and long-runtime issues, and a legacy crash. |
| Consistency | 5 | Looks unified; behaves differently per module. |

---

## Top 10 Fixes

| # | Issue | Reason | Expected user benefit | Complexity |
|---|---|---|---|---|
| 1 | **Vessel identity in Configure, used as the single source for all displays and exports** (001) | Every VDR export is currently missing vessel name, hire date and Report No. | Correct reports from day one; no repeated entry across VDR and VJR | **LOW–MEDIUM** |
| 2 | **Store resilience: input caps, per-record quarantine, rotating backups, blocking recovery banner** (003) | One bad field can silently stop all saving | No lost days; recovery without a support call | **MEDIUM** |
| 3 | **Correct carry-forward: linked openings, roll over from the last report, mismatch warning** (002, 008) | Wrong ROB and meter readings flow into every following day | Trustworthy inventory figures; less re-typing | **MEDIUM** |
| 4 | **One validation contract for finalize and export; read-only finalized reports with explicit Reopen; no destructive 2400** (004, 005, 006, 010) | Finalized reports fail to export or change silently; VJR accepts nonsense | "Finalized" becomes meaningful; export always succeeds after Finalize | **MEDIUM** |
| 5 | **Connectivity wiring: telemetry panel, error and state signals, Disconnect, reconnect, port cleanup** (012, 013, 014) | Main connection feedback is missing or wrong | Users know whether the sensor is working, and why not | **MEDIUM** |
| 6 | **NAV truthfulness: zero values, no-heading marker, stale/lost marker and banner, WebGL and offline messaging, squall feed status** (016, 017, 018, 019, 021) | The map can present old or invented data as current | Safe situational awareness | **LOW–MEDIUM** |
| 7 | **BLE persistent event loop and asynchronous scan and connect** (015) | BLE is likely non-functional and freezes the UI | Working wireless telemetry | **MEDIUM** (needs hardware testing) |
| 8 | **Release engineering: rebuild from a committed tree, distinct names and versions, signed installer, crash dialog, log access** (025, 047, 048, 050) | The current `dist/` lacks VJR; installation needs technical knowledge; crashes are invisible | Reliable installs, upgrades and support | **MEDIUM–HIGH** |
| 9 | **Runtime stability: limited shutdown wait, legacy shapely crash, track thinning, publish only changes** (020, 023, 024, 046) | Hangs, legacy crashes and slowdown over long voyages | Stable multi-day operation | **MEDIUM–HIGH** |
| 10 | **Data-entry efficiency: VJR New Voyage, "Add next hour", dates you can type, undo grouped per field, debounced saving, strict decimal parsing, field-level errors** (007, 011, 026, 027, 031) | Repetitive entry is slow and error-prone | Faster daily and voyage reporting with fewer mistakes | **MEDIUM** |

None of these have been implemented. This audit made no code changes.

---

## Recommended Roadmap

**Phase 1: Correctness and safety (1–2 weeks)**
- Fixes 1–4: identity, store resilience, carry-forward, validation and finalize contract.
- 007 decimal parsing; 009 PDF robustness.
- Commit the VJR work. Get the test suite back to green (033 / 061).

**Phase 2: Connectivity and NAV truthfulness (1–2 weeks)**
- Fixes 5–7.
- 041/042 telemetry robustness.
- 022 Overpass privacy decision.

**Phase 3: Release readiness (1–2 weeks)**
- Fixes 8–9.
- Rebuild both targets, then repeat this audit on the **packaged** modern and legacy builds and on real hardware (Patroller-I via FTDI/CDC, a BLE device, a Windows 7 PC).

**Phase 4: Efficiency and polish (ongoing)**
- Fix 10.
- 026–039 VJR and VDR usability.
- 040/045/049 shell, NAV controls and terminology.
- P3 items.

---

## Production-Readiness Verdict

### **D. NOT YET PRODUCTION READY**

The architecture, design language and export engines are strong, and many fixes are small. The verdict is D rather than C because three areas affect the core purpose of the product:

1. **The reports it produces are wrong out of the box, or can quietly become wrong.**
   - The vessel identity, Date of Hire and therefore the Report No. cannot be entered, so they are missing from every VDR export on a new install.
   - Opening stock and meter readings can silently go stale.
   - A finalized report can be changed by one keystroke.
2. **Work can be silently lost.** A single bad field stops all saving, and the only sign is faint grey text.
3. **The live-telemetry promise of a "Vessel Telemetry System" is not delivered in the UI.**
   - The Configure telemetry panel never shows data.
   - Connection errors and unplug events are invisible.
   - BLE data is likely never received.
   - NAV can show stale or invented values as current.

Also, the packaged build in `dist/` does not contain the current VJR module, and the VJR work itself is uncommitted. Once Phases 1–3 of the roadmap are complete and re-verified on packaged builds with real hardware, the application should reach **C** and plausibly **B**.
