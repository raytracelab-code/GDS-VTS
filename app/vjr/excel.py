"""Original-template export: replace cell values, preserve all other OOXML bytes.

Critical calculations and linked operational values are materialized. Reference,
title, validation and date-relative guide formulas remain in the template.
"""
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import sys
import tempfile
from xml.sax.saxutils import escape
from zipfile import ZipFile
from openpyxl import load_workbook
from openpyxl.utils.datetime import to_excel
from .schema import (SHEETS, META, GENERAL, DEPARTURE, ARRIVAL, TABLES, DECK, CAPACITIES,
                     INVENTORY_NAMES)
from .model import normalize, with_identity, arrival_fields
from .validation import validate, normalized_name
from .calculations import numeric, working_days, deck_values, deck_totals

TEMPLATE_HASH = '04e1ad4b53066f05475c962f05ac39f918e579ac1ee5b1bb0dd5f7634961d4e8'
CELL = re.compile(r'<c\b(?P<attrs>[^>]*?)(?:\s*/>|>(?P<body>.*?)</c>)',re.S)


class ExcelExportError(ValueError):
    """An invalid draft, changed template or unsavable destination."""


def template_path():
    root = Path(sys._MEIPASS)/'app/resources' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'resources'
    return root/'templates/vjr_template.xlsx'


def suggested_filename(vessel, departure_date):
    def safe(value):
        return re.sub(r'[<>:"/\\|?*\x00-\x1f\s]','_',str(value)).strip(' ._')[:100]
    return 'VJR_%s_%s.xlsx' % (safe(vessel) or 'Vessel',safe(departure_date) or 'Undated')


def typed(value, kind):
    if value in ('',None):
        return None
    if kind == 'date':
        return date.fromisoformat(value)
    if kind not in ('text','fixed','automatic','ns','ew','compass','time','derived'):
        return numeric(value)
    return value


