import sys
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
from pathlib import Path
from PySide6.QtTest import QTest
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import Qt
app = QApplication.instance() or QApplication([])
from app.ui.pages.vjr_workspace import VjrPage
from app.vjr.store import VjrStore
from app.vjr.schema import TABLES
tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
for f in tmp.glob('*.json'): f.unlink()
def pump(n=5):
    for _ in range(n): app.processEvents()
store = VjrStore(tmp/'k.json'); page = VjrPage(store, lambda:{}); page.resize(1366,708); page.show(); pump()
page.tabs.setCurrentIndex(6); pump(); page.add_row(('progress',), TABLES['progress'], 100); pump()
def type_cell(col, text):
    tb = page.tables[('progress',)][0]
    tb.setCurrentCell(0, col); tb.setFocus(); pump()
    QTest.keyClick(tb, text[0]); pump()
    for ch in text[1:]:
        QTest.keyClick(app.focusWidget(), ch); pump(1)
    w = app.focusWidget(); shown = w.currentText() if hasattr(w,'currentText') else w.text() if hasattr(w,'text') else ''
    QTest.keyClick(w, Qt.Key.Key_Tab); pump()
    key = TABLES['progress'][col][0]
    print('%-10s typed %-12r editor=%s showed %r -> stored %r' % (key, text, type(w).__name__, shown, store.report['progress'][0][key]))
for col,text in ((0,'2026-11-18'),(0,'18112026'),(1,'14'),(1,'07'),(2,'30'),(3,'5'),(6,'N'),(13,'Rainy'),(14,'6'),(16,'NE')):
    type_cell(col,text)
