# GDS VTS release checklist

Copy this list into the release notes and tick every line. Record the exact outputs.

## Source state
- [ ] `git status` is clean, or every intentional change is listed in the release notes.
- [ ] Version bumped in `app/version.py` (`__version__`, `STAGE`), with the release notes updated.
- [ ] `docs/GDS-VTS-NON-HARDWARE-FIX-REPORT.md`: the open items are reviewed.

## Tests and compile
- [ ] Modern tests: `.\.venv\Scripts\python.exe -m pytest -q --tb=short` → all passed (record the count).
- [ ] Legacy tests: `.\.venv-win7\Scripts\python.exe -m pytest -q --tb=short` → all passed (record the count).
- [ ] Modern compile: `.\.venv\Scripts\python.exe -m compileall -q app main.py`
- [ ] Legacy compile: `.\.venv-win7\Scripts\python.exe -m compileall -q app main.py`

## Packages
- [ ] Modern package: `.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --workpath build\modern-pyinstaller --distpath dist\modern gds_vts.spec`
- [ ] Legacy package: `scripts\build_windows_compat.ps1`, which writes `dist\legacy-win7\GDS VTS\` and `SHA256SUMS.json`.
- [ ] The old `dist\` output was removed before building, and the two editions are in separate folders.
- [ ] Smoke launch of each `GDS VTS.exe --validation-profile --validation-close-after=20`: the log shows STARTUP 1–10 and exit code 0.
- [ ] Version check: `(Get-Item "dist\<edition>\GDS VTS\GDS VTS.exe").VersionInfo` shows the expected FileVersion and an edition-specific ProductVersion.
- [ ] Build info check: `BUILD_INFO.txt` and Configure → About & build info show the version, edition and commit, with no `+uncommitted` for a release.
- [ ] Checksums: SHA-256 of each exe and `SHA256SUMS.json` recorded.

## Functional smoke tests
- [ ] Dialogs: run `docs/evidence/dialog-visibility/capture_dialogs.py 1366x768 1.0` and `app_sweep.py` → 0 problems.
- [ ] VDR export: finalize a test report → Download PDF and Download Excel open correctly.
- [ ] VJR export: a complete journey → Download Excel opens correctly, with photos present.
- [ ] NAV: the map loads; Retry map recovers; Map regions… opens; telemetry shows LIVE / STALE / NO DATA correctly.
- [ ] Support bundle: Export support bundle → the ZIP opens and contains no report data, photos or credentials (spot-check `logs/`).
- [ ] Backup and restore: Create backup → Restore backup on a test profile; the data comes back; `backups/before-restore-*.zip` exists.
- [ ] First run: on a clean profile the setup appears once; after Finish or Skip it never appears again.

## Validation status (state it in the release notes)
- [ ] Hardware: Patroller-I over FTDI USB, USB CDC and BLE, each with date, device, firmware and result. **Pending until performed on real hardware.**
- [ ] Real phone photo upload, with date, phone model and result. **Pending until performed.**
- [ ] Cross-OS runtime: Windows 7 SP1, 8.1, 10 and 11, each with date, machine, edition installed and result. **Pending until performed on real machines.**
- [ ] Installer and code signing: not yet available (audit 047). The app ships as a portable folder.
