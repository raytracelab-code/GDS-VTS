import sys, os, copy, time, json, tempfile
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS'); sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from pathlib import Path
from openpyxl import load_workbook
from app.vjr.model import new_report, arrival_fields
from app.vjr.validation import validate
from app.vjr.excel import VjrExcelExporter, suggested_filename, ExcelExportError
from vjr_fixture import full_report
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
print('--- blank report validate:', validate(new_report()))
# blank export
try:
    VjrExcelExporter().export(new_report(), OUT/'blank.xlsx'); print('blank export OK (no required fields)')
except ExcelExportError as e: print('blank export blocked', e)
# invalid waypoint values
for field,val in [('lat_degree','91'),('lon_degree','181'),('lat_minute','60'),('lat_second','60'),('course','360'),('lat_degree','-5'),
                  ('lat_degree','5.5'),('speed','999'),('speed','1e3'),('lat_minute','59.5'),('lat_second','59.999'),('lat_degree',' 5 '),('speed','5,5')]:
    r = full_report(); r['waypoints'][0][field]=val
    errs = validate(r); print('waypoint',field,repr(val),'->', errs[:1] or 'ACCEPTED')
# progress realism
r = full_report(); r['progress'][0].update(visibility='500', wind_speed='400', wave_height='60')
print('progress absurd weather ->', validate(r) or 'ACCEPTED')
# ETA before departure / arrival before departure
r = full_report(); r['departure'].update(departure_date='2026-11-20', arrival_date='2026-11-18')
r['arrival'].update(arrival_date='2026-11-17', report_date='2026-11-10')
print('ETA/arrival before departure ->', validate(r) or 'ACCEPTED')
# duplicated / out-of-order progress hours, progress outside voyage window
r = full_report(); r['progress'][1].update(date='2026-11-18', hour='10', minute='05'); r['progress'][2].update(date='2025-01-01')
print('dup/out-of-order progress ->', validate(r) or 'ACCEPTED')
# crew working days > 90 (template says max 90)
r = full_report(); r['crew'][0]['sign_on']='2025-01-01'
print('crew 300+ working days ->', validate(r) or 'ACCEPTED')
# deck utilisation > 100%
r = full_report(); r['meta']['capacity']='100'
print('deck >100% util ->', validate(r) or 'ACCEPTED')
# arrival destination linkage
r = full_report(); a = arrival_fields(r); print('arrival destination/drafts from departure:', a['destination'], a['draft_forward'], a['captain'])
# dense export
r = full_report()
r['meta'].update(vessel='Ünïcødé & <Vessel> "Q" 船', client='A&B <Co>', report_id='=SUM(1,2)')
r['crew'] = [dict(name='Crew %d ñ & <x>' % i, rank='AB', age='30', nationality='Malaysia', passport='P%d' % i, sign_on='2026-11-01', remarks='x'*500) for i in range(200)]
r['contractors'] = [dict(name='Ctr %d' % i, vendor='V&V', age='40', nationality='MY', passport='C', remarks='') for i in range(200)]
r['waypoints'] = [dict(lat_degree='5',lat_minute='59',lat_second='59.99',lat_direction='N',lon_degree='180',lon_minute='0',lon_second='0',lon_direction='E',course='359.99',speed='12',remarks='WP %d' % i) for i in range(30)]
base = r['progress'][0]
r['progress'] = []
for i in range(100):
    row = dict(base); d,h = divmod(i,24); row.update(date='2026-11-%02d' % (18+d), hour=str(h), minute='0', remarks='Long remark '+('éß漢 & ' * 2000)[:32000] if i==5 else 'H%d' % i)
    r['progress'].append(row)
r['departure']['departure_remarks'] = 'Line1\nLine2\tTabbed & <b>bold</b>'
t=time.time(); VjrExcelExporter().export(r, OUT/'dense.xlsx', identity={}); print('dense export s', round(time.time()-t,2))
wb = load_workbook(OUT/'dense.xlsx')
ws = wb['6. Voyage Progress']; print('progress row 8', [ws.cell(8,c).value for c in range(2,8)], 'row107', [ws.cell(107,c).value for c in (2,3,4,5)], 'len AA13', len(ws['AA13'].value or ''))
print('meta', wb['GDS Meta']['D11'].value, wb['GDS Meta']['D7'].value, wb['GDS Meta']['D10'].value)
d = wb['4. Departure Report']; print('dep D2', d['D2'].value, '| J10', d['J10'].value, '| J18', d['J18'].value, '| D19/F19', repr(d['D19'].value), repr(d['F19'].value), '| D21', repr(d['D21'].value))
a = wb['5. Arrival Report']; print('arr E13', a['E13'].value, 'D26', a['D26'].value, 'D9', a['D9'].value, 'J24', a['J24'].value)
c = wb['1. Core Crew']; print('crew I8 (working days)', c['I8'].value, 'C207', c['C207'].value)
# 101 progress rows
r2 = copy.deepcopy(r); r2['progress'].append(dict(base))
try: VjrExcelExporter().export(r2, OUT/'over.xlsx'); print('101 rows exported?!')
except ExcelExportError as e: print('101 rows blocked:', str(e).splitlines()[1])
print('filenames:', suggested_filename('', ''), suggested_filename('M/V Sea:Star <1>', '2026-11-18'), suggested_filename('CON', '2026-11-18'), suggested_filename('...', 'x'))
# overwrite existing user file silently?
p = OUT/'existing.xlsx'; p.write_bytes(b'user data'); VjrExcelExporter().export(full_report(), p); print('existing file overwritten by exporter, size', p.stat().st_size)
