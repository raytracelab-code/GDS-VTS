# Vessel identity, Report No. and VDR carry-forward rules

This page describes the rules the application uses after the non-hardware fixes. The audit findings it relates to are GDS-AUDIT-001, 002, 003, 004, 005 and 008.

## 1. Vessel identity: one source

| Field | Where it is entered | Stored as (Windows settings `HKCU\Software\GDS\VTS`) | Used by |
|---|---|---|---|
| Vessel Name * | Configure → Vessel & Client | `vessel/name` | VDR title bar, VDR PDF, VDR Excel (`GDS Meta!C9`, `VDR!E12`), VJR (read-only), VJR Excel (`D11`, `D6`) |
| Vessel IMO | Configure | `vessel/imo` | VJR (read-only), VJR Excel |
| Client Name | Configure | `vessel/client` | VDR title bar, VDR PDF, VDR Excel (`GDS Meta!C11`), VJR, VJR Excel |
| Client ID | Configure | `vessel/client_id` | VJR, VJR Excel |
| Date of Hire * | Configure | `vessel/date_of_hire` | VDR title bar, Report No., HSE perfect days, VDR PDF, VDR Excel (`C10`, `I12`) |
| Total Deck Space (m²) | Configure | `vessel/deck_capacity` | VJR deck utilisation, VJR Excel |

\* Required before a VDR report can be finalized.

- **Writer and readers.** `app/core/vessel_identity.py` is the only code that writes or reads these settings, and the Configure card is its only editor. A test, `tests/test_non_hardware_fixes.py::test_no_independent_identity_writer_remains`, checks that no other module writes `vessel/*` settings and no other module reads them directly.
- **Validation:**
  - IMO must be 7 digits with a valid check digit.
  - Date of Hire must be a real date, no earlier than 1990 and not in the future.
  - Deck space must be a number greater than 0 and no more than 100,000 m².
  - Lengths are limited. An invalid value is never stored.
- **The screen, PDF and Excel always use the current Configure values.** This is so a screen and an export of the same day can never disagree, which is the GDS-AUDIT-001 defect where the screen showed Report No. 322 and Excel showed 171.
- **Finalize keeps a copy for the record.** When a report is finalized, the identity at that moment is copied into the report's `identity` field and embedded in the PDF. This copy is not used for display or export.
- **VJR identity fields are read-only.** They show the Configure values, with the tooltip "Set in Configure → Vessel & Client".
- **No other source.** The earlier VDR behaviour, where the NAV vessel-config name ("Unnamed Vessel") was copied into each report, has been removed.

## 2. Report No. rule (unchanged formula, now never silently blank)

```
Report No. = (report date − Date of Hire) + 1        # Date of Hire is day 1
```

This is the original VDR formula, implemented in `app/vdr/model.py::report_number`, and it has not changed. What has changed:

- **Finalize checks the inputs.** Finalize and Excel export are blocked, with a clear message, when:
  - Date of Hire is not set;
  - Date of Hire is invalid;
  - Date of Hire is after the report date, which would give a Report No. below 1.
- **The number is always visible.** The VDR title bar shows **REPORT NO.** next to **DATE OF HIRE**.
- **Consistent everywhere.** The PDF and Excel print exactly the same number, because all three use the same identity source and the same function.

## 3. VDR carry-forward rule

### Source report

The openings for report date **D** come from the most recent earlier report (date < D) that the user created, edited or imported.

- **Skipped days.** Days with no report are skipped. For example, a report on 10 Nov followed by nothing until 13 Nov means 13 Nov carries from 10 Nov.
- **Browsing does not create reports.** Pages the app created only because the user looked at a date are not used as a source and are not saved. This also fixes GDS-AUDIT-051 (stub reports saved by browsing).
- **Gap notice.** When the gap is more than one day, the section notice says so.

### Carried values (closing becomes opening)

| Opening in report D | Taken from the source report |
|---|---|
| Bulk item *Opening @0000H* (every item, matched by name) | That item's computed *Closing @2400H* (opening + received − consumed − transferred) |
| Equipment *Flowmeter @0000H* | *Flowmeter @2400H*, or *@0000H* if no 2400H reading was entered |
| Equipment *Total run hrs* | Total + daily run hours |

Crew, contractors, equipment and bulk rows, captain, location and drafts are also copied when a new report is created. These are editable starting values, not linked figures.

### When the source changes later (correction propagation)

- **Linked values follow corrections.** An inherited value that the user has not changed is *linked*. If the source report is corrected later, every later non-finalized report updates automatically, oldest first, the next time it is opened or saved. The usual case is correcting yesterday after today's report has already been created.
- **Manual values are kept.** A value the user typed over is a *manual override* and is never overwritten.
- **The differences are shown.** The Running hours and Bulk inventory sections show a notice like this:

  > Openings carried from the 17 Nov 2026 closing. 1 value(s) were changed by hand and differ: LUB. OIL (ltrs) opening @0000H: 1,234 (closing was 4,990).

  A **Use 17 Nov 2026 closing values** button resets every opening to the source closing. It is an ordinary edit, so it can be undone.
- **Finalized reports are never changed by carry-forward.** If their source is corrected afterwards, the difference appears in the same notice. **Reopen report** is the only way to change a finalized report, and it asks for confirmation.
- **Older stores.** Reports saved before this change have no link history. For those, only blank values, or values already equal to the source closing, are treated as linked. Everything else is treated as manual, so nothing a user typed is overwritten silently.

## 4. Storage safety

| Situation | Behaviour |
|---|---|
| One stored day is malformed | Only that day is set aside. It is kept verbatim under `quarantined` in the file. All other days load, a banner names the affected days, and saving continues. |
| The whole file is unreadable | The file is copied to `reports.json.damaged-<time>`. The last-known-good `reports.json.bak` is loaded and a banner says how old it is. If no backup is usable, an empty store is started and the banner says so. The damaged copy is never deleted. |
| The damaged file cannot be copied | The original is never overwritten. Saving pauses and the banner explains what to do. |
| A change could not be read back after a restart | It is refused before writing. The previous file stays intact and the banner says what to undo or shorten. |
| Text longer than the field limit | It is refused at entry and not truncated. A banner says "It has NOT been saved — shorten it". The limit is 1,000 characters for activity, remarks and comments, and 200 for other fields. |
| Permission denied, disk full or other write errors | A red banner says what happened, that previously saved data is safe, and what to do next. Saving retries on the next change. |
| Backup | There is one `reports.json.bak` (VJR uses `report.json.bak`). It is refreshed from a known-good file at load and at most every 15 minutes while saving. Writes are atomic: temp file, fsync, replace. |

VJR uses the same recovery and backup behaviour for `vjr/report.json`.

## 5. Finalize = export contract

- **One shared check.** `app/vdr/validation.py::final_issues` is used by Finalize, Excel export and PDF export. It covers:
  - the content rules;
  - identity, meaning Vessel Name and a valid Date of Hire;
  - template capacity: 90 activity rows, 22 locations, 200 crew, 200 contractors, 2 fuel transfers and 1 transfer for every other item;
  - names known to the template, with no duplicates;
  - every number and date the exporters parse.

  Finalize then runs the real Excel cell mapping as a dry run as a final safety check.
- **No rules the UI can't meet.** The UI no longer lets the user add more transfers than the template holds.
- **What the user sees.** When Finalize is blocked, the user gets a list of problems grouped by section with a **Go** button for each section. Excel errors now list every problem, not only the first.
- **Imports are re-checked.** An imported report marked finalized is checked again. If it fails, it is imported as a draft and the problems are shown.
