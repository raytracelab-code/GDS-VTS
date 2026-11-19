"""Qt 5 custom-scheme Fetch fallback, using the same bundled map and tile readers.

Qt 5 WebEngine lacks FetchApiAllowed. A token-scoped, loopback-only origin serves
existing resources without changing map/data behavior or weakening external TLS.
"""
import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import unquote, urlsplit

from .web_scheme import MIME, resolve_gds_map_path


class LegacyResourceServer:
    def __init__(self, handler):
        self.handler = handler
        # Match the Qt6 scheme's qrc resource, which is not a disk asset.
        from app.qt.QtCore import QFile,QIODevice
        resource=QFile(':/qtwebchannel/qwebchannel.js')
        if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError('Qt WebChannel JavaScript resource is unavailable')
        from .legacy_bridge import browser_adapter
        self.webchannel=bytes(resource.readAll())+browser_adapter();resource.close()
        self.token = secrets.token_urlsafe(24)
        owner = self
        class Request(BaseHTTPRequestHandler):
            def setup(self):
                super().setup();self.connection.settimeout(5)
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.headers.get('Host') != owner.authority or self.headers.get('Origin') not in (None,owner.origin):
                    self.send_error(403); return
                path = unquote(urlsplit(self.path).path)
                prefix = '/'+owner.token+'/'
                if not path.startswith(prefix):
                    self.send_error(404); return
                parts = path[len(prefix):].split('/',1)
                try:
                    mime, payload = owner.read(parts[0],'/'+parts[1] if len(parts)>1 else '/')
                except (OSError,ValueError,KeyError):
                    self.send_error(404); return
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                try:self.wfile.write(payload)
                except (BrokenPipeError,ConnectionResetError,TimeoutError):pass
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Request)
        self.server.daemon_threads = False
        self.authority = '127.0.0.1:'+str(self.server.server_port)
        self.origin = 'http://'+self.authority
        self.base = self.origin+'/'+self.token+'/'
        self.url = self.base+'map/index.html'
        self.thread = Thread(target=self.server.serve_forever,kwargs={'poll_interval':.1},daemon=True,name='legacy-map-assets')
        self.thread.start()

    def read(self, host, path):
        if host == 'map':
            if path=='/assets/qwebchannel.js':
                return MIME['.js'],self.webchannel
            target = resolve_gds_map_path(host,path)
            if target is None:raise ValueError('Unknown map resource')
            payload = target.read_bytes()
            if path == '/index.html':
                # Resource URLs emitted by the existing bridge remain gds://.
                # Normalize only local resources; remote HTTPS is untouched.
                payload=self.html(payload)
            return MIME.get(target.suffix,'application/octet-stream'),payload
        if host == 'tiles':
            error=('application/json',b'{"error":"offline_tile_unavailable"}')
            match=re.fullmatch(r'/([A-Za-z0-9._-]+)/([A-Za-z0-9-]+)/(\d+)/(\d+)/(\d+)\.(pbf|mvt|png|jpg|jpeg|webp)',path)
            if not match:return error
            package,role,z,x,y,extension=match.groups()
            config=next((p for p in self.handler.config.get('regional_packages',[]) if p['package_id']==package),{})
            spec=config.get('tiles',{}).get(role)
            if not spec or spec['format']!=extension:return error
            from .offline_maps.mbtiles import xyz_to_tms
            z,x,y=int(z),int(x),int(y);xyz_to_tms(z,x,y)
            payload=self.handler.regional.tile(package,role,z,x,y,extension)
            return (spec['mime'],payload) if payload is not None else error
        if host == 'package' and self.handler.package:
            from .offline_maps.manager import safe_file
            name=path.lstrip('/')
            if name not in self.handler.package.manifest.get('asset_files',[]):raise ValueError('Unknown asset')
            target=safe_file(self.handler.package.root,name)
            if target.stat().st_size>16*1024*1024:raise ValueError('Asset too large')
            return MIME.get(target.suffix,'application/octet-stream'),target.read_bytes()
        raise ValueError('Unknown local resource host')

    def html(self, payload):
        script = '''<script>(function(){
const base=BASE;
const local=u=>typeof u==='string'&&u.startsWith('gds://')?base+u.slice(6):u;
const fetchOriginal=window.fetch.bind(window);
window.fetch=(u,o)=>fetchOriginal(typeof u==='string'?local(u):u instanceof Request&&u.url.startsWith('gds://')?new Request(local(u.url),u):u,o);
const openOriginal=XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open=function(m,u,...a){return openOriginal.call(this,m,local(u),...a)};
if(!Array.prototype.at)Object.defineProperty(Array.prototype,'at',{value:function(i){i=Math.trunc(i)||0;return this[i<0?this.length+i:i]}});
if(!Object.hasOwn)Object.hasOwn=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
})();</script>'''.replace('BASE',json.dumps(self.base))
        return payload.replace(b'<head>',b'<head>'+script.encode('utf-8'),1)

    def browser_config(self,value):
        """Normalize bridge URLs too: MapLibre workers have a separate Fetch."""
        if isinstance(value,str):return self.base+value[6:] if value.startswith('gds://') else value
        if isinstance(value,dict):return {key:self.browser_config(item) for key,item in value.items()}
        if isinstance(value,(list,tuple)):return [self.browser_config(item) for item in value]
        return value

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
