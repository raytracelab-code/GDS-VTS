"""One Qt API surface: current PySide6 or the controlled PySide2 legacy build.

Only binding/API location differences live here. Application widgets and tests use
the same code and assertions with either binding; third-party modules are not spoofed.
"""
import importlib
import importlib.util
import os
import sys
from types import ModuleType

API = os.environ.get('GDS_QT_API') or ('PySide6' if importlib.util.find_spec('PySide6') else 'PySide2')
if API not in ('PySide6', 'PySide2'):
    raise RuntimeError('GDS_QT_API must be PySide6 or PySide2')
LEGACY = API == 'PySide2'

QtCore = importlib.import_module(API+'.QtCore')
QtGui = importlib.import_module(API+'.QtGui')
QtWidgets = importlib.import_module(API+'.QtWidgets')
QtSvg = importlib.import_module(API+'.QtSvg')
QtWebChannel = importlib.import_module(API+'.QtWebChannel')

if LEGACY:
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    from PySide2.QtWebEngine import QtWebEngine
    QtWebEngine.initialize()
    QtGui.QShortcut = QtWidgets.QShortcut
    for cls in (QtCore.QCoreApplication, QtWidgets.QApplication, QtWidgets.QDialog, QtWidgets.QMessageBox):
        if not hasattr(cls, 'exec'):
            cls.exec = cls.exec_
    QtGui.QMouseEvent.position = QtGui.QMouseEvent.localPos
    QtGui.QMouseEvent.globalPosition = lambda event: QtCore.QPointF(event.globalPos())
    QtSvgWidgets = QtSvg
    QtWebEngineWidgets = importlib.import_module(API+'.QtWebEngineWidgets')
    # Qt5 keeps page/profile/settings in Widgets; Qt6 moved them to Core.
    native_core = importlib.import_module(API+'.QtWebEngineCore')
    QtWebEngineCore = ModuleType('app.qt.QtWebEngineCore')
    QtWebEngineCore.__dict__.update({k:getattr(native_core,k) for k in dir(native_core) if not k.startswith('__')})
    for name in ('QWebEnginePage', 'QWebEngineProfile', 'QWebEngineSettings'):
        setattr(QtWebEngineCore, name, getattr(QtWebEngineWidgets,name))
    from shiboken2 import isValid
else:
    QtSvgWidgets = importlib.import_module(API+'.QtSvgWidgets')
    QtWebEngineCore = importlib.import_module(API+'.QtWebEngineCore')
    QtWebEngineWidgets = importlib.import_module(API+'.QtWebEngineWidgets')
    from shiboken6 import isValid

for name in ('QtCore','QtGui','QtWidgets','QtSvg','QtSvgWidgets','QtWebChannel','QtWebEngineCore','QtWebEngineWidgets'):
    sys.modules[__name__+'.'+name] = globals()[name]
