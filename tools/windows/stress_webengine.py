"""Execute independent native processes, preserving exit codes and diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[2]
results=[]
env=os.environ.copy()
for key in ('QT_QPA_PLATFORM','QT_QPA_FONTDIR','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QTWEBENGINE_CHROMIUM_FLAGS','QT_OPENGL'):
    env.pop(key,None)
for render in ('default','software','gpu-disabled'):
    for cycle in range(1,11):
        start=time.monotonic()
        process=subprocess.Popen([sys.executable,str(root/'tools/windows/webengine_probe.py'),'--render',render],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            stdout,stderr=process.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            process.kill();stdout,stderr=process.communicate()
        record={'render':render,'cycle':cycle,'pid':process.pid,'exit_code':process.returncode,
                'seconds':round(time.monotonic()-start,2),'stdout':stdout,'stderr':stderr}
        results.append(record);print(render,cycle,process.returncode,flush=True)
        (root/'docs/evidence/windows-compatibility/webengine-stress.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if process.returncode:raise SystemExit('Native probe failed; inspect captured evidence')
