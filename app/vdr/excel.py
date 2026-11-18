"""Final VDR snapshots in the verified original workbook, preserving its OOXML parts.

openpyxl reads/validates the template. Cell-value patches are applied directly to
original worksheet XML, avoiding lossy workbook round trips (drawings, protection,
extensions, print setup, guide, and all other ZIP parts remain intact).
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from xml.sax.saxutils import escape
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils.datetime import to_excel

from .model import (activity_summary, calculate, derive_location_durations, hhmm,
                    hse_perfect_days, minutes, normalize, number, report_number, tour_days, validate)

TEMPLATE_HASH = '94b92a23932300dd7795cbe86a11fdec4ce3b6e2158df259994dea98d2521161'
TEMPLATE_NAME = 'vdr_executive_brilliance_template.xlsx'
SHEETS = ('GDS Meta', 'VDR GUIDE', 'VDR', 'CORE-CREW', 'CONTRACTORS', 'FLEET MANAGEMENT')
EQUIPMENT = ('PORT ME', 'PORT ME OUTLET FLOWMETER', 'CENTER ME (P)', 'CENTER ME (P) OUTLET FLOWMETER',
             'CENTER ME (STBD)', 'CENTER ME (STBD) OUTLET FLOWMETER', 'STBD ME', 'STBD ME OUTLET FLOWMETER',
             'BOW THRUSTER 1', 'BOW THRUSTER 2', 'BOW THRUSTER 3', 'STERN THRUSTER 1', 'STERN THRUSTER 2',
             'SHAFT GENERATOR 1', 'SHAFT GENERATOR 2', 'GENERATOR 1', 'GENERATOR 2', 'GENERATOR 3',
             'GENERATOR 4', 'GENERATOR 5', 'GENERATOR 6', 'EMERGENCY GENERATOR')
BULK_ROWS = dict(zip(('FUEL (ltrs)', 'FRESH WATER (ltrs)', 'LUB. OIL (ltrs)', 'GEAR OIL (ltrs)',
    'DISPERSANT (ltrs)', 'DRILL WATER (ltrs)', 'CEMENT (Slag) (mt)', 'CEMENT (mt)', 'BARITE (mt)',
    'SARAPAR (bbls)', 'BENTONITE (mt)', 'New OBM (bbls)', 'Used OBM (bbls)', 'VERSAPRO 9.3PPG (bbls)',
    'OBM 7,5 PPG (bbls)', 'OBM 7,8 PPG (bbls)', 'SBM (bbls)', 'FOAM', 'BASE OIL (bbls)',
    'NABM (bbls)', 'PREMIX (bbls)'), (52, *range(58, 78))))
MOVEMENT_ROWS = (82, 83, 84, 86, 87, 89, 90, 91, 92, 93)
CELL = re.compile(r'<c\b(?P<attrs>[^>]*?)(?:\s*/>|>(?P<body>.*?)</c>)', re.S)
ILLEGAL_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


class ExcelExportError(ValueError):
    """Actionable export failure; no partially written destination is published."""


def resource_root():
    return Path(sys._MEIPASS)/'app/resources' if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]/'resources'


def template_path():
    return resource_root()/'templates'/TEMPLATE_NAME


def normalized_name(value):
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()


def suggested_filename(vessel, day):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(vessel or 'Vessel'))
    safe = re.sub(r'\s+', '_', safe).strip(' ._')[:100] or 'Vessel'
    return f'VDR_{safe}_{date.fromisoformat(day).isoformat()}.xlsx'


def _numeric(value, label):
    if value in ('', None):
        return None
    result = number(value)
    if result is None:
        raise ExcelExportError(f'{label}: invalid numeric value {value!r}.')
    return result


def _date(value, label):
    if not value:
        return None
    try:
        result = date.fromisoformat(value)
        if result < date(1900, 1, 1):
            raise ValueError('before Excel date range')
        return result
    except (ValueError, TypeError) as error:
        raise ExcelExportError(f'{label}: invalid Excel date {value!r}.') from error


def _indexed(rows, standard, label):
    allowed = {normalized_name(n): n for n in standard}
    result = {}
    for i, row in enumerate(rows):
        if not any(v for k, v in row.items() if k != 'det'):
            continue
        key = normalized_name(row['name'])
        if key not in allowed:
            raise ExcelExportError(f'Unknown {label}: {row["name"]!r}. The original template has no matching row.')
        if key in result:
            raise ExcelExportError(f'Duplicate {label}: {row["name"]!r}; cannot map two records to one template row.')
        result[key] = (i, row)
    return result


def _fleet_equipment(label):
    label = re.sub(r'\s*\(L\)\s*$', '', label, flags=re.I)
    aliases = {'Port Main Engine':'PORT ME', 'Port Main Engine Outlet':'PORT ME OUTLET FLOWMETER',
        'Port Center Main Engine':'CENTER ME (P)', 'Port Center Main Engine Outlet':'CENTER ME (P) OUTLET FLOWMETER',
        'Stbd Center Main Engine':'CENTER ME (STBD)', 'Stbd Center Main Engine Outlet':'CENTER ME (STBD) OUTLET FLOWMETER',
        'Stbd Main Engine':'STBD ME', 'Stbd Main Engine Outlet':'STBD ME OUTLET FLOWMETER', 'Bow Thruster':'BOW THRUSTER 1'}
    return aliases.get(label, label.upper())


class VdrExcelExporter:
    def __init__(self, template=None):
        self.template = Path(template) if template is not None else template_path()

    def _template(self):
        try:
            raw = self.template.read_bytes()
        except OSError as error:
            raise ExcelExportError(f'Excel template missing or unreadable: {self.template}. {error}') from error
        if len(raw) != 139111 or sha256(raw).hexdigest() != TEMPLATE_HASH:
            raise ExcelExportError('Excel template hash mismatch. Restore the verified original bundled template.')
        try:
            workbook = load_workbook(BytesIO(raw), data_only=False)
            self._validate_structure(workbook)
            return raw, workbook
        except ExcelExportError:
            raise
        except Exception as error:
            raise ExcelExportError(f'Excel template cannot be opened: {error}') from error

    @staticmethod
    def _validate_structure(workbook):
        if tuple(workbook.sheetnames) != SHEETS:
            raise ExcelExportError('Excel template structure mismatch: sheet order or names differ.')
        if tuple(s.sheet_state for s in workbook) != ('hidden','visible','visible','visible','visible','hidden'):
            raise ExcelExportError('Excel template structure mismatch: sheet visibility differs.')
        checks = {'GDS Meta':{'B9':'Vessel Name','B10':'Date of Hire'},
                  'VDR':{'B14':'HSE PERFORMANCE','B23':'PORT ME','B76':'NABM (bbls)','B77':'PREMIX (bbls)',
                         'W13':'FROM (0000)','AL13':'TO (2400)'},
                  'CORE-CREW':{'C4':'Name','J4':'Comments'}, 'CONTRACTORS':{'D4':'Vendor'},
                  'FLEET MANAGEMENT':{'B6':'Date of Last Containment Loss','B19':'Stern Thruster 2 (L)',
                                      'B38':'Bow Thruster (L)','B60':'Bow Thruster (L)'}}
        for sheet, cells in checks.items():
            for ref, expected in cells.items():
                if workbook[sheet][ref].value != expected:
                    raise ExcelExportError(f'Excel template structure mismatch at {sheet}!{ref}.')

    def values(self, report, workbook, identity=None):
        """Explicit cell map; typed values only. Never reads UI or retains sample outputs."""
        if not report.get('finalized'):
            raise ExcelExportError('Finalize the report before downloading Excel.')
        # Capacity checks precede normalization's generic record-size guard.
        for group, capacity, label in [('acts',90,'Activity Log'),('crew',200,'Core crew'),('ctr',200,'Contractors')]:
            if len(report.get(group, [])) > capacity:
                raise ExcelExportError(f'{label} has {len(report[group])} rows; template capacity = {capacity}.')
        try:
            r = normalize(deepcopy(report))
        except (ValueError, TypeError, KeyError) as error:
            raise ExcelExportError(f'Invalid VDR report: {error}') from error
        errors = validate(r)
        if errors:
            raise ExcelExportError('Report has validation issues. Finalize a valid report before Excel export: '+errors[0]['msg'])
        identity = r.get('identity', {}) if identity is None else identity
        calc = calculate(r); summary = activity_summary(r); visits = derive_location_durations(r['acts'])
        if len(summary['locations']) > 22:
            raise ExcelExportError(f'Location summary has {len(summary["locations"])} locations; template capacity = 22.')
        eq = _indexed(r['eq'], EQUIPMENT, 'equipment')
        bulk = _indexed(r['bulk'], BULK_ROWS, 'bulk item')
        categories = [workbook['VDR'][f'B{row}'].value for row in MOVEMENT_ROWS]
        if any(category not in categories for category in summary['movement']):
            raise ExcelExportError('Unknown activity movement category; no matching template summary row.')
        for key, (_, row) in bulk.items():
            count = len(row['tr']); capacity = 2 if key == normalized_name('FUEL (ltrs)') else 1
            if count > capacity:
                if capacity == 2:
                    raise ExcelExportError(f'FUEL has {count} transfers. Fleet Management template supports a maximum of two fuel bunker-out transfers.')
                raise ExcelExportError(f'{row["name"]} has {count} transfers; template capacity = 1.')
        output = {s:{} for s in SHEETS if s != 'VDR GUIDE'}

        def put(sheet, cell, value):
            # K58:K77 belong to the merged J:K receiver field. Never write a
            # non-anchor merged cell or overwrite the fuel J52:J57 # labels.
            if isinstance(workbook[sheet][cell], MergedCell):
                merged = next(m for m in workbook[sheet].merged_cells.ranges if cell in m)
                cell = merged.start_cell.coordinate
            output[sheet][cell] = value

        def v(cell, value): put('VDR',cell,value)
        def fleet(row, value): put('FLEET MANAGEMENT',f'D{row}',value)
        vessel = identity.get('vessel','').strip(); hire = _date(identity.get('hireDate',''),'Date of hire')
        put('GDS Meta','C9',vessel or None); put('GDS Meta','C10',hire)
        if identity.get('client','').strip(): put('GDS Meta','C11',identity['client'].strip())
        for cell, value in {'B12':_date(r['meta']['date'],'Report date'),'C12':report_number(r,identity),
            'E12':vessel or None,'I12':hire,'J12':r['meta']['captain'],'L12':r['meta']['loc24'],
            'P12':_numeric(r['meta']['fwd'],'Draft FWD'),'T12':_numeric(r['meta']['aft'],'Draft AFT'),
            'E15':hse_perfect_days(r,identity),'E16':r['hse']['inc24']}.items(): v(cell,value)
        for key, cell in [('lti','E17'),('inj','E18'),('incd','E19')]: v(cell,_date(r['hse'][key],key))
        for key, cell in [('fuel','H16'),('water','H17'),('prov','H18')]: v(cell,_numeric(r['end'][key],key+' endurance'))
        v('H19',r['end']['nextProv'])
        for i, wx in enumerate(r['wx'],16):
            for key, col in [('wind','L'),('swell','N'),('sea','P'),('sky','R'),('vis','T'),('temp','U')]:
                v(f'{col}{i}',_numeric(wx[key],f'Weather {key}') if key in ('wind','swell','vis','temp') else wx[key])
        # Clear every mapped slot, including former formulas/shared formula followers.
        for row in range(14,104):
            for col in ('W','X','Y','Z','AE','AG','AH','AI','AK','AL','AM','AN'): v(f'{col}{row}',None)
        for i, (act, interval) in enumerate(zip(r['acts'],calc['actD']),14):
            if not any(act.values()): continue
            for col, value in {'W':hhmm(interval['fromM']),'X':hhmm(interval['toM']),
                'Y':interval['min']/1440,'Z':act['act'],'AE':act['cat'],'AG':act['dp'],
                'AH':_numeric(act['lifts'],'Lifts'),'AI':_numeric(act['pob'],'Non-crew POB')}.items(): v(f'{col}{i}',value)
        for i, visit in enumerate(visits,14):
            for col,key in [('AK','from'),('AL','to'),('AN','location')]: v(f'{col}{i}',visit[key])
            v(f'AM{i}',(minutes(visit['to'])-minutes(visit['from']))/1440)
        for i, name in enumerate(EQUIPMENT,23):
            match = eq.get(normalized_name(name))
            for col,key in [('H','total'),('J','daily'),('L','fm0'),('P','fm24')]:
                v(f'{col}{i}',_numeric(match[1][key],name+' '+key) if match else None)
            v(f'T{i}',calc['eqCons'][match[0]] if match else None)
        v('T45',calc['totalCons'])
        for name, row in BULK_ROWS.items():
            match = bulk.get(normalized_name(name)); item = match[1] if match else None
            for col,key in [('C','open'),('D','rcvFrom'),('E','rcvQty'),('F','rcvB'),('G','rcvA'),('H','rcvTicket'),('I','cons'),('U','remarks')]:
                value = item[key] if item else None
                if col in ('C','E','F','G','I'): value = _numeric(value,name+' '+key)
                if col == 'I' and row == 52: value = calc['totalCons'] if item else None
                v(f'{col}{row}',value)
            v(f'T{row}',calc['bulkClose'][match[0]] if match else None)
            for offset in range(6 if row == 52 else 1):
                tr = item['tr'][offset] if item and offset < len(item['tr']) else None
                for col,key in [('K','to'),('L','qty'),('N','mb'),('P','ma'),('R','tk')]:
                    value = tr[key] if tr else None
                    if col in ('L','N','P'): value = _numeric(value,name+' transfer '+key)
                    v(f'{col}{row+offset}',value)
        for i, category in zip(MOVEMENT_ROWS,categories): v(f'I{i}',summary['movement'].get(category,0)/1440)
        for i in range(94,102): v(f'I{i}',0)
        v('I102',summary['total']/1440); v('I103',summary['dp']/1440)
        for i in range(82,104): v(f'R{i}',None); v(f'T{i}',None)
        for i,(location,duration) in enumerate(summary['locations'].items(),82): v(f'R{i}',location); v(f'T{i}',duration/1440)
        catalogs = json.loads((resource_root()/'vdr/catalogs.json').read_text(encoding='utf-8'))
        countries = {v:k for k,v in catalogs['countryCodes'].items()}
        # Stored ISO country codes use the same names as the native nationality selector.
        for group,sheet,columns in [('crew','CORE-CREW','BCDEFGHIJ'),('ctr','CONTRACTORS','BCDEFG')]:
            for i in range(6,206):
                for col in columns: put(sheet,f'{col}{i}',None)
            people = [p for p in r[group] if any(p.values())]
            for i,p in enumerate(people,6):
                vals = [i-5,p['name'],p['rank'] if group == 'crew' else p['vendor'],_numeric(p['age'],'Age'),countries.get(p['nat'],p['nat']),p['ic']]
                if group == 'crew': vals += [_date(p['signon'],'Crew sign-on'),tour_days(p['signon'],r['meta']['date']),p['comments']]
                for col,value in zip(columns,vals): put(sheet,f'{col}{i}',value)
        for i,key in [(3,'inc24'),(4,'lti'),(5,'inj'),(6,'containment_loss')]: fleet(i,r['hse'][key] if i==3 else _date(r['hse'][key],key))
        for start,key in [(8,'fm0'),(30,'fm24'),(52,'cons')]:
            for i in range(start,start+22):
                name = _fleet_equipment(workbook['FLEET MANAGEMENT'][f'B{i}'].value)
                if name not in EQUIPMENT: raise ExcelExportError(f'Unknown Fleet equipment template label at B{i}.')
                match = eq.get(normalized_name(name))
                fleet(i,(calc['eqCons'][match[0]] if key=='cons' else _numeric(match[1][key],name+' '+key)) if match else None)
        fuel = bulk.get(normalized_name('FUEL (ltrs)')); item = fuel[1] if fuel else None
        fleet(74,calc['totalCons'])
        fleet(75,_numeric(item['rcvQty'],'Fuel received') if item else None); fleet(76,item['rcvFrom'] if item else None)
        for offset, start in [(0,77),(1,79)]:
            tr = item['tr'][offset] if item and len(item['tr'])>offset else None
            fleet(start,_numeric(tr['qty'],'Fuel transferred') if tr else None); fleet(start+1,tr['to'] if tr else None)
        fleet(81,_numeric(item['open'],'Fuel opening') if item else None); fleet(82,calc['bulkClose'][fuel[0]] if fuel else None)
        for i,category in enumerate(categories,84): fleet(i,summary['movement'].get(category,0)/1440)
        return output

    @staticmethod
    def _patch(xml, values, epoch):
        remaining = set(values)
        def replace(match):
            attrs = match['attrs']; ref = re.search(r'\br="([A-Z]+\d+)"',attrs).group(1)
            if ref not in values: return match.group(0)
            remaining.discard(ref); value = values[ref]
            attrs = re.sub(r'\s+t="[^"]*"','',attrs).rstrip()
            # Preserve all attributes/styles but replace formulas and cached values.
            if value in ('',None): return '<c'+attrs+'/>'
            if isinstance(value,date): value = to_excel(value,epoch)
            if isinstance(value,(int,float)):
                if not math.isfinite(value): raise ExcelExportError(f'Non-finite calculated value at {ref}.')
                return '<c'+attrs+'><v>'+str(value)+'</v></c>'
            text = str(value)
            if len(text)>32767 or ILLEGAL_XML.search(text):
                raise ExcelExportError(f'Invalid Excel text at {ref}: control character or cell text exceeds 32767 characters.')
            return '<c'+attrs+' t="inlineStr"><is><t xml:space="preserve">'+escape(text)+'</t></is></c>'
        result = CELL.sub(replace,xml)
        if remaining: raise ExcelExportError('Excel template structure mismatch: mapped cells missing: '+', '.join(sorted(remaining)[:8]))
        return result

    def export(self, report, destination, identity=None):
        destination = Path(destination)
        if destination.suffix.lower() != '.xlsx': raise ExcelExportError('Choose an .xlsx destination.')
        if destination.resolve() == self.template.resolve() or (destination.exists() and self.template.exists() and os.path.samefile(destination,self.template)):
            raise ExcelExportError('Cannot overwrite the source Excel template. Choose another destination.')
        raw, workbook = self._template()
        try:
            output = self.values(report,workbook,identity)
            buffer = BytesIO()
            with ZipFile(BytesIO(raw)) as source, ZipFile(buffer,'w') as target:
                for info in source.infolist():
                    value = source.read(info.filename)
                    match = re.fullmatch(r'xl/worksheets/sheet([1-6])\.xml',info.filename)
                    if match and SHEETS[int(match[1])-1] in output:
                        value = self._patch(value.decode('utf-8'),output[SHEETS[int(match[1])-1]],workbook.epoch).encode('utf-8')
                    target.writestr(info,value)
            payload = buffer.getvalue()
        finally:
            workbook.close()
        temp = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.vdr-excel-',suffix='.xlsx',dir=destination.parent,delete=False) as stream:
                temp = Path(stream.name); stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp,destination)
        except OSError as error:
            raise ExcelExportError(f'Cannot save Excel report to {destination}. Check folder permissions and close the destination in Excel. {error}') from error
        finally:
            if temp is not None and temp.exists(): temp.unlink()
        return destination
