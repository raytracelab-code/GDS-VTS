from io import BytesIO
import http.client
import json
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlsplit
import uuid
from zipfile import ZipFile
import re
from hashlib import sha256
from xml.etree import ElementTree as ET
import pytest
from PIL import Image
from openpyxl import load_workbook
from app.vjr.model import new_report, normalize
from app.vjr.store import VjrStore
from app.vjr.photo_storage import PhotoStorage, PhotoError, SLOTS, MAX_UPLOAD
from app.vjr.photo_server import UploadService, Delivery, EXPIRED, is_lan_address
from app.vjr.excel import VjrExcelExporter, ExcelExportError, template_path, TEMPLATE_HASH
from app.vjr.photo_excel import region_dimensions, column_pixels, EMU
from vjr_fixture import full_report


def photo_bytes(color='blue',size=(800,400),image_format='JPEG',orientation=None):
    output=BytesIO(); image=Image.new('RGB',size,color)
    options={}
    if orientation:
        exif=Image.Exif(); exif[274]=orientation; options['exif']=exif
    image.save(output,image_format,**options)
    return output.getvalue()


def request(service,session=None,payload=None,path=None,headers=None):
    target=path or '/vjr-photo/'+session.token
    connection=http.client.HTTPConnection(service.address,service.port,timeout=5)
    request_headers=dict(headers or {})
    if payload is not None:
        request_headers.setdefault('Content-Type','image/jpeg')
        request_headers.setdefault('X-Photo-Name','mobile.jpg')
    connection.request('GET' if payload is None else 'POST',target,body=payload,headers=request_headers)
    response=connection.getresponse(); result=(response.status,response.read(),dict(response.getheaders()))
    connection.close(); return result


@pytest.fixture
def server(tmp_path):
    store=VjrStore(tmp_path/'report.json')
    store.report.update(photo_report_id=uuid.uuid4().hex,photos={})
    storage=PhotoStorage(tmp_path/'attachments')
    def deliver(delivery):
        def commit():
            if store.report.get('photo_report_id')!=delivery.session.report_id:
                raise PhotoError('Report changed')
            store.mutate(lambda report:report['photos'].__setitem__(delivery.session.slot,delivery.reference))
        delivery.apply(commit)
    service=UploadService(storage,deliver,allow_loopback=True)
    service.start('127.0.0.1')
    yield service,store,storage
    service.close()


def test_page_two_slots_and_success_token_invalidation(server,caplog):
    service,store,storage=server
    departure=service.create_session(store.report['photo_report_id'],SLOTS[0])
    arrival=service.create_session(store.report['photo_report_id'],SLOTS[1])
    assert departure.token!=arrival.token and len(departure.token)==43
    status,page,headers=request(service,departure)
    assert status==200 and b'Departure Back Deck Photo' in page
    assert b'capture="environment"' in page and b'id="gallery"' in page
    assert b'name="viewport"' in page and b'15 MB' in page
    assert headers['Cache-Control']=='no-store'
    assert request(service,arrival)[0]==200
    assert request(service,departure,photo_bytes())[0]==200
    assert SLOTS[0] in store.report['photos'] and SLOTS[1] not in store.report['photos']
    assert request(service,departure)[0]==410
    assert request(service,departure,photo_bytes())[0]==410
    assert request(service,arrival,photo_bytes('red'))[0]==200
    assert store.report['photos'][SLOTS[0]]!=store.report['photos'][SLOTS[1]]
    assert VjrStore(store.path).report==store.report
    assert departure.token not in caplog.text and arrival.token not in caplog.text


@pytest.mark.parametrize('path',['/','/../main.py','/app/vjr/model.py','/vjr-photo/../../main.py','/vjr-photo/'+'A'*43])
def test_wrong_tokens_and_unrelated_paths(server,path):
    service,_,_=server
    status,body,_=request(service,path=path)
    assert status==404 and b'Traceback' not in body and b'import ' not in body


