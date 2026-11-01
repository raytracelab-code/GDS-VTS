"""Secure application scheme for bundled NAV resources; registered pre-QApplication."""
from pathlib import Path
import mimetypes
from PySide6.QtCore import QByteArray,QBuffer,QIODevice,QFile
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
 def requestStarted(self,job):
  url=job.requestUrl();host,path=url.host(),url.path();print(f'GDS REQUEST host={host} path={path}',flush=True)
  if host!='map': job.fail(QWebEngineUrlRequestJob.Error.RequestDenied);return
  if path=='/assets/qwebchannel.js': f=QFile(':/qtwebchannel/qwebchannel.js');f.open(QIODevice.OpenModeFlag.ReadOnly);data=f.readAll()
  else:
   target=resolve_gds_map_path(host,path)
   if not target: job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
   data=QByteArray(target.read_bytes())
  suffix=Path(path).suffix; mime=MIME.get(suffix)
  if not mime: job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound);return
  buf=QBuffer(job);buf.setData(data);buf.open(QIODevice.OpenModeFlag.ReadOnly);job.reply(mime.encode(),buf);print(f'GDS SERVED {path}',flush=True)
