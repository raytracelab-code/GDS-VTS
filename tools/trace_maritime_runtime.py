"""Opt-in real NAV diagnostics: no fixtures, telemetry, credentials or payload dumps.

Launches the actual main entry point and observes its existing runtime/bridge/map.
--bounds repositions only the diagnostic map; it never creates an own vessel.
"""
import argparse
from collections import Counter
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

ENV_KEYS=('AISSTREAM_ENABLED AISSTREAM_API_KEY GDS_MARITIME_RADIUS_NM GDS_OWN_MMSI '
          'GDS_OVERPASS_ENDPOINT GDS_OVERPASS_FALLBACK_ENDPOINTS GDS_OPENSEAMAP_ENABLED GDS_OPENWATERS_ENABLED GDS_OPENWATERS_STYLE_URL '
          'GDS_GEBCO_ENABLED GDS_GEBCO_WMS_ENDPOINT COPERNICUSMARINE_USERNAME COPERNICUSMARINE_PASSWORD '
          'GDS_CMEMS_WAVE_DATASET GDS_CMEMS_CURRENT_DATASET GDS_CMEMS_SST_DATASET GDS_CMEMS_SEALEVEL_DATASET '
          'GDS_GFW_ENABLED GDS_GFW_API_TOKEN GDS_GFW_LICENSE_ACK GDS_BOEM_ENABLED GDS_BOEM_BASE_URL '
          'GDS_EMODNET_ENABLED GDS_EMODNET_WFS_ENDPOINT GDS_NAVAREA8_ENABLED GDS_NAVAREA8_SOURCE_URL').split()

