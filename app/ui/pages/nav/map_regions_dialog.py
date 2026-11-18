"""Compact NAV map configuration; installation runs in a separate process."""
import json
from pathlib import Path
import sys
from app.qt.QtCore import QProcess,Qt
from app.qt.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTreeWidget,QTreeWidgetItem,QPushButton,QMessageBox
from app.nav.offline_maps.manager import PackageManager,MapPackageError
from app.nav.offline_maps.regions import cache_root


class MapRegionsDialog(QDialog):
    def __init__(self,parent=None,changed=None,release=None):
        super().__init__(parent);self.setWindowTitle('OFFLINE MAP REGIONS');self.resize(760,470)
        self.setObjectName('offlineMapRegions')
        self.setStyleSheet('''
        QDialog#offlineMapRegions { background:#edf2f5; color:#243c50; font-family:'Segoe UI'; }
        QDialog#offlineMapRegions QTreeWidget { background:#fbfcfd; alternate-background-color:#f1f6f7; color:#243c50; border:1px solid #c8d5db; }
        QDialog#offlineMapRegions QTreeWidget::item { padding:3px 2px; }
        QDialog#offlineMapRegions QTreeWidget::item:selected { background:#d8eae4; color:#244d4b; }
        QDialog#offlineMapRegions QHeaderView::section { background:#e5ecef; color:#35546b; padding:5px; border:0; border-bottom:1px solid #c8d5db; }
        QDialog#offlineMapRegions QLabel { color:#607485; }
        QDialog#offlineMapRegions QPushButton { background:#fbfcfd; color:#35546b; border:1px solid #b9cbd3; border-radius:3px; padding:5px 8px; }
        QDialog#offlineMapRegions QPushButton:hover { background:#e5f1ee; }
        QDialog#offlineMapRegions QPushButton:disabled { color:#8c9da5; }
        ''')
        self.manager=PackageManager();self.changed=changed;self.release=release
        root=QVBoxLayout(self);self.tree=QTreeWidget();self.tree.setAlternatingRowColors(True);self.tree.setHeaderLabels(['Region','Status','Size','Revision']);root.addWidget(self.tree)
        self.note=QLabel('Independent regional packages · 30 GiB disk reserve · OpenStreetMap / Geofabrik');self.note.setWordWrap(True);root.addWidget(self.note)
        bar=QHBoxLayout();root.addLayout(bar)
        self.buttons=[]
        for caption,callback in [('Install / update',self.install),('Enable',lambda:self.toggle(True)),('Disable',lambda:self.toggle(False)),('Rollback',self.rollback),('Remove',self.remove),('Check for map updates',self.check_updates)]:
            button=QPushButton(caption);button.clicked.connect(callback);bar.addWidget(button);self.buttons.append(button)
        self.process=QProcess(self);self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.output);self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(lambda _:self.finished(1))
        self.refresh()

    def refresh(self):
        self.tree.clear();installed={p.manifest['package_id']:p for p in self.manager.installed_regions()}
        catalog=cache_root().parent/'regions-catalog.json'
        try:entries=json.loads(catalog.read_text(encoding='utf-8'))
        except (OSError,ValueError):entries=[]
        known={e['region_id'] for e in entries}
        entries += [dict(region_id=k,display_name=p.manifest['name'],group='Installed',status='INSTALLED') for k,p in installed.items() if k not in known]
        invalid=getattr(self.manager,'invalid_regions',{})
        entries += [dict(region_id=k,display_name=k,group='Invalid',status='INVALID') for k in invalid if k not in known and k not in installed]
        groups={}
        for entry in entries:
            key=entry['region_id'];package=installed.get(key);group=entry['group']
            if group not in groups:groups[group]=QTreeWidgetItem(self.tree,[group]);groups[group].setExpanded(True)
            size=entry.get('download_size') or 0;status=entry['status'];revision=entry.get('source_date') or ''
            if status=='UNAVAILABLE_PREBUILT':status='UNAVAILABLE'
            if key in invalid:status='INVALID'
            if package:
                size=sum((package.root/name).stat().st_size for name in package.files().values());revision=package.manifest['revision']
                status='INSTALLED' if package.manifest.get('enabled',True) else 'DISABLED'
                remote=entry.get('source_date');local=package.manifest.get('source',{}).get('http_headers',{}).get('Last-Modified')
                if remote and local and remote!=local:status+=' · UPDATE AVAILABLE'
            item=QTreeWidgetItem(groups[group],[entry['display_name'],status,f'{size/1024**2:,.1f} MiB',revision])
            item.setData(0,Qt.ItemDataRole.UserRole,key)
            item.setToolTip(3,revision)
            if key in invalid:item.setToolTip(1,invalid[key])
        self.tree.resizeColumnToContents(0);self.tree.resizeColumnToContents(1)

    def key(self):
        item=self.tree.currentItem()
        return item.data(0,Qt.ItemDataRole.UserRole) if item else None

    def output(self):
        text=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace').strip()
        if text:self.note.setText(text.splitlines()[-1][:250])

    def run(self,args):
        if self.process.state()!=QProcess.ProcessState.NotRunning:return
        for button in self.buttons:button.setEnabled(False)
        self.note.setText('DOWNLOADING / VALIDATING · Existing installed regions remain available')
        script=Path(__file__).resolve().parents[4]/'tools/maps/install_geofabrik_regions.py'
        self.process.start(sys.executable,[str(script),*args])

    def install(self):
        key=self.key()
        if key:
            self.tree.currentItem().setText(1,'DOWNLOADING')
            self.run(['--region',key,'--update'])

    def check_updates(self):self.run(['--refresh','--list'])

    def finished(self,code,*_):
        for button in self.buttons:button.setEnabled(True)
        self.note.setText('Completed; see per-region status.' if code==0 else 'Operation failed; existing revisions preserved.')
        self.refresh()
        if self.changed:self.changed()

    def mutate(self,operation):
        key=self.key()
        if not key:return
        try:
            if self.release:self.release()
            operation(key);self.refresh()
            if self.changed:self.changed()
        except (MapPackageError,OSError) as error:
            if self.changed:self.changed()
            QMessageBox.warning(self,'Offline map regions',str(error))

    def toggle(self,enabled):self.mutate(lambda key:self.manager.set_region_enabled(key,enabled))
    def rollback(self):self.mutate(self.manager.rollback_region)
    def remove(self):
        if self.key() and QMessageBox.question(self,'Remove regional map','Remove this installed region and its previous revision?')==QMessageBox.StandardButton.Yes:
            self.mutate(self.manager.remove_region)

    def closeEvent(self,event):
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            self.note.setText('Keep this window open until the download finishes.');event.ignore()
        else:super().closeEvent(event)
