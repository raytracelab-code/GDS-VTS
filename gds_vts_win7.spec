# Controlled legacy build. The complete onedir folder is required.
import sys
import struct
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.datastruct import TOC
if sys.version_info[:3] != (3,8,10) or struct.calcsize('P') != 8:
    raise RuntimeError('Use CPython 3.8.10 AMD64 in .venv-win7')
root=Path(SPECPATH)
import sys; sys.path.insert(0,str(root/'packaging'))
from versioning import write_version_info
version_file=write_version_info(root,'Legacy Compatibility',root/'build/legacy-win7-version'/'version_info.txt')
gis=root/'data/maritime/malaysia'
gis_data=[(str(p),str(p.parent.relative_to(root))) for p in gis.rglob('*')
          if p.is_file() and p.suffix in ('.geojson','.json') and not p.name.startswith('._') and '__MACOSX' not in p.parts]
import shapely
libs=Path(shapely.__file__).parent.parent/'shapely.libs'
binaries=[(str(path),'shapely.libs') for path in libs.glob('*.dll')]
hidden=['PySide2.'+name for name in ('QtCore','QtGui','QtWidgets','QtSvg','QtWebChannel','QtWebEngine','QtWebEngineCore','QtWebEngineWidgets')]
hidden+=['shiboken2','shapely._geos','PySide2.QtNetwork','PIL.JpegImagePlugin','PIL.PngImagePlugin','PIL.TiffImagePlugin']+collect_submodules('openpyxl')+collect_submodules('qrcode')
a=Analysis(['main.py'],pathex=[str(root)],binaries=binaries,
 datas=[('app/resources','app/resources'),(str(Path(version_file).parent/'BUILD_INFO.txt'),'.')]+gis_data,
 hiddenimports=hidden,hookspath=[],runtime_hooks=['packaging/startup_log.py'],
 excludes=['PySide6','shiboken6','copernicusmarine','xarray','pandas','pytest','tkinter','matplotlib'])
# Never inherit the build host's newer VC runtime (14.50 imports Win8+ APIs).
# Qt's redistributed MSVC 2019 DLLs and Python's matching runtime are controlled
# wheel/installer inputs, not arbitrary files from System32.
import PySide2
runtime={p.name.lower():p for p in Path(PySide2.__file__).parent.glob('*140*.dll')}
runtime.update({p.name.lower():p for p in Path(sys.base_prefix).glob('*140*.dll')})
a.binaries=TOC([(dest,str(runtime[Path(dest).name.lower()]) if Path(dest).name.lower() in runtime else src,kind)
                for dest,src,kind in a.binaries])
pyz=PYZ(a.pure,a.zipped_data)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='GDS VTS',debug=False,
 bootloader_ignore_signals=False,strip=False,upx=False,console=False,
 icon='app/resources/theme/deep-current/gds-vts.ico',manifest='packaging/windows.manifest',version=version_file)
coll=COLLECT(exe,a.binaries,a.zipfiles,a.datas,strip=False,upx=False,name='GDS VTS')
