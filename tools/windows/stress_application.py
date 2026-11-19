"""Observe real application process exit codes; no external UI driver required."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser();parser.add_argument('--packaged',action='store_true');parser.add_argument('--cycles',type=int,default=10)
parser.add_argument('--render',choices=['default','software','gpu-disabled'],default='default')
parser.add_argument('--isolate',choices=['without-filter','without-channel','without-timers'])
parser.add_argument('--network-failure',action='store_true',help='Exercise provider failure without waiting for remote 35s timeouts')
args=parser.parse_args();root=Path(__file__).resolve().parents[2]
env=os.environ.copy()
for name in ('QT_QPA_PLATFORM','QT_QPA_FONTDIR','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','GDS_QT_API'):
    env.pop(name,None)
for name in ('QT_OPENGL','QTWEBENGINE_CHROMIUM_FLAGS'):env.pop(name,None)
if args.render=='software':env['QT_OPENGL']='software'
if args.render=='gpu-disabled':env['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu'
env['PYTHONFAULTHANDLER']='1'
if args.network_failure:
    # Keep adapters enabled and TLS verification intact. The closed local port
    # simulates an unreachable provider deterministically; GIS/browser stay live.
    env['GDS_OVERPASS_ENDPOINT']='https://127.0.0.1:1/api/interpreter'
    env['GDS_OVERPASS_FALLBACK_ENDPOINTS']=env['GDS_OVERPASS_ENDPOINT']
    env['GDS_GEBCO_WMS_ENDPOINT']='https://127.0.0.1:1/mapserv'
if args.packaged:
    env['PATH']=os.environ['WINDIR']+'\\System32;'+os.environ['WINDIR']
    command=[str(root/'dist/GDS VTS/GDS VTS.exe')]
else:command=[sys.executable,'-u',str(root/'main.py')]
if args.isolate:
    if args.packaged:raise ValueError('Isolation is source-only')
    command=[sys.executable,'-u',str(root/'tools/windows/isolate_application.py'),args.isolate]
command+=['--validation-profile','--validation-cycle','--validation-close-after=5000']
out=root/'docs/evidence/windows-compatibility';out.mkdir(parents=True,exist_ok=True)
tag=('packaged' if args.packaged else 'source')+'-'+args.render
if args.isolate:tag+='-'+args.isolate
if args.network_failure:tag+='-network-failure'
results=[]
for cycle in range(1,args.cycles+1):
    start=time.monotonic()
    # Packaged resources must also work from a non-project current directory.
    logfile=root/'build'/('stress-'+tag+'-'+str(cycle)+'.txt')
    timed_out=False
    with logfile.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen(command,cwd=os.environ['TEMP'] if args.packaged else root,env=env,stdout=stream,stderr=subprocess.STDOUT)
        try:process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            timed_out=True
            # Only the process tree created above; Windows venv has a launcher.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
            process.wait(timeout=10)
    record={'cycle':cycle,'pid':process.pid,'exit_code':process.returncode,'timeout':timed_out,'seconds':round(time.monotonic()-start,2)}
    results.append(record);print(tag+' '+json.dumps(record),flush=True)
    (out/(tag+'-cycles.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
    if timed_out or process.returncode:raise SystemExit('Native application cycle failed; inspect the process log')
