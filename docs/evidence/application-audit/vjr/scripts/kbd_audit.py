import sys
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
from pathlib import Path
from PySide6.QtTest import QTest
from app.qt.QtWidgets import QApplication
from app.qt.QtCore import Qt
app = QApplication.instance() or QApplication([])
from app.ui.pages.vjr_workspace import VjrPage
from app.vjr.store import VjrStore
tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
for f in tmp.glob('*.json'): f.unlink()
def pump(n=5):
    for _ in range(n): app.processEvents()
store = VjrStore(tmp/'k.json'); page = VjrPage(store, lambda:{}); page.resize(1366,708); page.show(); pump()
page.tabs.setCurrentIndex(6); pump(); page.add_row(('progress',), __import__('app.vjr.schema',fromlist=['x']).TABLES['progress'], 100); pump()
tb = page.tables[('progress',)][0]; tb.setFocus(); pump()
def type_cell(col, text, label):
    tb.setCurrentCell(0, col); tb.setFocus(); pump()
    QTest.keyClicks(tb, text); pump()
    w = app.focusWidget(); QTest.keyClick(w, Qt.Key.Key_Tab); pump()
    print(label, 'typed', repr(text), '-> stored', repr(store.report['progress'][0][page.tables[('progress',)][0] and __import__('app.vjr.schema',fromlist=['x']).TABLES['progress'][col][0]]), '| focus after Tab:', type(app.focusWidget()).__name__, 'col', page.tables[('progress',)][0].currentColumn())
    return page.tables[('progress',)][0]
type_cell(0, '2026-11-18', 'Date')
tb = page.tables[('progress',)][0]
type_cell(1, '14', 'Hour')
tb = page.tables[('progress',)][0]
type_cell(3, '5', 'LatDeg')
tb = page.tables[('progress',)][0]
type_cell(6, 'N', 'N/S')
tb = page.tables[('progress',)][0]
type_cell(14, 'Rainy', 'Sky (free text)')
print('row', {k:v for k,v in store.report['progress'][0].items() if v})
# corrupt store
p = tmp/'bad.json'; p.write_text('{"schemaVersion":1,"meta":', encoding='utf-8')
bad = VjrPage(VjrStore(p), lambda:{}); bad.show(); pump()
print('corrupt store banner:', bad.saved.text()[:120]); bad.set_field(('meta','vessel'),'X'); print('after edit:', bad.saved.text()[:80]); print('excel enabled', bad.excel_button.isEnabled())
