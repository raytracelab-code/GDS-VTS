# VDR offline access acceptance

Verified 19 November 2026 (Asia/Dhaka). This checkpoint supersedes the earlier
VDR reference report's note that VDR requires a live telemetry connection.

The authoritative gate was `TopTabs.set_locked()` in
`app/ui/components/top_tabs.py`, called at construction and on every
`MainWindow.refresh()` (500ms). It previously disabled VDR and VJR whenever
`AppState.modules_unlocked` was false. That session flag becomes true only after
observing LIVE, and stays true through later outages. Consequently a fresh
NO_SOURCE/WAITING/STALE/LOST session could not click VDR at all. The router itself
was not rejecting clicks and already contained exactly one reference VDR page.
The unused legacy `Sidebar` class is not instantiated by this application.

The only product-code change makes Configure and VDR always enabled and keeps
VJR's original `unlocked` flag and explanatory tooltip. NAV's existing always
enabled behavior is unchanged. No VDR UI/model, routing, transport, map or
Configure changes are needed.

| CHECK | RESULT | NOTES |
|---|---|---|
| 1. Cause | IDENTIFIED | Disabled QToolButton prevented the click signal from reaching the router. |
| 2. Authoritative gate | IDENTIFIED | `TopTabs.set_locked()`, called by `MainWindow.refresh()`. |
| 3. Previous behavior | RECORDED | VDR and VJR locked until the session first observed LIVE. |
| 4. New VDR rule | PASS | Always available, independent of telemetry. |
| 5. NO_SOURCE | PASS | Actual normal-app rail click opens VDR; automated shell-routing test passes. |
| 6. CONNECTED_WAITING | PASS | Automated actual MainWindow routing/refresh test; enum displays WAITING. |
| 7. LIVE | PASS | Automated actual MainWindow routing/refresh test. |
| 8. STALE | PASS | Automated actual MainWindow routing/refresh test. |
| 9. LOST | PASS | Automated actual MainWindow routing/refresh test. |
| 10. Active styling | PASS | Physical rail click selects/highlights VDR; unchanged selected style. |
| 11. Normal shell | PASS | Started `.\.venv\Scripts\python.exe -u main.py`; no fixture patching or injected telemetry. |
| 12. Reference page | PASS | Existing reference VDR workspace opens; single instance/four-page stack tested. |
| 13. Scroll | PASS | Physically clicked SCROLL in the normal NO_SOURCE app. |
| 14. Steps | PASS | Physically clicked STEPS and Weather in the normal NO_SOURCE app. |
| 15. Edit | PASS | Entered OFFLINE ACCESS CHECK in an initially empty captain field. |
| 16. Undo | PASS | Toolbar Undo restored the empty field. |
| 17. Redo | PASS | Toolbar Redo restored the test text; another Undo restored the original blank. |
| 18. Autosave | PASS | Normal app displayed Saved feedback; isolated-store save/reopen test also passes. |
| 19. Finalization offline | PASS | NO_SOURCE shell test rejects missing fields and finalizes deterministic valid test data. |
| 20. PDF export offline | PASS | NO_SOURCE shell test executes the Download action and writes a PDF. |
| 21. PDF import offline | PASS | Same test executes Import, restores values/finalization; only dialogs are stubbed. |
| 22. Configure | PASS | Normal-app click returns to Configure, displaying NO SOURCE. Source unchanged. |
| 23. NAV | PASS | Normal-app click opens NAV; regression suite passes. Source unchanged. |
| 24. VJR gate | PASS | Remains disabled before LIVE; retains existing session unlock after LIVE even if later LOST. |
| 25. Map untouched | PASS | Protected-source SHA256 comparison unchanged. |
| 26. VDR UI untouched | PASS | Protected-source SHA256 comparison unchanged, including fonts/assets/model/exporter. |
| 27. py_compile | PASS | Navigation component and new test module. |
| 28. compileall | PASS | `.\.venv\Scripts\python.exe -m compileall app main.py`. |
| 29. Exact pytest | PASS | `.\.venv\Scripts\python.exe -m pytest -q --tb=short`, with offscreen Qt. |
| 30. Total tests | PASS | **558 passed in 105.65s**. Ten new navigation/offline shell cases. |
| 31. Startup | PASS | Normal main.py starts; no device connection attempted. App left on VDR. |
| 32. Runtime evidence | SAVED | `diagnostics/vdr-offline/`: before/after screenshots, Steps capture, edit/undo/redo accessibility trees and manual-checks JSON. |
| 33. Files modified | RECORDED | `top_tabs.py`, one obsolete rail assertion/name in `test_nav_map_first.py`; added `test_vdr_navigation.py`, this report and evidence. |
| 34. Remaining issues | NONE FOR GATE | No confirmed offline-navigation defect remains. Required-field validation remains active as intended. |

## Baseline and test conditions

The requested pre-edit desktop baseline was **544 passed, 4 failed in 116.95s**.
The four failures were existing wide-table viewport checks: Windows clamped the
1680px test window to the physical monitor's available width. A Windows
accessibility/COM diagnostic also appeared during desktop pytest. No VDR layout
code was changed to accommodate the test environment.

Final regression uses `QT_QPA_PLATFORM=offscreen`, matching the previous VDR
checkpoint's successful validation environment, with the exact requested pytest
arguments. Focused navigation plus existing rail checks: **22 passed in 8.28s**.
Windows sandbox access to pytest temporary/cache folders required a retry outside
the sandbox. The final full run completed cleanly with **558 passed**.

The automated integration fixture uses the real MainWindow constructor, rail,
refresh/router/session gate/stack and reference VDR page, while isolating hardware,
network services and unrelated page contents. PDF tests use a temporary store and
deterministic report data. The separate desktop acceptance uses unmodified
`main.py`, real normal-shell navigation and no telemetry connection. The safe
manual test value was restored to its original blank; no demo telemetry was used.

SHA256 checks of 114 protected source/assets files before and after confirm no
change to NAV/map, Configure, VJR, main window, VDR UI/model/PDF or fonts.
Existing unrelated working-tree changes were preserved. No commit was created.

**A. VDR OFFLINE ACCESS ACCEPTED — VDR OPENS WITHOUT TELEMETRY**
