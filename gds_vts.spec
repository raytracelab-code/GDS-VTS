# Build with: pyinstaller gds_vts.spec
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(['main.py'], pathex=[], binaries=[], datas=[('app/resources', 'app/resources')],
             hiddenimports=collect_submodules('openpyxl')+['PySide6.'+n for n in ('QtCore','QtGui','QtWidgets','QtSvg','QtSvgWidgets','QtWebChannel','QtWebEngineCore','QtWebEngineWidgets')]+['shiboken6'], hookspath=[], hooksconfig={}, runtime_hooks=['packaging/startup_log.py'], excludes=['PySide2','shiboken2'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GDS VTS', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon='app/resources/theme/deep-current/gds-vts.ico',manifest='packaging/windows.manifest',version='packaging/version_info.txt')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GDS VTS')
