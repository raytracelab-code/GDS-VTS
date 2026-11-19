import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from test_vdr import fixture_report
from app.vdr.pdf import export_pdf
from app.vdr.store import ReportStore
d = Path(tempfile.mkdtemp())
def ok(n, field):
    r = fixture_report(); r['finalized'] = True
    if field == 'act': r['acts'][0]['act'] = 'word ' * (n//5)
    elif field == 'comments': r['crew'][0]['comments'] = 'word ' * (n//5)
    else: r['bulk'][1]['remarks'] = 'word ' * (n//5)
    try: export_pdf(r, d/'t.pdf'); return True
    except Exception as e: return False
for field in ('act', 'remarks'):
    lo, hi = 100, 20000
    while hi - lo > 50:
        mid = (lo+hi)//2
        lo, hi = (mid, hi) if ok(mid, field) else (lo, mid)
    print(f'[PDF max chars before LayoutError in {field}] ~{lo}')
# store reload with a >20000-char field
p = d/'r.json'; s = ReportStore(p, today='2026-11-18')
s.mutate(lambda r: r['meta'].update(captain='Capt')); s.mutate(lambda r: r['bulk'][1].update(remarks='x'*20001)); s.save()
s2 = ReportStore(p, today='2026-11-18')
print('[reload with 20001-char remark] load_error=', s2.load_error, '| reports=', list(s2.reports), '| captain=', repr(s2.report['meta']['captain']))
try: s2.save()
except OSError as e: print('[subsequent save]', e)
