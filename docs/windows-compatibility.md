# Windows compatibility build

Target: **Windows 7 SP1 / 8 / 8.1 / 10 / 11 — 64-bit**. This is a controlled legacy build target, not a claim that all five operating systems have passed runtime testing. Actual OS results and release hashes are recorded in `docs/evidence/windows-compatibility/`.

The shared application uses Python 3.8.10 AMD64 and PySide2 5.15.2.1 for this build. The existing `.venv` continues to use Python 3.13 and PySide6. Qt 6 cannot target Windows 7/8; importing `app.qt` selects the installed binding, with `GDS_QT_API` available for explicit development selection. Widgets, VDR business logic and export mappings are shared.

## Approved optional capabilities

| Capability | Legacy build on Windows 7 SP1 / 8 / 8.1 | Legacy build on Windows 10 / 11 | Current modern build |
|---|---|---|---|
| USB/serial/FTDI VCP | Retained; install the device vendor's OS-compatible driver | Retained | Retained |
| Native BLE | Unavailable; controls explain “Bluetooth LE is not supported on this Windows version.” | Retained with Bleak 0.22.3; requires Windows 10 build 16299 or later and compatible hardware | Retained with installed backend's own OS requirements |
| NAV/map and other supported data providers | Retained | Retained | Retained |
| Copernicus Marine SDK | Optional provider unavailable | Optional provider unavailable in the Python 3.8 compatibility build | Existing functionality retained when SDK installed/configured |

The Python 3.8 build deliberately does not install Copernicus Marine: published SDK releases require Python 3.9 or newer. Its provider health and actions report **“Copernicus Marine data is unavailable in the Windows 7/8 compatibility build.”** Missing SDK imports never prevent application or NAV startup. Provider credentials/configuration remain required in modern builds. This user-approved limitation is not a compatibility-task failure.

Camera recording has no implemented backend in the supplied repository. VJR is the existing telemetry-gated placeholder. No camera compatibility pass or recording feature is claimed.

## Recreate and build

Install the signed official **Python 3.8.10 Windows x86-64** distribution without replacing the normal Python installation. Run from the repository:

```powershell
powershell -File scripts/build_windows_compat.ps1 -Python38 C:\Path\Python3810\python.exe
```

The script creates `.venv-win7` if absent, installs `requirements-win7-test.txt`, checks Python 3.8.10/64-bit, dependency consistency, compilation and regression tests, then builds `gds_vts_win7.spec`. On an existing environment install the lock explicitly before building: `.\.venv-win7\Scripts\python.exe -m pip install -r requirements-win7-test.txt`. Test dependencies xarray/pandas are excluded from the release. The SDK-contract test is expected to skip only in this build; the other provider normalization tests still run.

The build host used here is Windows 11, not a Windows 7 machine. Python 3.8 and Qt 5 are legacy dependencies; updates require a deliberate compatibility review and renewed testing. `requirements-win7.txt` pins runtime/build dependencies and transitives; `pip==24.3.1`, `setuptools==69.5.1`, `wheel==0.45.1` bootstrap this environment.

Output: **`dist\GDS VTS\GDS VTS.exe`**. Distribute the **entire `GDS VTS` folder**, including Qt DLLs, QtWebEngineProcess, plugins, locales, fonts and resources. One-directory avoids one-file extraction, temporary-directory and WebEngine subprocess startup risks. UPX/obfuscation is disabled. `SHA256SUMS.json` records all distribution files. Keep the installation path short (for example `C:\GDS VTS`); do not rely on Windows long-path opt-in. External map package and export paths also need to fit the legacy Windows path limit.

## Windows prerequisites and launch

Run the bundled `Check-WindowsPrerequisites.ps1 -Launch` before first launch. It checks architecture, SP1/minimum OS, UCRT and VC runtime DLLs; on Windows 7 it probes `AddDllDirectory` and warns if SHA-2/servicing KBs are not individually listed. Superseding rollups can satisfy those updates. PowerShell/.NET must be installed and functional; do not bypass execution policy or security software. The script does not certify the OS and does not install or change system components.

Windows 7 SP1 needs a maintained patch baseline including SHA-2 signing support **KB4474419**, servicing update **KB4490628** (or superseding applicable updates), loader support **KB2533623 / KB3063858** or its replacement, and the **Universal C Runtime KB2999226 / applicable replacement**. Install an OS-compatible **Microsoft Visual C++ 2015–2019 x64 Redistributable 14.29** and restart when requested. Obtain prerequisites from Microsoft and device drivers from the manufacturer. The newest Visual C++ installer must not be assumed to support Windows 7. FTDI uses the existing pyserial/COM transport and needs an appropriate signed VCP driver; no Windows 10-only FTDI API was introduced.

Normal operation runs as the current user (`asInvoker`), without administrator rights. Prerequisite installation can require administrator rights. Loader failures happen before Python starts, hence the external prerequisite checker. No installer existed in the supplied project; this change provides a portable folder and preflight rather than adding an installer framework.

## Resource, browser and data behavior

