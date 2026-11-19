import os,sys,time
sys.path.insert(0,r'C:\Users\rayha\GDS-VTS')
SCR=os.path.dirname(os.path.abspath(__file__))
env={'GDS_MARITIME_CACHE_DIR':os.path.join(SCR,'mcache3'),'GDS_OVERPASS_ENDPOINT':'https://127.0.0.1:1/x','GDS_OVERPASS_FALLBACK_ENDPOINTS':'https://127.0.0.1:1/y','GDS_GEBCO_WMS_ENDPOINT':'https://127.0.0.1:1/m?'}
from app.qt.QtCore import QCoreApplication,QTimer
app=QCoreApplication([])
from app.nav.maritime.runtime import MaritimeRuntime
from app.nav.maritime.config import MaritimeConfig
from app.nav.maritime.render_state import build_render_state
import logging;logging.disable(logging.WARNING)
rt=MaritimeRuntime(config=MaritimeConfig(env))
rt.own_position(5.0,104.5)
ev=[];cost=[]
def on():
    s=time.perf_counter();st=build_render_state(rt.service);cost.append(time.perf_counter()-s);ev.append((time.monotonic(),rt.service.sources['malaysia_gis'].state.value,len(st['objects'])))
rt.changed.connect(on)
t0=time.monotonic()
def done():
    loaded=[e for e in ev if e[1]=='READY']
    first=loaded[0][0] if loaded else None
    after=[e for e in ev if first and e[0]>=first]
    print('total emissions',len(ev),'ready_at',round(first-t0,1) if first else None,'emissions after ready',len(after),'over',round(ev[-1][0]-first,1) if first else 0,'s')
    print('emission times after ready',[round(e[0]-first,1) for e in after][:20])
    print('build cost ms avg',round(1000*sum(cost)/len(cost)),'max',round(1000*max(cost)),'objects',ev[-1][2])
    rt.close(wait=True);app.quit()
QTimer.singleShot(95000,done)
app.exec()
