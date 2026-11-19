"""Original-template snapshots: independent openpyxl reads and byte-level preservation."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import json
import pytest
from openpyxl import load_workbook
from app.vdr.excel import (BULK_ROWS, EQUIPMENT, ExcelExportError, MOVEMENT_ROWS, SHEETS,
    TEMPLATE_HASH, VdrExcelExporter, suggested_filename, template_path)
from app.vdr.model import blank_row, hse_perfect_days, report_number, validate
from app.ui.pages.vdr.sections import CATALOG
from app.ui.pages.vdr.workspace import VdrPage
from app.vdr.store import ReportStore
from test_vdr import fixture_report


def full_excel_report():
    """Test/evidence data only; production never imports this module."""
    r = fixture_report('2026-11-19')
    r['identity'] = dict(vessel='TEST EXPORT VESSEL',hireDate='2026-01-01',client='TEST CLIENT')
    r['hse'].update(inc24='No incidents',lti='2026-11-01',inj='2026-11-02',incd='2026-11-03',containment_loss='2026-11-04')
    r['end'].update(fuel='12',water='13',prov='14',nextProv='Next port on 22 Nov')
    for i,wx in enumerate(r['wx']): wx.update(wind=str(10+i),swell=str(1+i),sea='SLIGHT',sky='CLEAR',vis='10',temp=str(30+i))
    r['acts'] = [dict(blank_row('acts'),to=to,loc=loc,act=f'TEST OPERATION {i+1}',cat=CATALOG['movement'][i],
                      dp='Y' if i in (0,2) else 'N',lifts=str(i+1),pob=str(i+2))
        for i,(to,loc) in enumerate([('0400','DUYONG'),('0800','DUYONG'),('1200','DUYONG'),('1800','JAMPUK'),('2400','JAMPUK')])]
    r['eq'] = [dict(blank_row('eq',name),total=str(10000+i),daily=str(10+i),fm0=str(1000+i*100),fm24=str(1020+i*101))
               for i,name in enumerate(EQUIPMENT)][::-1]
    r['bulk'] = []
    for i,name in enumerate(BULK_ROWS):
        row = blank_row('bulk',name)
        row.update(open=str(1000+i),rcvQty=str(100+i),cons=str(10+i),rcvFrom=f'TEST DONOR {i}',
                   rcvB=str(200+i),rcvA=str(300+i),rcvTicket=f'RECEIPT-{i}',remarks=f'TEST REMARK {i}',det=True)
        row['tr'] = [dict(to=f'TEST RECEIVER {i}',qty=str(1+i),mb='400',ma=str(401+i),tk=f'TRANSFER-{i}')]
        if i == 0:
            row['tr'] = [dict(to='FUEL RECEIVER ONE',qty='10',mb='400',ma='410',tk='FUEL-1'),
                         dict(to='FUEL RECEIVER TWO',qty='15',mb='410',ma='425',tk='FUEL-2')]
        r['bulk'].append(row)
    r['bulk'].reverse()
    r['crew'] = [dict(blank_row('crew'),name=f'TEST CREW {i}',rank='Master',age=str(30+i),nat='my',
                     ic=f'CREW-ID-{i}',signon=f'2026-11-0{i+1}',comments=f'Crew comment {i}') for i in range(2)]
    r['ctr'] = [dict(blank_row('ctr'),name=f'TEST CONTRACTOR {i}',vendor=f'TEST VENDOR {i}',age=str(40+i),nat='bd',ic=f'CTR-ID-{i}') for i in range(2)]
    r.update(finalized=True,finalizedAt='2026-11-19T00:00:00+00:00')
    assert not validate(r)
    return r


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    path = tmp_path_factory.mktemp('excel')/'full.xlsx'
    report = full_excel_report(); VdrExcelExporter().export(report,path)
    return report,path


def duration(cell):
    value=cell.value
    if isinstance(value,timedelta): return round(value.total_seconds()/60)
    if hasattr(value,'hour'): return value.hour*60+value.minute
    return round(value*1440)


def test_exact_template_and_preservation(exported):
    _,path=exported; source=template_path().read_bytes()
    assert len(source)==139111 and sha256(source).hexdigest()==TEMPLATE_HASH
    with ZipFile(BytesIO(source)) as original, ZipFile(path) as output:
        assert original.namelist()==output.namelist()
        changed={n for n in original.namelist() if original.read(n)!=output.read(n)}
        assert changed=={f'xl/worksheets/sheet{i}.xml' for i in (1,3,4,5,6)}
        assert original.read('xl/worksheets/sheet2.xml')==output.read('xl/worksheets/sheet2.xml')
    before=load_workbook(BytesIO(source)); after=load_workbook(path)
    assert tuple(after.sheetnames)==SHEETS
    for left,right in zip(before,after):
        assert left.sheet_state==right.sheet_state
        assert str(left.merged_cells)==str(right.merged_cells)
        assert str(left.print_options)==str(right.print_options)
        assert str(left.page_setup)==str(right.page_setup)
        assert str(left.page_margins)==str(right.page_margins)
        assert str(left.protection)==str(right.protection)
        assert left.print_area==right.print_area
        assert {k:str(v) for k,v in left.row_dimensions.items()}=={k:str(v) for k,v in right.row_dimensions.items()}
        assert {k:str(v) for k,v in left.column_dimensions.items()}=={k:str(v) for k,v in right.column_dimensions.items()}
        for row in left:
            for cell in row:
                assert cell._style==right[cell.coordinate]._style
    assert template_path().read_bytes()==source


def test_main_hse_endurance_weather_and_metadata(exported):
    _,path=exported; w=load_workbook(path,data_only=True);s=w['VDR']
    assert s['B12'].value==datetime(2026,11,19) and s['C12'].value==323
    assert s['E12'].value=='TEST EXPORT VESSEL' and s['I12'].value==datetime(2026,1,1)
    assert s['J12'].value=='Test Captain' and s['L12'].value=='LABUAN'
    assert (s['P12'].value,s['T12'].value)==(2.5,2.7)
    assert s['E15'].value==15 and s['E16'].value=='No incidents'
    assert [s[f'E{i}'].value for i in (17,18,19)]==[datetime(2026,11,i) for i in (1,2,3)]
    assert [s[f'H{i}'].value for i in range(16,20)]==[12,13,14,'Next port on 22 Nov']
    assert w['GDS Meta']['C9'].value=='TEST EXPORT VESSEL' and w['GDS Meta']['C10'].value==datetime(2026,1,1)
    for i in range(4):
        assert [s[f'{col}{16+i}'].value for col in ('L','N','P','R','T','U')]==[10+i,1+i,'SLIGHT','CLEAR',10,30+i]
        assert s[f'K{16+i}'].value==('0000H','0600H','1200H','1800H')[i]


def test_activities_contiguous_locations_and_summaries(exported):
    _,path=exported;s=load_workbook(path,data_only=True)['VDR']
    assert [s['W14'].value,s['X14'].value,s['Z14'].value,s['AG14'].value,s['AH14'].value,s['AI14'].value]==['0000','0400','TEST OPERATION 1','Y',1,2]
    assert duration(s['Y14'])==240
    assert [s[f'{c}14'].value for c in ('AK','AL','AN')]==['0000','1200','DUYONG']
    assert [s[f'{c}15'].value for c in ('AK','AL','AN')]==['1200','2400','JAMPUK']
    assert duration(s['AM14'])==duration(s['AM15'])==720
    assert [s[f'R{i}'].value for i in (82,83)]==['DUYONG','JAMPUK']
    assert duration(s['T82'])==duration(s['T83'])==720
    assert [duration(s[f'I{i}']) for i in MOVEMENT_ROWS]==[240,240,240,360,360,0,0,0,0,0]
    assert duration(s['I102'])==1440 and duration(s['I103'])==480
    assert all(duration(s[f'I{i}'])==0 for i in range(94,102))


def test_all_equipment_and_fleet_blocks_name_matching(exported):
    _,path=exported;w=load_workbook(path,data_only=True);s=w['VDR'];f=w['FLEET MANAGEMENT']
    for i,name in enumerate(EQUIPMENT):
        row=23+i
        assert [s[f'{c}{row}'].value for c in ('H','J','L','P','T')]==[10000+i,10+i,1000+i*100,1020+i*101,20+i]
    # Fleet order has STBD stern before PORT stern and a shortened Bow Thruster label.
    assert f['D16'].value==1800 and f['D38'].value==1828 and f['D60'].value==28
    assert f['D19'].value==2200 and f['D20'].value==2100
    assert f['D41'].value==2232 and f['D42'].value==2131
    assert f['D63'].value==32 and f['D64'].value==31
    assert s['T45'].value==671 and f['D74'].value==671
    # Every cell in all three blocks is a materialized numeric value.
    assert all(isinstance(f[f'D{i}'].value,(float,int)) for i in range(8,74))
    for offset,i in enumerate([*range(11),12,11,*range(13,22)]):
        assert f[f'D{8+offset}'].value==1000+i*100
        assert f[f'D{30+offset}'].value==1020+i*101
        assert f[f'D{52+offset}'].value==20+i


def test_all_bulk_including_nabm_premix_and_fuel_fleet(exported):
    _,path=exported;w=load_workbook(path,data_only=True);s=w['VDR'];f=w['FLEET MANAGEMENT']
    for i,(name,row) in enumerate(BULK_ROWS.items()):
        assert [s[f'{c}{row}'].value for c in ('C','D','E','F','G','H','U')]==[1000+i,f'TEST DONOR {i}',100+i,200+i,300+i,f'RECEIPT-{i}',f'TEST REMARK {i}']
        if row!=52:
            assert s[f'I{row}'].value==10+i
            assert s[f'J{row}'].value==f'TEST RECEIVER {i}'
            assert [s[f'{c}{row}'].value for c in ('L','N','P','R')]==[1+i,400,401+i,f'TRANSFER-{i}']
            assert s[f'T{row}'].value==1089
    assert s['I52'].value==671 and s['T52'].value==404
    assert [s[f'K{i}'].value for i in (52,53)]==['FUEL RECEIVER ONE','FUEL RECEIVER TWO']
    assert [s[f'J{i}'].value for i in range(52,58)]==[f'#{i}' for i in range(1,7)]
    assert [f[f'D{i}'].value for i in range(75,83)]==[100,'TEST DONOR 0',10,'FUEL RECEIVER ONE',15,'FUEL RECEIVER TWO',1000,404]


def test_crew_contractors_fleet_hse_and_movement(exported):
    _,path=exported;w=load_workbook(path,data_only=True)
    for i in range(2):
        assert [w['CORE-CREW'][f'{c}{6+i}'].value for c in 'BCDEFGHIJ']==[i+1,f'TEST CREW {i}','Master',30+i,'Malaysia',f'CREW-ID-{i}',datetime(2026,11,i+1),19-i,f'Crew comment {i}']
        assert [w['CONTRACTORS'][f'{c}{6+i}'].value for c in 'BCDEFG']==[i+1,f'TEST CONTRACTOR {i}',f'TEST VENDOR {i}',40+i,'Bangladesh',f'CTR-ID-{i}']
    f=w['FLEET MANAGEMENT']
    assert [f[f'D{i}'].value for i in range(3,7)]==['No incidents',datetime(2026,11,1),datetime(2026,11,2),datetime(2026,11,4)]
    assert [duration(f[f'D{i}']) for i in range(84,94)]==[240,240,240,360,360,0,0,0,0,0]
    assert all('#REF!' not in str(c.value) for sheet in w for row in sheet for c in row)


def test_stale_sample_destinations_cleared_and_missing_config_blocked(tmp_path):
    r=fixture_report();r['finalized']=True
    r['eq']=[];r['bulk']=[];r['ctr']=[];r['hse']=dict.fromkeys(r['hse'],'')
    # Missing Configure identity no longer exports a blank Vessel/Date of Hire/Report No. (GDS-AUDIT-001).
    with pytest.raises(ExcelExportError,match='Date of Hire is not set'):
        VdrExcelExporter().export(r,tmp_path/'blocked.xlsx',identity={})
    assert not (tmp_path/'blocked.xlsx').exists()
    configured=dict(vessel='CONFIGURED VESSEL',hireDate='2026-01-01')
    path=tmp_path/'empty.xlsx';VdrExcelExporter().export(r,path,identity=configured)
    w=load_workbook(path,data_only=True);s=w['VDR'];f=w['FLEET MANAGEMENT']
    assert w['GDS Meta']['C9'].value=='CONFIGURED VESSEL' and s['E12'].value=='CONFIGURED VESSEL' and s['C12'].value==322
    assert all(s[c].value is None for c in ('E16','E17','E18','E19'))
    for row in range(15,104):
        assert all(s[f'{col}{row}'].value is None for col in ('W','X','Y','Z','AE','AG','AH','AI','AK','AL','AM','AN'))
    for row in range(23,45): assert all(s[f'{c}{row}'].value is None for c in ('H','J','L','P','T'))
    for row in BULK_ROWS.values(): assert all(s[f'{c}{row}'].value is None for c in ('C','D','E','F','G','H','I','L','N','P','R','T','U'))
    for sheet,columns,start in [('CORE-CREW','BCDEFGHIJ',7),('CONTRACTORS','BCDEFG',6)]:
        assert all(w[sheet][f'{c}{row}'].value is None for row in range(start,206) for c in columns)
    assert all(f[f'D{i}'].value is None for i in [3,4,5,6,*range(8,74),*range(75,83)])
    assert f['D74'].value==0
    assert 'TEST VESSEL' not in [s['E12'].value,w['GDS Meta']['C9'].value]  # report copy never overrides Configure


@pytest.mark.parametrize('group,limit,label',[('acts',90,'Activity'),('crew',200,'crew'),('ctr',200,'Contractors')])
def test_row_capacity_is_blocked_without_changing_destination(tmp_path,group,limit,label):
    r=full_excel_report();r[group]=[deepcopy(r[group][0]) for _ in range(limit+1)]
    path=tmp_path/'existing.xlsx';path.write_bytes(b'existing output')
    with pytest.raises(ExcelExportError,match=label): VdrExcelExporter().export(r,path)
    assert path.read_bytes()==b'existing output'


@pytest.mark.parametrize('name,count,message',[('FUEL (ltrs)',3,'maximum of two'),('NABM (bbls)',2,'capacity = 1'),('PREMIX (bbls)',2,'capacity = 1')])
def test_transfer_overflow_blocks_export(tmp_path,name,count,message):
    r=full_excel_report();row=next(b for b in r['bulk'] if b['name']==name);row['tr']=[row['tr'][0]]*count
    with pytest.raises(ExcelExportError,match=message): VdrExcelExporter().export(r,tmp_path/'bad.xlsx')
    assert not (tmp_path/'bad.xlsx').exists()


@pytest.mark.parametrize('group,label',[('eq','equipment'),('bulk','bulk item')])
def test_unknown_and_duplicate_names_block_export(tmp_path,group,label):
    r=full_excel_report();r[group][0]['name']='UNKNOWN ITEM'
    with pytest.raises(ExcelExportError,match='Unknown '+label): VdrExcelExporter().export(r,tmp_path/'bad.xlsx')
    r=full_excel_report();r[group].append(deepcopy(r[group][0]))
    with pytest.raises(ExcelExportError,match='Duplicate '+label): VdrExcelExporter().export(r,tmp_path/'bad.xlsx')


def test_template_missing_hash_structure_and_source_overwrite(tmp_path):
    r=full_excel_report();path=tmp_path/'out.xlsx'
    with pytest.raises(ExcelExportError,match='missing'): VdrExcelExporter(tmp_path/'missing.xlsx').export(r,path)
    wrong=tmp_path/'wrong.xlsx';wrong.write_bytes(b'not the template')
    with pytest.raises(ExcelExportError,match='hash mismatch'): VdrExcelExporter(wrong).export(r,path)
    book=load_workbook(template_path());book['VDR']['B76']='WRONG'
    with pytest.raises(ExcelExportError,match='structure mismatch'): VdrExcelExporter._validate_structure(book)
    with pytest.raises(ExcelExportError,match='source Excel template'): VdrExcelExporter().export(r,template_path())


def test_atomic_locked_destination_error(tmp_path,monkeypatch):
    import app.vdr.excel as excel
    path=tmp_path/'locked.xlsx';path.write_bytes(b'preserve')
    def locked(*args): raise PermissionError('locked by Excel')
    monkeypatch.setattr(excel.os,'replace',locked)
    with pytest.raises(ExcelExportError,match='close the destination in Excel'): VdrExcelExporter().export(full_excel_report(),path)
    assert path.read_bytes()==b'preserve' and not list(tmp_path.glob('.vdr-excel-*'))


def test_filename_normalized_names_literal_text_and_frozen_resources(tmp_path,monkeypatch):
    import app.vdr.excel as excel
    assert suggested_filename('A/B:*?"<>| VESSEL','2026-11-19')=='VDR_A_B________VESSEL_2026-11-19.xlsx'
    r=full_excel_report();r['bulk'][0]['name']='  premix   (BBLS) '
    r['acts'][0]['act']='=HYPERLINK("bad") & <literal>'
    path=tmp_path/'literal.xlsx';VdrExcelExporter().export(r,path)
    cell=load_workbook(path)['VDR']['Z14'];assert cell.value==r['acts'][0]['act'] and cell.data_type=='s'
    monkeypatch.setattr(excel.sys,'frozen',True,raising=False);monkeypatch.setattr(excel.sys,'_MEIPASS',str(tmp_path),raising=False)
    assert excel.template_path()==tmp_path/'app/resources/templates'/excel.TEMPLATE_NAME


def test_location_capacity_and_return_visit_totals(tmp_path):
    r=full_excel_report()
    r['acts']=[dict(r['acts'][0],to=f'{(i+1):02d}00',loc=f'LOCATION {i}') for i in range(24)]
    with pytest.raises(ExcelExportError,match='capacity = 22'): VdrExcelExporter().export(r,tmp_path/'bad.xlsx')
    r=full_excel_report();r['acts'][1]['loc']='JAMPUK'
    path=tmp_path/'return.xlsx';VdrExcelExporter().export(r,path)
    s=load_workbook(path,data_only=True)['VDR']
    assert [s[f'AN{i}'].value for i in range(14,18)]==['DUYONG','JAMPUK','DUYONG','JAMPUK']
    assert duration(s['T82'])==480 and duration(s['T83'])==960


def test_ui_gate_save_cancel_success_and_error(qtbot,tmp_path,monkeypatch):
    from app.ui.pages.vdr import workspace
    store=ReportStore(tmp_path/'state.json',today='2026-11-19')
    p=VdrPage(store,identity_provider=lambda:dict(vessel='Configured Vessel',hireDate='2026-01-01'))
    qtbot.addWidget(p);assert not p.excel_button.isEnabled() and p.download_button.text()=='Download PDF'
    calls=[]
    monkeypatch.setattr(workspace.QFileDialog,'getSaveFileName',lambda *a: calls.append(a) or ('',''))
    p.download_excel();assert not calls
    store.reports[store.current]=full_excel_report();p._rebuild();assert p.excel_button.isEnabled()
    before=deepcopy(p.report);p.download_excel();assert calls and p.report==before
    path=tmp_path/'ui.xlsx'
    monkeypatch.setattr(workspace.QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    p.excel_button.click();assert path.exists() and p.saved.text()=='Excel report downloaded'
    assert load_workbook(path,data_only=True)['VDR']['E12'].value=='Configured Vessel'
    assert p.report==before
    errors=[];monkeypatch.setattr(workspace.QMessageBox,'warning',lambda *a:errors.append(a[-1]))
    monkeypatch.setattr(workspace.QFileDialog,'getSaveFileName',lambda *a:(str(tmp_path/'missing/out.xlsx'),''))
    p.download_excel();assert errors and 'Cannot save' in errors[-1]
    p.save_timer.stop()


def test_domain_snapshot_helpers_match_display():
    r=full_excel_report()
    assert report_number(r)==323 and hse_perfect_days(r)==15
    assert report_number(r,{}) is None and hse_perfect_days(dict(r,hse=dict.fromkeys(r['hse'],'')),{}) is None


@pytest.mark.parametrize('name',['fuel (ltrs)','  Fuel (LTRS)  '])
def test_normalized_fuel_consumption_matches_domain_and_excel(tmp_path,name):
    from app.vdr.model import calculate
    r=full_excel_report();fuel=next(b for b in r['bulk'] if b['name']=='FUEL (ltrs)');fuel['name']=name
    index=r['bulk'].index(fuel)
    assert calculate(r)['bulkClose'][index]==404
    path=tmp_path/'fuel.xlsx';VdrExcelExporter().export(r,path)
    s=load_workbook(path,data_only=True)['VDR']
    assert s['I52'].value==671 and s['T52'].value==404


def test_finalization_invalid_values_and_xml_guard(tmp_path):
    r=full_excel_report();r['finalized']=False
    with pytest.raises(ExcelExportError,match='Finalize'): VdrExcelExporter().export(r,tmp_path/'out.xlsx')
    r=full_excel_report();r['bulk'][0]['rcvB']='bad'
    with pytest.raises(ExcelExportError,match='validation issues'): VdrExcelExporter().export(r,tmp_path/'out.xlsx')
    r=full_excel_report();r['hse']['containment_loss']='not-a-date'
    with pytest.raises(ExcelExportError,match='invalid Excel date'): VdrExcelExporter().export(r,tmp_path/'out.xlsx')
    r=full_excel_report();r['acts'][0]['act']='Invalid\x01text'
    with pytest.raises(ExcelExportError,match='Invalid Excel text'): VdrExcelExporter().export(r,tmp_path/'out.xlsx')


def test_all_movement_categories_and_fleet_shortened_towing_label(tmp_path):
    r=full_excel_report()
    r['acts']=[dict(r['acts'][0],to=f'{i+1:02d}00' if i<9 else '2400',cat=category,loc='ONE LOCATION')
               for i,category in enumerate(CATALOG['movement'])]
    path=tmp_path/'movements.xlsx';VdrExcelExporter().export(r,path);w=load_workbook(path,data_only=True)
    assert [duration(w['VDR'][f'I{i}']) for i in MOVEMENT_ROWS]==[60]*9+[900]
    assert [duration(w['FLEET MANAGEMENT'][f'D{i}']) for i in range(84,94)]==[60]*9+[900]


@pytest.mark.parametrize('group,capacity',[('acts',90),('crew',200),('ctr',200)])
def test_exact_row_capacity_supported(tmp_path,group,capacity):
    r=full_excel_report()
    r[group]=[deepcopy(r[group][0]) for _ in range(capacity)]
    if group=='acts':
        for i,row in enumerate(r[group]):
            minute=i+1 if i<89 else 1440
            row['to']=f'{minute//60:02d}{minute%60:02d}';row['loc']='ONE LOCATION'
    path=tmp_path/'capacity.xlsx';VdrExcelExporter().export(r,path);w=load_workbook(path,data_only=True)
    sheet,col,last=('VDR','X',103) if group=='acts' else ('CORE-CREW' if group=='crew' else 'CONTRACTORS','C',205)
    assert w[sheet][f'{col}{last}'].value is not None
