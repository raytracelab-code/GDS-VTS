"""Subprocess integration probe: no provider runtime and no production assets."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.nav.web_scheme import register_gds_scheme, GdsMapSchemeHandler
register_gds_scheme()
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor

app=QApplication([])
profile=QWebEngineProfile()
class BlockHTTP(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self,info):
        if info.requestUrl().scheme() in ('http','https'):info.block(True)
interceptor=BlockHTTP();profile.setUrlRequestInterceptor(interceptor)
handler=GdsMapSchemeHandler(profile);profile.installUrlSchemeHandler(b'gds',handler)
class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self,level,message,line,source):print('PROBE JS '+message,flush=True)
view=QWebEngineView();page=Page(profile,view);view.setPage(page);view.show()
result=[]
def loaded(ok):
    page.runJavaScript("""window.records=[];console.log('probe started');Promise.all([
     'gds://tiles/test-sea/basemap/4/12/8.pbf',
     'gds://tiles/test-sea/bathymetry/4/12/8.png',
     'gds://map/assets/glyphs/KlokanTech%20Noto%20Sans%20Regular/0-255.pbf',
     'gds://tiles/test-sea/basemap/4/12/7.pbf',
     'gds://tiles/wrong/basemap/4/12/8.pbf'
    ].map(async url=>{try{const response=await fetch(url);console.log('headers '+url);const b=await response.arrayBuffer();const r={url,ok:response.ok,length:b.byteLength,type:response.headers.get('content-type')};window.records.push(r);console.log(JSON.stringify(r));return r}catch(e){const r={url,ok:false};window.records.push(r);console.log('fetch failed '+url);return r}})).then(value=>window.probe=value)""")
page.loadFinished.connect(loaded)
def capture(value):
    parsed=json.loads(value) if value else None
    if parsed:
        result.extend(parsed);print('PROBE_RESULT '+value,flush=True);app.quit()
timer=QTimer();timer.setInterval(100);timer.timeout.connect(lambda:page.runJavaScript('JSON.stringify(window.probe||null)',capture));timer.start()
QTimer.singleShot(20000,app.quit)
QTimer.singleShot(5000,lambda:print('HANDLER pending='+str(handler.pending)+' readers='+str(list(handler.readers)),flush=True))
page.setHtml('<!doctype html><title>Offline scheme test</title>',QUrl('gds://map/probe.html'))
app.exec()
handler.close()
page.deleteLater()
assert len(result)==5,result
assert all(r['ok'] for r in result[:3]),result
assert all(r['type']=='application/json' and r['length']>0 for r in result[3:]),result
assert result[0]['type']=='application/x-protobuf' and result[1]['type']=='image/png',result
assert result[0]['length']==35,result
assert result[2]['length']>70000,result
