"""Opt-in real NASA GIBS acceptance. Normal HTTP cache only; no credentials."""
import json
import sys
import time
import argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import main as entry
from app.nav.satellite_map import satellite_config
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

OUTPUT=Path('docs/diagnostics')
SCENES=[('marine','MARINE','DAY'),('satellite-day','SATELLITE','DAY'),
        ('satellite-twilight','SATELLITE','TWILIGHT'),('satellite-night','SATELLITE','NIGHT'),
        ('satellite-3d','SATELLITE','NIGHT'),('satellite-panels','SATELLITE','NIGHT'),
        ('marine-return','MARINE','NIGHT'),('satellite-return','SATELLITE','NIGHT'),
        ('network-loss','MARINE','NIGHT'),('all-network-loss','MARINE','NIGHT')]

SNAPSHOT="""JSON.stringify((()=>{
 if(typeof map==='undefined'||!ready||!basemapModes)return null;
 const layers=map.getStyle().layers,base=window.satelliteAcceptanceBaseline;
 const op=layers.filter(l=>l.source&&!['basemap','satellite','hybrid'].includes(l.metadata?.['gds:owner'])&&!l.metadata?.['gds:effect']).map(l=>l.id);
 const raster=map.getLayer('nasa-gibs-satellite-raster'),state=basemapModes.snapshot;
 const count=ids=>ids.length?map.queryRenderedFeatures({layers:ids}).length:0;
 return {ready,status:status.textContent,basemap:state,tiles_loaded:map.areTilesLoaded(),
  camera:{center:map.getCenter(),zoom:map.getZoom(),bearing:map.getBearing(),pitch:map.getPitch()},
  source_identity:!base||Object.entries(base.sources).every(([id,source])=>map.getSource(id)===source),
  selected_id:latestMaritimeState?.selected_object_id,follow:followEnabled,
  source_ids:Object.keys(map.getStyle().sources),operational_rendered:count(op),
  platforms:count(['gis-malaysia_platform-point']),pipelines:count(['gis-malaysia_pipeline-line']),
  fields:count(['gis-malaysia_fields_all-boundary']),
  raster:raster?{visible:raster.layout?.visibility||'visible',
   brightness:map.getPaintProperty(raster.id,'raster-brightness-max'),
   saturation:map.getPaintProperty(raster.id,'raster-saturation'),
   below_operational:op.every(id=>layers.findIndex(l=>l.id===raster.id)<layers.findIndex(l=>l.id===id)),
   source:map.getStyle().sources[raster.source]}:null,
  hybrid_layers:layers.filter(l=>l.metadata?.['gds:owner']==='hybrid').map(l=>({id:l.id,visibility:l.layout?.visibility,paint:l.paint})),
  hud_present:Boolean(document.getElementById('geographic-hud')),
  pipeline_glow:map.getPaintProperty('gis-malaysia_pipeline-line-glow','line-opacity')};
})())"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick',action='store_true')
    args=parser.parse_args()
    if args.quick:SCENES[:]=[SCENES[0],SCENES[1]]
    app=QApplication([]);app.setApplicationName('GDS VTS');window=entry.MainWindow()
    class Requests(QWebEngineUrlRequestInterceptor):
        def __init__(self,parent):super().__init__(parent);self.nasa=0;self.block_nasa=False;self.block_all=False
        def interceptRequest(self,info):
            nasa=info.requestUrl().host()=='gibs.earthdata.nasa.gov'
            if nasa:self.nasa+=1
            if (nasa and self.block_nasa) or (self.block_all and info.requestUrl().scheme() in ('http','https')):info.block(True)
    interceptor=Requests(window);window.nav.web_profile.setUrlRequestInterceptor(interceptor)
    window.setWindowTitle('GDS VTS - NASA GIBS validation');window.showMaximized();window.tabs.buttons['Nav'].click()
    nav=window.nav;nav.palette.minute.stop();nav.palette.changed.disconnect(nav._palette_changed)
    report={'provider':satellite_config(),'scenes':[]};index=-1;phase_started=time.monotonic();finishing=False;capturing=False
    timer=QTimer(window);timer.setInterval(500)

    def finish():
        nonlocal finishing
        if finishing:return
        finishing=True;timer.stop();OUTPUT.mkdir(parents=True,exist_ok=True)
        report['offline_readers']=len(nav._gds_scheme_handler.readers)
        (OUTPUT/'hybrid-satellite-runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('NASA_VALIDATION '+json.dumps(report),flush=True);window.close();app.quit()

    def begin_scene():
        nonlocal index,phase_started,capturing
        index+=1;capturing=False
        if index>=len(SCENES):finish();return
        name,mode,palette=SCENES[index];phase_started=time.monotonic()
        nav._palette_changed({**nav.palette.payload,'effective_state':palette,'computed_solar_state':palette})
        if index==0:
            nav.web.page().runJavaScript("setLayerVisibility('Bathymetry',true);map.jumpTo({center:[104,5.5],zoom:8,bearing:17,pitch:0})")
            # Select a real installation without moving the diagnostic camera.
            def select():
                objects=[o for o in window.maritime_service.render_snapshot() if o.properties.get('gis_layer')=='malaysia_platform' and o.geometry['type']=='Point']
                if objects:
                    obj=min(objects,key=lambda o:(o.geometry['coordinates'][0]-104)**2+(o.geometry['coordinates'][1]-5.5)**2)
                    nav.bridge.selectMaritimeObject(obj.object_id)
            QTimer.singleShot(3000,select)
            QTimer.singleShot(4000,lambda:nav.web.page().runJavaScript("window.satelliteAcceptanceBaseline={sources:Object.fromEntries(Object.keys(map.getStyle().sources).map(id=>[id,map.getSource(id)]))}"))
        elif name=='satellite-3d':nav.command('3D')
        elif name=='satellite-panels':
            nav.search.setText('Resak');nav.search_timer.stop();nav.search_results.hide()
            if nav.layers_panel.isHidden():nav.toggle_layers()
        elif name=='network-loss':
            interceptor.block_nasa=True
            nav.web.page().runJavaScript("map.jumpTo({center:[110.5,4.5],zoom:9})")
        elif name=='all-network-loss':
            interceptor.block_all=True
            nav.web.page().runJavaScript("map.jumpTo({center:[115.5,5.5],zoom:9})")
        else:nav.command(mode)

    def captured(value):
        nonlocal capturing
        if finishing:return
        if not value:capturing=False;return
        snapshot=json.loads(value);name=SCENES[index][0]
        snapshot.update(scene=name,nasa_requests=interceptor.nasa,
            satellite_button_enabled=nav.control_buttons['SATELLITE'].isEnabled(),
            marine_checked=nav.control_buttons['MARINE'].isChecked(),satellite_checked=nav.control_buttons['SATELLITE'].isChecked(),
            layers_visible=nav.layers_panel.isVisible(),search=nav.search.text())
        report['scenes'].append(snapshot);window.grab().save(str(OUTPUT/f'hybrid-{name}.png'))
        print('NASA_SCENE '+json.dumps(snapshot),flush=True);begin_scene()

    def check(value):
        nonlocal capturing
        if finishing or capturing or not value:return
        if index<0:
            if value:begin_scene()
            return
        elapsed=time.monotonic()-phase_started
        state=json.loads(value);name,expected,_=SCENES[index]
        settled=state['basemap']['mode']==expected and state['basemap']['state']!='LOADING'
        if elapsed>=6 and (settled or state['basemap']['state']=='ERROR' or elapsed>38):
            capturing=True;nav.web.page().runJavaScript(SNAPSHOT,captured)

    def tick():
        if index<0:
            nav.web.page().runJavaScript("typeof ready!=='undefined'&&ready&&typeof latestMaritimeState!=='undefined'&&latestMaritimeState?.sources?.malaysia_gis?.state==='READY'",check)
        else:nav.web.page().runJavaScript("typeof basemapModes!=='undefined'&&basemapModes?JSON.stringify({basemap:basemapModes.snapshot}):null",check)
    timer.timeout.connect(tick);timer.start();QTimer.singleShot(230000,finish)
    return app.exec()


if __name__=='__main__':raise SystemExit(main())
