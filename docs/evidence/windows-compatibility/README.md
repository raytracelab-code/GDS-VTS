# Windows compatibility stabilization evidence

Test host: Windows 11 Home Single Language, x64, **10.0.26200**, 19 November 2026. No Windows 7/8/8.1/10 machine or VM was available. No commit was created by this work.

Final executable: `dist/GDS VTS/GDS VTS.exe` (distribute the entire folder).

SHA-256: `AFD6556E65C68F5A4AA00539FB2D25DFCCB599B9D260C628933ED34348411546`

| Check | Result | Notes |
|---|---|---|
| Existing implementation | Preserved | Continued the shared facade, Qt5 path, optional capabilities and existing packaging |
| Original accepted baseline | 636 passed | Previously verified before compatibility tests were added |
| Legacy Python | PASS | CPython 3.8.10 AMD64; exact runtime/build lock verified |
| PyQt5 / PyQtWebEngine | Not installed | Actual binding is PySide2, not PyQt |
| PySide2 / shiboken2 | 5.15.2.1 / 5.15.2.1 | Qt runtime 5.15.2, Qt5WebEngineCore.dll 5.15.2.0 |
| Mixed Qt5/Qt6 | None found | Legacy environment, dump module inventory and packaged PE audit checked |
| Minimal WebEngine | 30 clean cycles | Ten default, ten software OpenGL, ten GPU-disabled; `webengine-stress.json` |
| Full default pre-fix crash | Reproduced | Native access violations were recorded and investigated |
| Reported 0x80000003 breakpoint | Absent in final runs | No native error was suppressed; restricted Chromium IPC failure was also isolated during diagnosis |
| Software/GPU-disabled pre-fix | Did not fix full app | Their JSON files are diagnostic failures, not final release results |
| Failure boundary | Qt5 WebChannel dictionary conversion | Ten channel-disconnected control cycles passed; no such switch is used by the release |
| Native symbols | Resolved | Official matching Python PDB: dictionary traversal and object/function deallocation |
| Legacy bridge fix | PASS | QString JSON wire adapter preserves the existing browser bridge API |
| Ownership/shutdown | PASS | Retained channel/bridge, GUI-owned cyclic collection, page before profile before QApplication, workers/request threads stopped |
| Final source cycles | 10/10 exit 0 | `source-default-network-failure-cycles.json`; GIS/browser active, unreachable external data endpoints |
| Normal-network source | 3/3 exit 0 | `source-default-cycles.json` |
| Final packaged cycles | 10/10 exit 0 | `packaged-default-network-failure-cycles.json`, Python removed from PATH, external working directory |
| Packaged WebEngine cleanup | PASS | `packaged-process-cleanup.json`: zero remaining processes |
| Native packaged workflow | PASS | `interactive-close.json`: exit 0 after Configure/VDR/NAV, import/edit/autosave/undo/redo/finalize/exports/settings/USB scan |
| Normal pytest | 653 passed in 209.02s | `normal-pytest.txt` |
| Legacy pytest | 652 passed, 1 skipped in 343.50s | `legacy-pytest.txt`; approved absent SDK contract test only |
| Compileall | PASS / PASS | Both environments, app/main and Windows tooling |
| Dependencies / prerequisites | PASS on current host | Exact lock and `pip check`; prerequisite checker remains read-only |
| PyInstaller | PASS | 4.10; controlled x64 Python 3.8 build; no UPX; asInvoker |
| Distribution audit | PASS for detectable issues | `pe-audit.json`: no unresolved local/system import candidates, no checked newer API imports; actual old-OS execution still required |
| Native Excel/PDF | PASS | `packaged-exports.json`; actual UI-generated `.xlsx` and `.pdf` included |
| Excel preservation | PASS | Six sheets, VDR GUIDE identical, template hash intact, 33 non-worksheet parts unchanged, no `#REF!` |
| PDF round trip | PASS | Six pages, edited captain, finalized, zero validation errors on reimport |
| NAV/settings | PASS on host | Online basemap rendered, WebChannel controls work, settings opened/cancelled |
| USB/FTDI | Enumeration + simulated coverage | Native scan reported no devices; actual hardware pending |
| Camera / VDR Data | Absent in supplied source | No backend/screen was removed or newly fabricated |
| BLE legacy | Approved capability limit | Unavailable before supported Windows 10 backend; USB retained |
| Copernicus legacy | Approved capability limit | Optional SDK absent only in Python 3.8 build; current modern SDK retained |
| Windows 7/8/8.1/10 | Runtime pending | Build candidate only; not certified on those OSes |
| Windows 11 | Recorded workflows pass | Build 26200; hardware/DPI coverage limits documented |
| Signing | Unsigned | Ready for authorized Authenticode signing; no certificate fabricated |
| User data | Isolated validation profile | Test report stayed in Qt test AppData; production reports were not imported/overwritten |

The files `source-cycles.json`, `source-default-failures.json`, `source-software-cycles.json`, `source-gpu-disabled-cycles.json` and `packaged-default-cycles.json` preserve **earlier diagnostic failures**. They must not be mistaken for the final bridge-fixed cycle results linked above. `source-default-without-filter-cycles.json` and `source-default-without-channel-network-failure-cycles.json` are isolation controls. Native dump contents remain outside the repository; no raw memory dump is shipped.

Run the documented build pipeline and repeat actual target-OS/device testing before broad distribution. A successful PE audit or Windows 11 test does not establish Windows 7 compatibility.
