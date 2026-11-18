"""Opt-in real NAV validation. Blocks WebEngine HTTP; no production fake maps.

The diagnostic alone injects deterministic UTC for AUTO visual checks.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=90)
    parser.add_argument('--output',type=Path,default=Path('docs/diagnostics/offline-map-runtime.json'))
    parser.add_argument('--offline-providers',action='store_true',help='Disable online operational adapters in this diagnostic process only')
    parser.add_argument('--show-nav-after',type=float,default=0,help='Delay opening NAV to exercise hidden-tab canvas sizing')
    parser.add_argument('--route',help='Comma-separated installed regional package IDs; 35 seconds per region')
    parser.add_argument('--fixed-palette',choices=('DAY','TWILIGHT','NIGHT'),help='Diagnostic-only fixed solar scene')
    args=parser.parse_args()
    import main as entry
    if args.offline_providers:
        from app.nav.maritime.runtime import MaritimeRuntime
        from app.nav.maritime.config import MaritimeConfig
        from app.nav.maritime.source_health import SourceState
        def local_runtime(parent):
            runtime=MaritimeRuntime(parent,config=MaritimeConfig(env={'AISSTREAM_ENABLED':'false','GDS_GEBCO_ENABLED':'false'}))
            # This runs before the first Qt tick; no online adapter starts I/O.
            runtime.adapters.clear();runtime.config.sources.clear()
            for key,health in runtime.service.sources.items():
                if key!='malaysia_gis':health.state=SourceState.DISABLED
            return runtime
        entry.MainWindow.__init__.__globals__['MaritimeRuntime']=local_runtime
    from PySide6.QtCore import QTimer
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    class BlockHTTP(QWebEngineUrlRequestInterceptor):
        def __init__(self,parent):super().__init__(parent);self.blocked=[];self.local=[]
        def interceptRequest(self,info):
            if info.requestUrl().scheme() in ('http','https'):
                self.blocked.append(info.requestUrl().host());info.block(True)
            elif info.requestUrl().scheme()=='gds':
                self.local.append(info.requestUrl().toString())
    original=entry.MainWindow.__init__
    def initialize(window):
        original(window)
        window.setWindowTitle('GDS VTS - Offline palette validation')
        if args.show_nav_after:
            QTimer.singleShot(int(args.show_nav_after*1000),window.tabs.buttons['Nav'].click)
        else:window.tabs.buttons['Nav'].click()
        window.validation_interceptor=BlockHTTP(window)
        window.nav.web_profile.setUrlRequestInterceptor(window.validation_interceptor)
        report={'asset_installed':window.nav.bridge.offline_config['installed'],'snapshots':[],
                'offline_providers':args.offline_providers,'clock':'DIAGNOSTIC ONLY deterministic UTC'}
        original_mode=window.nav.palette.engine.mode
        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(lambda:window.nav.palette.settings.setValue('nav/palette',original_mode))
        def capture(value):
            if not value:return
            snapshot=json.loads(value)
            snapshot['palette']=window.nav.palette.payload
            snapshot['blocked_http']=window.validation_interceptor.blocked
            snapshot['local_request_count']=len(window.validation_interceptor.local)
            snapshot['local_tile_requests']=[url for url in window.validation_interceptor.local if url.startswith('gds://tiles/')]
            snapshot['local_glyph_requests']=[url for url in window.validation_interceptor.local if '/glyphs/' in url]
            snapshot['sqlite_reader_count']=len(window.nav._gds_scheme_handler.readers)
            snapshot['sqlite_reader_keys']=['/'.join(key) for key in list(window.nav._gds_scheme_handler.readers)]
            report['snapshots'].append(snapshot)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
            print('OFFLINE VALIDATION '+json.dumps(snapshot),flush=True)
        snapshot="""JSON.stringify((()=>{
         if(typeof map==='undefined'||!map||!ready)return {ready:false};
         const layers=map.getStyle().layers,ids=layers.filter(l=>l.id.startsWith('gis-')).map(l=>l.id);
         const baseIds=layers.filter(l=>l.source&&l.metadata&&l.metadata['gds:owner']==='basemap').map(l=>l.id);
         const sourceIds=Object.keys(map.getStyle().sources);
         if(!window.paletteBaseline)window.paletteBaseline={
          sources:Object.fromEntries(sourceIds.map(id=>[id,map.getSource(id)])),
          camera:JSON.stringify([map.getCenter(),map.getZoom(),map.getBearing(),map.getPitch()]),
          layers:layers.map(l=>l.id)};
         const base=window.paletteBaseline;
         const canvas=map.getCanvas(),container=map.getContainer();
         return {ready:true,center:map.getCenter(),zoom:map.getZoom(),source_count:Object.keys(map.getStyle().sources).length,
          canvas_fits_container:canvas.clientWidth===container.clientWidth&&canvas.clientHeight===container.clientHeight,
          layer_count:layers.length,rendered_gis:map.queryRenderedFeatures({layers:ids}).length,
          basemap_sources:Object.keys(map.getStyle().sources).filter(id=>id.startsWith('offline-')),
          basemap_layer_count:baseIds.length,
          rendered_basemap:baseIds.length?map.queryRenderedFeatures({layers:baseIds}).length:0,
          rendered_basemap_layers:baseIds.filter(id=>map.queryRenderedFeatures({layers:[id]}).length>0),
          source_identity_preserved:Object.entries(base.sources).every(([id,source])=>map.getSource(id)===source),
          layer_ids_preserved:JSON.stringify(base.layers)===JSON.stringify(layers.map(l=>l.id)),
          camera_matches_initial:base.camera===JSON.stringify([map.getCenter(),map.getZoom(),map.getBearing(),map.getPitch()]),
          palette_updates:window.paletteChecks||[],
          camera_preserved:(window.paletteChecks||[]).every(c=>c.camera_preserved),
          own_marker:Boolean(marker),errors:window.offlineValidationErrors||[],status:status.textContent,
          visual_effects:layers.filter(l=>l.metadata&&l.metadata['gds:effect']).map(l=>({id:l.id,
           core:l.metadata['gds:core'],kind:l.metadata['gds:effect'],opacity:map.getPaintProperty(l.id,l.type==='line'?'line-opacity':'circle-opacity'),
           adjacent:layers.findIndex(c=>c.id===l.metadata['gds:core'])===layers.indexOf(l)+1})),
          background:map.getPaintProperty('offline-background','background-color')};
        })())"""
        def setup(ok):
            if ok:window.nav.web.page().runJavaScript("""(function wait(){
             if(typeof map==='undefined'||!map||!ready){setTimeout(wait,100);return;}
             window.offlineValidationErrors=[];map.on('error',e=>window.offlineValidationErrors.push(String(e.error&&e.error.message)));
             // Measure immediately across each palette application; the user
             // may pan/zoom during a visible diagnostic session.
             window.paletteChecks=[];
             const originalApply=GdsOffline.apply;
             GdsOffline.apply=function(target,payload){
              const camera=()=>JSON.stringify([target.getCenter(),target.getZoom(),target.getBearing(),target.getPitch()]);
              const before=camera(),style=target.getStyle(),ids=Object.keys(style.sources);
              const sources=ids.map(id=>target.getSource(id));
              const layers=JSON.stringify(style.layers.map(l=>[l.id,l.layout&&l.layout.visibility]));
              const result=originalApply(target,payload);
              window.paletteChecks.push({state:payload.effective_state,camera_preserved:before===camera(),
               sources_preserved:ids.length===Object.keys(target.getStyle().sources).length&&ids.every((id,i)=>target.getSource(id)===sources[i]),
               layers_and_visibility_preserved:layers===JSON.stringify(target.getStyle().layers.map(l=>[l.id,l.layout&&l.layout.visibility]))});
              return result;
             };
             map.fitBounds([[103.3,4.5],[104.6,6.8]],{duration:0,padding:20});
            })()""")
        window.nav.web.loadFinished.connect(setup)
        # Frame the detail scene after a hidden NAV canvas has been shown/resized.
        QTimer.singleShot(max(8000,int(args.show_nav_after*1000)+2000),lambda:
            window.nav.web.page().runJavaScript("if(typeof map!=='undefined'&&ready)map.fitBounds([[103.3,4.5],[104.6,6.8]],{duration:0,padding:20})"))
        def diagnostic(hour,minute=0):
            palette=window.nav.palette
            window.nav.palette_control.setCurrentIndex(window.nav.palette_control.findData('AUTO'))
            palette.engine.mode='AUTO';palette.engine.previous=None
            # Keep the three solar test instants meaningful if the operator
            # pans east/west during this diagnostic. This clock is process-local.
            longitude=palette.center[1] if palette.center else 104
            instant=datetime(2026,3,20,hour,minute,tzinfo=timezone.utc)-timedelta(minutes=4*(longitude-104))
            palette.clock=lambda:instant
            palette.update(force=True)
        if args.route:
            regions={p['package_id']:p for p in window.nav.bridge.offline_config.get('regional_packages',[])}
            def frame(key):
                b=regions[key]['bounds']
                # Official country bounds can include remote islands or span
                # the date line; use explicit camera scenes for visual QA only.
                scenes={'malaysia_singapore_brunei':[[103.3,4.5],[104.6,6.8]],
                        'australia':[[149.8,-34.8],[152.4,-32.7]],
                        'new-zealand':[[165,-48],[180,-33]]}
                scene=scenes.get(key,[[b[0],b[1]],[b[2],b[3]]])
                window.nav.web.page().runJavaScript('map.fitBounds('+json.dumps(scene)+',{duration:0,padding:20,maxZoom:8})')
            for i,key in enumerate(args.route.split(',')):
                if key not in regions:raise ValueError('Route region is not installed: '+key)
                QTimer.singleShot((i*35+9)*1000,lambda k=key:frame(k))
                scenes=((11,5,0),(21,11,20),(31,17,0))
                if args.fixed_palette:
                    scenes=((11,*(dict(DAY=(5,0),TWILIGHT=(11,20),NIGHT=(17,0))[args.fixed_palette])),)
                for offset,hour,minute in scenes:
                    QTimer.singleShot((i*35+offset)*1000,lambda h=hour,m=minute:diagnostic(h,m))
        else:
            for seconds,hour,minute in ((10,5,0),(30,11,20),(50,17,0)):
                QTimer.singleShot(seconds*1000,lambda h=hour,m=minute:diagnostic(h,m))
        window.validation_timer=QTimer(window);window.validation_timer.setInterval(5000)
        window.validation_timer.timeout.connect(lambda:window.nav.web.page().runJavaScript(snapshot,capture));window.validation_timer.start()
        QTimer.singleShot(args.seconds*1000,window.close)
    entry.MainWindow.__init__=initialize
    return entry.main()


if __name__=='__main__':raise SystemExit(main())
