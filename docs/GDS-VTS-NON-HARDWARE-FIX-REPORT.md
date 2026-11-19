# GDS VTS — Non-Hardware Fix Report

| | |
|---|---|
| **Date** | 19 November 2026 |
| **Branch** | `feature/nav-squall-phase3` (HEAD `99302a2`), all changes uncommitted |
| **Source audit** | [`GDS-VTS-FULL-APPLICATION-AUDIT.md`](GDS-VTS-FULL-APPLICATION-AUDIT.md) (61 issues) |
| **Scope** | Software-side fixes that need no Patroller-I, FTDI, USB CDC or BLE hardware, no phone and no other Windows version |
| **Evidence** | [`docs/evidence/non-hardware-fixes/`](evidence/non-hardware-fixes/) |
| **Rules reference** | [`vessel-identity-and-carry-forward.md`](vessel-identity-and-carry-forward.md), [`nav-external-data-privacy.md`](nav-external-data-privacy.md) |

Nothing was committed. The VJR module and photo workflow were already uncommitted before this work. They are kept and extended, not reverted.

> **Status:** All P0 issues and most P1 non-hardware issues are fixed and covered by tests. Both test suites pass: modern 801/801; legacy 800 passed, 1 skipped. Both release candidates were rebuilt into separate folders and launch cleanly. Several P1 items are only partly fixed, one P1 was not attempted, and many P2/P3 items remain (§8). **Conclusion: C — NON-HARDWARE FIXES PARTIALLY COMPLETE.**

---

## 1. Baseline (before any change)

| Run | Result |
|---|---|
| Modern `.venv` (Py 3.13.15, PySide6 6.12.0), native Windows platform | **750 passed, 4 failed** in 4 min 39 s. All four failures are `test_vdr.py::test_wide_grids_fill_available_width_without_compressing_columns[acts/bulk/crew/ctr]`: columns summed to 1310 px against a 1169 px viewport. The audit saw three; which cases fail varies from run to run (see §4.10). |
| Legacy `.venv-win7` (Py 3.8.10, PySide2 5.15.2.1) | **753 passed, 1 skipped** in 5 min 33 s |

Both baseline logs are kept in `docs/evidence/non-hardware-fixes/baseline/`.

## 2. Status of every audit issue

**Legend:**
- **FIXED:** done and verified by automated tests or runtime checks.
- **PARTIALLY FIXED:** the main defect is gone; the remaining part is listed.
- **DEFERRED — HARDWARE REQUIRED:** needs real Patroller-I, FTDI, CDC or BLE hardware, or a real phone.
- **DEFERRED — CROSS-OS TEST REQUIRED:** needs a real Windows 7, 8 or 10 machine.
- **NOT FIXED:** not attempted in this task (mostly P2/P3 polish, or product decisions).

### P0

| ID | Issue | Status | What was done |
|---|---|---|---|
| 001 | Vessel identity cannot be entered; screen, PDF and Excel disagree | **FIXED** | New **Configure → Vessel & Client** card: Vessel Name, IMO (check digit validated), Client Name, Client ID, Date of Hire, Total Deck Space, with validation, Save and Revert. One module, `app/core/vessel_identity.py`, owns all reads and writes. VDR screen, PDF and Excel and VJR screen and Excel all read it; VJR identity fields are read-only. Finalize records a copy in the report. The NAV vessel-name copy into VDR was removed. A test confirms no other module reads or writes `vessel/*`. |
| 002 | Stale carry-forward after correcting the previous day | **FIXED** | Openings are *linked* to the source report's closing values and re-derived, oldest day first, whenever a day is opened or saved. Values the user typed over are never overwritten; they appear in a notice with a **Use … closing values** button. Finalized days are never changed. Rule: [`vessel-identity-and-carry-forward.md` §3](vessel-identity-and-carry-forward.md). |
| 003 | One bad record locks the store; saves silently refused | **FIXED** | Bad days are quarantined individually and kept verbatim. An unreadable file is preserved as `.damaged-<time>` and the store recovers from the last-known-good `.bak`, or starts fresh, with a banner. Each save is checked to be readable back before it is written. Text over the limit is refused at entry, never truncated. Save, permission and corruption failures show a clear banner saying what happened, that saved data is safe, and what to do next. VJR has the same recovery, and photo clean-up pauses after a recovery so no photo can be lost. |