class VjrExcelExporter:
    def __init__(self, template=None, photo_root=None):
        self.template = Path(template) if template else template_path()
        self.photo_root = photo_root

    def _template(self):
        raw = self.template.read_bytes()
        if sha256(raw).hexdigest() != TEMPLATE_HASH:
            raise ExcelExportError('The bundled VJR template has changed. Restore the pristine template.')
        book = load_workbook(BytesIO(raw))
        if tuple(book.sheetnames) != SHEETS:
            book.close()
            raise ExcelExportError('Unexpected VJR template sheet structure')
        # Capacities come from template numbering and validation ranges, not max_row
        # (which includes formatting far below the actual tables).
        for group,sheet in (('crew',2),('contractors',3),('waypoints',4)):
            rows = [r for r in range(8,book[SHEETS[sheet]].max_row+1)
                    if book[SHEETS[sheet]].cell(r,2).value == r-7]
            if rows != list(range(8,8+CAPACITIES[group])):
                raise ExcelExportError('Unexpected '+group+' template capacity')
        if not any(str(v.sqref)=='B8:B107' for v in book[SHEETS[7]].data_validations.dataValidation):
            raise ExcelExportError('Unexpected voyage progress template capacity')
        return raw,book

    def values(self, report, book, identity=None, generated=None):
        report = with_identity(normalize(report),identity or {})
        errors = validate(report)
        if errors:
            raise ExcelExportError('Please correct VJR validation errors:\n'+'\n'.join(errors[:20]))
        result = {sheet:{} for sheet in SHEETS if sheet != SHEETS[1]}
        def put(sheet,ref,value):
            result[sheet][ref] = value
        def fields(sheet,row,schema):
            for key,_,ref,kind in schema:
                value = row.get(key,'')
                if kind == 'time':
                    hour,minute = ref.split('/')
                    put(sheet,hour,value.split(':')[0] if value else None)
                    put(sheet,minute,value.split(':')[1] if value else None)
                else:
                    put(sheet,ref,typed(value,kind))
        meta = dict(report['meta'],generated=generated or datetime.now(timezone.utc).isoformat())
        fields(SHEETS[0],meta,META)
        for group,sheet in (('crew',2),('contractors',3),('waypoints',4),('progress',7)):
            schema = TABLES[group]
            for index in range(CAPACITIES[group]):
                rowno = index+8
                row = report[group][index] if index<len(report[group]) else {}
                if group!='progress':
                    put(SHEETS[sheet],'B'+str(rowno),index+1 if row else None)
                for key,_,col,kind in schema:
                    value = row.get(key,'')
                    if key == 'working_days':
                        value = working_days(row.get('sign_on',''),report['departure']['report_date'],report['arrival']['report_date'])
                    put(SHEETS[sheet],col+str(rowno),typed(value,kind))
        for group,sheet in (('departure',SHEETS[5]),('arrival',SHEETS[6])):
            row = report[group] if group=='departure' else arrival_fields(report)
            fields(sheet,row,GENERAL+DEPARTURE+ARRIVAL)
            # These formula caches contain the old client/report dates. A snapshot
            # must also be correct in readers that do not recalculate formulas.
            put(sheet,'D2',(str(meta.get('client','')).upper()+' VESSEL '+group.upper()+' REPORT ').lstrip())
            put(sheet,'N3',str(meta.get('client','')).upper()+'-'+str(meta.get('reader_version','')))
            for key,cell in (('report_date','J10'),('departure_date','J18'),('arrival_date','J24')):
                value = row.get(key,'')
                delta = (date.fromisoformat(value)-date.today()).days if value else None
                annotation = None if delta is None else 'TODAY' if delta==0 else (
                    'IN %s DAY(S)' % delta if delta>0 else '%s DAY(S) AGO' % -delta)
                put(sheet,cell,annotation)
            for key,cell in (('vessel','D6'),('imo','D7'),('capacity','D8')):
                put(sheet,cell,typed(meta.get(key,''),'number' if key=='capacity' else 'text'))
            for cell,value in (('D15','Crew (%s)' % len(report['crew'])),('E15',len(report['crew'])),
                               ('F15','Contr (%s)' % len(report['contractors'])),('G15',len(report['contractors']))):
                put(sheet,cell,value)
            for index in range(5):
                deck = row['deck'][index] if index<len(row['deck']) else {}
                values = dict(deck,**deck_values(deck,meta.get('capacity','')))
                put(sheet,'B'+str(32+index),index+1)
                for key,_,col,kind in DECK:
                    put(sheet,col+str(32+index),typed(values.get(key,''),kind))
            totals = deck_totals(row['deck'],meta.get('capacity',''))
            for key,col in (('lifts','D'),('total','H'),('utilization','I'),('weight','J')):
                put(sheet,col+'37',totals[key])
            inventory = {normalized_name(item['product']):item for item in row['inventory']}
            # Discover exact product rows by normalized name; never zip current rows.
            destinations = {normalized_name(book[sheet]['B'+str(i)].value):i for i in range(41,58)}
            for name in INVENTORY_NAMES:
                index = destinations.get(normalized_name(name))
                if index is None:
                    raise ExcelExportError('Template inventory product missing: '+name)
                item = inventory.get(normalized_name(name),{})
                put(sheet,'D'+str(index),typed(item.get('quantity',''),'number'))
                put(sheet,'I'+str(index),item.get('remarks',''))
                # Product names and units remain exactly as supplied in the template.
        return result

    @staticmethod
    def _patch(xml, values, epoch):
        remaining = set(values)
        def replace(match):
            attrs = match['attrs']
            ref = re.search(r'\br="([A-Z]+\d+)"',attrs).group(1)
            if ref not in values:
                return match.group(0)
            remaining.discard(ref)
            value = values[ref]
            attrs = re.sub(r'\s+t="[^"]*"','',attrs).rstrip()
            if value in ('',None):
                return '<c'+attrs+'/>'
            if isinstance(value,date):
                value = to_excel(value,epoch)
            if isinstance(value,(int,float)):
                return '<c'+attrs+'><v>'+str(value)+'</v></c>'
            return '<c'+attrs+' t="inlineStr"><is><t xml:space="preserve">'+escape(str(value))+'</t></is></c>'
        result = CELL.sub(replace,xml)
        if remaining:
            raise ExcelExportError('Template mapped cells missing: '+', '.join(sorted(remaining)[:10]))
        return result

    def export(self, report, destination, identity=None):
        destination = Path(destination)
        if destination.suffix.lower()!='.xlsx':
            raise ExcelExportError('Choose an .xlsx destination')
        if destination.resolve()==self.template.resolve() or (destination.exists() and os.path.samefile(str(destination),str(self.template))):
            raise ExcelExportError('Cannot overwrite the source template. Choose another destination.')
        if destination.exists() and sha256(destination.read_bytes()).hexdigest()==TEMPLATE_HASH:
            raise ExcelExportError('Cannot overwrite a pristine source template copy. Choose another destination.')
        try:
            raw,book = self._template()
            try:
                values = self.values(report,book,identity)
                buffer = BytesIO()
                with ZipFile(BytesIO(raw)) as source, ZipFile(buffer,'w') as target:
                    from .photo_excel import photo_parts
                    from .photo_storage import PhotoError
                    try:
                        images = photo_parts(source,book,report,self.photo_root)
                    except PhotoError as error:
                        raise ExcelExportError(str(error)) from error
                    for info in source.infolist():
                        payload = images.get(info.filename,source.read(info.filename))
                        match = re.fullmatch(r'xl/worksheets/sheet([1-8])\.xml',info.filename)
                        if match and SHEETS[int(match[1])-1] in values:
                            payload = self._patch(payload.decode('utf-8'),values[SHEETS[int(match[1])-1]],book.epoch).encode('utf-8')
                        target.writestr(info,payload)
                    for name,payload in images.items():
                        if name not in source.namelist():
                            target.writestr(name,payload)
            finally:
                book.close()
            temp = None
            try:
                with tempfile.NamedTemporaryFile(prefix='.vjr-excel-',suffix='.xlsx',dir=str(destination.parent),delete=False) as stream:
                    temp = stream.name
                    stream.write(buffer.getvalue())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp,str(destination))
            finally:
                if temp and os.path.exists(temp):
                    os.unlink(temp)
        except OSError as error:
            raise ExcelExportError('Cannot save VJR Excel. Check folder permissions and close the destination in Excel. '+str(error)) from error
        return destination
