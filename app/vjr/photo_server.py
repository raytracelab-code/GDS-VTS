"""Bounded, on-demand LAN HTTP service. It exposes one token-scoped route only."""
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import logging
from pathlib import Path
import re
import secrets
import socket
import sys
import threading
import time
from urllib.parse import unquote, urlsplit
from .photo_storage import MAX_UPLOAD, PhotoError, SLOTS, TITLES

LOG = logging.getLogger(__name__)
TOKEN = re.compile(r'/vjr-photo/([A-Za-z0-9_-]{43})')
EXPIRED = 'This upload link has expired. Please generate a new QR code in GDS VTS.'
INACTIVE = 'This upload link is no longer active. Please generate a new QR code in GDS VTS.'
PRIVATE = tuple(ipaddress.ip_network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))


def is_lan_address(value):
    try:
        address = ipaddress.ip_address(value)
        return address.version==4 and any(address in network for network in PRIVATE)
    except ValueError:
        return False


def upload_page(title):
    root = Path(sys._MEIPASS)/'app/resources' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'resources'
    return (root/'vjr/mobile_photo.html').read_text(encoding='utf-8').replace('@@TARGET@@',title).encode('utf-8')


@dataclass
class Session:
    token: str
    report_id: str
    slot: str
    expires: float
    state: str = 'waiting'
    attempts: int = 0
    message: str = ''


class SessionError(PhotoError):
    def __init__(self, message, status=410):
        super().__init__(message); self.status = status


class Sessions:
    def __init__(self, lifetime=600, clock=None):
        self.lifetime = lifetime; self.clock = clock or time.monotonic
        self.lock = threading.RLock(); self.items = {}

    def create(self, report_id, slot):
        if slot not in SLOTS:
            raise PhotoError('Unknown photo slot')
        with self.lock:
            for session in self.items.values():
                if session.report_id==report_id and session.slot==slot and session.state in ('waiting','uploading','error'):
                    session.state = 'cancelled'
            token = secrets.token_urlsafe(32)
            session = Session(token,report_id,slot,self.clock()+self.lifetime)
            self.items[token] = session
            if len(self.items)>128:
                for key in list(self.items):
                    if key!=token and self.items[key].state not in ('waiting','uploading','error'):
                        del self.items[key]
                    if len(self.items)<=64:
                        break
            LOG.info('Photo session created: %s',slot)
            return session

    def get(self, token):
        with self.lock:
            session = self.items.get(token)
            if session is None:
                raise SessionError('This upload link is not valid. Please generate a new QR code in GDS VTS.',404)
            if self.clock()>=session.expires and session.state in ('waiting','uploading','error'):
                session.state = 'expired'; session.message = EXPIRED
                LOG.info('Photo session expired: %s',session.slot)
            return session

    def active(self, token):
        session = self.get(token)
        if session.state=='expired':
            raise SessionError(EXPIRED)
        if session.state not in ('waiting','error'):
            raise SessionError(INACTIVE,409 if session.state=='uploading' else 410)
        return session

    def begin(self, token):
        with self.lock:
            session = self.active(token)
            session.state = 'uploading'; session.attempts += 1; session.message = ''
            return session

    def finish(self, token, success, message=''):
        with self.lock:
            session = self.get(token)
            if session.state!='uploading':
                return
            session.state = 'used' if success else 'failed' if session.attempts>=3 else 'error'
            session.message = message

    def cancel(self, token):
        with self.lock:
            if token in self.items and self.items[token].state in ('waiting','uploading','error'):
                self.items[token].state = 'cancelled'

    def cancel_all(self):
        with self.lock:
            for token in self.items:
                self.cancel(token)


class Delivery:
    """A request waits for the Qt-thread commit; a timeout cannot commit later."""
    def __init__(self, session, reference):
        self.session = session; self.reference = reference
        self.event = threading.Event(); self.lock = threading.Lock()
        self.closed = False; self.success = False; self.message = ''

    def apply(self, action):
        with self.lock:
            if self.closed:
                return
            try:
                action(); self.success = True
            except (OSError,ValueError):
                self.message = 'GDS VTS could not save this photo. Please generate a new QR and try again.'
            finally:
                self.closed = True; self.event.set()

    def abort(self, message):
        with self.lock:
            if not self.closed:
                self.closed = True; self.message = message; self.event.set()