### P1

| ID | Issue | Status | What was done / what remains |
|---|---|---|---|
| 004 | Finalize passes but Excel export fails | **FIXED** | One shared check (`app/vdr/validation.py::final_issues`) is used by Finalize, Excel and PDF. It also runs a dry run of the real Excel cell mapping at Finalize. The UI now limits transfers to the template's capacity (2 fuel, 1 for other items). Blocked Finalize shows every issue grouped by section with a **Go** button; Excel errors list every issue. |
| 005 | A keystroke silently un-finalizes a report | **FIXED** (second pass) | A finalized report is read-only, and **Reopen report** asks for confirmation. Each report records last modified, revision (finalize count) and reopen count; these are stored as `reportActivity` in the same `reports.json`. **VDR → Previous reports…** lists the saved reports newest first: date, Report No., vessel, status (DRAFT / FINALIZED · REV n / REOPENED · DRAFT / UNREADABLE · SET ASIDE), last modified. It has search and an empty state. Opening a report navigates only. **VJR → Voyage history…** lists archived journeys and can make one current (a safe swap: the current journey is archived first). *Remaining:* no user identity on reopen (the app has no user accounts); the revision is not printed on exports (the template has no cell for it). Evidence: `evidence/remaining-p1-fixes/runtime/01–04`. |
| 006 | TO = 2400 deletes later activity rows | **FIXED** | Only *empty* trailing rows are removed. Logged rows are kept, marked invalid, and a banner explains what to do. |
| 007 | Comma decimal "2,5" read as 25 | **PARTIALLY FIXED** | VDR accepts a comma only as a strict thousands separator; "2,5" and "1.000,5" are rejected. *Remaining:* plausibility ranges (e.g. draft 0–15 m); VJR's message for a rejected comma is unchanged. |
| 008 | Missed day gives a blank report | **FIXED** | A new day rolls over from the most recent earlier report. The notice gives the source date and the gap length. |
| 009 | PDF crashes on long cells or invalid imports | **FIXED** (second pass) | Every VDR PDF table now uses ReportLab `splitInRow=1` with `repeatRows=1`. A row taller than the remaining page continues on the next page, the header repeats, and no text is lost or duplicated (tested with a 900-word cell). The crew table gains the Comments column (029). VJR has no PDF export, so not applicable. Evidence: `evidence/remaining-p1-fixes/pdf/01–05*.pdf`, `03_render-p1..3.png`. |
| 010 | VJR has no required fields or date-order checks | **FIXED** | Required: Vessel Name (from Configure), Departure Date, Departure Location. Ordering: ETA ≥ departure, actual arrival ≥ departure, arrival report ≥ departure report, progress rows within the voyage, no duplicate progress timestamps. Crew working days limited to 90. *Remaining:* no `*` markers in the VJR UI (056). |
| 011 | VJR has no "New voyage" | **FIXED** | **New voyage…** asks for confirmation, archives the journey to `vjr/archive/journey-<time>.json` (atomic), and starts a new journey keeping the crew and contractor lists. Undo restores the previous journey. *Not done:* a browsable list of past voyages. |
| 012 | Live Telemetry panel never updates | **FIXED** (software) | The panel is refreshed on every 500 ms tick, with units. Zero is shown as 0 (e.g. "0.0 kn", "000°"). Values are dimmed and labelled when telemetry is STALE or LOST, and cleared with no source. *Pending:* check on a real device. |
| 013 | Transport errors and unplug invisible | **PARTIALLY FIXED / DEFERRED — HARDWARE REQUIRED** | The UI now handles the transports' existing `on_error`/`on_state` callbacks, queued safely from worker threads. Errors appear on the card. When the read thread ends, the card shows DISCONNECTED, the dead handle is released through the transport's own `disconnect()`, and the source is marked disconnected. Scan with no devices gives guidance. *Not done:* transport message wording and auto-reconnect; changing USB/BLE transport code was outside this task's hardware rule. *Unverified* with a real device. |
| 014 | No Disconnect; reconnect leaks the COM port | **FIXED in UI / DEFERRED — HARDWARE REQUIRED** | DISCONNECT button; a previous connection is released before connecting again; closing the app disconnects USB and BLE and flushes VDR and VJR saves. Device details follow the selected port (043). *Unverified* with a real port. |
| 015 | BLE event loop drops notifications | **DEFERRED — HARDWARE REQUIRED** | Not changed. A persistent asyncio loop must be tested with a real BLE device. |
| 016 | NAV shows zero as "—"; invents a north heading | **FIXED** | `is None` checks throughout. A missing heading is sent as `null` and drawn as a neutral, unrotated marker labelled "HDG UNKNOWN"; COG is used and labelled when present. |
| 017 | No stale or lost telemetry state on NAV | **FIXED** | LIVE / STALE / NO DATA from the last frame time. Bottom bar shows "TELEMETRY STALE · last update 42 s ago" (amber) and "TRACK PAUSED"; marker greyed. Text updates at most once a second. *Unverified:* WebGL rendering of the greyed marker (offscreen). |
| 018 | No internet at startup: blank map; regions dialog unreachable | **PARTIALLY FIXED** | The online map retries with backoff (10 s doubling to 5 min) and recovers without a restart; status says RETRYING. **Retry online map** and **Map regions…** buttons were added. Switching to installed offline regions while offline is implemented, but tested only in the JavaScript harness. *Unverified* in a real browser or a real outage. |
| 019 | WebGL/renderer failure undetected | **FIXED** (second pass) | `app/nav/renderer_health.py` and `NavPage` detect: page load failure (`loadFinished(False)`); render-process termination (`QWebEnginePage.renderProcessTerminated`, Qt5 and Qt6); WebGL start failure and context loss (reported by `nav.js`); a blank map (no style 30 s after load). A plain-language overlay offers **Retry map**, which reloads the same view, page and profile: no new WebEngine objects, and repeated retries are ignored while loading. **Verified with a real renderer crash (`chrome://crash`) on both runtimes:** detected in 0.17 s (modern) / 1.71 s (legacy); recovered in 0.45 s / 5.49 s; one `QWebEngineView` after 5 failure/retry cycles; no `QtWebEngineProcess` left after exit. *Fixed while testing:* map reloads blocked the GUI for ~27 s, because every layer re-published the full maritime state. They now publish once; in-app recovery went from 28 s to 2.8 s. *Deferred, cross-OS test required:* a software-GL fallback flag and lazy WebEngine loading for the legacy build. |
| 020 | Track unbounded and rebuilt every frame | **FIXED** | At most 6,000 points are kept (newest 1,800 at full resolution, older thinned). Distance is a running total, so it is unchanged. |
| 021 | "No active events" reads as an all-clear | **PARTIALLY FIXED** (second pass: everything except a real provider) | Feed states LIVE / STALE / NO DATA / PROVIDER UNAVAILABLE, with last-update time (receipt time). On provider failure, events are marked STALE immediately and expire normally, which clears their shapes. Recovery needs no restart. ETA counts down. Impact is judged against the own vessel's position. A top-level alert banner shows, plus **NAV ⚠** on the rail. See [`nav-squall-feed.md`](nav-squall-feed.md). *Remaining:* **no real squall provider exists** (a product/contract decision); the adapter interface is ready. Evidence: `evidence/remaining-p1-fixes/runtime/05–07b`. |
| 022 | Exact vessel position sent to Overpass | **FIXED** | Overpass, AIS, Copernicus, BOEM/EMODnet and generic feeds receive a generalised area: centred on a 0.5° grid, with a wider radius so coverage is kept. Opt-out with `GDS_OVERPASS_ENABLED=false`. Disclosure under Layers → DATA SOURCES and in [`nav-external-data-privacy.md`](nav-external-data-privacy.md). |
| 023 | Shutdown blocks on a stalled provider (32 s) | **FIXED** | Daemon network workers and a close that waits at most 2 s. Cache writes are atomic, so abandoning a request is safe. Every remote call has a timeout; Copernicus is capped at 120 s. **Measured with a local server that never answers:** 32.30 s → **2.01 s** (modern), 32.28 s → **2.01 s** (legacy). |
| 024 | Legacy shapely access violation during GIS load | **DEFERRED — CROSS-OS TEST REQUIRED** | Not reproducible in the test environments. GIS loading now runs on its own single thread (a side effect of the 023 work), which may reduce exposure, but this is **not verified**. Needs a real Windows 7/8 machine with software rendering. |
| 025 | Stale `dist/`; builds indistinguishable; version 0.0.0.0 | **FIXED** | Version source `app/version.py` = **0.9.0 (development)**. The edition (*Modern* or *Legacy Compatibility*) and the git commit are stamped into the exe version resource and a bundled `BUILD_INFO.txt`, and the window title shows them. Output goes to `dist/modern/GDS VTS/` and `dist/legacy-win7/GDS VTS/`. The stale `dist/GDS VTS` was removed and both builds were rebuilt (§6). Builds are stamped `+uncommitted` because nothing may be committed. |

