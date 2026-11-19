# VJR Excel cell map

Source: `Downloads/Untitled spreadsheet.xlsx`. Bundled unchanged as `app/resources/templates/vjr_template.xlsx`.

SHA-256: `04e1ad4b53066f05475c962f05ac39f918e579ac1ee5b1bb0dd5f7634961d4e8`.

Schema version 1. Dates are stored as ISO calendar dates in JSON and exported as Excel date numbers with the original cell number formats. Times are 24-hour HH:MM, split into original hour/minute cells. Numbers are finite, nonnegative values. Identifiers remain text.

| Model field | UI section | Sheet | Cell/range | Type | Source / transformation |
| --- | --- | --- | --- | --- | --- |
| meta.report_id | General / Report ID | GDS Meta | D7 | text | Manual; blank remains blank |
| meta.report_name | General / Report Name | GDS Meta | D8 | text | Manual; blank remains blank |
| meta.client_id | General / Client ID | GDS Meta | D9 | text | Manual; blank remains blank |
| meta.generated | General / Generated Timestamp | GDS Meta | D10 | automatic | UTC timestamp at export |
| meta.vessel | General / Vessel Name | GDS Meta | D11 | text | QSettings GDS/VTS vessel/name or vessel/client if present; otherwise manual |
| meta.imo | General / Vessel IMO | GDS Meta | D12 | text | Manual; blank remains blank |
| meta.capacity | General / Total Deck Space (m²) | GDS Meta | D13 | number | Manual; blank remains blank |
| meta.client | General / Client Name | GDS Meta | D14 | text | QSettings GDS/VTS vessel/name or vessel/client if present; otherwise manual |
| meta.reader_version | General / Reader Version | GDS Meta | D26 | text | Manual; blank remains blank |
| meta.reader_revision | General / Reader Revision | GDS Meta | D27 | text | Manual; blank remains blank |
| crew[].sequence | crew | 1. Core Crew | B8:B207 | integer | Sequential row number; unused rows cleared |
| crew[].name | crew / Name | 1. Core Crew | C8:C207 | text | Manual; unused rows cleared |
| crew[].rank | crew / Rank | 1. Core Crew | D8:D207 | text | Manual; unused rows cleared |
| crew[].age | crew / Age | 1. Core Crew | E8:E207 | age | Manual; unused rows cleared |
| crew[].nationality | crew / Country of Nationality | 1. Core Crew | F8:F207 | text | Manual; unused rows cleared |
| crew[].passport | crew / IC / Passport No. | 1. Core Crew | G8:G207 | text | Manual; unused rows cleared |
| crew[].sign_on | crew / Date Sign-on | 1. Core Crew | H8:H207 | date | Manual; unused rows cleared |
| crew[].working_days | crew / Working Days | 1. Core Crew | I8:I207 | derived | Derived: (arrival report date, else departure report date) − sign-on + 1; materialized |
| crew[].remarks | crew / Remarks | 1. Core Crew | J8:J207 | text | Manual; unused rows cleared |
| contractors[].sequence | contractors | 2. Contractor | B8:B207 | integer | Sequential row number; unused rows cleared |
| contractors[].name | contractors / Name | 2. Contractor | C8:C207 | text | Manual; unused rows cleared |
| contractors[].vendor | contractors / Vendor | 2. Contractor | D8:D207 | text | Manual; unused rows cleared |
| contractors[].age | contractors / Age | 2. Contractor | E8:E207 | age | Manual; unused rows cleared |
| contractors[].nationality | contractors / Country of Nationality | 2. Contractor | F8:F207 | text | Manual; unused rows cleared |
| contractors[].passport | contractors / IC / Passport No. | 2. Contractor | G8:G207 | text | Manual; unused rows cleared |
| contractors[].remarks | contractors / Remarks | 2. Contractor | H8:H207 | text | Manual; unused rows cleared |
| waypoints[].sequence | waypoints | 3. Waypoint Plan | B8:B37 | integer | Sequential row number; unused rows cleared |
| waypoints[].lat_degree | waypoints / Latitude Degree | 3. Waypoint Plan | C8:C37 | lat_degree | Manual; unused rows cleared |
| waypoints[].lat_minute | waypoints / Latitude Minute | 3. Waypoint Plan | E8:E37 | minute | Manual; unused rows cleared |
| waypoints[].lat_second | waypoints / Latitude Second | 3. Waypoint Plan | G8:G37 | second | Manual; unused rows cleared |
| waypoints[].lat_direction | waypoints / N/S | 3. Waypoint Plan | I8:I37 | ns | Manual; unused rows cleared |
| waypoints[].lon_degree | waypoints / Longitude Degree | 3. Waypoint Plan | J8:J37 | lon_degree | Manual; unused rows cleared |
| waypoints[].lon_minute | waypoints / Longitude Minute | 3. Waypoint Plan | L8:L37 | minute | Manual; unused rows cleared |
| waypoints[].lon_second | waypoints / Longitude Second | 3. Waypoint Plan | N8:N37 | second | Manual; unused rows cleared |
| waypoints[].lon_direction | waypoints / E/W | 3. Waypoint Plan | P8:P37 | ew | Manual; unused rows cleared |
| waypoints[].course | waypoints / Course (°) | 3. Waypoint Plan | Q8:Q37 | course | Manual; unused rows cleared |
| waypoints[].speed | waypoints / Planned Speed (knots) | 3. Waypoint Plan | R8:R37 | number | Manual; unused rows cleared |
| waypoints[].remarks | waypoints / Remarks | 3. Waypoint Plan | S8:S37 | text | Manual; unused rows cleared |
| progress[].date | progress / Date | 6. Voyage Progress | B8:B107 | date | Manual; unused rows cleared |
| progress[].hour | progress / Hour | 6. Voyage Progress | C8:C107 | hour | Manual; unused rows cleared |
| progress[].minute | progress / Minute | 6. Voyage Progress | D8:D107 | minute | Manual; unused rows cleared |
| progress[].lat_degree | progress / Latitude Degree | 6. Voyage Progress | E8:E107 | lat_degree | Manual; unused rows cleared |
| progress[].lat_minute | progress / Latitude Minute | 6. Voyage Progress | G8:G107 | minute | Manual; unused rows cleared |
| progress[].lat_second | progress / Latitude Second | 6. Voyage Progress | I8:I107 | second | Manual; unused rows cleared |
| progress[].lat_direction | progress / N/S | 6. Voyage Progress | K8:K107 | ns | Manual; unused rows cleared |
| progress[].lon_degree | progress / Longitude Degree | 6. Voyage Progress | L8:L107 | lon_degree | Manual; unused rows cleared |
| progress[].lon_minute | progress / Longitude Minute | 6. Voyage Progress | N8:N107 | minute | Manual; unused rows cleared |
| progress[].lon_second | progress / Longitude Second | 6. Voyage Progress | P8:P107 | second | Manual; unused rows cleared |
| progress[].lon_direction | progress / E/W | 6. Voyage Progress | R8:R107 | ew | Manual; unused rows cleared |
| progress[].course | progress / Course (°) | 6. Voyage Progress | S8:S107 | course | Manual; unused rows cleared |
| progress[].speed | progress / Actual Speed (knots) | 6. Voyage Progress | T8:T107 | number | Manual; unused rows cleared |
| progress[].sky | progress / Sky | 6. Voyage Progress | U8:U107 | text | Manual; unused rows cleared |
| progress[].visibility | progress / Visibility (nm) | 6. Voyage Progress | V8:V107 | number | Manual; unused rows cleared |
| progress[].wind_speed | progress / Wind Speed (knots) | 6. Voyage Progress | W8:W107 | number | Manual; unused rows cleared |
| progress[].wind_direction | progress / Wind Direction | 6. Voyage Progress | X8:X107 | compass | Manual; unused rows cleared |
| progress[].wave_height | progress / Wave / Swell Height (m) | 6. Voyage Progress | Y8:Y107 | number | Manual; unused rows cleared |
| progress[].wave_direction | progress / Wave / Swell Direction | 6. Voyage Progress | Z8:Z107 | compass | Manual; unused rows cleared |
| progress[].remarks | progress / Remarks | 6. Voyage Progress | AA8:AA107 | text | Manual; unused rows cleared |
| departure.captain | departure / Captain Name | 4. Departure Report | D9 | text | Manual |
| departure.report_date | departure / Report Date | 4. Departure Report | D10 | date | Manual |
| departure.prepared_by | departure / Report Prepared By | 4. Departure Report | D11 | text | Manual |
| departure.prepared_tel | departure / Prepared By Tel No. | 4. Departure Report | I11 | text | Manual |
| departure.checked_by | departure / Checked By | 4. Departure Report | D12 | text | Manual |
| departure.checked_tel | departure / Checked By Tel No. | 4. Departure Report | I12 | text | Manual |
| departure.draft_forward | departure / Draft Forward | 4. Departure Report | E13 | number | Manual |
| departure.draft_midship | departure / Draft Midship | 4. Departure Report | G13 | number | Manual |
| departure.draft_aft | departure / Draft AFT | 4. Departure Report | I13 | number | Manual |
| departure.fuel_requirement | departure / Requirements: Fuel Oil | 4. Departure Report | E14 | number | Manual |
| departure.fw_requirement | departure / Requirements: FW | 4. Departure Report | G14 | number | Manual |
| departure.dw_requirement | departure / Requirements: DW | 4. Departure Report | I14 | number | Manual |
| departure.departure_date | departure / Departure Date | 4. Departure Report | D18 | date | Manual |
| departure.departure_time | departure / Departure Time (24-hour) | 4. Departure Report | D19/F19 | time | Manual |
| departure.departure_location | departure / Departure Location | 4. Departure Report | D20 | text | Manual |
| departure.departure_remarks | departure / Departure Remarks | 4. Departure Report | D21 | text | Manual |
| departure.arrival_date | departure / Arrival Date | 4. Departure Report | D24 | date | Manual |
| departure.arrival_time | departure / Arrival Time (24-hour) | 4. Departure Report | D25/F25 | time | Manual |
| departure.destination | departure / Arrival Destination | 4. Departure Report | D26 | text | Manual |
| departure.arrival_remarks | departure / Arrival Remarks | 4. Departure Report | D27 | text | Manual |
| meta.vessel | departure / Vessel information | 4. Departure Report | D6 | text / number | Linked from General; materialized |
| meta.imo | departure / Vessel information | 4. Departure Report | D7 | text / number | Linked from General; materialized |
| meta.capacity | departure / Vessel information | 4. Departure Report | D8 | text / number | Linked from General; materialized |
| crew / contractors count | departure | 4. Departure Report | D15/E15, F15/G15 | integer / text | Derived from current lists; materialized |
| departure.deck[].sequence | departure Deck space | 4. Departure Report | B32:B36 | integer | Five destination rows |
| departure.deck[].location | departure / Destination Location | 4. Departure Report | C32:C36 | text | Manual; independent departure values |
| departure.deck[].lifts | departure / Lifts Expected | 4. Departure Report | D32:D36 | count | Manual; independent departure values |
| departure.deck[].ops | departure / OPS (m²) | 4. Departure Report | E32:E36 | number | Manual; independent departure values |
| departure.deck[].fso | departure / FSO (m²) | 4. Departure Report | F32:F36 | number | Manual; independent departure values |
| departure.deck[].drilling | departure / Drilling / Projects (m²) | 4. Departure Report | G32:G36 | number | Manual; independent departure values |
| departure.deck[].total | departure / Total (m²) | 4. Departure Report | H32:H36 | derived | OPS + FSO + Drilling/Projects; materialized |
| departure.deck[].utilization | departure / Utilization (%) | 4. Departure Report | I32:I36 | derived | Total / capacity; stored as fraction with original percentage format; blank for zero/missing capacity |
| departure.deck[].weight | departure / Cargo Weight (Tonnes) | 4. Departure Report | J32:J36 | number | Manual; independent departure values |
| departure.deck[].remarks | departure / Remarks | 4. Departure Report | K32:K36 | text | Manual; independent departure values |
| departure.deck totals | departure | 4. Departure Report | D37, H37, I37, J37 | number | Sum lifts, used space, utilization and cargo; materialized |
| departure.inventory[normalized product=FUEL] | departure Inventory | 4. Departure Report | D41 / I41 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=FRESH WATER] | departure Inventory | 4. Departure Report | D42 / I42 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=LUB. OIL] | departure Inventory | 4. Departure Report | D43 / I43 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=GEAR OIL] | departure Inventory | 4. Departure Report | D44 / I44 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=DISPERSANT] | departure Inventory | 4. Departure Report | D45 / I45 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=DRILL WATER] | departure Inventory | 4. Departure Report | D46 / I46 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=CEMENT (Slag)] | departure Inventory | 4. Departure Report | D47 / I47 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=CEMENT] | departure Inventory | 4. Departure Report | D48 / I48 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=BARITE] | departure Inventory | 4. Departure Report | D49 / I49 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=SARAPAR] | departure Inventory | 4. Departure Report | D50 / I50 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=BENTONITE] | departure Inventory | 4. Departure Report | D51 / I51 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=New OBM] | departure Inventory | 4. Departure Report | D52 / I52 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=Used OBM] | departure Inventory | 4. Departure Report | D53 / I53 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=VERSAPRO 9.3PPG] | departure Inventory | 4. Departure Report | D54 / I54 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=OBM 7,5 PPG] | departure Inventory | 4. Departure Report | D55 / I55 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=OBM 7,8 PPG] | departure Inventory | 4. Departure Report | D56 / I56 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| departure.inventory[normalized product=SBM] | departure Inventory | 4. Departure Report | D57 / I57 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| current client / reader version | departure | 4. Departure Report | D2, N3 | text | Materialized titles to eliminate stale formula caches |
| report / departure / arrival date annotations | departure | 4. Departure Report | J10, J18, J24 | text | Materialized relative to local export date; blanks stay blank |
| arrival.captain | arrival / Captain Name | 5. Arrival Report | D9 | text | Linked from Departure; read-only; materialized |
| arrival.report_date | arrival / Report Date | 5. Arrival Report | D10 | date | Manual |
| arrival.prepared_by | arrival / Report Prepared By | 5. Arrival Report | D11 | text | Linked from Departure; read-only; materialized |
| arrival.prepared_tel | arrival / Prepared By Tel No. | 5. Arrival Report | I11 | text | Linked from Departure; read-only; materialized |
| arrival.checked_by | arrival / Checked By | 5. Arrival Report | D12 | text | Linked from Departure; read-only; materialized |
| arrival.checked_tel | arrival / Checked By Tel No. | 5. Arrival Report | I12 | text | Linked from Departure; read-only; materialized |
| arrival.draft_forward | arrival / Draft Forward | 5. Arrival Report | E13 | number | Linked from Departure; read-only; materialized |
| arrival.draft_midship | arrival / Draft Midship | 5. Arrival Report | G13 | number | Linked from Departure; read-only; materialized |
| arrival.draft_aft | arrival / Draft AFT | 5. Arrival Report | I13 | number | Linked from Departure; read-only; materialized |
| arrival.fuel_requirement | arrival / Requirements: Fuel Oil | 5. Arrival Report | E14 | number | Linked from Departure; read-only; materialized |
| arrival.fw_requirement | arrival / Requirements: FW | 5. Arrival Report | G14 | number | Linked from Departure; read-only; materialized |
| arrival.dw_requirement | arrival / Requirements: DW | 5. Arrival Report | I14 | number | Linked from Departure; read-only; materialized |
| arrival.departure_date | arrival / Departure Date | 5. Arrival Report | D18 | date | Linked from Departure; read-only; materialized |
| arrival.departure_time | arrival / Departure Time (24-hour) | 5. Arrival Report | D19/F19 | time | Linked from Departure; read-only; materialized |
| arrival.departure_location | arrival / Departure Location | 5. Arrival Report | D20 | text | Linked from Departure; read-only; materialized |
| arrival.departure_remarks | arrival / Departure Remarks | 5. Arrival Report | D21 | text | Linked from Departure; read-only; materialized |
| arrival.arrival_date | arrival / Arrival Date | 5. Arrival Report | D24 | date | Manual |
| arrival.arrival_time | arrival / Arrival Time (24-hour) | 5. Arrival Report | D25/F25 | time | Manual |
| arrival.destination | arrival / Arrival Destination | 5. Arrival Report | D26 | text | Linked from Departure; read-only; materialized |
| arrival.arrival_remarks | arrival / Arrival Remarks | 5. Arrival Report | D27 | text | Manual |
| meta.vessel | arrival / Vessel information | 5. Arrival Report | D6 | text / number | Linked from General; materialized |
| meta.imo | arrival / Vessel information | 5. Arrival Report | D7 | text / number | Linked from General; materialized |
| meta.capacity | arrival / Vessel information | 5. Arrival Report | D8 | text / number | Linked from General; materialized |
| crew / contractors count | arrival | 5. Arrival Report | D15/E15, F15/G15 | integer / text | Derived from current lists; materialized |
| arrival.deck[].sequence | arrival Deck space | 5. Arrival Report | B32:B36 | integer | Five destination rows |
| arrival.deck[].location | arrival / Destination Location | 5. Arrival Report | C32:C36 | text | Manual; independent arrival values |
| arrival.deck[].lifts | arrival / Lifts Expected | 5. Arrival Report | D32:D36 | count | Manual; independent arrival values |
| arrival.deck[].ops | arrival / OPS (m²) | 5. Arrival Report | E32:E36 | number | Manual; independent arrival values |
| arrival.deck[].fso | arrival / FSO (m²) | 5. Arrival Report | F32:F36 | number | Manual; independent arrival values |
| arrival.deck[].drilling | arrival / Drilling / Projects (m²) | 5. Arrival Report | G32:G36 | number | Manual; independent arrival values |
| arrival.deck[].total | arrival / Total (m²) | 5. Arrival Report | H32:H36 | derived | OPS + FSO + Drilling/Projects; materialized |
| arrival.deck[].utilization | arrival / Utilization (%) | 5. Arrival Report | I32:I36 | derived | Total / capacity; stored as fraction with original percentage format; blank for zero/missing capacity |
| arrival.deck[].weight | arrival / Cargo Weight (Tonnes) | 5. Arrival Report | J32:J36 | number | Manual; independent arrival values |
| arrival.deck[].remarks | arrival / Remarks | 5. Arrival Report | K32:K36 | text | Manual; independent arrival values |
| arrival.deck totals | arrival | 5. Arrival Report | D37, H37, I37, J37 | number | Sum lifts, used space, utilization and cargo; materialized |
| arrival.inventory[normalized product=FUEL] | arrival Inventory | 5. Arrival Report | D41 / I41 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=FRESH WATER] | arrival Inventory | 5. Arrival Report | D42 / I42 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=LUB. OIL] | arrival Inventory | 5. Arrival Report | D43 / I43 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=GEAR OIL] | arrival Inventory | 5. Arrival Report | D44 / I44 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=DISPERSANT] | arrival Inventory | 5. Arrival Report | D45 / I45 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=DRILL WATER] | arrival Inventory | 5. Arrival Report | D46 / I46 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=CEMENT (Slag)] | arrival Inventory | 5. Arrival Report | D47 / I47 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=CEMENT] | arrival Inventory | 5. Arrival Report | D48 / I48 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=BARITE] | arrival Inventory | 5. Arrival Report | D49 / I49 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=SARAPAR] | arrival Inventory | 5. Arrival Report | D50 / I50 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=BENTONITE] | arrival Inventory | 5. Arrival Report | D51 / I51 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=New OBM] | arrival Inventory | 5. Arrival Report | D52 / I52 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=Used OBM] | arrival Inventory | 5. Arrival Report | D53 / I53 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=VERSAPRO 9.3PPG] | arrival Inventory | 5. Arrival Report | D54 / I54 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=OBM 7,5 PPG] | arrival Inventory | 5. Arrival Report | D55 / I55 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=OBM 7,8 PPG] | arrival Inventory | 5. Arrival Report | D56 / I56 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| arrival.inventory[normalized product=SBM] | arrival Inventory | 5. Arrival Report | D57 / I57 | number / text | Quantity / remarks; normalized-name lookup; product B and unit H untouched |
| current client / reader version | arrival | 5. Arrival Report | D2, N3 | text | Materialized titles to eliminate stale formula caches |
| report / departure / arrival date annotations | arrival | 5. Arrival Report | J10, J18, J24 | text | Materialized relative to local export date; blanks stay blank |

