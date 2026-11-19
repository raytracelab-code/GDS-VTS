from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import json
import re
from zipfile import ZipFile
import pytest
from openpyxl import load_workbook
from app.vjr.calculations import working_days, decimal_to_dms, deck_values, deck_totals
from app.vjr.model import new_report, normalize, blank_row
from app.vjr.schema import CAPACITIES, TABLES, SHEETS
from app.vjr.store import VjrStore
from app.vjr.validation import validate, validate_value
from app.vjr.excel import VjrExcelExporter, ExcelExportError, template_path, TEMPLATE_HASH, CELL, suggested_filename
from vjr_fixture import full_report


@pytest.fixture
def exported(tmp_path):
    report = full_report(); path = tmp_path/'report.xlsx'
    VjrExcelExporter().export(report,path)
    book = load_workbook(path)
    yield report,path,book
    book.close()


def test_working_days():
    assert working_days('2026-11-01','2026-11-18')==18
    assert working_days('2026-11-01','2026-11-18','2026-11-19')==19
    assert working_days('2024-02-28','2024-03-01')==3
    assert working_days('','2026-11-18') is None
    assert working_days('2026-11-01','') is None
    with pytest.raises(ValueError):
        working_days('invalid','2026-11-18')


@pytest.mark.parametrize('value,latitude,expected',[(0,True,(0,0,0,'N')),(-5.5,True,(5,30,0,'S')),
    (102.25,False,(102,15,0,'E')),(-180,False,(180,0,0,'W')),(90,True,(90,0,0,'N')),
    (89.999999999999,True,(90,0,0,'N'))])
def test_decimal_to_dms(value,latitude,expected):
    dms = decimal_to_dms(value,latitude)
    assert tuple(dms[k] for k in ('degree','minute','second','direction'))==expected


@pytest.mark.parametrize('value,latitude',[(91,True),(181,False),('nan',True),('',True)])
def test_bad_decimal_coordinates(value,latitude):
    with pytest.raises(ValueError):
        decimal_to_dms(value,latitude)


def test_deck_calculations():
    row = dict(ops='10',fso='20',drilling='30',lifts='2',weight='50')
    assert deck_values(row,'1000')==dict(total=60,utilization=.06)
    assert deck_values(row,'0')['utilization'] is None
    assert deck_values(row,'')['utilization'] is None
    assert deck_values({},'1000')==dict(total=None,utilization=None)
    assert deck_totals([row,row],'1000')==dict(ops=20,fso=40,drilling=60,lifts=4,weight=100,total=120,utilization=.12)


@pytest.mark.parametrize('group',list(TABLES))
def test_row_edit_delete_history_autosave(tmp_path,group):
    path = tmp_path/'vjr.json'; store = VjrStore(path)
    store.mutate(lambda r:r[group].append(blank_row(TABLES[group])))
    key = TABLES[group][0][0]
    store.mutate(lambda r:r[group][0].update({key:'edited'}))
    assert VjrStore(path).report[group][0][key]=='edited'
    store.mutate(lambda r:r[group].pop())
    assert not VjrStore(path).report[group]
    assert store.undo() and store.report[group][0][key]=='edited'
    assert store.redo() and not store.report[group]


def test_corrupt_store_is_preserved(tmp_path):
    # GDS-AUDIT-003: the damaged file is kept, the user is told, and editing continues (no dead end).
    path = tmp_path/'bad.json'; path.write_text('{broken',encoding='utf-8')
    store = VjrStore(path)
    assert store.notices and 'no usable backup' in store.notices[0]
    damaged = list(tmp_path.glob('bad.json.damaged-*'))
    assert len(damaged)==1 and damaged[0].read_text(encoding='utf-8')=='{broken'
    store.mutate(lambda r:r['meta'].update(vessel='New'))
    assert store.report['meta']['vessel']=='New' and damaged[0].read_text(encoding='utf-8')=='{broken'


def test_store_write_failure_rolls_back(tmp_path,monkeypatch):
    store = VjrStore(tmp_path/'report.json')
    def failure(*args):
        raise OSError('disk full')
    monkeypatch.setattr('app.vjr.store.os.replace',failure)
    with pytest.raises(OSError):
        store.mutate(lambda r:r['meta'].update(vessel='Unsaved'))
    assert store.report['meta']['vessel']=='' and not store.undo_stack
    assert not list(tmp_path.glob('.vjr-*'))


def test_normalization_defaults_without_truncation():
    report = normalize(dict(departure=dict(deck=[dict(ops='2')],inventory=[])))
    assert len(report['departure']['deck'])==5 and len(report['departure']['inventory'])==17
    assert report['departure']['deck'][0]['ops']=='2'
    with pytest.raises(ValueError):
        normalize(dict(schemaVersion=2))


@pytest.mark.parametrize('kind,value',[('date','2026-02-30'),('date','20261119'),('time','24:00'),
    ('time','9:05'),('hour','24'),('minute','60'),('lat_degree','91'),('lon_degree','181'),
    ('second','60'),('ns','E'),('ew','N'),('course','360'),('number','-1'),('number','nan'),
    ('number','inf'),('age','-1'),('age','2.5'),('count','1.1'),('text','=x\x00')])