### P2

| ID | Status | Notes |
|---|---|---|
| 026 VJR hourly entry slow | NOT FIXED | |
| 027 Validation feedback | PARTIALLY FIXED | VDR Finalize lists all issues grouped by section with **Go**; Excel lists every issue. No inline field outlining yet. |
| 028 VDR domain checks | PARTIALLY FIXED | Added: transfer recipient required; unnamed crew/contractor rows; duplicate equipment and bulk items; numeric lifts, POB, ages and endurances; transfer meter readings. Not added: run hours > 24, total < daily, received > meter difference. |
| 029 PDF parity | PARTIALLY FIXED | The PDF now shows Vessel, Client, Date of Hire, Report No. and HSE perfect days, and says "Drinking water endurance". Non-Latin glyphs, location summary and crew comments are still missing. |
| 030 Location names | NOT FIXED | The 22-location cap is now caught at Finalize (004). |
| 031 Undo/autosave granularity | NOT FIXED | |
| 032 Weather entry | NOT FIXED | |
| 033 Layout at 1366×768 | PARTIALLY FIXED | VDR tables are responsive: spare width goes to text columns, and columns shrink proportionally to readable minimums before any horizontal scrolling. The three or four failing layout tests now pass consistently. VJR progress table unchanged. |
| 034 VJR upper bounds | FIXED | Speed ≤ 300 kn (template), visibility ≤ 100 nm, wind ≤ 250 kn, wave ≤ 40 m, cargo ≤ 100,000 t. |
| 035 VJR frozen relative dates | NOT FIXED | |
| 036 VJR template drop-downs | NOT FIXED | |
| 037 VJR arrival drafts | NOT FIXED | Product decision. |
| 038 Photo server lifecycle | NOT FIXED | |
| 039 VJR 100-row cap | NOT FIXED | Client decision. |
| 040 Shell header | PARTIALLY FIXED | The global header now shows on Configure only, so VJR no longer has a double header. The status pill has not been moved into the rail. |
| 041 Telemetry display | PARTIALLY FIXED | Units, zero values and STALE/LOST labels in the Live Telemetry panel. Health tiles and diagnostics placeholders unchanged. |
| 042 Telemetry ingest robustness | NOT FIXED | Protocol-level: test against real Patroller-I frames first. |
| 043 COM port UX | PARTIALLY FIXED | Details follow the selected device. Last port is not remembered. |
| 044 Settings page | NOT FIXED | Vessel identity now lives in Configure. |
| 045 NAV controls | PARTIALLY FIXED | "Map regions…" and "Retry online map" are labelled buttons. The rest is unchanged. |
| 046 NAV status / render cost | NOT FIXED | |
| 047 Installer | NOT FIXED | Documented as future work (§7). |
| 048 Packaged diagnosability | NOT FIXED | `BUILD_INFO.txt` and the window title now identify the build. |
| 049 Terminology | PARTIALLY FIXED | "Download PDF" / "Download Excel"; rail tooltips spell out VDR, VJR and NAV; ROB, FW and DW explained; VJR subtitle now "Vessel Journey Report" to match the template. |
| 050 Reproducible modern build | PARTIALLY FIXED | PyInstaller installed in `.venv` and pinned in the new `requirements-build.txt`. No full lock file yet. |

