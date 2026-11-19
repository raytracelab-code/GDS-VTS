import os,sys,time,socket,threading
sys.path.insert(0,r'C:\Users\rayha\GDS-VTS')
srv=socket.socket();srv.bind(('127.0.0.1',0));srv.listen(16);port=srv.getsockname()[1]
held=[]
def accept():
    while True:
        c,_=srv.accept();held.append(c)  # never respond: TLS handshake stalls
threading.Thread(target=accept,daemon=True).start()
SCR=os.path.dirname(os.path.abspath(__file__))
env={'GDS_MARITIME_CACHE_DIR':os.path.join(SCR,'mcache2'),'GDS_OVERPASS_ENDPOINT':f'https://127.0.0.1:{port}/api/interpreter','GDS_OVERPASS_FALLBACK_ENDPOINTS':f'https://127.0.0.1:{port}/b','GDS_GEBCO_WMS_ENDPOINT':f'https://127.0.0.1:{port}/mapserv?','GDS_MALAYSIA_GIS_PATH':os.path.join(SCR,'empty_gis')}
os.makedirs(env['GDS_MALAYSIA_GIS_PATH'],exist_ok=True)
from app.qt.QtCore import QCoreApplication,QTimer
app=QCoreApplication([])
from app.nav.maritime.runtime import MaritimeRuntime
from app.nav.maritime.config import MaritimeConfig
rt=MaritimeRuntime(config=MaritimeConfig(env))
t0=time.perf_counter()
rt.own_position(2.5,104.0)
def close():
    print('conns held',len(held),'busy',rt._busy,flush=True)
    s=time.perf_counter();rt.close(wait=True);print(f'CLOSE wait=True took {time.perf_counter()-s:.1f}s',flush=True);app.quit()
QTimer.singleShot(3000,close)
app.exec()
