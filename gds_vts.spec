# Build with: pyinstaller gds_vts.spec
from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path
root=Path(SPECPATH)
import sys; sys.path.insert(0,str(root/'packaging'))
from versioning import write_version_info
version_file=write_version_info(root,'Modern',root/'build/modern-version'/'version_info.txt')
gis_data=[(str(p),str(p.parent.relative_to(root))) for p in (root/'data/maritime/malaysia').rglob('*')
          if p.is_file() and p.suffix in ('.geojson','.json') and not p.name.startswith('._') and '__MACOSX' not in p.parts]

a = Analysis(['main.py'], pathex=[], binaries=[], datas=[('app/resources', 'app/resources'),(str(Path(version_file).parent/'BUILD_INFO.txt'),'.')]+gis_data,
             hiddenimports=collect_submodules('openpyxl')+collect_submodules('qrcode')+['PIL.JpegImagePlugin','PIL.PngImagePlugin','PIL.TiffImagePlugin']+['PySide6.'+n for n in ('QtCore','QtGui','QtWidgets','QtSvg','QtSvgWidgets','QtWebChannel','QtWebEngineCore','QtWebEngineWidgets','QtNetwork')]+['shiboken6'], hookspath=[], hooksconfig={}, runtime_hooks=['packaging/startup_log.py'], excludes=['PySide2','shiboken2'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GDS VTS', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon='app/resources/theme/deep-current/gds-vts.ico',manifest='packaging/windows.manifest',version=version_file)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GDS VTS')