### P3

| ID | Status | Notes |
|---|---|---|
| 051 Stub reports from browsing | FIXED | Days the app created only because the user looked at them are not saved and never used as a carry-forward source. |
| 052 "5650.0" / exponent notation | FIXED | Carried values are plain numbers (`5650`, `1012`). |
| 053 Slow with 120 crew | NOT FIXED | |
| 054 VJR filename collisions | NOT FIXED | |
| 055 VJR delete row | NOT FIXED | |
| 056 VJR polish | NOT FIXED | |
| 057 NAV garbled placeholder text | FIXED | |
| 058 Legacy Copernicus wording | NOT FIXED | |
| 059 Photo GPS metadata | NOT FIXED | |
| 060 Bundle size | NOT FIXED | |
| 061 Repository hygiene | PARTIALLY FIXED | The failing tests are fixed. Junk files and dead code not removed. |

## 3. Final behaviour rules (summary)

- **Identity:** Configure is the only editor; screen, PDF and Excel read the same values at all times. See [`vessel-identity-and-carry-forward.md`](vessel-identity-and-carry-forward.md) §1.
- **Report No.:** `(report date − Date of Hire) + 1`. The formula is unchanged. Finalize and export are blocked when Date of Hire is missing or after the report date, so Report No. is never silently blank.
- **Carry-forward:** see [`vessel-identity-and-carry-forward.md`](vessel-identity-and-carry-forward.md) §3.
  - Source: the most recent earlier report the user created or edited.
  - Linked openings follow corrections; manual overrides are kept and flagged.
  - Finalized days are never changed.
