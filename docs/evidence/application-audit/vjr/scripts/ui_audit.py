import sys, time, json, copy
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from pathlib import Path
from app.qt.QtWidgets import QApplication, QPushButton, QLineEdit, QComboBox
from app.qt.QtCore import Qt
from PySide6.QtTest import QTest
app = QApplication.instance() or QApplication([])
from app.ui.pages.vjr_workspace import VjrPage
from app.vjr.store import VjrStore
from app.vjr.schema import TABLES
from vjr_fixture import full_report
tmp = Path(sys.argv[1]); ev = Path(sys.argv[2]); tmp.mkdir(parents=True, exist_ok=True); ev.mkdir(parents=True, exist_ok=True)
for f in tmp.glob('*.json'): f.unlink()
def pump(n=5):
    for _ in range(n): app.processEvents()
# ---- empty store workflow: adding 72 progress rows via button
store = VjrStore(tmp/'a.json'); page = VjrPage(store, lambda:{}); page.resize(1366,708); page.show(); pump()
page.tabs.setCurrentIndex(6); pump()
def add_button(): return [b for b in page.tabs.currentWidget().findChildren(QPushButton) if b.text()=='Add Voyage Progress Row'][0]
times=[]
for i in range(72):
    t=time.perf_counter(); add_button().click(); pump(2); times.append(time.perf_counter()-t)
print('add row: first %.3fs, 72nd %.3fs, total %.1fs' % (times[0], times[-1], sum(times)))
print('new row content', store.report['progress'][1])
print('undo stack', len(store.undo_stack))
# delete with no selection
table = page.tables[('progress',)][0]; print('currentRow after rebuild', table.currentRow())
n=len(store.report['progress']); [b for b in page.tabs.currentWidget().findChildren(QPushButton) if b.text()=='Delete row'][0].click(); pump()
print('Delete row w/o selection: rows', n, '->', len(store.report['progress']), 'deleted index?')
# ---- per-keystroke cost with dense report
r = full_report(); base=r['progress'][0]
r['progress']=[dict(base, hour=str(i%24)) for i in range(100)]
r['crew']=[dict(r['crew'][0], name='C%d'%i) for i in range(200)]
(tmp/'dense.json').write_text(json.dumps(r), encoding='utf-8')
store2 = VjrStore(tmp/'dense.json'); t=time.perf_counter(); page2 = VjrPage(store2, lambda:{}); page2.resize(1366,708); page2.show(); pump(); print('dense page build %.2fs' % (time.perf_counter()-t))
page2.tabs.setCurrentIndex(0); pump()
ed = page2.editors[('meta','report_id')]; ed.setFocus()
t=time.perf_counter(); QTest.keyClicks(ed, 'ABCDEFGHIJ'); pump(); dt=time.perf_counter()-t
print('10 keystrokes on dense report %.2fs (%.0f ms/key); undo depth %d; file %d KB' % (dt, dt*100, len(store2.undo_stack), (tmp/'dense.json').stat().st_size//1024))
page2.undo(); pump(); print('after one undo report_id =', store2.report['meta']['report_id'])
t=time.perf_counter(); page2.tables[('progress',)][0].item(5,19).setText('edited'); pump(); print('progress cell edit %.3fs' % (time.perf_counter()-t))
t=time.perf_counter(); page2.undo(); pump(); print('undo (rebuild) %.3fs' % (time.perf_counter()-t))
# arrival vs departure linkage in UI
page2.tabs.setCurrentIndex(5); pump()
ro = {k[1]: e.isReadOnly() for k,e in page2.editors.items() if k[0]=='arrival' and isinstance(e,QLineEdit)}
print('arrival editors readOnly:', ro)
print('arrival linked editors:', sorted({p[1] for p,e in page2.linked if p[0]=='arrival'}))
# Departure 'Estimated Arrival' date vs Arrival actual date distinct?
print('dep arrival_date', store2.report['departure']['arrival_date'], 'arr arrival_date', store2.report['arrival']['arrival_date'])
# progress table geometry
page2.tabs.setCurrentIndex(6); pump(); tb = page2.tables[('progress',)][0]
print('progress table h=%d viewport w=%d content w=%d hscroll max=%d' % (tb.height(), tb.viewport().width(), tb.horizontalHeader().length(), tb.horizontalScrollBar().maximum()))
# keyboard: tab through cells, type into hour combobox
tb.setFocus(); tb.setCurrentCell(0,0); QTest.keyClick(tb, Qt.Key.Key_Tab); pump(); print('after Tab current col', tb.currentColumn())
QTest.keyClicks(tb, '7'); pump(); w=tb.indexWidget(tb.currentIndex()) or app.focusWidget(); print('typing "7" in Hour cell opens', type(w).__name__, getattr(w,'currentText',lambda:'-')())
QTest.keyClick(app.focusWidget(), Qt.Key.Key_Return); pump(); print('hour[0] now', repr(store2.report['progress'][0]['hour']))
# screenshots
for size in ((1366,708),(1920,1020)):
    page2.resize(*size); pump(10)
    for i in range(7):
        page2.tabs.setCurrentIndex(i); pump(10)
        page2.grab().save(str(ev/('vjr_%02d_%s_%dx%d.png' % (i+1, page2.tabs.tabText(i).split(' ')[0].replace('/','').lower(), size[0], size[1]+60))))
    page2.tabs.setCurrentIndex(4); pump(); sc=page2.tabs.currentWidget(); sc.verticalScrollBar().setValue(sc.verticalScrollBar().maximum()); pump(10)
    page2.grab().save(str(ev/('vjr_05_departure_bottom_%dx%d.png' % (size[0], size[1]+60))))
    sc.verticalScrollBar().setValue(0)
# validation banner screenshot
page2.tabs.setCurrentIndex(3); pump()
store2.mutate(lambda r: r['waypoints'][0].update(lat_degree='91', lat_minute='60', course='360')); page2.rebuild(); pump(10)
page2.resize(1366,708); pump(10); page2.grab().save(str(ev/'vjr_04_waypoints_invalid_1366x768.png'))
print('excel enabled with errors:', page2.excel_button.isEnabled(), '| banner:', page2.errors.text()[:160])
# VDR comparison
from app.vdr.store import ReportStore
from app.ui.pages.vdr.workspace import VdrPage
vs = ReportStore(tmp/'vdr.json', today='2026-11-18'); vp = VdrPage(vs); vp.resize(1366,708); vp.show(); pump(20)
vp.grab().save(str(ev/'vdr_reference_1366x768.png')); vp.resize(1920,1020); pump(20); vp.grab().save(str(ev/'vdr_reference_1920x1080.png'))
vp.save_timer.stop(); print('screens saved', len(list(ev.glob('*.png'))))
