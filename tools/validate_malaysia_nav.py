"""Opt-in real WebEngine/MapLibre validation over supplied GIS, without telemetry."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

SNAPSHOT = """JSON.stringify((()=>{
 if(typeof map==='undefined'||!map||!ready)return {ready:false};
 const layers=map.getStyle().layers.filter(l=>l.id.startsWith('gis-'));
 const rendered=map.queryRenderedFeatures({layers:layers.map(l=>l.id)});
 const counts={},unique=new Set();
 for(const f of rendered){if(!f.properties.object_id||unique.has(f.properties.object_id))continue;
 unique.add(f.properties.object_id);const key=f.properties.gis_layer;counts[key]=(counts[key]||0)+1;}
 return {ready:true,zoom:map.getZoom(),rendered:counts,errors:window.gisValidationErrors||[],
  source_counts:Object.fromEntries((latestMaritimeState.gis_layers||[]).map(l=>[l.dataset_id,(latestMaritimeState.geojson[l.dataset_id]||{features:[]}).features.length])),
  own_marker:Boolean(marker),layer_count:layers.length,source_count:Object.keys(map.getStyle().sources).filter(k=>k.startsWith('gis-')).length,
  bounds:[map.getBounds().getWest(),map.getBounds().getSouth(),map.getBounds().getEast(),map.getBounds().getNorth()]};
})())"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=90)
    parser.add_argument('--output',type=Path,default=Path('docs/diagnostics/malaysia-nav-runtime.json'))
    parser.add_argument('--bisect-pipeline',action='store_true')
    parser.add_argument('--focus-layer',help='Fit the first valid supplied geometry and enable this manifest layer for the diagnostic only')
    args=parser.parse_args()
    import main as entry
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    original=entry.MainWindow.__init__
    def initialize(window):
        original(window)
        window.setWindowTitle('GDS VTS - Malaysia GIS validation')
        window.navigate('Nav')
        bounds=(103.3,4.5,104.6,6.8)
        if args.focus_layer:
            from PySide6.QtCore import QSettings
            from shapely.geometry import shape
            from app.nav.maritime.malaysia_config import read_manifest,dataset_directory
            directory=dataset_directory()
            layer=next(l for l in read_manifest(directory)['layers'] if l['dataset_id']==args.focus_layer)
            features=json.loads((directory/layer['filename']).read_text(encoding='utf-8-sig'))['features']
            bounds=next(g.bounds for f in features if f.get('geometry') for g in [shape(f['geometry'])] if g.is_valid and not g.is_empty)
            name='Malaysia '+layer['display_name']
            original_value=window.nav.layer_checks[name].isChecked()
            window.nav.layer_checks[name].setChecked(True)
            def restore():
                settings=QSettings('GDS','VTS');settings.setValue('nav/layers/'+name,original_value);settings.sync()
            QApplication.instance().aboutToQuit.connect(restore)
        report={'telemetry':'NO SOURCE','snapshots':[]}
        bisected=False
        def capture(value):
            nonlocal bisected
            if not value:return
            snapshot=json.loads(value)
            snapshot['gis_dataset']=dict(window.maritime_service.gis_dataset)
            report['snapshots'].append(snapshot)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print('MALAYSIA NAV '+json.dumps(snapshot),flush=True)
            if args.bisect_pipeline and not bisected and snapshot.get('gis_dataset',{}).get('in_view'):
                bisected=True
                window.nav.web.page().runJavaScript("""(async()=>{
                 const all=latestMaritimeState.geojson.malaysia_pipeline.features;
                 const source=map.getSource('gis-malaysia_pipeline');
                 window.pipelineDiagnostic=[];
                 async function check(features){window.gisValidationErrors=[];source.setData({type:'FeatureCollection',features});await new Promise(r=>setTimeout(r,1000));
                  return window.gisValidationErrors.some(e=>e.source==='gis-malaysia_pipeline');}
                 async function bisect(features){if(!await check(features))return;
                  if(features.length===1){window.pipelineDiagnostic.push({id:features[0].id,name:features[0].properties.name,geometry:features[0].geometry.type});console.info('PIPELINE BAD '+JSON.stringify(window.pipelineDiagnostic));return;}
                  const middle=Math.floor(features.length/2);await bisect(features.slice(0,middle));await bisect(features.slice(middle));}
                 await bisect(all);console.info('PIPELINE BISECT COMPLETE '+JSON.stringify(window.pipelineDiagnostic));
                })()""")
        def position(ok):
            if ok:window.nav.web.page().runJavaScript("""(function position(){
             if(typeof map==='undefined'||!map||!ready){setTimeout(position,100);return;}
             window.gisValidationErrors=[];
             map.on('error',e=>window.gisValidationErrors.push({source:e.sourceId||null,message:e.error&&e.error.message,stack:e.error&&e.error.stack}));
             map.fitBounds(BOUNDS,{padding:20,duration:0});
            })()""".replace('BOUNDS',json.dumps([[bounds[0],bounds[1]],[bounds[2],bounds[3]]])))
        window.nav.web.loadFinished.connect(position)
        window.validation_timer=QTimer(window);window.validation_timer.setInterval(5000)
        window.validation_timer.timeout.connect(lambda:window.nav.web.page().runJavaScript(SNAPSHOT,capture))
        window.validation_timer.start()
        QTimer.singleShot(args.seconds*1000,window.close)
    entry.MainWindow.__init__=initialize
    return entry.main()


if __name__=='__main__':raise SystemExit(main())
