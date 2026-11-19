"""Shutdown with a stalled provider: a local TCP server accepts and never answers.

Measures (a) MaritimeRuntime.close(wait=True) and (b) total time from the close
call until the Python process has fully exited (interpreter-exit thread joins
included). No public network is used. Run:  python shutdown_stalled_probe.py
"""
import os, socket, subprocess, sys, tempfile, threading, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
CHILD = r'''
import os,sys,time
sys.path.insert(0,ROOT)
from app.qt.QtCore import QCoreApplication,QTimer
app=QCoreApplication([])
from app.nav.maritime.runtime import MaritimeRuntime
from app.nav.maritime.config import MaritimeConfig
port=int(sys.argv[1]);scratch=sys.argv[2]
env={'GDS_MARITIME_CACHE_DIR':os.path.join(scratch,'cache'),
     'GDS_OVERPASS_ENDPOINT':f'https://127.0.0.1:{port}/api/interpreter',
     'GDS_OVERPASS_FALLBACK_ENDPOINTS':f'https://127.0.0.1:{port}/b',
     'GDS_GEBCO_WMS_ENDPOINT':f'https://127.0.0.1:{port}/mapserv?',
     'GDS_MALAYSIA_GIS_PATH':os.path.join(scratch,'empty_gis')}
os.makedirs(env['GDS_MALAYSIA_GIS_PATH'],exist_ok=True)
rt=MaritimeRuntime(config=MaritimeConfig(env))
rt.own_position(2.5,104.0)
def close():
    print('BUSY',sorted(rt._busy),flush=True)
    s=time.perf_counter();drained=rt.close(wait=True)
    print(f'CLOSE_SECONDS {time.perf_counter()-s:.2f} drained={drained}',flush=True)
    print(f'CLOSE_AT {time.time():.3f}',flush=True);app.quit()
QTimer.singleShot(3000,close)
app.exec() if hasattr(app,'exec') else app.exec_()
'''.replace('ROOT', repr(ROOT))


def main():
    server = socket.socket(); server.bind(('127.0.0.1', 0)); server.listen(16)
    held = []
    def accept():
        while True:
            conn, _ = server.accept(); held.append(conn)  # never respond: TLS handshake stalls
    threading.Thread(target=accept, daemon=True).start()
    scratch = tempfile.mkdtemp(prefix='gds-shutdown-')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    proc = subprocess.Popen([sys.executable, '-c', CHILD, str(server.getsockname()[1]), scratch],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    out, _ = proc.communicate(timeout=120)
    exited = time.time()
    close_at = next(float(line.split()[1]) for line in out.splitlines() if line.startswith('CLOSE_AT'))
    for line in out.splitlines():
        if line.startswith(('BUSY', 'CLOSE_SECONDS')):
            print(line)
    print(f'STALLED_CONNECTIONS {len(held)}')
    print(f'PROCESS_EXIT_AFTER_CLOSE_SECONDS {exited-close_at:.2f}')
    print(f'EXIT_CODE {proc.returncode}')
    print(f'PYTHON {sys.version.split()[0]}')


if __name__ == '__main__':
    main()
