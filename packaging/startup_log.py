"""PyInstaller runtime hook: private, rotating diagnostics before GUI imports."""
import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys

class RedactedStream:
    def __init__(self, stream):self.stream=stream
    def write(self, text):
        text=str(text)
        for key,value in os.environ.items():
            if value and (key=='USERPROFILE' or any(word in key.upper() for word in ('TOKEN','PASSWORD','SECRET','API_KEY'))):
                text=text.replace(value,'[redacted]').replace(value.replace('\\','/'),'[redacted]')
        text=re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[redacted]',text)
        return self.stream.write(text)
    def flush(self):self.stream.flush()
    def isatty(self):return False

try:
    root=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'GDS VTS'/'logs'
    root.mkdir(parents=True,exist_ok=True)
    target=root/'startup.log'
    if target.exists() and target.stat().st_size>2*1024*1024:
        old=root/'startup.previous.log'
        if old.exists():old.unlink()
        target.replace(old)
    raw=target.open('a',encoding='utf-8',buffering=1)
    faulthandler.enable(file=raw)
    sys.stdout=sys.stderr=RedactedStream(raw)
    print('GDS VTS frozen startup; Python '+sys.version.split()[0])
    def uncaught(kind,value,tb):
        # Avoid exception messages, which can contain report data or credentials.
        import traceback
        print('Unhandled '+kind.__name__)
        for item in traceback.extract_tb(tb):print(Path(item.filename).name+':'+str(item.lineno)+' '+item.name)
    sys.excepthook=uncaught
except OSError:
    # A log directory failure must not itself prevent startup.
    pass
