# Product polish: reliability, diagnostics and UI evidence

`capture_app.py` drives the **real MainWindow** at 1366×768 with isolated data:
- Qt test-mode folders;
- vessel identity and first-run state in a temporary INI file, so the registry is only read;
- a software telemetry fixture fed through the normal ingest path (no hardware).

It writes screenshots plus `runtime_output.txt` into these folders:

| Folder | Effective scaling |
|---|---|
| `1366x768@100%-PySide6`, `1366x768@100%-PySide2` | The build PC's Windows 125 % display scaling (images are 1.25× size) |
| `1366x768@125%-PySide6`, `1366x768@125%-PySide2` | `QT_SCALE_FACTOR=1.25` on top of that, ≈156 % in total |

| # | Screenshot | Shows |
|---|---|---|
| 00 | `00_first_run_step1/2` | First-run setup: Vessel & client form (reuses the Configure card), then the connectivity step |
| 01 | `01_configure_top` | Configure, unchanged structure; the header status uses the shared badge |
| 02 | `02_configure_connection_link_state` | USB card. Hierarchy: device/port → status badge → action buttons → link detail (LIVE, packets, valid/invalid frames, last packet, reconnects) |
| 03 | `03_configure_telemetry_plausibility` | Live Telemetry: 55 kn speed is flagged "▲" with a tooltip; the value itself is unchanged |
| 04 | `04_configure_support_card` | New Support & maintenance card in the existing card style |
| 05 | `05_about_build_info` | About & build info (copyable) |
| 06 | `06_raw_data_monitor` | Raw data monitor: bounded and pausable, with the invalid fixture line visible |
| 07 | `07_restore_confirmation` | The restore preview lists what will be restored; Cancel is the default |
| 08 | `08_vdr_plausibility_and_markers` | VDR: 30 h daily run hours in an amber field; side navigation markers ✓ / ▲ / ⚠ n; autosave badge |
| 09 | `09_vjr_progress_plausibility` | VJR: 60 kn actual speed shown in an amber cell with an outline |
| 10 | `10_vjr_required_markers` | VJR: `*` on required fields; section markers |
| 11 | `11_nav_readout_and_squall` | NAV: the map is unchanged. The readout adds "CHECK VALUES ▲ Speed 55 kn…". Squall shows PROVIDER UNAVAILABLE, not "No current warnings". |

`backup-sample.zip` (test fixture data only) is included. The sample support bundle was **not** kept, because it is built from this PC's real (redacted) settings and logs. Its member list is in `runtime_output.txt`; see `docs/support-bundle.md` for the contents.
