import sys
from app.nav.web_scheme import register_gds_scheme
register_gds_scheme()
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
def main():
    print('STARTUP 1: main entered', flush=True)
    app=QApplication(sys.argv); print('STARTUP 2: QApplication created', flush=True); app.setApplicationName('GDS VTS')
    print('STARTUP 3: before MainWindow import', flush=True)
    from app.ui.main_window import MainWindow
    print('STARTUP 4: MainWindow imported', flush=True); print('STARTUP 5: before MainWindow construction', flush=True)
    window=MainWindow(); print('STARTUP 6: MainWindow constructed', flush=True); window.show(); print('STARTUP 7: window shown', flush=True); print('STARTUP 8: entering app.exec', flush=True)
    result=app.exec(); print('STARTUP 9: app.exec returned', flush=True); return result
if __name__ == '__main__': raise SystemExit(main())
