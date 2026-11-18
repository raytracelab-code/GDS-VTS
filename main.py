import sys
from app.nav.web_scheme import register_gds_scheme
register_gds_scheme()
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import QStandardPaths
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
    args=[arg for arg in sys.argv if arg!='--validation-profile']
    if validation:QStandardPaths.setTestModeEnabled(True)
    app=QApplication(args); print('STARTUP 2: QApplication created', flush=True); app.setApplicationName('GDS VTS Validation' if validation else 'GDS VTS')
    QFont.insertSubstitutions('Cascadia Mono',['Consolas','JetBrains Mono','Courier New'])
    QFont.insertSubstitutions('Segoe UI Semibold',['Segoe UI','Arial'])
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'app/resources/theme/deep-current/gds-vts.ico')))
    print('STARTUP 3: before MainWindow import', flush=True)
    from app.ui.main_window import MainWindow
    print('STARTUP 4: MainWindow imported', flush=True); print('STARTUP 5: before MainWindow construction', flush=True)
    window=MainWindow(); print('STARTUP 6: MainWindow constructed', flush=True); window.show(); print('STARTUP 7: window shown', flush=True); print('STARTUP 8: entering app.exec', flush=True)
    result=app.exec(); print('STARTUP 9: app.exec returned', flush=True); return result
if __name__ == '__main__': raise SystemExit(main())
