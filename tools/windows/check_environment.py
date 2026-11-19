"""Fail a legacy release build when its interpreter or locked inputs drift."""
import importlib.metadata
import importlib.util
from pathlib import Path
import struct
import sys

if sys.version_info[:3]!=(3,8,10) or struct.calcsize('P')!=8 or sys.platform!='win32':
    raise SystemExit('The legacy release requires CPython 3.8.10 AMD64 on Windows.')
root=Path(__file__).resolve().parents[2]
failures=[]
for line in (root/'requirements-win7.txt').read_text().splitlines():
    line=line.strip()
    if not line or line.startswith('#'):continue
    name,expected=line.split('==',1)
    try:actual=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:actual='MISSING'
    if actual!=expected:failures.append(name+': expected '+expected+', found '+actual)
if importlib.util.find_spec('PySide6') or importlib.util.find_spec('PyQt6'):
    failures.append('Qt6 is installed in the isolated legacy environment.')
if failures:raise SystemExit('\n'.join(failures))
print('PASS: Python 3.8.10 AMD64 and every legacy runtime/build lock entry match.')
