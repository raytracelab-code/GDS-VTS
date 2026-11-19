import sys,time,os
t0=time.perf_counter()
sys.path.insert(0,r'C:\Users\rayha\GDS-VTS')
from app.nav.web_scheme import register_gds_scheme; register_gds_scheme()
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import QStandardPaths,QTimer
QStandardPaths.setTestModeEnabled(True)
app=QApplication(sys.argv); app.setApplicationName('GDS VTS Audit')
t1=time.perf_counter()
from app.ui.main_window import MainWindow
t2=time.perf_counter()
w=MainWindow(); t3=time.perf_counter()
print(f'import {t2-t1:.2f}s construct {t3-t2:.2f}s qt-init {t1-t0:.2f}s',flush=True)
out=r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\shell'
w.show()
shots=[]
for size in ((1366,768),(1600,900),(1920,1080)):
    for name in ('Configure','VDR','VJR'):
        shots.append((size,name))
def run():
    for (wd,ht),name in shots:
        w.resize(wd,ht); w.navigate(name); w.tabs.buttons[name].setChecked(True)
        for _ in range(20): app.processEvents()
        w.grab().save(os.path.join(out,f'{name.lower()}-{wd}x{ht}.png'))
    print('min size',w.minimumSizeHint().width(),w.minimumSizeHint().height(),flush=True)
    w.close(); app.quit()
QTimer.singleShot(1500,run)
app.exec()
w.maritime_runtime.close(wait=True); w.nav.shutdown_webengine()
print(f'total {time.perf_counter()-t0:.2f}s')