- **Storage:** one `.bak` backup, refreshed at most every 15 minutes, with atomic writes. Corruption is preserved and recovered from, and the user is told.
- **Finalize = export:** one shared check, plus an Excel dry run at Finalize.
- **NAV:** zero is a value; an unknown heading is never drawn as 000°; LIVE/STALE/NO DATA with the data age; online map retries automatically; positions sent to public services are generalised.

## 4. Verification

### 4.1 Automated tests

| Check | Result | Evidence |
|---|---|---|
| Baseline, modern | 750 passed, 4 failed | `evidence/non-hardware-fixes/baseline/pytest-modern-baseline.txt` |
| Baseline, legacy | 753 passed, 1 skipped | `…/baseline/pytest-legacy-baseline.txt` |
| **Final, modern** `.\.venv\Scripts\python.exe -m pytest -q --tb=short` | **801 passed, 0 failed** (4 min 14 s) | `…/final/pytest-modern-raw.txt` |
| **Final, legacy** `.\.venv-win7\Scripts\python.exe -m pytest -q --tb=short` | **800 passed, 1 skipped, 0 failed** (5 min 52 s) | `…/final/pytest-legacy-raw.txt` |
| Modern re-run of all VDR files and the new tests after the last title-bar layout edits | 153 passed | `…/final/pytest-modern-vdr-recheck.txt` |
| `compileall app main.py` (modern and legacy) | both succeed | — |

