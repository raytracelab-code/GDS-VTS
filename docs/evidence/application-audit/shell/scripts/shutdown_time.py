import sys,time
sys.path.insert(0,r'C:\Users\rayha\GDS-VTS')
from app.nav.web_scheme import register_gds_scheme; register_gds_scheme()
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import QStandardPaths,QTimer,QCoreApplication,QEvent
QStandardPaths.setTestModeEnabled(True)
app=QApplication(sys.argv); app.setApplicationName('GDS VTS Audit')
from app.ui.main_window import MainWindow
w=MainWindow(); w.show()
T={}
def close(): T['c']=time.perf_counter(); w.close()
QTimer.singleShot(4000,close)
app.exec(); T['e']=time.perf_counter()
w.maritime_runtime.close(wait=True); T['m']=time.perf_counter()
w.nav.shutdown_webengine(); T['w']=time.perf_counter()
w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); T['d']=time.perf_counter()
print(f"exec-return {T['e']-T['c']:.2f}s maritime-close {T['m']-T['e']:.2f}s webengine {T['w']-T['m']:.2f}s delete {T['d']-T['w']:.2f}s",flush=True)
