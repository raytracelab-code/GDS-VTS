import sys,time,json,os
sys.path.insert(0,r'C:\Users\rayha\GDS-VTS')
from datetime import datetime,timedelta,timezone
from app.nav.track_manager import TrackManager,TrackPoint
from app.nav.presentation import track_metrics
t=TrackManager();base=datetime(2026,1,1,tzinfo=timezone.utc)
for n in (3600,86400,7*86400):
    t=TrackManager()
    for i in range(n):t.append(TrackPoint(base+timedelta(seconds=i),5+i*1e-6,100+i*1e-6,10,10,5))
    s=time.perf_counter();g=t.geojson_segments();st=t.start_geojson();a=time.perf_counter()-s
    s=time.perf_counter();js=json.dumps(g);b=time.perf_counter()-s
    s=time.perf_counter();m=track_metrics(t);c=time.perf_counter()-s
    print(f'TRACK points={n} geojson_build={a*1000:.0f}ms json={b*1000:.0f}ms bytes={len(js)/1e6:.1f}MB metrics={c*1000:.0f}ms segments={len(t.segments)}')
# zero-value formatting as in nav_page.refresh
for sog,cog,hdg in ((0.0,0.0,0.0),(None,None,None)):
    print('READOUT', repr(f'SOG {sog or "—"} kn COG {cog or "—"}° HEADING {hdg or "—"}°'))
# malaysia gis + render state
os.environ['GDS_MARITIME_CACHE_DIR']=os.path.join(os.path.dirname(__file__),'mcache')
from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider
from app.nav.maritime.malaysia_config import dataset_directory
from app.nav.maritime.service import MaritimeObjectService
from app.nav.maritime.area_controller import MaritimeAreaController
from app.nav.maritime.render_state import build_render_state
p=MalaysiaOffshoreGISProvider(dataset_directory({}))
s=time.perf_counter();p.load();print(f'MALAYSIA load={time.perf_counter()-s:.1f}s')
svc=MaritimeObjectService()
c=MaritimeAreaController(50,10,0)
area=c.viewport(103,1,106,6)
s=time.perf_counter();r=p.fetch(area);print(f'MALAYSIA fetch={time.perf_counter()-s:.2f}s objects={len(r.objects)}')
svc.area=area
s=time.perf_counter();svc.set_gis_result(r);print(f'set_gis_result={time.perf_counter()-s:.2f}s')
for i in range(3):
    s=time.perf_counter();st=build_render_state(svc);a=time.perf_counter()-s
    s=time.perf_counter();js=json.dumps(st,default=str);b=time.perf_counter()-s
    print(f'RENDER_STATE build={a*1000:.0f}ms json={b*1000:.0f}ms size={len(js)/1e6:.2f}MB objects={len(st["objects"])}')