def test_expired_cancelled_regenerated_sessions(server):
    service,store,_=server
    clock=[100.0]; service.sessions.clock=lambda:clock[0]; service.sessions.lifetime=10
    first=service.create_session(store.report['photo_report_id'],SLOTS[0])
    replacement=service.create_session(store.report['photo_report_id'],SLOTS[0])
    assert request(service,first)[0]==410 and first.token!=replacement.token
    service.sessions.cancel(replacement.token)
    assert request(service,replacement)[0]==410
    expired=service.create_session(store.report['photo_report_id'],SLOTS[1]); clock[0]=111
    status,body,_=request(service,expired)
    assert status==410 and EXPIRED.encode() in body
    assert request(service,expired,photo_bytes())[0]==410


def test_invalid_image_oversize_types_and_attempt_limit(server):
    service,store,storage=server
    session=service.create_session(store.report['photo_report_id'],SLOTS[0])
    assert request(service,session,b'not an image')[0]==400
    assert request(service,session,b'',headers={'Content-Length':str(MAX_UPLOAD+1)})[0]==413
    assert not storage.root.exists()
    assert request(service,session,photo_bytes(),headers={'X-Photo-Name':'mobile.exe'})[0]==400
    assert request(service,session,photo_bytes())[0]==410
    assert not store.report['photos']


def test_origin_host_and_chunked_rejected(server):
    service,store,_=server; session=service.create_session(store.report['photo_report_id'],SLOTS[0])
    assert request(service,session,headers={'Host':'attacker.example'})[0]==403
    assert request(service,session,photo_bytes(),headers={'Origin':'https://attacker.example'})[0]==403
    assert request(service,session,photo_bytes(),headers={'Transfer-Encoding':'chunked'})[0]==400


def test_late_upload_does_not_attach_to_another_report(server):
    service,store,storage=server
    old=service.create_session(store.report['photo_report_id'],SLOTS[0])
    store.report.update(photo_report_id=uuid.uuid4().hex,photos={})
    assert request(service,old,photo_bytes())[0]==400
    assert not store.report['photos']
    assert not list(storage.root.glob('*/photos/[a-f0-9]*'))


def test_storage_orientation_paths_original_and_recovery(tmp_path):
    storage=PhotoStorage(tmp_path/'photos'); identity=uuid.uuid4().hex
    data=photo_bytes(size=(80,40),orientation=6)
    reference=storage.create(identity,data,'../../phone.jpg','image/jpeg')
    assert reference.startswith(identity+'/photos/')
    assert (storage.directory(reference)/'original.jpg').read_bytes()==data
    with Image.open(storage.image_path(reference)) as image:
        assert image.size==(40,80) and image.getexif().get(274,1)==1
    with pytest.raises(PhotoError):
        storage.image_path('../../secret')
    with pytest.raises(PhotoError,match='unavailable'):
        storage.image_path(identity+'/photos/'+uuid.uuid4().hex)
    report=normalize(dict(photo_report_id=identity,photos={SLOTS[0]:reference}))
    assert report['photos'][SLOTS[0]]==reference
    with pytest.raises(PhotoError):
        normalize(dict(photo_report_id=identity,photos={SLOTS[0]:'../escape'}))


def test_png_validation_and_quality_copy(tmp_path):
    storage=PhotoStorage(tmp_path/'photos'); identity=uuid.uuid4().hex
    data=photo_bytes(size=(3200,1800),image_format='PNG')
    reference=storage.create(identity,data,'phone.png','image/png')
    with Image.open(storage.image_path(reference)) as image:
        assert image.size==(2400,1350)
    with pytest.raises(PhotoError,match='filename'):
        storage.create(identity,data,'fake.jpg','image/jpeg')
    with pytest.raises(PhotoError,match='JPEG or PNG'):
        storage.create(identity,photo_bytes(image_format='GIF'),'fake.gif','image/gif')


def test_storage_replace_delete_and_undo_retention(server):
    service,store,storage=server
    session=service.create_session(store.report['photo_report_id'],SLOTS[0])
    assert request(service,session,photo_bytes())[0]==200
    original=store.report['photos'][SLOTS[0]]
    replacement=service.create_session(store.report['photo_report_id'],SLOTS[0])
    assert store.report['photos'][SLOTS[0]]==original
    assert request(service,replacement,b'invalid replacement')[0]==400
    assert store.report['photos'][SLOTS[0]]==original and storage.image_path(original).exists()
    assert request(service,replacement,photo_bytes('red'))[0]==200
    updated=store.report['photos'][SLOTS[0]]; storage.collect(store)
    assert original!=updated and storage.image_path(original).exists()
    store.undo(); assert store.report['photos'][SLOTS[0]]==original
    store.redo(); store.mutate(lambda report:report['photos'].pop(SLOTS[0]))
    assert not VjrStore(store.path).report['photos']
    storage.collect(store); assert storage.image_path(updated).exists()
    store.undo_stack.clear(); store.redo_stack.clear(); storage.collect(store)
    assert not storage.directory(updated).exists() and not storage.directory(original).exists()


