import sys, json, os, traceback
from pathlib import Path
from copy import deepcopy
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from test_vdr import fixture_report
from app.vdr.model import *
from app.vdr.pdf import export_pdf, import_pdf
from pypdf import PdfReader
OUT = Path(r'C:\Users\rayha\AppData\Local\Temp\claude\53cd7aab76db0ca9\a2b5405c-7886-40e0-954f-52fa559c6aae\scratchpad\vdr\pdf'); OUT.mkdir(exist_ok=True)
EV = Path(r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\vdr')
def show(t, v): print(f'[{t}]', v)
def fin(r): r['finalized'] = True; r['finalizedAt'] = '2026-11-18T10:00:00+00:00'; return r
def run(name, r, keep=False):
    p = (EV if keep else OUT)/f'{name}.pdf'
    try:
        export_pdf(fin(r), p)
        back = import_pdf(p)
        text = '\n'.join(pg.extract_text() for pg in PdfReader(p).pages)
        show(name, f'OK pages={len(PdfReader(p).pages)} roundtrip_equal={back == normalize(r)}')
        return p, back, text
    except Exception as e:
        show(name, f'FAIL {type(e).__name__}: {str(e)[:300]}')
        if p.exists(): show(name+' partial file left', p.stat().st_size)
        return None, None, None

r = fixture_report()
r['meta']['captain'] = "Capt. O'Brien & Sons <b>bold</b> / 船长 Ñandú"
r['acts'][0]['act'] = 'Cargo & backload — “quotes” ‘single’ 30°C ± ✓ 中文'
p, back, text = run('unicode_small', deepcopy(r), keep=True)
if text:
    for needle in ("O'Brien & Sons", '<b>bold</b>', '船长', 'Ñandú', '“quotes”', '✓', '中文'):
        show(f'text contains {needle!r}', needle in text)
    show('missing in PDF: report no / perfect days / location summary / DP total', [k for k in ('PERFECT', 'Report no', 'DURATION AT LOCATION', 'DP') if k.lower() not in text.lower()])
    print(text[:1500])

# very long single cell
r2 = fixture_report(); r2['acts'][0]['act'] = 'Long activity narrative. ' * 300
run('long_cell_7500', r2)
r3 = fixture_report(); r3['bulk'][1]['remarks'] = 'remark ' * 3000
run('long_remarks_21000', r3)
r3b = fixture_report(); r3b['bulk'][1]['remarks'] = 'remark ' * 1000
run('long_remarks_7000', r3b)
# dense 48 activities, 60 crew
r4 = fixture_report(); r4['acts'] = []
for i in range(48):
    a = blank_row('acts'); a.update(to=hhmm((i+1)*30), act=f'Act {i} & ops', cat='Standby steaming offshore', dp='N', lifts='1', pob='2', loc='LABUAN'); r4['acts'].append(a)
r4['crew'] = [dict(blank_row('crew'), name=f'Crew {i}', rank='AB', signon='2026-11-01', nat='my') for i in range(60)]
run('dense', r4, keep=True)
# imported report with invalid transfer qty (finalized flag preserved by normalize)
r5 = fixture_report(); r5['bulk'][1]['tr'] = [dict(to='X', qty='ten', mb='', ma='', tk='')]
run('invalid_qty_finalized_import', r5)
# lowercase fuel name
r6 = fixture_report(); r6['bulk'][0]['name'] = 'Fuel (ltrs)'
p6, b6, t6 = run('lowercase_fuel', r6)
# not finalized
try: export_pdf(fixture_report(), OUT/'nf.pdf'); show('unfinalized export', 'allowed')
except Exception as e: show('unfinalized export', e)
# write to locked file -> non-atomic?
tgt = OUT/'locked.pdf'; export_pdf(fin(fixture_report()), tgt); size0 = tgt.stat().st_size
r7 = fixture_report(); r7['acts'][0]['act'] = 'Long ' * 3000
try: export_pdf(fin(r7), tgt)
except Exception as e: show('failed re-export over existing', f'{type(e).__name__}; existing size before={size0} after={tgt.stat().st_size}')
# truncated pdf import
raw = (EV/'unicode_small.pdf').read_bytes(); (OUT/'trunc.pdf').write_bytes(raw[:len(raw)//3])
try: show('truncated import', import_pdf(OUT/'trunc.pdf')['meta']['date'])
except Exception as e: show('truncated import', e)