def test_invalid_fields(kind,value):
    with pytest.raises((ValueError,TypeError)):
        validate_value(value,kind)


def test_coordinate_boundaries_and_incomplete_rows():
    report = full_report(); report['waypoints'][0]['lat_degree']='90'
    assert any('must be zero' in error for error in validate(report))
    report['waypoints'][0].update(lat_minute='0',lat_second='0')
    assert not validate(report)
    report['waypoints'][0]['lat_direction']=''
    assert any('complete all' in error for error in validate(report))
    report['progress'][0]['minute']=''
    assert any('both hour and minute' in error for error in validate(report))


@pytest.mark.parametrize('group,capacity',list(CAPACITIES.items()))
def test_capacity_exact_and_overflow(tmp_path,group,capacity):
    report = required_minimum(new_report()); report[group]=[blank_row(TABLES[group]) for _ in range(capacity)]
    key = 'name' if group in ('crew','contractors') else 'remarks'
    report[group][-1][key]='Last supported row'
    exporter = VjrExcelExporter(); path=tmp_path/'full.xlsx'; exporter.export(report,path)
    assert path.exists()
    book=load_workbook(path)
    sheet,cell = dict(crew=(SHEETS[2],'C207'),contractors=(SHEETS[3],'C207'),
                     waypoints=(SHEETS[4],'S37'),progress=(SHEETS[7],'AA107'))[group]
    assert book[sheet][cell].value=='Last supported row'
    book.close()
    original = path.read_bytes(); report[group].append(blank_row(TABLES[group]))
    with pytest.raises(ExcelExportError,match='capacity'):
        exporter.export(report,path)
    assert path.read_bytes()==original


def test_meta_and_people_exact_mapping(exported):
    report,path,book = exported; meta = book[SHEETS[0]]
    assert [meta['D'+str(i)].value for i in (7,8,9,11,12,13,14,26,27)]==[
        'VJR-42','Vessel Journey Report','CLIENT-7','Acceptance Vessel','1234567',1000,'Acceptance Client','2','1']
    assert datetime.fromisoformat(meta['D10'].value)
    crew = book[SHEETS[2]]; contractor = book[SHEETS[3]]
    assert [crew.cell(8,c).value for c in range(2,11)]==[1,'Captain Example','MASTER',45,'Bangladesh','P001',datetime(2026,11,1),19,'First crew']
    assert crew['I9'].value==10
    assert [contractor.cell(8,c).value for c in range(2,9)]==[1,'Contractor One','Vendor A',29,'Malaysia','C001','Inspection']
    assert crew['C10'].value is None and crew['I10'].value is None and contractor['C10'].value is None


def test_waypoints_and_progress_exact_mapping(exported):
    _,_,book=exported; wp=book[SHEETS[4]]; progress=book[SHEETS[7]]
    assert [wp[col+'8'].value for col in ('B','C','E','G','I','J','L','N','P','Q','R','S')]==[
        1,5,20,30.25,'N',102,40,15.5,'E',123.45,8.5,'Waypoint 1']
    assert wp['I9'].value=='S' and wp['P9'].value=='W' and wp['S10'].value=='Waypoint 3'
    assert [progress[col+'8'].value for col in ('B','C','D','E','G','I','K','L','N','P','R','S','T','U','V','W','X','Y','Z','AA')]==[
        datetime(2026,11,18),10,5,5,20,30.25,'N',102,40,15.5,'E',123.45,8.5,'Rain',6,12.5,'NE',1.25,'E','Progress 1']
    assert progress['C10'].value==12 and progress['AA10'].value=='Progress 3'
    assert wp['C11'].value is None and progress['B11'].value is None


def test_departure_and_arrival_exact_mapping(exported):
    _,_,book=exported; dep=book[SHEETS[5]]; arr=book[SHEETS[6]]
    expected = dict(D6='Acceptance Vessel',D7='1234567',D8=1000,D9='Captain Example',
        D10=datetime(2026,11,18),D11='Officer Example',I11='+880100',D12='Captain Example',I12='+880200',
        E13=4.1,G13=4.2,I13=4.3,E14=100,G14=200,I14=300,D15='Crew (2)',E15=2,F15='Contr (2)',G15=2,
        D18=datetime(2026,11,18),D19='09',F19='05',D20='Supply Base',D21='Departed safely',
        D24=datetime(2026,11,19),D25='10',F25='30',D26='Platform Alpha',D27='Estimated arrival')
    for ref,value in expected.items():
        assert dep[ref].value==value,ref
        if ref not in ('D10','D24','D25','F25','D27'):
            assert arr[ref].value==value,ref
    assert [arr[ref].value for ref in ('D10','D24','D25','F25','D27')]==[
        datetime(2026,11,19),datetime(2026,11,19),'11','45','Arrived safely']
    for sheet,offset in ((dep,0),(arr,10)):
        for i in range(5):
            assert [sheet[col+str(32+i)].value for col in ('B','C','D','E','F','G','H','I','J','K')]==[
                i+1,'Platform '+str(i+1),i+1+offset,10+offset,20,30,60+offset,(60+offset)/1000,40+i+offset,
                ('departure' if offset==0 else 'arrival')+' deck '+str(i+1)]
        assert [sheet[ref].value for ref in ('D37','H37','I37','J37')]==[15+5*offset,300+5*offset,(300+5*offset)/1000,210+5*offset]
        for i in range(17):
            assert sheet['D'+str(41+i)].value==100+i+offset
            assert sheet['I'+str(41+i)].value==('departure' if offset==0 else 'arrival')+' inventory '+str(i+1)