The suites ran on the native Windows platform, as the baseline did. Offscreen runs differ in fonts and layout, so they were not used for the totals. Both logs contain the harmless `Windows fatal exception: code 0x8001010d` COM dump already noted by the audit (048).

### 4.2 Runtime check (real `MainWindow`, source, 1366×768)

Script: `evidence/non-hardware-fixes/runtime/runtime_check.py`. It uses Qt test-mode data folders and an INI file for identity. Output and screenshots 01–07 are in the same folder.

| Area | Observed |
|---|---|
| Version | Window title "GDS VTS 0.9.0 (development) · Modern" |
| Configure identity | Empty at start: "Required before finalizing reports: Vessel Name, Date of Hire". An invalid IMO is rejected with a message. A valid save is persisted. |
| VDR identity | Title bar "RUNTIME CLIENT — MV RUNTIME CHECK", Date of Hire 01 Jan 2026, **Report No. 323** (19 Nov 2026) |
| Carry-forward | Today's FW opening 5000 → yesterday corrected → **4000**. A hand-edited LUB. OIL opening (1,234) is kept and flagged with the reset button. |
| Finalize | An incomplete report is blocked. The dialog groups issues by section, with **Go** buttons. |
| Over-long text | 250 characters in Captain (limit 200) is refused with a red banner: "It has NOT been saved". |
| VJR | Vessel and IMO come from Configure and are read-only |
| NAV | Map rendered on the native platform. Bottom bar: "NO TELEMETRY DATA · vessel position unknown · TRACK IDLE". |
| Close | Window close plus bounded maritime close: 0.04 s |

### 4.3 Shutdown with a stalled map provider

Local server that accepts and never answers (`evidence/non-hardware-fixes/nav/shutdown_stalled_probe.py`):

| | Before | After |
|---|---|---|
| Modern | 32.30 s | **2.01 s** |
| Legacy | 32.28 s | **2.01 s** |

### 4.4 Not verifiable here

- Physical devices (USB, BLE, Patroller-I).
- A real phone.
- Windows 7/8/10.
- WebGL appearance of the new NAV marker states.
- A real network outage and recovery.

## 5. Changed tests (behaviour changed on purpose)

Each of these existing tests asserted the defect being fixed, so it was updated to the new rule:

| Test | Old assertion | New assertion | Audit ID |
|---|---|---|---|
| `test_vdr.py::test_calculations_and_rollover` | carried `'1012.0'`, `'5650.0'` | `'1012'`, `'5650'` | 052 |
| `test_vdr.py::test_store_does_not_overwrite_corruption` | save raises; file stays broken | renamed `…destroy_corruption`: damaged copy preserved, notice shown, saving continues | 003 |
| `test_vdr.py::test_ui_undo_redo_save_finalize_download` | button text `FINALIZED`; edit after finalize un-finalizes | `Reopen report`; edit ignored until a confirmed Reopen | 005 |
| `test_vdr.py::test_narrow_width_preserves_columns` | columns keep base width at 1000 px | renamed `…keeps_readable_minimum_columns`: columns ≥ readable minimum; scroll only below that | 033 |
| `test_vdr.py::test_ui_pdf_download_and_import_actions`, `test_vdr_calendar.py::test_finalized_dates_lock…`, `test_vdr_navigation.py::test_offline_vdr…` | edit a finalized report directly | Reopen first | 005 |
| `test_vdr.py::test_old_finalized_import_preserved` | crew sign-on after report date accepted as finalized | uses a valid sign-on date; invalid content now imports as a draft (new test) | 009 |
| VDR fixtures in `test_vdr*.py` | finalize with no identity | pass a Configure test identity | 001 |
| `test_vdr_excel_export.py::test_stale_sample…_missing_config_blank` | identity `{}` exports blank Vessel, Date of Hire and Report No. | renamed `…_missing_config_blocked`: export blocked with a clear message; with identity, the configured values are exported | 001 |
| `test_vdr_excel_export.py::test_ui_gate…` | `Download Report` | `Download PDF` | 049 |
| `test_vdr_navigation.py` tooltips | `'VDR'`, `'VJR'` | `'VDR — Vessel Daily Report'`, `'VJR — Vessel Journey Report'` | 049 |
| `test_vjr.py::test_corrupt_store_is_preserved` | edit raises; dead end | damaged copy preserved, notice shown, editing continues | 003 |
| `test_vjr.py::test_capacity_exact_and_overflow`, `test_empty_export…` | blank VJR exports | the minimum required fields are filled first | 010 |
| `test_vjr_photos.py::test_cleanup_preserves_attachments_when_report_is_unreadable` | `store.load_error` set | store recovers; photos and damaged file are kept | 003 |
| `test_maritime.py:405`, `test_maritime_providers.py:386` | exact-position query box | generalised (grid-snapped) box | 022 |

