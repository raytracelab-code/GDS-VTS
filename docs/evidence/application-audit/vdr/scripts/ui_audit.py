import sys, os, json, tempfile, time
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from app.qt.QtWidgets import QApplication, QLineEdit, QComboBox, QPushButton, QWidget, QDialog, QMessageBox, QAbstractButton
from app.qt.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
app = QApplication.instance() or QApplication([])
from test_vdr import fixture_report
from app.vdr.store import ReportStore
from app.vdr.model import validate, calculate
from app.ui.pages.vdr.workspace import VdrPage
EV = Path(r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\vdr')
TMP = Path(tempfile.mkdtemp(prefix='vdr-ui-audit-'))
IDENT = lambda: dict(vessel='AUDIT VESSEL', client='AUDIT CLIENT', hireDate='2026-01-01')
def show(t, v): print(f'[{t}]', v, flush=True)
def pump(ms=50):
    end = time.time()+ms/1000
    while time.time() < end: app.processEvents()
def make(report=None, name='r.json', size=(1440, 900)):
    s = ReportStore(TMP/name, today='2026-11-18', identity=IDENT())
    if report is not None: s.reports[s.current] = report
    p = VdrPage(s, identity_provider=IDENT); p.resize(*size); p.show(); pump(100)
    return p
def grab(p, name):
    p.grab().save(str(EV/name)); show('saved', name)
def full_grab(p, name):
    # render whole scroll content
    w = p.scroll.widget(); w.grab().save(str(EV/name)); show('saved', name)
def type_into(w, text):
    w.setFocus(); w.selectAll() if isinstance(w, QLineEdit) else None
    QTest.keyClicks(w, text); pump(20)

# 1. Blank report at 1366x768 and with nav rail (1306 wide)
p = make(None, 'blank.json', (1366, 768)); grab(p, '01_blank_1366x768.png')
show('blank badge', p.badge.text())
show('activity table width vs viewport', (sum(p.tables['acts'].property('baseWidths')), p.tables['acts'].viewport().width(), p.tables['acts'].horizontalScrollBar().maximum()))
show('crew table width vs viewport', (sum(p.tables['crew'].property('baseWidths')), p.tables['crew'].viewport().width(), p.tables['crew'].horizontalScrollBar().maximum()))
show('topbar hscroll max (buttons offscreen?)', p.topbar_scroll.horizontalScrollBar().maximum())
p.resize(1306, 728); pump(200); grab(p, '02_blank_in_shell_1306x728.png')
show('in-shell topbar hscroll max', p.topbar_scroll.horizontalScrollBar().maximum())
show('in-shell acts table hscroll max', p.tables['acts'].horizontalScrollBar().maximum())
vis = [w.text() for w in (p.finalize_button, p.excel_button) if w.visibleRegion().isEmpty()]
show('topbar buttons not visible at 1306', vis)
p.go_section(2); pump(400); grab(p, '03_activity_1306x728.png')
p.go_section(5); pump(400); grab(p, '04_crew_1306x728.png')
# Validation dialog content
errors = validate(p.report); show('blank errors count', len(errors)); show('first errors', [e['msg'] for e in errors[:6]])
# Is there any inline error marker on an invalid line edit?
e = p.editors[('meta', 'fwd')]; type_into(e, '-3'); show('fwd=-3 stylesheet/property', (e.styleSheet(), e.property('invalid'), p.badge.text()))
p.close(); p.deleteLater(); pump()

# 2. Finalized report: typing silently un-finalizes
p = make(fixture_report(), 'fin.json'); ok = p.finalize(); pump(400)
show('finalize ok/badge', (ok, p.badge.text(), p.report['finalized']))
cap = p.editors[('meta', 'captain')]
show('captain read-only when finalized?', cap.isReadOnly())
cap.setFocus(); QTest.keyClicks(cap, 'X'); pump(400)
show('after typing 1 char: finalized/badge/excel enabled', (p.report['finalized'], p.badge.text(), p.excel_button.isEnabled()))
grab(p, '05_finalized_then_typed.png')
p.undo(); pump(50); show('after undo finalized', p.report['finalized'])
p.close(); p.deleteLater(); pump()

# 3. Undo granularity: per keystroke
p = make(fixture_report(), 'undo.json'); before = len(p.store.undo_stack)
cap = p.editors[('meta', 'captain')]; cap.setFocus(); cap.selectAll(); QTest.keyClicks(cap, 'Capt Ahmad'); pump(50)
show('undo entries from typing "Capt Ahmad"', len(p.store.undo_stack)-before)
p.undo(); pump(50); show('captain after one Ctrl+Z', p.report['meta']['captain'])
show('focus widget after undo (rebuild)', type(app.focusWidget()).__name__ if app.focusWidget() else None)
p.close(); p.deleteLater(); pump()

# 4. Activity log: set 2400 on an earlier row => later rows deleted
r = fixture_report(); from app.vdr.model import blank_row
r['acts'] = []
for to, act in (('0600', 'Alongside LABUAN'), ('1200', 'Enroute to KND'), ('1800', 'Cargo ops at KND'), ('', '')):
    a = blank_row('acts'); a.update(to=to, act=act, cat='Standby steaming offshore' if act else '', loc='LABUAN' if act else '', dp='N' if act else ''); r['acts'].append(a)
p = make(r, 'acts.json')
show('rows before', [(a['to'], a['act']) for a in p.report['acts']])
to2 = p.editors[('acts', 1, 'to')]; to2.setFocus(); to2.selectAll(); QTest.keyClicks(to2, '2400'); QTest.keyClick(to2, Qt.Key.Key_Tab); pump(200)
show('rows after typing 2400 in row 2 TO + Tab', [(a['to'], a['act']) for a in p.report['acts']])
show('any confirmation shown? (top-level dialogs)', [w.windowTitle() for w in app.topLevelWidgets() if isinstance(w, (QDialog, QMessageBox)) and w.isVisible()])
p.undo(); pump(100); show('rows after one undo', [(a['to'], a['act']) for a in p.report['acts']])
# typing "24" as shorthand
p.close(); p.deleteLater(); pump()
r = fixture_report(); r['acts'][0]['to'] = ''
p = make(r, 'acts2.json'); t = p.editors[('acts', 0, 'to')]; t.setFocus(); QTest.keyClicks(t, '6'); QTest.keyClick(t, Qt.Key.Key_Tab); pump(100)
show('TO "6" becomes', p.report['acts'][0]['to'])
t = p.editors[('acts', 1, 'to')] if ('acts', 1, 'to') in p.editors else None
show('row auto-added after valid TO', len(p.report['acts']))
if t:
    t.setFocus(); QTest.keyClicks(t, '0500'); QTest.keyClick(t, Qt.Key.Key_Tab); pump(100)
    show('row2 0500 < 0600 duration label', p.computed[('duration', 1)].text())
    show('row2 FROM shown', p.computed[('from', 1)].text())
grab(p, '06_activity_invalid_row.png')
p.go_section(2); pump(400); grab(p, '06b_activity_invalid_row_scrolled.png')
p.close(); p.deleteLater(); pump()

# 5. Autosave: edit then reopen within debounce
p = make(fixture_report(), 'auto.json'); p.flush_save(); pump(50)
cap = p.editors[('meta', 'captain')]; cap.setFocus(); cap.selectAll(); QTest.keyClicks(cap, 'Within debounce');
reopened = ReportStore(TMP/'auto.json', today='2026-11-18')
show('on-disk captain immediately after typing (within 300ms)', reopened.report['meta']['captain'])
show('save_timer active', p.save_timer.isActive())
p.close(); pump(10)  # widget close does NOT flush
show('after page.close() timer active', p.save_timer.isActive())
pump(400); show('on-disk after 400ms (timer still parented)', ReportStore(TMP/'auto.json', today='2026-11-18').report['meta']['captain'])
p.deleteLater(); pump()

# 6. Load error UX
bad = TMP/'corrupt.json'; bad.write_text('{"schemaVersion":1,"reports":{"2026-11-18": {"meta": 5}}}', encoding='utf-8')
s = ReportStore(bad, today='2026-11-18'); p = VdrPage(s, identity_provider=IDENT); p.resize(1440, 900); p.show(); pump(100)
show('load error label/tooltip', (p.saved.text(), p.saved.toolTip()))
cap = p.editors[('meta', 'captain')]; cap.setFocus(); QTest.keyClicks(cap, 'Typing a whole day of data'); pump(500)
show('label after edits', (p.saved.text(), p.saved.toolTip()[:120]))
grab(p, '07_load_error_save_failed.png')
p.close(); p.deleteLater(); pump()

# 7. Weather tab order: count Tab presses from 0000 wind to 0600 wind
p = make(fixture_report(), 'wx.json')
start = p.editors[('wx', 0, 'wind')]; start.setFocus(); pump(20); seq = []
for i in range(60):
    QTest.keyClick(app.focusWidget(), Qt.Key.Key_Tab); pump(5); w = app.focusWidget()
    seq.append(w.accessibleName() or w.text() if hasattr(w, 'text') else type(w).__name__)
    if w is p.editors[('wx', 1, 'wind')]: break
show('tabs from wx0.wind to wx1.wind', (i+1, seq))
show('weather button focus policy', [b.focusPolicy() for b in list(p.weather_buttons.values())[:1]])
p.go_section(1); pump(400); grab(p, '08_weather.png')
# Location summary vs daily duration
r = fixture_report(); r['acts'] = []
for to, loc in (('0600', 'LABUAN'), ('1200', 'KND'), ('1800', 'LABUAN'), ('2400', 'labuan')):
    a = blank_row('acts'); a.update(to=to, act='x', cat='Standby steaming offshore', loc=loc, dp='N'); r['acts'].append(a)
p.close(); p.deleteLater(); pump()
p = make(r, 'locs.json'); p.go_section(2); pump(400); grab(p, '09_location_durations.png')
rows = [[p.location_durations.item(i, j).text() for j in range(4)] for i in range(p.location_durations.rowCount())]
show('Daily duration at location rows', rows)
p.close(); p.deleteLater(); pump()

# 8. Bulk: transfers UI cap vs excel
p = make(fixture_report(), 'bulk.json'); p.go_section(4); pump(300)
for _ in range(3): p.add_transfer(1); pump(20)
show('FW transfers allowed by UI', len(p.report['bulk'][1]['tr']))
p.go_section(4); pump(400); grab(p, '10_bulk_details.png')
p.close(); p.deleteLater(); pump()

# 9. Large crew list perf (keystroke latency)
r = fixture_report(); r['crew'] = [dict(blank_row('crew'), name=f'Crew {i}', rank='AB', signon='2026-11-01', nat='my') for i in range(120)]
t0 = time.time(); p = make(r, 'crew.json'); show('build page with 120 crew (s)', round(time.time()-t0, 2))
cap = p.editors[('meta', 'captain')]; cap.setFocus(); t0 = time.time(); QTest.keyClicks(cap, 'abcdefghij'); show('10 keystrokes latency (s)', round(time.time()-t0, 3))
t0 = time.time(); p.add_row('crew'); show('add crew row (full rebuild) (s)', round(time.time()-t0, 2))
p.close(); p.deleteLater(); pump()
show('tmp dir', TMP)