def test_inventory_is_matched_by_normalized_name(tmp_path):
    report=full_report(); report['departure']['inventory'].reverse()
    report['departure']['inventory'][-1]['product']='  fuel  '
    path=tmp_path/'report.xlsx'; VjrExcelExporter().export(report,path)
    book=load_workbook(path); assert book[SHEETS[5]]['D41'].value==100; book.close()
    report['departure']['inventory'].append(dict(product='UNKNOWN',quantity='1'))
    with pytest.raises(ExcelExportError,match='unknown or duplicate'):
        VjrExcelExporter().export(report,path)


def test_preservation_all_zip_parts_unmapped_cells_and_photos(exported):
    report,path,book = exported; exporter=VjrExcelExporter()
    raw,source_book=exporter._template(); mapping=exporter.values(report,source_book)
    source_book.close()
    with ZipFile(BytesIO(raw)) as source,ZipFile(path) as target:
        assert source.namelist()==target.namelist()
        for name in source.namelist():
            before=source.read(name); after=target.read(name)
            match=re.fullmatch(r'xl/worksheets/sheet([1-8])\.xml',name)
            if not match or SHEETS[int(match[1])-1] not in mapping:
                assert before==after,name
                continue
            cells=mapping[SHEETS[int(match[1])-1]]
            def mask(m):
                ref=re.search(r'\br="([A-Z]+\d+)"',m['attrs']).group(1)
                return '<mapped ref="'+ref+'"/>' if ref in cells else m.group(0)
            # This proves every unmapped cell (including photo L9:U27), row/col
            # dimension, merge, validation and print setting is byte-identical.
            assert CELL.sub(mask,before.decode())==CELL.sub(mask,after.decode()),name
        assert [name for name in source.namelist() if name.startswith('xl/media/')]==[
            name for name in target.namelist() if name.startswith('xl/media/')]
        for number in (6,7):
            def photo(xml):
                return [m.group(0) for m in CELL.finditer(xml) if re.search(
                    r'\br="(?:[L-U])(?:9|1\d|2[0-7])"',m['attrs'])]
            name='xl/worksheets/sheet%s.xml' % number
            assert photo(source.read(name).decode())==photo(target.read(name).decode())
    assert book.sheetnames==list(SHEETS) and book[SHEETS[0]].sheet_state=='hidden'
    assert sha256(template_path().read_bytes()).hexdigest()==TEMPLATE_HASH


def test_empty_export_clears_every_operational_destination(tmp_path):
    path=tmp_path/'blank.xlsx'; report=required_minimum(new_report()); exporter=VjrExcelExporter(); exporter.export(report,path)
    book=load_workbook(path); raw,source=exporter._template()
    mapping=exporter.values(report,source); source.close()
    for sheet,values in mapping.items():
        for ref,value in values.items():
            if sheet==SHEETS[0] and ref=='D10':
                continue
            cell=book[sheet][ref].value
            if isinstance(cell,datetime) and isinstance(value,date) and not isinstance(value,datetime): cell=cell.date()
            assert cell==(None if value=='' else value),(sheet,ref)
    text=' '.join(str(c.value) for sheet in book if sheet.title!=SHEETS[1] for row in sheet for c in row if c.value and c.data_type!='f')
    for stale in ('JM Abadi','HIBISCUS','9688788','AMIRSHAHRIZA','TUNE LIGHT CEMENT','TBSB, FAIRWAY BUOY'):
        assert stale not in text
    book.close()
    cached=load_workbook(path,data_only=True)
    assert 'HIBISCUS' not in cached[SHEETS[5]]['D2'].value
    assert cached[SHEETS[5]]['J10'].value is None
    cached.close()


def test_export_guards_source_filename_and_identity(tmp_path):
    exporter=VjrExcelExporter()
    with pytest.raises(ExcelExportError,match='source template'):
        exporter.export(new_report(),template_path())
    assert suggested_filename('A:/B*?','2026-11-19')=='VJR_A__B_2026-11-19.xlsx'
    path=tmp_path/'identity.xlsx'; report=full_report()
    exporter.export(report,path,dict(vessel='Configured Vessel',client='',capacity=''))
    book=load_workbook(path)
    assert book[SHEETS[0]]['D11'].value=='Configured Vessel'
    assert book[SHEETS[0]]['D14'].value is None and book[SHEETS[5]]['I32'].value is None
    book.close()


def required_minimum(report):
    """Smallest report that passes the required-field rules (GDS-AUDIT-010)."""
    report['meta']['vessel']='Minimum Vessel'
    report['departure'].update(departure_date='2026-11-18',departure_location='Supply Base')
    return report