def test_delivery_timeout_cannot_commit_later():
    delivery=Delivery(None,'reference'); calls=[]
    delivery.abort('Timed out'); delivery.apply(lambda:calls.append(True))
    assert not calls and not delivery.success and delivery.event.is_set()


def test_cleanup_preserves_attachments_when_report_is_unreadable(tmp_path):
    storage=PhotoStorage(tmp_path/'attachments'); identity=uuid.uuid4().hex
    reference=storage.create(identity,photo_bytes(),'phone.jpg','image/jpeg'); storage.release(reference)
    path=tmp_path/'report.json'; path.write_text('{invalid',encoding='utf-8')
    store=VjrStore(path); assert store.recovered and store.notices  # recovered to a fresh report, damaged copy kept
    storage.collect(store)
    assert storage.image_path(reference).exists() and path.read_text()=='{invalid'
    assert list(tmp_path.glob('report.json.damaged-*'))[0].read_text(encoding='utf-8')=='{invalid'


def test_cleanup_does_not_touch_other_report_directories(tmp_path):
    storage=PhotoStorage(tmp_path/'attachments'); other=uuid.uuid4().hex
    reference=storage.create(other,photo_bytes(),'phone.jpg','image/jpeg'); storage.release(reference)
    store=VjrStore(tmp_path/'report.json'); store.report.update(photo_report_id=uuid.uuid4().hex,photos={})
    storage.collect(store); assert storage.image_path(reference).exists()


def test_network_binding_and_port_fallback(tmp_path):
    service=UploadService(PhotoStorage(tmp_path),lambda d:None)
    for address in ('0.0.0.0','127.0.0.1','8.8.8.8','169.254.1.2'):
        with pytest.raises(PhotoError):
            service.start(address)
    assert is_lan_address('192.168.1.2') and is_lan_address('10.2.3.4')
    occupied=socket.socket(); occupied.bind(('127.0.0.1',0)); occupied.listen(1)
    service=UploadService(PhotoStorage(tmp_path),lambda d:None,allow_loopback=True)
    try:
        service.start('127.0.0.1',occupied.getsockname()[1])
        assert service.port!=occupied.getsockname()[1]
    finally:
        service.close(); occupied.close()


def test_repeated_start_stop_releases_workers_and_port(tmp_path):
    service=UploadService(PhotoStorage(tmp_path),lambda d:None,allow_loopback=True)
    for _ in range(5):
        service.start('127.0.0.1'); port=service.port
        connection=socket.create_connection(('127.0.0.1',port)); connection.sendall(b'GET /')
        service.close(); connection.close()
        assert service.server is None and service.thread is None
        probe=socket.socket(); probe.settimeout(.2)
        assert probe.connect_ex(('127.0.0.1',port))!=0; probe.close()
    assert not [t for t in threading.enumerate() if t.name.startswith('vjr-photo-')]


def test_concurrent_connections_are_bounded(server):
    service,_,_=server; connections=[]
    try:
        for _ in range(4):
            connection=socket.create_connection((service.address,service.port))
            connection.sendall(b'GET /'); connections.append(connection)
        deadline=time.monotonic()+2
        while len(service.server.workers)<4 and time.monotonic()<deadline:
            time.sleep(.01)
        assert request(service,path='/')[0]==503
        assert len(service.server.workers)==4
    finally:
        for connection in connections:
            connection.close()


