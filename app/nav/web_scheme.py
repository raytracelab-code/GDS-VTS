"""Secure application scheme for bundled NAV resources; registered pre-QApplication."""
from pathlib import Path
import mimetypes
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,QFile,Signal,QSettings,QCoreApplication
from PySide6.QtWebEngineCore import QWebEngineUrlScheme,QWebEngineUrlSchemeHandler,QWebEngineUrlRequestJob
def register_gds_scheme():
 scheme=QWebEngineUrlScheme(b'gds');scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
 scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme|QWebEngineUrlScheme.Flag.LocalAccessAllowed|QWebEngineUrlScheme.Flag.CorsEnabled|QWebEngineUrlScheme.Flag.FetchApiAllowed)
 QWebEngineUrlScheme.registerScheme(scheme)

ROOT=Path(__file__).resolve().parents[1]/'resources'/'map'
MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.pbf':'application/x-protobuf'}
def resolve_gds_map_path(host,path):
 if host!='map' or not path or '..' in path.replace('\\','/').split('/'): return None
 candidate=(ROOT/path.lstrip('/')).resolve()
 try: candidate.relative_to(ROOT.resolve())
 except ValueError: return None
 return candidate if candidate.is_file() else None
class GdsMapSchemeHandler(QWebEngineUrlSchemeHandler):
 tileReady=Signal(object,object,object)
 def __init__(self,parent=None):
  super().__init__(parent)
  from concurrent.futures import ThreadPoolExecutor
  from app.nav.offline_maps.manager import PackageManager
  from app.nav.offline_maps.render_config import render_config
  from app.nav.offline_maps.mbtiles import MapPackageError
  try:
   self.package=PackageManager().discover(QSettings('GDS','VTS').value('nav/map_package',''))
   self.config=render_config(self.package)
  except (MapPackageError,OSError):
   # A removable package can disappear after discovery, before style creation.
   self.package=None;self.config=render_config(None)
  self.readers={};self.pending=0;self.closed=False
  self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='offline-tiles')
  self.tileReady.connect(self._tile_reply)
  QCoreApplication.instance().aboutToQuit.connect(self.close)
 def close(self):
  if self.closed:return
  self.closed=True;self.pool.shutdown(wait=True,cancel_futures=True)
  for reader in self.readers.values():reader.close()
 def _tile_reply(self,job,mime,data):
  from shiboken6 import isValid
  self.pending-=1
  if self.closed or not isValid(job):return
  if data is None:self._tile_unavailable(job);return
  buf=QBuffer(job);buf.setData(QByteArray(data));buf.open(QIODevice.OpenModeFlag.ReadOnly);job.reply(mime.encode(),buf)
 def _tile_unavailable(self,job):
  # Qt custom-scheme fail() can leave Fetch arrayBuffer() pending after headers.
  # A finite explicit error body always completes; it contains no fabricated map.
  buf=QBuffer(job);buf.setData(QByteArray(b'{"error":"offline_tile_unavailable"}'));buf.open(QIODevice.OpenModeFlag.ReadOnly);job.reply(b'application/json',buf)
 def _tile_request(self,job,path):
  from app.nav.offline_maps.mbtiles import MBTiles,MapPackageError,xyz_to_tms
  from app.nav.offline_maps.manager import safe_file
  import os,re
  match=re.fullmatch(r'/([A-Za-z0-9._-]+)/([A-Za-z0-9-]+)/(\d{1,2})/(\d{1,8})/(\d{1,8})\.(pbf|mvt|png|jpg|jpeg|webp)',path)
  if self.closed or not self.package or not match or self.pending>=64:
   self._tile_unavailable(job);return
  package_id,role,z,x,y,extension=match.groups();spec=self.config['tiles'].get(role)
  if package_id!=self.package.manifest['package_id'] or not spec or spec['format']!=extension:
   self._tile_unavailable(job);return
  try:
   z,x,y=int(z),int(x),int(y);xyz_to_tms(z,x,y)
   if role not in self.readers:
    try:cache=int(os.environ.get('GDS_MAP_TILE_CACHE_SIZE','128'))
    except ValueError:cache=128
    self.readers[role]=MBTiles(safe_file(self.package.root,spec['file']),cache)
  except (MapPackageError,OSError):
   self._tile_unavailable(job);return
  self.pending+=1
  future=self.pool.submit(self.readers[role].tile,z,x,y)
  def finished(result):
   from shiboken6 import isValid
   try:data=result.result()
   except Exception:data=None
   if isValid(self):self.tileReady.emit(job,spec['mime'],data)
  future.add_done_callback(finished)
 def requestStarted(self,job):
  url=job.requestUrl();host,path=url.host(),url.path();print(f'GDS REQUEST host={host} path={path}',flush=True)
  if host=='tiles':self._tile_request(job,path);return
  if host=='package' and self.package:
   from app.nav.offline_maps.manager import safe_file
   try:
    name=path.lstrip('/')
    if name not in self.package.manifest.get('asset_files',[]):raise ValueError()
    target=safe_file(self.package.root,name)
    if target.stat().st_size>16*1024*1024:raise ValueError()
    data=QByteArray(target.read_bytes())
   except (ValueError,OSError):job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
  elif host!='map': job.fail(QWebEngineUrlRequestJob.Error.RequestDenied);return
  elif path=='/assets/qwebchannel.js': f=QFile(':/qtwebchannel/qwebchannel.js');f.open(QIODevice.OpenModeFlag.ReadOnly);data=f.readAll()
  else:
   target=resolve_gds_map_path(host,path)
   if not target: job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
   data=QByteArray(target.read_bytes())
  suffix=Path(path).suffix; mime=MIME.get(suffix)
  if not mime: job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
  buf=QBuffer(job);buf.setData(data);buf.open(QIODevice.OpenModeFlag.ReadOnly);job.reply(mime.encode(),buf);print(f'GDS SERVED {path}',flush=True)