SNAPSHOT="""JSON.stringify((()=>{
 if(typeof map==='undefined'||!map||!ready)return {ready:false};
 const bounds=map.getBounds(), sources={}, layers={};
 for(const [id,spec] of Object.entries(map.getStyle().sources)){
  if(!id.startsWith('maritime-')&&!id.startsWith('reference-'))continue;
  sources[id]={type:spec.type,count:spec.data&&spec.data.features?spec.data.features.length:0};
 }
 for(const layer of map.getStyle().layers){if(layer.id.startsWith('maritime-')||layer.id.startsWith('reference-'))
  layers[layer.id]={type:layer.type,filter:layer.filter,visibility:map.getLayoutProperty(layer.id,'visibility')||'visible',paint:layer.paint};}
 const hits=map.queryRenderedFeatures({layers:Object.keys(layers).filter(id=>id.startsWith('maritime-'))});
 const unique=new Map(hits.filter(f=>f.properties.object_id).map(f=>[f.properties.object_id,f.properties.category]));
 const categories={};for(const category of unique.values())categories[category]=(categories[category]||0)+1;
 return {ready:true,bounds:[bounds.getWest(),bounds.getSouth(),bounds.getEast(),bounds.getNorth()],zoom:map.getZoom(),
  own_marker:Boolean(marker),js_received:latestMaritimeState?latestMaritimeState.objects.length:0,
  sources,layers,icons:['vessel','neutral','platform','aton','hazard'].map(k=>map.hasImage('maritime-'+k)),
  rendered_unique:unique.size,rendered_categories:categories};
})())"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bounds',nargs=4,type=float,required=True,metavar=('W','S','E','N'))
    parser.add_argument('--seconds',type=int,default=120)
    parser.add_argument('--request-viewport',action='store_true',help='Explicitly submit actual map bounds when diagnosing the old event gate')
    parser.add_argument('--accept-any',action='store_true',help='Controlled comparison with the standalone HTTP probe (omit Accept header)')
    parser.add_argument('--fresh',action='store_true',help='Skip fresh cache in this diagnostic instance to verify real transport')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from app.nav.maritime.area_controller import MaritimeAreaController
    if MaritimeAreaController().viewport(*args.bounds) is None:parser.error('bounds must be a valid bounded viewport')
    import main as entry
    from PySide6.QtCore import QTimer
    from PySide6.QtWebEngineCore import QWebEngineScript
    from PySide6.QtWidgets import QApplication
    from app.nav.maritime.adapters import provider_common,overpass
    from app.nav.maritime.adapters.provider_common import bbox_parts
    from app.nav.maritime.runtime import MaritimeRuntime
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(name)s %(message)s')
    report={'environment':{k:('NOT SET' if not os.environ.get(k) else
            str(os.environ[k].strip().lower() in ('true','1','yes')).upper() if k.endswith(('_ENABLED','_ACK')) else 'SET') for k in ENV_KEYS},
            'requested_bounds':args.bounds,'http':[],'overpass':[],'deliveries':[],'viewport_events':[],'signal_counts':[]}
    lock=threading.Lock()
    original_open=provider_common.urlopen
    class Response:
        def __init__(self,response):self.response=response
        def __getattr__(self,name):return getattr(self.response,name)
        def __enter__(self):self.response.__enter__();return self
        def __exit__(self,*values):return self.response.__exit__(*values)
        def read(self,size):
            content=self.response.read(size)
            item={'status':self.response.status,'bytes':len(content),'headers':{k:self.response.headers.get(k) for k in ('Content-Type','Content-Length','Retry-After','Server') if self.response.headers.get(k)}}
            try:
                payload=json.loads(content)
                if isinstance(payload,dict) and 'elements' in payload:
                    item['osm_elements']=len(payload['elements'])
                    remark=str(payload.get('remark','')).lower()
                    item['incomplete']=bool(remark)
                    item['reason']='OUT_OF_MEMORY' if 'memory' in remark else 'TIMEOUT' if 'timed out' in remark or 'timeout' in remark else 'PROVIDER_ERROR' if remark else None
            except (ValueError,UnicodeError):pass
            with lock:report['http'].append(item)
            print('TRACE HTTP '+json.dumps(item),flush=True)
            return content
    def open_request(*values,**options):
        if args.accept_any and values and hasattr(values[0],'remove_header'):values[0].remove_header('Accept')
        try:return Response(original_open(*values,**options))
        except Exception as error:
            item={'error':type(error).__name__,'status':getattr(error,'code',None)}
            with lock:report['http'].append(item)
            print('TRACE HTTP '+json.dumps(item),flush=True);raise
    provider_common.urlopen=open_request
    original_normalize=overpass.OverpassAdapter.normalize
    def normalize(adapter,payload,area):
        result=original_normalize(adapter,payload,area)
        item={'raw':len(payload['elements']),'normalized':len(result),
              'categories':dict(Counter(str(o.category) for o in result)),
              'types':dict(Counter(o.object_type for o in result))}
        with lock:report['overpass'].append(item)
        print('TRACE NORMALIZE '+json.dumps(item),flush=True);return result
    overpass.OverpassAdapter.normalize=normalize
    original_receive=MaritimeRuntime._receive
    def receive(runtime,key,generation,objects,error,cached):
        count=len(objects) if isinstance(objects,list) else len(objects.objects) if objects is not None else 0
        original_receive(runtime,key,generation,objects,error,cached)
        item={'source':key,'normalized':count,'error':error,'cached':cached,'service':len(runtime.service.snapshot()),
              'bridge':len(runtime.parent().nav.bridge.getMaritimeState()['objects'])}
        report['deliveries'].append(item);print('TRACE DELIVERY '+json.dumps(item),flush=True)
    MaritimeRuntime._receive=receive
    original_init=entry.MainWindow.__init__
    def initialize(window):
        original_init(window)
        window.setWindowTitle('GDS VTS — Maritime diagnostics');window.navigate('Nav')
        w,s,e,n=args.bounds
        camera=QWebEngineScript();camera.setName('diagnostic-camera');camera.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        camera.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        camera.setSourceCode(f"(()=>{{const timer=setInterval(()=>{{if(typeof map!=='undefined'&&map){{clearInterval(timer);map.fitBounds([[{w},{s}],[{e},{n}]],{{padding:0,duration:0}})}}}},10)}})()")
        window.nav.web.page().scripts().insert(camera)
        runtime=window.maritime_runtime
        if args.fresh:runtime.cache.load_fresh=lambda *args:None
        report['startup_sources']={k:{'state':str(v.state),'instantiated':k in runtime.adapters or (k=='aisstream' and runtime.aisstream is not None)} for k,v in runtime.service.sources.items()}
        report['visibility']={k:v.isChecked() for k,v in window.nav.layer_checks.items()}
        print('TRACE STARTUP '+json.dumps(report['startup_sources']),flush=True)
        window.nav.bridge.maritimeViewportChanged.connect(lambda *bounds:report['viewport_events'].append(bounds))
        window.nav.bridge.maritimeStateChanged.connect(lambda payload:report['signal_counts'].append(len(payload['objects'])))
        started=time.monotonic();positioned=False;submitted=False
        def write_snapshot(value):
            nonlocal positioned,submitted
            if not value:return
            snapshot=json.loads(value);report['map']=snapshot
            if snapshot.get('ready') and not positioned:
                report['before_camera_change']={'map':snapshot,'area':runtime.service.area.payload() if runtime.service.area else None}
                w,s,e,n=args.bounds
                window.nav.web.page().runJavaScript(f'map.fitBounds([[{w},{s}],[{e},{n}]],{{padding:0,duration:0}})')
                positioned=True;return
            if positioned and args.request_viewport and not submitted:
                window.nav.web.page().runJavaScript('(()=>{const b=map.getBounds();bridge.reportMaritimeViewport(b.getWest(),b.getSouth(),b.getEast(),b.getNorth())})()')
                submitted=True
            service=runtime.service;payload=window.nav.bridge.getMaritimeState()
            report['runtime']={'telemetry':window.state.telemetry_status.value,'own_position':service.own_position,
                'area':service.area.payload() if service.area else None,'provider_bboxes':bbox_parts(service.area) if service.area else [],
                'service_count':len(service.snapshot()),'bridge_count':len(payload['objects']),
                'render_count':sum(len(v['features']) for k,v in payload['geojson'].items() if k!='selection'),
                'sources':payload['sources'],'busy':sorted(runtime._busy)}
            if snapshot.get('ready') and 'reference-gebco' in snapshot.get('sources',{}) and 'first_bathymetry' not in report:
                report['first_bathymetry']={'map':snapshot,'runtime':report['runtime']}
            if snapshot.get('rendered_unique') and 'first_rendered' not in report:
                report['first_rendered']={'map':snapshot,'runtime':report['runtime']}
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with lock:
                temporary=args.output.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2),encoding='utf8');temporary.replace(args.output)
            if time.monotonic()-started>=args.seconds:
                window.trace_timer.stop();window.close();QApplication.instance().quit()
        def tick():window.nav.web.page().runJavaScript(SNAPSHOT,write_snapshot)
        window.trace_timer=QTimer(window);window.trace_timer.setInterval(1000);window.trace_timer.timeout.connect(tick);window.trace_timer.start()
        QTimer.singleShot((args.seconds+15)*1000,window.close)
    entry.MainWindow.__init__=initialize
    return entry.main()


if __name__=='__main__':raise SystemExit(main())
