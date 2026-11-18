"""Opt-in real NAV country/palette validation; downloads no offline map assets."""
import json
from pathlib import Path
import sys
import time
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main as entry
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

OUTPUT = Path('docs/diagnostics')
SCENES = [
    ('bangladesh', 90.35, 22.35, 6, 'DAY'),
    ('myanmar', 96.0, 17.0, 6, 'DAY'),
    ('thailand', 100.5, 13.0, 6, 'DAY'),
    ('malaysia-day', 104.0, 5.5, 8, 'DAY'),
    ('malaysia-twilight', 104.0, 5.5, 8, 'TWILIGHT'),
    ('malaysia-night', 104.0, 5.5, 8, 'NIGHT'),
    ('vietnam', 108.0, 15.0, 6, 'DAY'),
    ('philippines', 122.0, 12.0, 6, 'DAY'),
    ('indonesia', 116.0, -3.0, 5, 'DAY'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--block-online', action='store_true')
    parser.add_argument('--presentation',action='store_true',help='Capture the full map-first shell and temporary panels')
    args = parser.parse_args()
    if args.block_online:
        SCENES[:] = [('local-fallback', 104.0, 5.5, 8, 'NIGHT')]
    elif args.presentation:
        SCENES.extend([('malaysia-platform-labels',103.9052,5.6079,12,'NIGHT'),
                       ('malaysia-layers',104,5.5,8,'NIGHT'),
                       ('malaysia-selection',104,5.5,8,'NIGHT'),
                       ('compact-layout',104,5.5,8,'NIGHT')])
    prefix='nav-map-first' if args.presentation else 'online-map'
    app = QApplication([])
    app.setApplicationName('GDS VTS')
    window = entry.MainWindow()
    if args.block_online:
        from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
        class BlockOnline(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info):
                if info.requestUrl().scheme() in ('http', 'https'):
                    info.block(True)
        window.interceptor = BlockOnline(window)
        window.nav.web_profile.setUrlRequestInterceptor(window.interceptor)
    window.setWindowTitle('GDS VTS - Online map validation')
    window.showMaximized() if args.presentation else window.show()
    window.tabs.buttons['Nav'].click()
    # Keep minute ticks from replacing a diagnostic palette during capture.
    window.nav.palette.minute.stop()
    window.nav.palette.changed.disconnect(window.nav._palette_changed)
    started = time.monotonic()
    report = {'scenes': [], 'config': window.nav.bridge.offline_config}
    saved = None
    index = 0
    timer = QTimer(window)
    timer.setInterval(1000)

    def finish():
        if report.get('finished'):return
        report['finished']=True
        OUTPUT.mkdir(exist_ok=True, parents=True)
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        report['offline_readers'] = len(window.nav._gds_scheme_handler.readers)
        filename = prefix+('-fallback-runtime.json' if args.block_online else '-runtime.json')
        (OUTPUT/filename).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('ONLINE_VALIDATION ' + json.dumps(report), flush=True)
        window.close()
        app.quit()

    def capture(value):
        nonlocal index
        if not value:
            return
        snapshot = json.loads(value)
        snapshot['scene'] = SCENES[index][0]
        if args.presentation:
            nav=window.nav
            snapshot['presentation']={'canvas_fills_nav':nav.web.geometry()==nav.rect(),
                'rail_width':window.tabs.width(),'layers_visible':nav.layers_panel.isVisible(),
                'selection_visible':nav.selection_panel.isVisible(),'palette_label':nav.palette_control.currentText(),
                'window_size':[window.width(),window.height()]}
        report['scenes'].append(snapshot)
        (window if args.presentation else window.nav.web).grab().save(str(OUTPUT/f'{prefix}-{SCENES[index][0]}.png'))
        print('ONLINE_SCENE ' + json.dumps(snapshot), flush=True)
        index += 1
        if index == len(SCENES):
            timer.stop()
            finish()
        else:
            scene()

    def scene():
        name, lng, lat, zoom, palette = SCENES[index]
        if args.presentation:
            nav=window.nav
            nav.close_overlays()
            if name=='malaysia-layers':nav.toggle_layers()
            if name=='malaysia-selection':
                objects=[o for o in window.maritime_service.render_snapshot() if o.properties.get('gis_layer')=='malaysia_platform' and o.geometry['type']=='Point']
                if objects:
                    selected=min(objects,key=lambda o:(o.geometry['coordinates'][0]-104)**2+(o.geometry['coordinates'][1]-5.5)**2)
                    nav.bridge.selectMaritimeObject(selected.object_id)
            if name=='compact-layout':window.showNormal();window.resize(800,600)
            payload={**nav.palette.payload,'effective_state':palette,'computed_solar_state':palette}
            QTimer.singleShot(2500,lambda p=payload:nav._palette_changed(p))
        # Diagnostic-only palette injection; leaves operator settings/solar logic intact.
        window.nav.web.page().runJavaScript(
            f"setLayerVisibility('Bathymetry',false);map.jumpTo({{center:[{lng},{lat}],zoom:{zoom}}});")
        QTimer.singleShot(2500, lambda: window.nav.web.page().runJavaScript(
            f"applyPalette({{effective_state:'{palette}'}})"))
        QTimer.singleShot(10000, lambda: window.nav.web.page().runJavaScript("""JSON.stringify((()=>{
         const layers=map.getStyle().layers,base=layers.filter(l=>l.metadata?.['gds:owner']==='basemap').map(l=>l.id);
         const count=ids=>ids.length?map.queryRenderedFeatures({layers:ids}).length:0;
         return {ready,status:status.textContent,center:map.getCenter(),zoom:map.getZoom(),
          loaded:map.loaded(),tiles_loaded:map.areTilesLoaded(),palette:latestPalette,
          basemap_rendered:count(base),
          gis_rendered:count(layers.filter(l=>l.source?.startsWith('gis-')&&!l.metadata?.['gds:effect']).map(l=>l.id)),
          platforms:count(['gis-malaysia_platform-point']),pipelines:count(['gis-malaysia_pipeline-line']),
          fields:count(['gis-malaysia_fields_all-boundary']),
          pipeline_glow:map.getPaintProperty('gis-malaysia_pipeline-line-glow','line-opacity'),
          platform_halo:map.getPaintProperty('gis-malaysia_platform-point-halo','circle-opacity'),
          platform_color:map.getPaintProperty('gis-malaysia_platform-point','icon-color'),
          hud_present:Boolean(document.getElementById('geographic-hud')),
          source_ids:Object.keys(map.getStyle().sources),camera_bounds:map.getBounds()};
        })())""", capture))

    def wait_ready(value):
        nonlocal saved
        if value and saved is None:
            saved = time.monotonic()
            report['ready_seconds'] = round(saved - started, 2)
            timer.stop()
            scene()

    timer.timeout.connect(lambda: window.nav.web.page().runJavaScript(
        "typeof ready!=='undefined'&&ready&&typeof latestMaritimeState!=='undefined'&&latestMaritimeState?.sources?.malaysia_gis?.state==='READY'", wait_ready))
    timer.start()
    QTimer.singleShot(160000, finish)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
