"""Secure application scheme for bundled NAV resources; registered pre-QApplication."""
from pathlib import Path
import mimetypes
from app.qt.QtCore import QByteArray,QBuffer,QIODevice,QFile,Signal,QSettings,QCoreApplication
from app.qt.QtWebEngineCore import QWebEngineUrlScheme,QWebEngineUrlSchemeHandler,QWebEngineUrlRequestJob
def register_gds_scheme():
 scheme=QWebEngineUrlScheme(b'gds');scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
 flags=QWebEngineUrlScheme.Flag.SecureScheme|QWebEngineUrlScheme.Flag.LocalAccessAllowed|QWebEngineUrlScheme.Flag.CorsEnabled
 if hasattr(QWebEngineUrlScheme.Flag,'FetchApiAllowed'):flags|=QWebEngineUrlScheme.Flag.FetchApiAllowed
 scheme.setFlags(flags)
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
  from app.core.compat import ThreadPoolExecutor
  from app.nav.offline_maps.manager import PackageManager
  from app.nav.offline_maps.render_config import render_config
  from app.nav.offline_maps.mbtiles import MapPackageError
  import os
  self.packages=[];self.package=None
  if os.environ.get('GDS_MAP_SOURCE','online').lower()=='offline':
   try:
    manager=PackageManager()
    self.packages=manager.installed_regions(enabled_only=True)
    from app.nav.offline_maps.regional import regional_config
    self.config=regional_config(self.packages)
    self.package=next((p for p in self.packages if p.manifest['package_id']==self.config.get('package_id')),None)
   except (MapPackageError,OSError):self.config=render_config(None)
  else:
   from app.nav.online_map import online_config
   self.config=online_config()
  from app.nav.offline_maps.regional import RegionalReaders
  self.regional=RegionalReaders(getattr(self,'packages',[]));self.readers=self.regional.readers;self.pending=0;self.closed=False
  self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='offline-tiles')
  self.tileReady.connect(self._tile_reply)
  QCoreApplication.instance().aboutToQuit.connect(self.close)
 def close(self):
  if self.closed:return
  self.closed=True
  if hasattr(self,'_legacy_server'):self._legacy_server.close()
  self.pool.shutdown(wait=True,cancel_futures=True)
  self.regional.close()
 def reload_packages(self):
  from app.nav.offline_maps.manager import PackageManager
  from app.nav.offline_maps.regional import regional_config
  manager=PackageManager();packages=manager.installed_regions(enabled_only=True)
  primary=manager.discover()
  if primary and not any(p.manifest['package_id']==primary.manifest['package_id'] for p in packages):primary=None
  config=regional_config(packages,primary)
  with self.regional.lock:
   self.regional.close();self.regional.packages={p.manifest['package_id']:p for p in packages}
  self.packages=packages;self.package=next((p for p in packages if p.manifest['package_id']==config.get('package_id')),None);self.config=config
  return config
 def _tile_reply(self,job,mime,data):
  from app.qt import isValid
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
  if self.closed or not match or self.pending>=64:
   self._tile_unavailable(job);return
  package_id,role,z,x,y,extension=match.groups()
  config=next((p for p in self.config.get('regional_packages',[]) if p['package_id']==package_id),{})
  spec=config.get('tiles',{}).get(role)
  if not spec or spec['format']!=extension:
   self._tile_unavailable(job);return
  try:
   z,x,y=int(z),int(x),int(y);xyz_to_tms(z,x,y)
  except (MapPackageError,OSError):
   self._tile_unavailable(job);return
  self.pending+=1
  future=self.pool.submit(self.regional.tile,package_id,role,z,x,y,extension)
  def finished(result):
   from app.qt import isValid
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