class LimitedServer(HTTPServer):
    allow_reuse_address = False
    request_queue_size = 4

    def __init__(self, address, owner):
        self.owner = owner; self.slots = threading.BoundedSemaphore(4)
        self.workers = {}; self.worker_lock = threading.Lock()
        super().__init__(address,UploadHandler)

    def get_request(self):
        connection,address = super().get_request()
        connection.settimeout(15)
        return connection,address

    def process_request(self, connection, address):
        if not self.slots.acquire(False):
            try:
                connection.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.finish_response(connection)
                self.shutdown_request(connection)
            return
        worker = threading.Thread(target=self.run_request,args=(connection,address),name='vjr-photo-request',daemon=True)
        with self.worker_lock:
            self.workers[connection] = worker
        worker.start()

    def run_request(self, connection, address):
        try:
            self.finish_request(connection,address)
        except (OSError,ValueError):
            pass
        finally:
            self.finish_response(connection)
            self.shutdown_request(connection)
            with self.worker_lock:
                self.workers.pop(connection,None)
            self.slots.release()

    @staticmethod
    def finish_response(connection):
        # Windows can reset a socket closed with an unread rejected POST body,
        # hiding the friendly error response from the phone. Half-close the
        # response first, then drain only a bounded amount of incoming data.
        try:
            connection.shutdown(socket.SHUT_WR)
            deadline = time.monotonic()+.2
            remaining = 65536
            while remaining:
                wait = deadline-time.monotonic()
                if wait<=0:
                    break
                connection.settimeout(wait)
                data = connection.recv(min(8192,remaining))
                if not data:
                    break
                remaining -= len(data)
        except OSError:
            pass

    def close_workers(self):
        with self.worker_lock:
            workers = list(self.workers.items())
        for connection,_ in workers:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        for _,worker in workers:
            if worker is not threading.current_thread():
                worker.join(timeout=3)


class UploadService:
    def __init__(self, storage, deliver, lifetime=600, clock=None, allow_loopback=False):
        self.storage = storage; self.deliver = deliver
        self.sessions = Sessions(lifetime,clock); self.allow_loopback = allow_loopback
        self.server = None; self.thread = None; self.address = ''; self.port = 0
        self.deliveries = set(); self.delivery_lock = threading.Lock(); self.stopping = False

    def start(self, address, preferred_port=0):
        if not is_lan_address(address) and not (self.allow_loopback and address=='127.0.0.1'):
            raise PhotoError('Select an active LAN IPv4 address, not localhost or a public address.')
        try:
            preferred_port = int(preferred_port)
            if not 0<=preferred_port<=65535:
                raise ValueError('Port out of range')
        except (ValueError,TypeError,OverflowError):
            raise PhotoError('Choose a local upload port between 0 and 65535 (0 selects a free port).')
        if self.server and self.address==address:
            return
        self.close(); self.stopping = False
        try:
            try:
                server = LimitedServer((address,int(preferred_port)),self)
            except OSError:
                if not preferred_port:
                    raise
                server = LimitedServer((address,0),self)
        except OSError as error:
            raise PhotoError('Cannot start local upload on the selected address. Check the network and try again.') from error
        self.server = server; self.address = address; self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.1),name='vjr-photo-server',daemon=True)
        self.thread.start(); LOG.info('Photo upload server started on local port %s',self.port)

    def create_session(self, report_id, slot):
        if not self.server:
            raise PhotoError('Upload service is not running')
        return self.sessions.create(report_id,slot)

    def url(self, session):
        return 'http://%s:%s/vjr-photo/%s' % (self.address,self.port,session.token)

    def accepts(self, delivery):
        session = self.sessions.get(delivery.session.token)
        return not self.stopping and session.state=='uploading'

    def upload(self, session, payload, filename, content_type):
        reference = self.storage.create(session.report_id,payload,filename,content_type)
        delivery = Delivery(session,reference)
        try:
            if self.stopping or not self.accepts(delivery):
                raise SessionError(INACTIVE)
            with self.delivery_lock:
                self.deliveries.add(delivery)
            self.deliver(delivery)
            if not delivery.event.wait(20):
                delivery.abort('GDS VTS did not respond in time. Please generate a new QR and try again.')
            if not delivery.success:
                raise PhotoError(delivery.message or INACTIVE)
            LOG.info('Photo upload completed: %s',session.slot)
        finally:
            self.storage.release(reference)
            if not delivery.success:
                self.storage.discard(reference)
            with self.delivery_lock:
                self.deliveries.discard(delivery)
        return reference

    def close(self):
        self.stopping = True; self.sessions.cancel_all()
        with self.delivery_lock:
            deliveries = list(self.deliveries)
        for delivery in deliveries:
            delivery.abort(INACTIVE)
        server,self.server = self.server,None
        if server:
            server.shutdown(); server.close_workers(); server.server_close()
            if self.thread:
                self.thread.join(timeout=3)
            LOG.info('Photo upload server stopped')
        self.thread = None; self.port = 0