Resources resolve relative to packaged modules, including the immutable Excel template `app/resources/templates/vdr_executive_brilliance_template.xlsx`. The icon is rendered from the existing logo into a multi-resolution ICO; branding is retained. Bundled VDR fonts and their license files are included. Optional Cascadia Mono/Segoe UI Semibold fonts have platform fallbacks.

Qt 5 lacks the custom-scheme Fetch capability available in Qt 6. The legacy NAV build serves the same local HTML, JavaScript, assets and tile readers through a random-token **127.0.0.1-only** ephemeral origin. Requests validate Host, Origin, token and resource containment. Remote HTTPS providers retain certificate verification. The current Qt 6 `gds://` path is unchanged. Qt 5 and Qt 6 use separate WebEngine cache directories to avoid incompatible profile databases.

Reports/settings remain in user-writable Qt application-data/settings locations; WebEngine caches and startup logs use `%LOCALAPPDATA%\GDS VTS`. Do not write user data into Program Files. `--validation-profile` uses Qt's isolated test data/settings paths for acceptance work. Logs rotate at 2 MiB and redact configured environment secrets, user profile paths and URL queries; do not include report contents in diagnostics. Pre-Python missing-DLL errors still require the prerequisite checker/Windows diagnostics.

TLS verification is not disabled. Python bundles its own OpenSSL; external HTTPS still needs valid system time, trusted certificates and supported remote TLS/ciphers. Qt 5 Chromium is old: rendering/network behavior must be verified on each target OS. No network security policy was weakened to obtain legacy support.

## Dependency rationale and limits

| Dependency | Legacy pin | Reason / audit scope |
|---|---|---|
| Python | 3.8.10 AMD64 | Last Python 3.8 Windows installer; isolated from current development |
| PySide2 / shiboken2 | 5.15.2.1 | Qt 5 legacy target, CPython 3.8 x64 wheel; shared facade handles API placement/events |
| PyInstaller / hooks | 4.10 / 2022.3 | Conservative Python 3.8 bootloader candidate; upstream lists Windows 8+ and calls Windows 7 unsupported, so actual Win7 testing is mandatory |
| pyserial | 3.5 | Existing standard COM/FTDI VCP transport retained |
| bleak / bleak-winrt | 0.22.3 / 1.2.0 | Windows 10-capable backend; never imported for unavailable old-OS capability |
| numpy | 1.21.6 | Conservative older CPython 3.8 Windows binary candidate; native DLL behavior requires real-OS validation |
| shapely | 2.0.7 | Python 3.8 wheel, geometry regressions retained; GEOS DLL included explicitly |
| openpyxl / et_xmlfile | 3.1.5 / 2.0.0 | Existing Excel engine/version; full accepted template/mapping assertions preserved |
| reportlab / Pillow / chardet | 4.3.1 / 9.5.0 / 5.2.0 | Python 3.8-compatible PDF/image stack; PDF round trips tested |
| pypdf / typing_extensions | 5.9.0 / 4.13.2 | Python 3.8-compatible parsing and annotations |
| websockets | 13.1 | Python 3.8 with existing `websockets.asyncio.client` API |
| mapbox-vector-tile / protobuf / pyclipper | 2.0.1 / 4.25.3 / 1.3.0.post5 | Existing vector tile validation support; matching x64 wheels |
| certifi | 2025.4.26 | Explicit reproducible trust-store version; review root updates before release |
| Copernicus Marine | omitted only in legacy | No Python 3.8 SDK release; approved optional provider fallback |

Other locked build/transitive packages are listed exactly in `requirements-win7.txt`; test-only packages in `requirements-win7-test.txt`. OpenCV, matplotlib, requests and cryptography are not direct application runtime requirements. Do not collect the whole development environment or add a camera dependency for a feature absent from this source.

Python compatibility changes preserve string-enum values, affix/path semantics, deferred annotations and queued-task cancellation. No VDR calculation or Excel cell mapping was changed for this task.

## Release validation and signing

Actual Windows 7 SP1, Windows 8/8.1 and Windows 10 machines/VMs are not available in this session: runtime validation remains pending. A PE header or successful build alone does not prove compatibility. Check missing DLLs/entry points, platform plugins, fonts, browser, save dialogs, Excel/PDF round trips, USB device reconnect and clean close on each OS. Test physical BLE/serial devices separately. Validate 100%, 125% and 150% DPI on target machines.

The output is unsigned. No certificate was created. Sign the final EXE and appropriate shipped binaries using authorized Authenticode credentials and timestamping, then regenerate hashes and repeat smoke checks. SmartScreen/reputation warnings can occur for unsigned builds; never disable security software.

Sources: [Qt 6 target decision](https://www.qt.io/blog/qt6-development-hosts-and-targets), [PyInstaller 4.10 requirements](https://www.pyinstaller.org/en/v4.10/requirements.html), [Microsoft UCRT deployment](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment), [Microsoft runtime lifecycle](https://learn.microsoft.com/en-us/lifecycle/faq/visual-c-faq), [Python loader prerequisite](https://bugs.python.org/msg380973), [Copernicus SDK release metadata](https://pypi.org/pypi/copernicusmarine/json).
