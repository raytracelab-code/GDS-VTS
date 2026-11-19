"""GDS-AUDIT-019 stress harness: real NavPage + QtWebEngine on this PC.

Scenarios: page load failure, real renderer crash (chrome://crash), retry, repeated retry,
clean shutdown after failure. Counts QWebEngineView objects and QtWebEngineProcess children.
Run: .venv\\Scripts\\python.exe docs\\evidence\\remaining-p1-fixes\\renderer\\renderer_stress.py
(also works with .venv-win7). Writes renderer_stress_output_<api>.txt next to this file.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]; OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ['GDS_OVERPASS_ENABLED'] = 'false'
from app.nav.web_scheme import register_gds_scheme  # noqa: E402
register_gds_scheme()
from app.qt import API  # noqa: E402
from app.qt.QtCore import QSettings, QStandardPaths, QUrl  # noqa: E402
from app.qt.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv[:1]); QStandardPaths.setTestModeEnabled(True)
from app.qt.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from app.telemetry.telemetry_state import TelemetryStateService  # noqa: E402
from app.nav.events import SquallEventService  # noqa: E402
from app.ui.pages.nav.nav_page import NavPage  # noqa: E402

lines = []
def note(text): lines.append(text); print(text, flush=True)
def pump(seconds, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)
        if until and until(): return True
    return bool(until and until())
def webengine_processes():
    out = subprocess.run(['tasklist', '/FI', f'PID ne {os.getpid()}', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    return sum(1 for line in out.splitlines() if 'QtWebEngineProcess' in line)

baseline = webengine_processes()
page = NavPage(TelemetryStateService(), SquallEventService()); page.resize(1200, 760); page.show()
health = page.renderer_health
pump(30, lambda: health.state == 'OK' or health.state in ('WEBGL_UNAVAILABLE',))
note(f'Qt API {API}; initial map state={health.state}; overlay visible={page.renderer_overlay.isVisible()}')
page.grab().save(str(OUT/f'01_initial_{API}.png'))

# 1. Load failure: an unknown local page.
page.web.setUrl(QUrl('gds://map/does-not-exist.html')); pump(10, lambda: health.state == 'LOAD_FAILED')
note(f'load failure -> state={health.state} title={page.renderer_title.text()!r} overlay={page.renderer_overlay.isVisible()}')
page.grab().save(str(OUT/f'02_load_failed_{API}.png'))
start = time.perf_counter(); page.retry_renderer(); pump(30, lambda: health.state == 'OK')
note(f'retry after load failure -> state={health.state} in {time.perf_counter()-start:.2f} s; overlay={page.renderer_overlay.isVisible()}')

# 2. Real renderer crash.
crash_start = time.perf_counter(); page.web.setUrl(QUrl('chrome://crash'))
crashed = pump(15, lambda: health.state == 'RENDERER_STOPPED')
if not crashed:
    note('chrome://crash did not terminate the renderer here; emitting renderProcessTerminated instead')
    page.web.page().renderProcessTerminated.emit(page.web.page().RenderProcessTerminationStatus.CrashedTerminationStatus, 1)
    pump(1)
note(f'renderer crash -> state={health.state} detected in {time.perf_counter()-crash_start:.2f} s detail={health.detail!r}')
page.grab().save(str(OUT/f'03_renderer_stopped_{API}.png'))
start = time.perf_counter(); ok = page.retry_renderer(); second = page.retry_renderer()
note(f'retry accepted={ok}; immediate second retry ignored={not second}')
pump(30, lambda: health.state == 'OK')
note(f'renderer recovery -> state={health.state} in {time.perf_counter()-start:.2f} s')

# 3. Repeated failure/retry cycles.
for cycle in range(1, 4):
    page.web.setUrl(QUrl('gds://map/missing-%d.html' % cycle)); pump(10, lambda: health.state == 'LOAD_FAILED')
    t = time.perf_counter(); page.retry_renderer(); pump(30, lambda: health.state == 'OK')
    note(f'cycle {cycle}: failed->retry->{health.state} in {time.perf_counter()-t:.2f} s')
views = len(page.findChildren(QWebEngineView))
note(f'QWebEngineView objects after all retries: {views}; retries={health.retries} failures={health.failures}')
note(f'QtWebEngineProcess before page={baseline}, while running={webengine_processes()}')

# 4. Clean shutdown after failure.
page.web.setUrl(QUrl('gds://map/final-failure.html')); pump(10, lambda: health.state == 'LOAD_FAILED')
start = time.perf_counter(); page.shutdown_webengine(); page.close(); page.deleteLater(); elapsed = time.perf_counter()-start; pump(3)
note(f"shutdown after failure: {elapsed:.2f} s, no exception")
app.quit(); pump(1)
note(f'QtWebEngineProcess after shutdown (this process alive): {webengine_processes()}')
(OUT/f'renderer_stress_output_{API}.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