## Capacities and preservation

- Crew 200 (8–207); contractors 200 (8–207); waypoints 30 (8–37); voyage progress 100 (8–107). Verified against numbering and validation ranges. Formatting extends below several tables and is not capacity.
- Five departure and five arrival deck rows (32–36), total row 37. Inventory rows 41–57.
- Capacity overflow and invalid data block export without touching the destination. Invalid drafts can autosave.
- Fresh pristine template archive on every export; only explicitly mapped cell values change. Every other ZIP part and unmapped worksheet cell remains byte-identical, including styles, merged cells, dimensions, validations, sheet states, print setup, drawings and the entire Departure Report Guide.
- Critical calculations and arrival reuse are snapshot values, not live Excel formulas. Unrelated template/reference/helper formulas are preserved. Subsequent Excel edits do not refresh materialized cells; edit in GDS VTS and export again for a consistent report.
- Back Deck Photo headings remain at row 9. QR mobile uploads now populate the original L10:U27 photo regions independently in Departure and Arrival. Without an upload, the original drawing stays unchanged. See [mobile photo upload](vjr-mobile-photo-upload.md).
- Autosave uses an atomic JSON replacement at AppLocalDataLocation/vjr/report.json; bounded 100-step snapshot undo/redo follows the VDR pattern and autosaves history actions. Unreadable or unsupported stores are preserved, with an actionable error.
- Existing VJR was a label only and had no stored schema to migrate. Partial version-1 data gets defaults without truncating records; unsupported future schemas are rejected.
- Decimal-to-DMS is a tested VJR helper. Telemetry integration is deferred; all journey data remains manually editable. NAV coordinates and sensor parsing are unchanged.
- VJR supports one persistent working journey. No journey archive or new-journey workflow was requested.
- Configure name/client settings are reused when present; IMO and deck capacity remain VJR fields because the current application exposes no authoritative settings for them.

Reproduce workbook and map: `.venv/Scripts/python.exe tools/verify_vjr_acceptance.py`.
