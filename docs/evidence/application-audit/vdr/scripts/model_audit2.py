import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from test_vdr import fixture_report
from app.vdr.model import *
from app.vdr.store import ReportStore
def show(t, v): print(f'[{t}]', v)
for v in ('2,5', '5,30', '1.000,5'):
    show(f'number({v!r})', number(v))
r = fixture_report(); r['meta'].update(fwd='2,5', aft='2,7'); show('draft 2,5 validate', validate(r))
with tempfile.TemporaryDirectory() as d:
    p = Path(d)/'r.json'
    s = ReportStore(p, today='2026-11-17'); s.reports['2026-11-17'] = fixture_report('2026-11-17'); s.save()
    s = ReportStore(p, today='2026-11-18')  # opens next day: rollover happens on construction
    show('day 18 opening FW after rollover', s.report['bulk'][1]['open'])
    s.select('2026-11-17'); s.mutate(lambda r: r['bulk'][1].update(cons='1000'))
    show('day 17 FW closing now', calculate(s.report)['bulkClose'][1])
    s.select('2026-11-18'); show('day 18 FW opening still', s.report['bulk'][1]['open'])
    s.mutate(lambda r: r['meta'].update(captain='x'))
    show('undo stack days', [d for d, _ in s.undo_stack])
    s.undo(); show('current after undo 1', s.current); s.undo(); show('current after undo 2 (jumps day?)', s.current)
    # gap
    s2 = ReportStore(Path(d)/'g.json', today='2026-11-15'); s2.reports['2026-11-15'] = fixture_report('2026-11-15'); s2.save()
    s2 = ReportStore(Path(d)/'g.json', today='2026-11-17')
    show('opened 2 days later: crew/bulk carried?', (s2.report['crew'][0]['name'], s2.report['bulk'][0]['open'], s2.report['meta']['captain']))
