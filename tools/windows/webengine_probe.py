"""Minimal native Qt5 WebEngine lifetime probe, independent of the application."""
import argparse
import sys
from PySide2.QtCore import QCoreApplication,QEvent,QTimer,Qt,qVersion
from PySide2.QtWidgets import QApplication
from PySide2.QtWebEngine import QtWebEngine
from PySide2.QtWebEngineWidgets import QWebEngineView

parser=argparse.ArgumentParser();parser.add_argument('--render',choices=['default','software','gpu-disabled'],default='default')
args=parser.parse_args()
if args.render=='software':QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
if args.render=='gpu-disabled':
    import os
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu'
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
QtWebEngine.initialize()
app=QApplication([])
view=QWebEngineView();view.resize(640,480)
loaded=[]
def ready(ok):
    loaded.append(bool(ok))
    QTimer.singleShot(250,view.close)
view.loadFinished.connect(ready)
view.setHtml('<!doctype html><title>Qt5 lifetime probe</title><h1>Local WebEngine probe</h1>')
view.show();QTimer.singleShot(15000,app.quit)
print('START Qt '+qVersion()+' '+args.render,flush=True)
result=app.exec_()
print('EVENT LOOP RETURNED '+str(result),flush=True)
view.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
app.processEvents()
assert loaded==[True],loaded
print('PROBE CLEAN EXIT',flush=True)
