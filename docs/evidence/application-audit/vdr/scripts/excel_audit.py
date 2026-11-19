import sys, json, os
from pathlib import Path
from copy import deepcopy
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from test_vdr import fixture_report
from app.vdr.model import *
from app.vdr.excel import VdrExcelExporter, suggested_filename, template_path, ExcelExportError
from openpyxl import load_workbook
OUT = Path(r'C:\Users\rayha\AppData\Local\Temp\claude\53cd7aab76db0ca9\a2b5405c-7886-40e0-954f-52fa559c6aae\scratchpad\vdr\xlsx'); OUT.mkdir(exist_ok=True)
EV = Path(r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\vdr')
ID = dict(vessel='GDS / Ünïcode: "Test" & Co*', client='Client & Sons', hireDate='2026-01-01')
def show(t, v): print(f'[{t}]', v)
def fin(r): r['finalized'] = True; r['finalizedAt'] = '2026-11-18T10:00:00+00:00'; return r
def try_export(name, r, identity=ID):
    try:
        p = VdrExcelExporter().export(fin(r), OUT/f'{name}.xlsx', identity=identity); show(name, 'OK '+str(p)); return p
    except ExcelExportError as e:
        show(name, 'EXPORT ERROR: '+str(e)); return None

show('suggested filename', suggested_filename(ID['vessel'], '2026-11-18'))
show('suggested filename CON', suggested_filename('CON', '2026-11-18'))

# dense valid report
LONG = ('Vsl on DP stbd side 50m off; crane ops & lifts / backload: "drums" — 30°C, crew’s rest; Ünïcødé 中文 ' * 40)
r = fixture_report()
r['meta']['captain'] = "Capt. O'Brien & Sons / 船长"
r['acts'] = []
cats = ['Maneuvering at Supply Base','Cargo works within 500m zone','Standby steaming offshore','En-route: full speed']
for i in range(48):
    a = blank_row('acts'); t = (i+1)*30 if i < 47 else 1440
    a.update(to=hhmm(t), act=(LONG if i == 0 else f"Act {i} & ops / ‘quoted’"), cat=cats[i%4], dp='Y' if i%2 else 'N', lifts=str(i), pob='3', loc=f'LOC-{i%5}')
    r['acts'].append(a)
r['crew'] = []
for i in range(30):
    c = blank_row('crew'); c.update(name=f'Crew Ñame {i} & Co', rank='AB', age='30', nat='my', ic=f'IC/{i}', signon='2026-11-01', comments='ok'); r['crew'].append(c)
r['bulk'][1]['remarks'] = LONG[:500]
p = try_export('dense', deepcopy(r))
if p:
    wb = load_workbook(p); ws = wb['VDR']; tpl = load_workbook(template_path())['VDR']
    show('B12 date value/format', (ws['B12'].value, ws['B12'].number_format))
    show('J12 captain', ws['J12'].value)
    show('Z14 long len', len(ws['Z14'].value))
    show('W14,X14,Y14', (ws['W14'].value, ws['X14'].value, ws['Y14'].value, ws['Y14'].number_format))
    show('W61,X61 last act', (ws['W61'].value, ws['X61'].value))
    show('row 62..64 act cells (should be empty)', [(ws[f'{c}62'].value) for c in ('W','X','Y','Z','AE')])
    show('R82..', [(ws[f'R{i}'].value, ws[f'T{i}'].value) for i in range(82, 88)])
    show('AK/AL/AM/AN 14..16', [(ws[f'AK{i}'].value, ws[f'AL{i}'].value, ws[f'AM{i}'].value, ws[f'AN{i}'].value) for i in range(14, 17)])
    show('I82..I103', [ws[f'I{i}'].value for i in (82,86,90,91,102,103)])
    show('E15..E19', [ws[f'E{i}'].value for i in range(15, 20)], )
    show('template E16..E19', [tpl[f'E{i}'].value for i in range(16, 20)])
    show('merged ranges equal', set(map(str, ws.merged_cells.ranges)) == set(map(str, tpl.merged_cells.ranges)))
    # stale template values: cells non-empty in template, not formulas, unchanged in output, outside header labels
    stale = []
    for row in tpl.iter_rows(min_row=12, max_row=110):
        for c in row:
            if c.value is None or isinstance(c.value, str) and c.value.startswith('='): continue
            o = ws[c.coordinate].value
            if o == c.value and not isinstance(c.value, str) or (isinstance(c.value, str) and o == c.value and c.row >= 14 and c.column_letter in ('C','D','E','F','G','H','I','K','L','N','P','R','T','U','X','Z','AE','AG','AH','AI','AN')):
                stale.append((c.coordinate, c.value))
    show('possible stale sample values in VDR (non-label)', stale[:60])
    for sname in ('CORE-CREW', 'CONTRACTORS', 'FLEET MANAGEMENT', 'GDS Meta'):
        t2 = load_workbook(template_path())[sname]; o2 = wb[sname]; st = []
        for row in t2.iter_rows():
            for c in row:
                if c.value is None or (isinstance(c.value, str) and c.value.startswith('=')): continue
                if o2[c.coordinate].value == c.value and not isinstance(c.value, str): st.append((c.coordinate, c.value))
        show(f'numeric/date template values unchanged in {sname}', st[:30])
    cc = wb['CORE-CREW']; show('CORE-CREW row 6', [cc.cell(6, j).value for j in range(2, 11)])
    show('CORE-CREW H6 fmt', cc['H6'].number_format)
    fm = wb['FLEET MANAGEMENT']; show('FLEET D3..D6', [fm[f'D{i}'].value for i in range(3, 7)])
    show('GDS Meta C9..C11', [wb['GDS Meta'][f'C{i}'].value for i in (9,10,11)])
    # data validations / formulas retained elsewhere
    show('T45 value', ws['T45'].value); show('T52', ws['T52'].value); show('C12 (report no.)', ws['C12'].value)

# edge cases
e = fixture_report(); e['acts'][0]['lifts'] = 'abc'; show('validate lifts=abc', validate(e)); try_export('lifts_text', e)
e = fixture_report(); e['crew'][0]['age'] = 'forty'; try_export('age_text', e)
e = fixture_report(); e['end']['fuel'] = '12 days'; try_export('endurance_text', e)
e = fixture_report(); e['wx'][0]['vis'] = '>10'; try_export('vis_text', e)
e = fixture_report(); e['bulk'][1]['tr'] = [dict(to='A', qty='1', mb='', ma='', tk=''), dict(to='B', qty='1', mb='', ma='', tk='')]; show('validate FW 2 transfers', validate(e)); try_export('fw_two_transfers', e)
e = fixture_report(); e['bulk'][0]['tr'] = [dict(to=f'P{i}', qty='1', mb='', ma='', tk='') for i in range(3)]; try_export('fuel_three_transfers', e)
e = fixture_report(); e['acts'] = []
for i in range(23):
    a = blank_row('acts'); a.update(to=hhmm(min(1440, (i+1)*60 if i < 22 else 1440)), act='x', cat='Standby steaming offshore', loc=f'L{i}', dp='N'); e['acts'].append(a)
show('validate 23 locations', validate(e)); try_export('locations_23', e)
e = fixture_report(); e['bulk'].append(blank_row('bulk', 'MUD (bbls)')); e['bulk'][-1]['open'] = '10'; show('validate unknown bulk', validate(e)); try_export('unknown_bulk', e)
e = fixture_report(); e['ctr'] = [dict(blank_row('ctr'), name=f'C{i}', vendor='V') for i in range(201)]; show('validate 201 ctr', validate(e)); try_export('ctr_201', e)
e = fixture_report(); e['meta']['captain'] = 'bad\x07bell'; try_export('control_char', e)
e = fixture_report(); try_export('no_identity', e, identity=dict(vessel='', client='', hireDate=''))
# identity mismatch between screen and excel
e = fixture_report(); p = try_export('identity_mismatch', e, identity=dict(vessel='OTHER', client='', hireDate='2026-06-01'))
if p:
    w = load_workbook(p)['VDR']; show('screen report no/perfect days (report identity)', (report_number(e), hse_perfect_days(e))); show('excel C12/E15 identity param', (w['C12'].value, w['E15'].value))
# overwrite existing & locked destination
dst = OUT/'dense.xlsx'
if dst.exists():
    f = open(dst, 'rb')
    show('overwrite while open-for-read (windows share)', 'attempt')
    try_export('dense', deepcopy(r)); f.close()
