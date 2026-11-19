"""Fully populated VJR evidence, never imported by production code."""
from app.vjr.model import new_report


def full_report():
    report = new_report()
    report['meta'].update(report_id='VJR-42',client_id='CLIENT-7',vessel='Acceptance Vessel',
        imo='1234567',capacity='1000',client='Acceptance Client',reader_version='2',reader_revision='1')
    report['crew'] = [dict(name='Captain Example',rank='MASTER',age='45',nationality='Bangladesh',
        passport='P001',sign_on='2026-11-01',remarks='First crew'),dict(name='Officer Example',
        rank='CH. OFF',age='32',nationality='Malaysia',passport='P002',sign_on='2026-11-10',remarks='Second crew')]
    report['contractors'] = [dict(name='Contractor One',vendor='Vendor A',age='29',nationality='Malaysia',
        passport='C001',remarks='Inspection'),dict(name='Contractor Two',vendor='Vendor B',age='40',
        nationality='Bangladesh',passport='C002',remarks='Maintenance')]
    report['waypoints'] = [dict(lat_degree='5',lat_minute='20',lat_second='30.25',lat_direction='N',
        lon_degree='102',lon_minute='40',lon_second='15.5',lon_direction='E',course='123.45',
        speed='8.5',remarks='Waypoint '+str(i+1)) for i in range(3)]
    report['waypoints'][1].update(lat_direction='S',lon_direction='W')
    report['departure'].update(captain='Captain Example',report_date='2026-11-18',prepared_by='Officer Example',
        prepared_tel='+880100',checked_by='Captain Example',checked_tel='+880200',draft_forward='4.1',
        draft_midship='4.2',draft_aft='4.3',fuel_requirement='100',fw_requirement='200',dw_requirement='300',
        departure_date='2026-11-18',departure_time='09:05',departure_location='Supply Base',
        departure_remarks='Departed safely',arrival_date='2026-11-19',arrival_time='10:30',
        destination='Platform Alpha',arrival_remarks='Estimated arrival')
    report['arrival'].update(report_date='2026-11-19',arrival_date='2026-11-19',arrival_time='11:45',
        arrival_remarks='Arrived safely')
    for group,offset in (('departure',0),('arrival',10)):
        for i,row in enumerate(report[group]['deck']):
            row.update(location='Platform '+str(i+1),lifts=str(i+1+offset),ops=str(10+offset),fso='20',
                drilling='30',weight=str(40+i+offset),remarks=group+' deck '+str(i+1))
        for i,item in enumerate(report[group]['inventory']):
            item.update(quantity=str(100+i+offset),remarks=group+' inventory '+str(i+1))
    report['progress'] = [dict(date='2026-11-18',hour=str(10+i),minute='05',
        lat_degree='5',lat_minute='20',lat_second='30.25',lat_direction='N',lon_degree='102',
        lon_minute='40',lon_second='15.5',lon_direction='E',course='123.45',speed='8.5',sky='Rain',
        visibility='6',wind_speed='12.5',wind_direction='NE',wave_height='1.25',wave_direction='E',
        remarks='Progress '+str(i+1)) for i in range(3)]
    return report
