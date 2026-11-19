# Final changed-file inventory

No commit was created. Existing snapshot: `7aa95eed6b371f4c28e47e4d237b8beefba878bb`.

Every final modified/created repository file, including untracked evidence:

- ` M` `app/nav/legacy_resources.py`
- ` M` `app/nav/maritime/adapters/overpass.py`
- ` M` `app/nav/maritime/runtime.py`
- ` M` `app/qt/__init__.py`
- ` M` `app/ui/main_window.py`
- ` M` `app/ui/pages/nav/floating_controls.py`
- ` M` `app/ui/pages/nav/nav_page.py`
- ` M` `app/ui/pages/vdr/date_picker.py`
- ` M` `app/ui/pages/vdr/workspace.py`
- ` M` `docs/evidence/windows-compatibility/pe-audit.json`
- ` M` `docs/windows-compatibility.md`
- ` M` `gds_vts.spec`
- ` M` `gds_vts_win7.spec`
- ` M` `main.py`
- ` M` `packaging/startup_log.py`
- ` M` `scripts/Check-WindowsPrerequisites.ps1`
- ` M` `scripts/build_windows_compat.ps1`
- ` M` `tests/offline_webengine_probe.py`
- ` M` `tests/test_windows_compatibility.py`
- ` M` `tools/windows/audit_distribution.py`
- `??` `app/nav/legacy_bridge.py`
- `??` `app/qt/garbage_collection.py`
- `??` `docs/evidence/windows-compatibility/README.md`
- `??` `docs/evidence/windows-compatibility/build-summary.json`
- `??` `docs/evidence/windows-compatibility/changed-files.md`
- `??` `docs/evidence/windows-compatibility/git-diff-stat.txt`
- `??` `docs/evidence/windows-compatibility/git-status.txt`
- `??` `docs/evidence/windows-compatibility/interactive-close.json`
- `??` `docs/evidence/windows-compatibility/legacy-pytest.txt`
- `??` `docs/evidence/windows-compatibility/loaded-runtime-modules.json`
- `??` `docs/evidence/windows-compatibility/native-crash-symbols.json`
- `??` `docs/evidence/windows-compatibility/normal-pytest.txt`
- `??` `docs/evidence/windows-compatibility/packaged-default-cycles.json`
- `??` `docs/evidence/windows-compatibility/packaged-default-network-failure-cycles.json`
- `??` `docs/evidence/windows-compatibility/packaged-exports.json`
- `??` `docs/evidence/windows-compatibility/packaged-process-cleanup.json`
- `??` `docs/evidence/windows-compatibility/packaged-vdr.pdf`
- `??` `docs/evidence/windows-compatibility/packaged-vdr.xlsx`
- `??` `docs/evidence/windows-compatibility/source-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-default-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-default-failures.json`
- `??` `docs/evidence/windows-compatibility/source-default-network-failure-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-default-without-channel-network-failure-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-default-without-filter-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-gpu-disabled-cycles.json`
- `??` `docs/evidence/windows-compatibility/source-software-cycles.json`
- `??` `docs/evidence/windows-compatibility/webengine-stress.json`
- `??` `tools/windows/check_environment.py`
- `??` `tools/windows/gis_lifetime_probe.py`
- `??` `tools/windows/inspect_minidump.py`
- `??` `tools/windows/isolate_application.py`
- `??` `tools/windows/qt_gis_probe.py`
- `??` `tools/windows/stress_application.py`
- `??` `tools/windows/stress_webengine.py`
- `??` `tools/windows/verify_packaged_exports.py`
- `??` `tools/windows/webengine_probe.py`

## git diff --stat

```text
 app/nav/legacy_resources.py                       |   16 +-
 app/nav/maritime/adapters/overpass.py             |    7 +
 app/nav/maritime/runtime.py                       |    4 +-
 app/qt/__init__.py                                |   20 +-
 app/ui/main_window.py                             |    1 +
 app/ui/pages/nav/floating_controls.py             |   21 +-
 app/ui/pages/nav/nav_page.py                      |   48 +-
 app/ui/pages/vdr/date_picker.py                   |    4 +-
 app/ui/pages/vdr/workspace.py                     |    3 +-
 docs/evidence/windows-compatibility/pe-audit.json | 5003 +++++++++++----------
 docs/windows-compatibility.md                     |   28 +-
 gds_vts.spec                                      |    6 +-
 gds_vts_win7.spec                                 |    6 +-
 main.py                                           |   31 +-
 packaging/startup_log.py                          |    3 +-
 scripts/Check-WindowsPrerequisites.ps1            |    8 +-
 scripts/build_windows_compat.ps1                  |    2 +
 tests/offline_webengine_probe.py                  |   32 +-
 tests/test_windows_compatibility.py               |   62 +
 tools/windows/audit_distribution.py               |   11 +-
 20 files changed, 2770 insertions(+), 2546 deletions(-)
```

Full status is in `git-status.txt`. Git diff statistics exclude new untracked files; the list above includes them. Ignored toolchains, build logs and debug symbols remain under `build/`. The complete ignored release folder is enumerated in `dist/GDS VTS/SHA256SUMS.json`; distribute that entire folder.
