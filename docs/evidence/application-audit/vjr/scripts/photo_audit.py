import sys, http.client, socket, time, uuid, json
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
from io import BytesIO
from pathlib import Path
from PIL import Image
from app.vjr.photo_server import UploadService, is_lan_address
from app.vjr.photo_storage import PhotoStorage, SLOTS
from app.vjr.store import VjrStore
tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
store = VjrStore(tmp/'p.json'); rid = uuid.uuid4().hex
store.mutate(lambda r: r.update(photo_report_id=rid, photos={}))
storage = PhotoStorage(tmp/'attachments')
def deliver(d):
    d.apply(lambda: store.mutate(lambda r: r['photos'].__setitem__(d.session.slot, d.reference)))
svc = UploadService(storage, deliver, allow_loopback=True); svc.start('127.0.0.1')
def req(method, path, body=None, headers=None):
    c = http.client.HTTPConnection('127.0.0.1', svc.port, timeout=5)
    h = {'Host': '127.0.0.1:%s' % svc.port}; h.update(headers or {})
    try:
        c.request(method, path, body=body, headers=h); r = c.getresponse(); return r.status, r.read()[:120]
    except Exception as e: return 'EXC', repr(e)[:120]
def jpeg(exif_gps=False):
    im = Image.new('RGB', (1600, 1200), 'red'); b = BytesIO()
    ex = Image.Exif()
    if exif_gps: ex[0x8825] = {1:'N', 2:(5.0,20.0,30.0), 3:'E', 4:(102.0,40.0,15.0)}
    im.save(b, 'JPEG', exif=ex); return b.getvalue()
s = svc.create_session(rid, SLOTS[0]); p = '/vjr-photo/' + s.token
print('GET / ->', req('GET', '/')[0])
print('GET traversal ->', req('GET', '/vjr-photo/../../etc/passwd')[0])
print('GET token+query ->', req('GET', p + '?x=1')[0])
print('GET wrong Host ->', req('GET', p, headers={'Host': 'evil.example'})[0])
print('GET cross-origin fetch ->', req('GET', p, headers={'Sec-Fetch-Site': 'cross-site'})[0])
print('GET valid ->', req('GET', p)[0])
print('HEAD ->', req('HEAD', p)[0])
print('POST 16MB declared ->', req('POST', p, body=b'x' * 10, headers={'Content-Length': str(16 * 1024 * 1024), 'X-Photo-Name': 'a.jpg', 'Content-Type': 'image/jpeg'}))
s = svc.create_session(rid, SLOTS[0]); p = '/vjr-photo/' + s.token
print('POST text as .jpg ->', req('POST', p, body=b'hello world', headers={'X-Photo-Name': 'a.jpg', 'Content-Type': 'image/jpeg'}))
print('POST svg ->', req('POST', p, body=b'<svg/>', headers={'X-Photo-Name': '../../x.svg', 'Content-Type': 'image/svg+xml'}))
print('POST third attempt valid jpeg w/ GPS EXIF ->', req('POST', p, body=jpeg(True), headers={'X-Photo-Name': '..\..\evil.jpg', 'Content-Type': 'image/jpeg'}))
print('session state', s.state, 'attempts', s.attempts)
s = svc.create_session(rid, SLOTS[0]); p = '/vjr-photo/' + s.token
print('POST fresh valid jpeg ->', req('POST', p, body=jpeg(True), headers={'X-Photo-Name': 'IMG_1.jpg', 'Content-Type': 'image/jpeg'}))
print('replay used token ->', req('POST', p, body=jpeg(), headers={'X-Photo-Name': 'IMG_1.jpg', 'Content-Type': 'image/jpeg'})[0])
ref = store.report['photos'].get(SLOTS[0]); print('stored ref', ref)
d = storage.directory(ref); print('stored files', sorted(x.name for x in d.iterdir()))
orig = [x for x in d.iterdir() if x.name.startswith('original')][0]
with Image.open(orig) as im: print('original keeps GPS EXIF:', 0x8825 in im.getexif())
with Image.open(d/'photo.jpg') as im: print('display photo GPS EXIF:', 0x8825 in im.getexif())
# server still listening after all sessions used?
time.sleep(0.3); sock = socket.socket(); r = sock.connect_ex(('127.0.0.1', svc.port)); sock.close()
print('server still listening after upload completed (no active session):', r == 0, 'server obj', svc.server is not None)
# slow-client exhaustion: 4 idle connections
socks = [socket.create_connection(('127.0.0.1', svc.port)) for _ in range(4)]; time.sleep(0.3)
s2 = svc.create_session(rid, SLOTS[1]); print('GET while 4 idle sockets held ->', req('GET', '/vjr-photo/' + s2.token))
for x in socks: x.close()
# Expiry
svc.sessions.lifetime = 0.5; s3 = svc.create_session(rid, SLOTS[1]); time.sleep(0.7); print('expired GET ->', req('GET', '/vjr-photo/' + s3.token)[0])
# switching address restarts server and cancels other slot's live QR
svc.sessions.lifetime = 600; a = svc.create_session(rid, SLOTS[0]); svc.address = 'other'; svc.start('127.0.0.1'); print('other-slot session after start() on a different NIC:', a.state)
svc.close()
for ip in ('169.254.10.2', '100.64.1.5', '172.16.0.1', '10.1.2.3', '192.168.1.5'): print(ip, is_lan_address(ip))
# Excel insertion with a photo
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests'); from vjr_fixture import full_report
from app.vjr.excel import VjrExcelExporter
rep = full_report(); rep.update(photo_report_id=rid, photos={SLOTS[0]: ref})
out = tmp/'photo_export.xlsx'; VjrExcelExporter(photo_root=tmp/'attachments').export(rep, out)
from zipfile import ZipFile
z = ZipFile(out); print('media in export', [n for n in z.namelist() if 'media' in n and 'vjr' in n])
from openpyxl import load_workbook
wb = load_workbook(out); print('dep sheet images', len(wb['4. Departure Report']._images), 'arr sheet images', len(wb['5. Arrival Report']._images))
# missing photo file -> export blocked?
import shutil; shutil.rmtree(d)
try: VjrExcelExporter(photo_root=tmp/'attachments').export(rep, tmp/'x.xlsx'); print('export with missing photo OK')
except Exception as e: print('export with missing photo blocked:', e)
