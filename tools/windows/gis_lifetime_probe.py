"""Isolate native GIS cancellation from Qt/Chromium; uses the configured data."""
import faulthandler
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.nav.maritime.adapters.malaysia import MalaysiaOffshoreGISProvider
faulthandler.enable()
for cycle in range(3):
    provider=MalaysiaOffshoreGISProvider()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(provider.load)
        time.sleep(3);provider.stop()
        try:future.result(timeout=45)
        except RuntimeError as error:
            if str(error)!='Malaysia GIS provider stopped':raise
    print('GIS CANCEL CLEAN '+str(cycle+1),flush=True)