class UploadHandler(BaseHTTPRequestHandler):
    server_version = 'GDSPhoto'
    sys_version = ''

    def log_message(self, *args):
        pass  # The default request logger would expose bearer tokens.

    def send_body(self, status, payload, content_type='text/html; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store'); self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Connection','close')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src blob:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers(); self.wfile.write(payload); self.close_connection = True

    def message(self, status, message, post=False):
        if post:
            return self.send_body(status,json.dumps(dict(message=message)).encode('utf-8'),'application/json')
        from html import escape
        return self.send_body(status,('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>GDS VTS</title><main style="font:18px sans-serif;max-width:480px;margin:40px auto;padding:24px"><h1>GDS VTS</h1><p>'+escape(message)+'</p></main>').encode('utf-8'))

    def route(self):
        owner = self.server.owner
        peer = self.client_address[0]
        if not is_lan_address(peer) and peer!='127.0.0.1':
            raise SessionError('This upload service is available on the local network only.',403)
        origin = 'http://%s:%s' % (owner.address,owner.port)
        if self.headers.get('Host')!='%s:%s' % (owner.address,owner.port):
            raise SessionError('Open the local address shown in GDS VTS.',403)
        if self.headers.get('Origin') not in (None,origin) or self.headers.get('Sec-Fetch-Site') not in (None,'none','same-origin'):
            raise SessionError('Open the upload page using the QR code in GDS VTS.',403)
        path = urlsplit(self.path)
        match = TOKEN.fullmatch(path.path)
        if not match or path.query:
            raise SessionError('This upload page was not found.',404)
        return owner,match[1]

    def do_GET(self):
        try:
            owner,token = self.route(); session = owner.sessions.active(token)
            self.send_body(200,upload_page(TITLES[session.slot]))
        except SessionError as error:
            self.message(error.status,str(error))
        except (OSError,ValueError):
            self.message(503,'The upload page is unavailable. Please regenerate the QR in GDS VTS.')

    def do_POST(self):
        owner = None; token = None; begun = False
        try:
            owner,token = self.route(); session = owner.sessions.begin(token); begun = True
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:
                raise PhotoError('Upload a single JPEG or PNG image with a known file size.')
            try:
                length = int(self.headers.get('Content-Length',''))
            except ValueError:
                raise PhotoError('The photo size could not be read.')
            if length>MAX_UPLOAD:
                raise SessionError('Photo exceeds maximum allowed size.',413)
            if length<=0:
                raise PhotoError('Choose a photo before uploading.')
            filename = unquote(self.headers.get('X-Photo-Name',''))
            if len(filename)>255:
                raise PhotoError('Photo filename is too long.')
            data = self.rfile.read(length)
            if len(data)!=length:
                raise PhotoError('Photo upload was interrupted. Please try again.')
            owner.upload(session,data,filename,self.headers.get_content_type())
            owner.sessions.finish(token,True)
            self.message(200,'Photo uploaded successfully. You may return to GDS VTS.',True)
        except (SessionError,PhotoError) as error:
            if begun:
                owner.sessions.finish(token,False,str(error))
            LOG.warning('Photo upload rejected: %s',type(error).__name__)
            self.message(getattr(error,'status',400),str(error),True)
        except (OSError,ValueError):
            if begun:
                owner.sessions.finish(token,False,'Photo upload was interrupted. Please try again.')
            self.message(400,'Photo upload was interrupted. Please try again.',True)

    def do_HEAD(self):
        self.message(405,'Use the upload page opened by the QR code.')