def test_network_adapters_prefer_physical_lan(monkeypatch):
    from types import SimpleNamespace as NS
    from app.vjr import photo_network
    class Adapter:
        def __init__(self,name,address,flags=3):
            self.label,self.address,self.state=name,address,flags
        def flags(self): return self.state
        def humanReadableName(self): return self.label
        def name(self): return self.label
        def addressEntries(self): return [NS(ip=lambda:NS(toString=lambda:self.address))]
    interfaces=NS(InterfaceFlag=NS(IsUp=1,IsRunning=2,IsLoopBack=4),allInterfaces=lambda:[
        Adapter('VirtualBox','192.168.56.1'),Adapter('Wi-Fi','192.168.1.10'),Adapter('Loopback','127.0.0.1',7),
        Adapter('Disconnected','192.168.2.2',0),Adapter('Public','8.8.8.8')])
    monkeypatch.setattr(photo_network,'import_module',lambda name:NS(QNetworkInterface=interfaces))
    addresses=photo_network.lan_addresses()
    assert [item.address for item in addresses]==['192.168.1.10','192.168.56.1']
    assert addresses[0].virtual is False and addresses[1].virtual is True


@pytest.mark.parametrize('slots',[(),(SLOTS[0],),(SLOTS[1],),SLOTS])
def test_excel_all_photo_combinations(tmp_path,slots):
    report=full_report(); storage=PhotoStorage(tmp_path/'attachments')
    report.update(photo_report_id=uuid.uuid4().hex,photos={})
    for slot in slots:
        report['photos'][slot]=storage.create(report['photo_report_id'],photo_bytes('blue' if slot==SLOTS[0] else 'red',size=(400,800) if slot==SLOTS[0] else (800,400)),'phone.jpg','image/jpeg')
    path=tmp_path/'photo.xlsx'; VjrExcelExporter(photo_root=storage.root).export(report,path)
    workbook=load_workbook(path)
    with ZipFile(template_path()) as original,ZipFile(path) as exported:
        for slot,number,sheet in ((SLOTS[0],6,'4. Departure Report'),(SLOTS[1],7,'5. Arrival Report')):
            part='xl/drawings/drawing%s.xml' % number
            if slot not in slots:
                assert original.read(part)==exported.read(part)
            else:
                text=exported.read(part).decode()
                assert 'VJR '+('Departure' if number==6 else 'Arrival')+' Back Deck Photo' in text
                assert b'image8.png' in exported.read(part) if number==6 else b'image10.png' in exported.read(part)
                assert len(workbook[sheet]._images)==2  # Original logo plus the replacement photo.
                image=next(image for image in workbook[sheet]._images if image.anchor._from.col>=11)
                anchor=image.anchor; widths,heights=region_dimensions(workbook[sheet])
                left=sum(widths[:anchor._from.col-11])+anchor._from.colOff/EMU
                top=sum(heights[:anchor._from.row-9])+anchor._from.rowOff/EMU
                assert left>=0 and top>=0
                assert left+anchor.ext.cx/EMU<=sum(widths)+.01
                assert top+anchor.ext.cy/EMU<=sum(heights)+.01
                assert abs((left+anchor.ext.cx/EMU/2)-sum(widths)/2)<.01
                assert abs((top+anchor.ext.cy/EMU/2)-sum(heights)/2)<.01
                assert anchor.ext.cx/anchor.ext.cy==pytest.approx(.5 if slot==SLOTS[0] else 2)
        for name in original.namelist():
            if not name.startswith('xl/drawings/drawing6') and not name.startswith('xl/drawings/drawing7') and not name.startswith('xl/drawings/_rels/drawing6') and not name.startswith('xl/drawings/_rels/drawing7') and not re.fullmatch(r'xl/worksheets/sheet[1-8].xml',name) and name!='[Content_Types].xml':
                assert original.read(name)==exported.read(name),name
    assert workbook['1. Core Crew']['C8'].value=='Captain Example'
    assert sha256(template_path().read_bytes()).hexdigest()==TEMPLATE_HASH
    workbook.close()


def test_excel_missing_photo_blocks_without_partial_destination(tmp_path):
    report=full_report(); identity=uuid.uuid4().hex
    report.update(photo_report_id=identity,photos={SLOTS[0]:identity+'/photos/'+uuid.uuid4().hex})
    path=tmp_path/'photo.xlsx'; path.write_bytes(b'previous file')
    with pytest.raises(ExcelExportError,match='unavailable'):
        VjrExcelExporter(photo_root=tmp_path/'photos').export(report,path)
    assert path.read_bytes()==b'previous file'
