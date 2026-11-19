# Backup and restore

**Where:** Configure → Support & maintenance → **Create backup…** / **Restore backup…**

These buttons sit on top of the automatic protection that already exists. That protection is unchanged:
- atomic saves;
- one `.bak` last-known-good copy per store;
- preservation of damaged files.

## Create backup

The backup is a single portable ZIP named `GDS-VTS-backup-YYYYMMDD-HHMM.zip`. Pending VDR and VJR edits are saved first. If they cannot be saved, you are asked before backing up only the data that is already saved.

| Included | Path in ZIP |
|---|---|
| VDR reports | `data/vdr/reports.json` |
| Current VJR journey | `data/vjr/report.json` |
| Archived voyages | `data/vjr/archive/*.json` |
| VJR photos (attachments) | `data/vjr/attachments/**` |
| Vessel & client identity and app preferences | `settings.json` (`vessel/*`, `nav/*`, `app/*` settings) |
| Manifest | `manifest.json`: format, app version, edition, created time, and a SHA-256 for every file |

**Not included:** executables, logs, map tiles and caches, browser/WebEngine data, `.bak`/`.damaged` copies, and temporary files.

## Restore backup

1. **Validate before anything changes.** The backup is rejected with a plain message if:
   - it is not a ZIP;
   - the manifest is missing or from an unsupported format;
   - a checksum does not match;
   - it contains unexpected or unsafe paths (e.g. `../`);
   - report data cannot be read.
2. **Show what will be restored:** backup date, app version and edition, the number of VDR reports and their date range, whether a current journey is included, the archived voyages and photos, and the number of settings.
3. **Confirm.** The button is **Restore backup**, and Cancel is the default.
4. **Safety copy.** The current data is saved as `backups/before-restore-<time>.zip` in the app data folder.
5. **Replace all-or-nothing.**
   - All folders are first copied next to the live data. If that fails, nothing has changed.
   - Then the folders are swapped by rename. If any swap fails, every swap is rolled back.
   - The replaced folders are kept as `.vdr-replaced-<time>` and `.vjr-replaced-<time>`, never deleted.
6. **Restart.** Editing is paused, because the open pages still hold the old data and must not save over the restored files. **Restart now** restarts GDS VTS.

**If restore fails:** the existing data is untouched and a clear error is shown. The archive that failed is copied to `backups/failed-restore-<time>-<name>.zip` for diagnostics.

**Tests:** `tests/test_product_polish.py` covers backup contents, a successful restore with a safety copy, five kinds of invalid backup, rollback of a restore that fails midway, and locking after restore.