New tests:
- `tests/test_non_hardware_fixes.py`: identity, carry-forward, store resilience, Finalize = export, Configure wiring, new voyage, squall wording.
- `tests/test_nav_truthfulness.py`, plus `tests/nav_truthfulness_runtime.cjs`.
- `tests/conftest.py`: an unexpected modal message box now fails a test instead of hanging the suite.

## 6. Release candidates

The stale `dist\GDS VTS` (an old legacy build without VJR) was deleted, then both builds were made from the current tree. Details: `evidence/non-hardware-fixes/build/release-candidates.txt`.

| Build | Folder | Exe version resource | Smoke launch (`--validation-profile`) |
|---|---|---|---|
| **Modern** (Windows 10/11) | `dist\modern\GDS VTS\` (6,615 files, ~853 MB) | 0.9.0.0, "0.9.0 development · Modern · 99302a2+uncommitted" | STARTUP 1–10, exit 0, 6.2 s |
| **Legacy Compatibility** (Windows 7/8) | `dist\legacy-win7\GDS VTS\` (1,789 files, ~401 MB, SHA256SUMS.json) | 0.9.0.0, "0.9.0 development · Legacy Compatibility · 99302a2+uncommitted" | STARTUP 1–10, exit 0, 5.6 s (on Windows 11) |

- **Contents:** both bundles contain the VJR module, the identity module, both Excel templates and `BUILD_INFO.txt`.
- **Build scripts:** `scriptsuild_windows_compat.ps1` now writes to `dist\legacy-win7`. The modern build command is `.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --workpath build\modern-pyinstaller --distpath dist\modern gds_vts.spec`; its tools are pinned in `requirements-build.txt`.
- **Versioning:** no release scheme existed before. 0.9.0 is a clearly-marked development version below 1.0 because hardware and cross-OS acceptance are still pending. Bump it in `app/version.py` only.
- **Installer:** future work (047); the app still ships as a portable folder.

## 7. Deferred and pending (not failures of this task)

| Item | Why it is pending |
|---|---|
| Real Patroller-I end-to-end test | No device. Telemetry panel, error, unplug and Disconnect UI verified with fake transports only. |
| FTDI physical test | No hardware |
| USB CDC physical test | No hardware |
| BLE physical test, and the BLE event-loop fix (015) | No hardware; the fix must be tested on a device |
| Real phone photo upload | No phone used. Photo tests are automated over local HTTP only. |
| Windows 7 / 8 / 10 real runtime, legacy shapely crash (024) | Only Windows 11 was available. The legacy build was tested on its Python 3.8 / PySide2 runtime on Windows 11. |
| Installer, code signing, firewall rule (047) | Future work. The app still ships as a portable folder. |
| WebGL rendering of new NAV marker and status styles; real offline-region switch | Offscreen WebEngine does not render WebGL. Covered by the JavaScript harness and code review only. |

### Side effect to clean up (action needed)

The first version of the runtime check script wrote **test vessel identity values to this PC's real Windows settings**, because `QSettings.setDefaultFormat` does not apply to `QSettings('GDS','VTS')`.

- **Key affected:** `HKCU\Software\GDS\VTS\vessel`.
- **Values written:** name = MV RUNTIME CHECK, imo = 9074729, client = RUNTIME CLIENT, client_id = RC-1, date_of_hire = 2026-01-01, deck_capacity = 850.
- **State before:** the key held no values; the audit and the first run both confirm this.
- **Removal:** the automated removal was blocked by the session's safety rules. Remove it manually with `Remove-Item 'HKCU:\Software\GDS\VTS\vessel'`, or clear the fields in Configure → Vessel & Client.
- **Already fixed:** the script now writes only to a temporary INI file.

## 7b. Second pass: remaining P1 items (005, 009, 019, 021)

Starting point: commit `5698673`. Baseline: modern **801 passed**; legacy **800 passed, 1 skipped** (`evidence/remaining-p1-fixes/baseline/`).

| Item | Result | Main evidence |
|---|---|---|
| 019 renderer failure | FIXED | `renderer/renderer_stress.py` and outputs (real `chrome://crash`), `tests/test_remaining_p1.py`, `tests/nav_renderer_runtime.cjs` |
| 005 history / reopen | FIXED | `runtime/01_vdr_previous_reports.png`, `02_…search.png`, `03_vdr_opened_old_finalized_readonly.png`, `04_vjr_voyage_history.png` |
| 009 PDF row split | FIXED | `pdf/03_single_row_crosses_pages.pdf` and `03_render-p2.png` (header repeated, row continued) |
| 021 squall feed | PARTIALLY FIXED (no real provider) | `runtime/05`–`07b`, `docs/nav-squall-feed.md` |

