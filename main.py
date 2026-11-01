import sys
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
def main():
    app=QApplication(sys.argv); app.setApplicationName('GDS VTS'); window=MainWindow(); window.show(); return app.exec()
if __name__ == '__main__': raise SystemExit(main())
