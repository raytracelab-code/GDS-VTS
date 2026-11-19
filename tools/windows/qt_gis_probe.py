"""Isolate real GIS loading alongside a native Qt event loop."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import faulthandler
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.qt.QtWidgets import QApplication,QLabel
from app.qt import exec_qt
from app.qt.QtCore import QTimer
from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider

parser=argparse.ArgumentParser();parser.add_argument('--webengine',action='store_true');args=parser.parse_args()
faulthandler.enable();app=QApplication([])
if args.webengine:
    from app.qt.QtWebEngineWidgets import QWebEngineView
    view=QWebEngineView();view.setHtml('<h1>GIS isolation</h1>')
else:view=QLabel('GIS isolation')
view.show();provider=MalaysiaOffshoreGISProvider();pool=ThreadPoolExecutor(1);future=pool.submit(provider.load)
def tick():
    if future.done():
        future.result();print('FULL GIS FINISHED',flush=True);view.close()
timer=QTimer();timer.timeout.connect(tick);timer.start(250)
QTimer.singleShot(120000,view.close)
exec_qt(app);provider.stop();pool.shutdown()
print('QT GIS CLEAN EXIT',flush=True)