**Final tests (second pass):** modern **824 passed**, legacy **823 passed, 1 skipped**; `compileall` passes on both runtimes (`evidence/remaining-p1-fixes/final/`).

**Conclusion of the second pass:** **C. REMAINING P1 SOFTWARE ISSUES PARTIALLY COMPLETE.** 005, 009 and 019 are fixed. 021 is complete except for a real squall provider, which does not exist yet.

**Measured:**

| Measurement | Result |
|---|---|
| Renderer crash detection | 0.17 s (modern) / 1.7 s (legacy) |
| Recovery, standalone | 0.45 s / 5.5 s |
| Recovery inside the full app, with GIS and a vessel | 2.8 s (was 28 s before the publish fix) / 6.8 s |
| History filtering | under 1 ms |
| PDF with a cell longer than a page | ~0.3 s |
| Shutdown after a renderer failure | 0.02 s / 0.12 s |

## 8. Remaining non-hardware defects (honest list)

- **P1, partially fixed:**
  - 007: plausibility ranges are not added.
  - 018: the real-browser offline fallback is unverified.
  - 021: no real squall provider exists (the interface is ready).
- **Deferred:** legacy software-GL fallback and lazy WebEngine loading (019 follow-up, needs a Windows 7/8 machine).
- **P2/P3:** see §2. The main ones are VJR entry efficiency (026), undo/autosave granularity (031), weather entry (032), template drop-downs (036), Settings page (044) and diagnosability (048).

## 9. Conclusion

**C. NON-HARDWARE FIXES PARTIALLY COMPLETE**

**Fixed and verified:**
- All three P0 issues: identity, carry-forward, store resilience.
- The finalize/export contract (004).
- NAV truthfulness (016, 017, 020), privacy (022) and shutdown (023).
- New voyage (011) and the VJR rules (010, 034).
- The table-width test failures.
- Versioned, distinguishable release candidates (025).

**Why C rather than A or B:**
- One P1 non-hardware issue was not attempted: 019, WebGL/renderer failure detection.
- Several P1 issues are only partly fixed: 005, 007, 009, 018, 021.
- Many P2/P3 usability items remain (§2).

None of these block the hardware and cross-OS acceptance runs. They should be scheduled before a production release.
