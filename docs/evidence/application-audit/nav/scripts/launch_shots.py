import os, sys, time, json
SCR=os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['GDS_MARITIME_CACHE_DIR']=os.path.join(SCR,'mcache')
os.environ['GDS_OVERPASS_ENDPOINT']='https://127.0.0.1:1/api/interpreter'
os.environ['GDS_OVERPASS_FALLBACK_ENDPOINTS']='https://127.0.0.1:1/api/interpreter'
os.environ['GDS_GEBCO_WMS_ENDPOINT']='https://127.0.0.1:1/mapserv?'
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
os.chdir(r'C:\Users\rayha\GDS-VTS')
t0=time.perf_counter()
from app.nav.web_scheme import register_gds_scheme
register_gds_scheme()
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import QStandardPaths, QSettings, QTimer
QStandardPaths.setTestModeEnabled(True)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, os.path.join(SCR,'settings'))
app=QApplication(sys.argv)
t1=time.perf_counter()
from app.telemetry.telemetry_state import TelemetryStateService
from app.nav.events import SquallEventService
from app.nav.maritime.runtime import MaritimeRuntime
from app.ui.pages.nav.nav_page import NavPage
t2=time.perf_counter()
state=TelemetryStateService(); sq=SquallEventService(); rt=MaritimeRuntime()
t3=time.perf_counter()
page=NavPage(state,sq,rt); page.resize(1200,800); page.show()
t4=time.perf_counter()
print(f'TIMING import={t2-t1:.3f}s runtime_ctor={t3-t2:.3f}s navpage_ctor={t4-t3:.3f}s', flush=True)
loaded={}
page.web.loadFinished.connect(lambda ok: loaded.setdefault('t',time.perf_counter()-t3))
def probe():
    page.web.page().runJavaScript("JSON.stringify({ou:onlineUnavailable, styleLayers:(offlineConfig.online_style&&offlineConfig.online_style.layers.length), status:document.getElementById('map-status').textContent, hasMap:typeof map!=='undefined'&&!!map, ready:typeof ready!=='undefined'&&ready, gl: (function(){try{return !!document.createElement('canvas').getContext('webgl')}catch(e){return 'err'}})()})", lambda r: print('PROBE', loaded, r, flush=True))
    print('SOURCES', {k:(str(v.state),v.error) for k,v in rt.service.sources.items()}, flush=True)
    print('MAP_STATUS_LABEL', repr(page.map_package_status.text()), 'BADGE', page.online_status.text(), flush=True)
    print('READOUT', repr(page.readout.text()), 'TRACKBAR visible', page.trackbar.isVisible(), flush=True)
QTimer.singleShot(int(os.environ.get('PROBE_MS','12000')), probe)
def close():
    tc=time.perf_counter(); rt.close(wait=True); print(f'TIMING close_wait={time.perf_counter()-tc:.3f}s', flush=True)
    page.shutdown_webengine(); app.quit()
QTimer.singleShot(int(os.environ.get('PROBE_MS','12000'))+1500, close)
EV=r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\nav'
def shots():
    page.grab().save(EV+r'\nav_default_offscreen.png')
    page.toggle_layers(); app.processEvents(); page.grab().save(EV+r'\nav_layers_panel_offscreen.png'); page.toggle_layers()
    print('SHOTS saved',flush=True)
QTimer.singleShot(int(os.environ.get('PROBE_MS','12000'))-500, shots)
app.exec()
print('DONE',flush=True)
