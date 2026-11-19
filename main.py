import sys
from app.nav.web_scheme import register_gds_scheme
register_gds_scheme()
from app.qt.QtWidgets import QApplication
from app.qt import exec_qt
from app.qt.QtCore import QStandardPaths,QTimer,QCoreApplication,QEvent
from app.qt.QtGui import QFont, QIcon
from pathlib import Path
from app.ui.main_window import MainWindow
def main():
    import logging
    maritime_log=logging.getLogger('app.nav.maritime')
    if not maritime_log.handlers:
        handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(message)s'))
        maritime_log.addHandler(handler)
    maritime_log.setLevel(logging.INFO);maritime_log.propagate=False
    print('STARTUP 1: main entered', flush=True)
    validation='--validation-profile' in sys.argv
    cycle='--validation-cycle' in sys.argv
    if cycle and not validation:raise ValueError('Validation cycle requires --validation-profile')
    close_args=[arg for arg in sys.argv if arg.startswith('--validation-close-after=')]
    if close_args and not validation:raise ValueError('Automatic validation close requires --validation-profile')
    close_ms=int(close_args[0].split('=',1)[1]) if close_args else 0
    args=[arg for arg in sys.argv if arg not in ('--validation-profile','--validation-cycle') and arg not in close_args]
    if validation:QStandardPaths.setTestModeEnabled(True)
    app=QApplication(args); print('STARTUP 2: QApplication created', flush=True); app.setApplicationName('GDS VTS Validation' if validation else 'GDS VTS')
    from app.qt import LEGACY
    collector=None
    if LEGACY:
        from app.qt.garbage_collection import GuiGarbageCollector
        collector=GuiGarbageCollector(app)
    QFont.insertSubstitutions('Cascadia Mono',['Consolas','JetBrains Mono','Courier New'])
    QFont.insertSubstitutions('Segoe UI Semibold',['Segoe UI','Arial'])
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'app/resources/theme/deep-current/gds-vts.ico')))
    print('STARTUP 3: before MainWindow import', flush=True)
    from app.ui.main_window import MainWindow
    print('STARTUP 4: MainWindow imported', flush=True); print('STARTUP 5: before MainWindow construction', flush=True)
    window=MainWindow(); print('STARTUP 6: MainWindow constructed', flush=True); window.show(); print('STARTUP 7: window shown', flush=True); print('STARTUP 8: entering app.exec', flush=True)
    if close_ms:QTimer.singleShot(max(1000,close_ms),window.close)
    if cycle:
        QTimer.singleShot(500,lambda:window.navigate('Nav'))
        QTimer.singleShot(2000,lambda:window.navigate('VDR'))
    try:
        result=exec_qt(app); print('STARTUP 9: app.exec returned', flush=True)
        return result
    finally:
        # Explicit ownership order avoids Python local-variable finalization
        # destroying QApplication before a page/profile's native objects.
        window.maritime_runtime.close(wait=True,timeout=2.0)  # bounded: stalled providers are abandoned
        window.nav.shutdown_webengine()
        window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        if collector:collector.finish()
        print('STARTUP 10: Qt objects destroyed before QApplication',flush=True)
if __name__ == '__main__': raise SystemExit(main())
