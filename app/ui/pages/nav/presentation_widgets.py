"""NAV-only presentation components. No provider or operational state is owned here."""
from collections import Counter
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy


NAV_STYLE = """
QWidget#navSurface { color:#243c50; font-family:'Segoe UI'; font-size:12px; }
QWidget#navSurface QLabel { font-family:'Segoe UI'; font-size:12px; font-weight:400; }
QWidget#navSurface QLabel#sectionTitle { font-size:14px; font-weight:600; }
QWidget#navSurface QLabel#cardTitle { font-size:11px; font-weight:600; letter-spacing:.7px; }
QWidget#navSurface QLabel#navMuted { color:#7b8b97; font-size:11px; }
QWidget#navSurface QLabel#navInspector { color:#294256; font-size:12px; }
QWidget#navSurface QLabel#navReadout { font-size:11px; color:#607485; }
QWidget#navSurface QFrame#navPanel { background:#fbfcfd; border:1px solid #d5dfe5; border-radius:5px; }
QWidget#navSurface QFrame#navInspectorBox { background:#f1f6f7; border:1px solid #b8cdd1; border-radius:4px; }
QWidget#navSurface QPushButton { min-height:26px; max-height:28px; padding:0 9px; border-radius:3px; font-size:11px; font-weight:500; }
QWidget#navSurface QPushButton#secondaryButton { background:#fbfcfd; border:1px solid #d5dfe5; color:#35546b; }
QWidget#navSurface QPushButton#secondaryButton:hover { background:#edf3f5; border-color:#9db6c1; }
QWidget#navSurface QPushButton#secondaryButton:checked { background:#e5f1ee; border-color:#8ab8aa; color:#326f63; }
QWidget#navSurface QToolButton#navDisclosure { border:0; border-bottom:1px solid #e1e8ec; border-radius:0; background:transparent; color:#365268; min-height:25px; padding:1px 0; text-align:left; font-size:11px; font-weight:600; }
QWidget#navSurface QToolButton#navDisclosure:hover { color:#2c7c70; background:#f0f5f6; }
QWidget#navSurface QCheckBox { font-family:'Segoe UI'; font-size:11px; spacing:7px; min-height:20px; }
QWidget#navSurface QCheckBox::indicator { width:12px; height:12px; }
QWidget#navSurface QScrollBar:vertical { width:7px; margin:0; }
"""


class Disclosure(QWidget):
    def __init__(self, title, key, expanded=False, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or QSettings('GDS','VTS')
        self.key, self.title, self.default_expanded = 'nav/groups/'+key, title, expanded
        self.expanded = self.settings.value(self.key,expanded,type=bool)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(2)
        self.header=QToolButton();self.header.setObjectName('navDisclosure')
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.header.setCheckable(True);layout.addWidget(self.header)
        self.body=QWidget();self.content=QVBoxLayout(self.body)
        self.content.setContentsMargins(6,2,0,5);self.content.setSpacing(2);layout.addWidget(self.body)
        self.header.toggled.connect(self.set_expanded)
        self.set_expanded(self.expanded,persist=False)

    def set_expanded(self, expanded, *, persist=True):
        self.expanded=bool(expanded)
        self.header.blockSignals(True);self.header.setChecked(self.expanded);self.header.blockSignals(False)
        self.header.setArrowType(Qt.ArrowType.DownArrow if self.expanded else Qt.ArrowType.RightArrow)
        self.header.setText(self.title);self.body.setVisible(self.expanded)
        if persist:self.settings.setValue(self.key,self.expanded)

    def restore_preference(self):
        self.set_expanded(self.settings.value(self.key,self.default_expanded,type=bool),persist=False)


def source_rows(payload):
    """Present existing health/count values; grouping does not alter source state."""
    sources=payload.get('sources',{})
    counts=Counter(o['source'] for o in payload.get('objects',[]))
    names={'malaysia_gis':'Malaysia GIS','aisstream':'AISStream','overpass':'Overpass','gebco':'GEBCO',
        'openseamap':'OpenSeaMap','openwaters':'OpenWaters','gfw':'GFW','boem':'BOEM','emodnet':'EMODnet','navarea8':'NAVAREA 8'}
    rows=[]
    for key in ('malaysia_gis','aisstream','overpass','gebco'):
        if key not in sources:continue
        h=sources[key];count=payload.get('gis_dataset',{}).get('in_view',0) if key=='malaysia_gis' else counts[key]
        rows.append(dict(key=key,name=names[key],state=h['state'],count=count if key in ('malaysia_gis','overpass') or count else None,detail=h.get('error') or ''))
    copernicus=[(k,v) for k,v in sources.items() if k.startswith('copernicus_')]
    if copernicus:
        states=[v['state'] for _,v in copernicus]
        state=next((s for s in ('LIVE','READY','DEGRADED','STALE','ERROR','CONNECTING','LOADING') if s in states),'NOT_CONFIGURED')
        rows.append(dict(key='copernicus',name='Copernicus',state=state,count=None,detail='\n'.join(k.removeprefix('copernicus_')+': '+v['state'].replace('_',' ') for k,v in copernicus)))
    for key,h in sources.items():
        if key in ('malaysia_gis','aisstream','overpass','gebco') or key.startswith('copernicus_'):continue
        rows.append(dict(key=key,name=names.get(key,key.replace('_',' ').title()),state=h['state'],count=counts[key] or None,detail=h.get('error') or '',secondary=True))
    return rows


class SourceStatusPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.layout=QVBoxLayout(self);self.layout.setContentsMargins(0,0,0,0);self.layout.setSpacing(2)
        self.primary=QVBoxLayout();self.primary.setSpacing(2);self.layout.addLayout(self.primary)
        self.more=Disclosure('Other sources','other-sources',False);self.layout.addWidget(self.more)
        self.rows={};self.summary=''
        self.detail=QLabel();self.detail.setObjectName('navMuted');self.detail.setWordWrap(True);self.layout.addWidget(self.detail)

    def setText(self,text):
        # Preserve a useful accessible/diagnostic summary, without displaying raw debug text.
        self.summary=text;self.setAccessibleDescription(text)

    def text(self):return self.summary

    def set_payload(self,payload):
        current=source_rows(payload);keys={row['key'] for row in current}
        for key in set(self.rows)-keys:
            self.rows.pop(key)[0].deleteLater()
        for row in current:
            key=row['key']
            if key not in self.rows:
                host=QWidget();line=QHBoxLayout(host);line.setContentsMargins(0,1,0,1);line.setSpacing(4)
                name,dot,status,count=QLabel(row['name']),QLabel('●'),QLabel(),QLabel()
                name.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
                dot.setFixedWidth(10);status.setFixedWidth(87);count.setFixedWidth(36);count.setAlignment(Qt.AlignmentFlag.AlignRight)
                for label in (name,dot,status,count):line.addWidget(label)
                (self.more.content if row.get('secondary') else self.primary).addWidget(host)
                self.rows[key]=(host,name,dot,status,count)
            host,name,dot,status,count=self.rows[key]
            state=row['state'];color='#3f8a79' if state in ('READY','LIVE') else '#aa854c' if state in ('DEGRADED','STALE') else '#b5635e' if state=='ERROR' else '#89969f'
            dot.setStyleSheet('color:'+color+';font-size:9px;')
            status.setText(state.replace('_',' ').title());status.setStyleSheet('color:'+color+';font-size:10px;')
            count.setText(f"{row['count']:,}" if row['count'] is not None else '')
            count.setStyleSheet('color:#607a89;font-size:10px;')
            host.setToolTip(row['name']+' · '+state.replace('_',' ')+('\n'+row['detail'] if row['detail'] else ''))
        data=payload.get('gis_dataset',{})
        self.detail.setText(f"{data.get('in_view',0):,} in view · {data.get('total_features',0):,} total · Local GIS" if data else '')
        if data:self.detail.setToolTip(f"MALAYSIA OFFSHORE GIS\nLicence / authority: NOT YET RECORDED\n{data.get('directory','')}\n{data.get('invalid_features',0)} rejected source records")
        self.more.setVisible(any(row.get('secondary') for row in current))


class InspectorRows(QWidget):
    """Reusable rows for the one selected object, with plain-text values."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.layout=QVBoxLayout(self);self.layout.setContentsMargins(0,0,0,0);self.layout.setSpacing(4)
        self.rows=[];self.summary=''

    def setWordWrap(self,value):pass
    def setTextFormat(self,value):pass  # All values are explicitly plain text.
    def text(self):return self.summary

    def setText(self,text):
        if text==self.summary:return
        self.summary=text
        lines=text.splitlines()
        fields=[line.split('  ',1) if '  ' in line else ['',line] for line in lines]
        for i,(key,value) in enumerate(fields):
            if i>=len(self.rows):
                host=QWidget();row=QHBoxLayout(host);row.setContentsMargins(0,0,0,0);row.setSpacing(7)
                label,content=QLabel(),QLabel();label.setFixedWidth(77);label.setObjectName('navMuted')
                content.setWordWrap(True);content.setTextFormat(Qt.TextFormat.PlainText)
                content.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
                row.addWidget(label,0,Qt.AlignmentFlag.AlignTop);row.addWidget(content,1)
                self.layout.addWidget(host);self.rows.append((host,label,content))
            host,label,content=self.rows[i];host.show()
            label.setText(key.title() if key.isupper() and key not in ('MMSI','IMO','SOG','COG','ETA') else key)
            content.setText(value);content.setToolTip(value)
        for host,_,_ in self.rows[len(fields):]:host.hide()


def legend_symbol(kind):
    """Small native vector swatches matching the map's operational hierarchy."""
    pixmap=QPixmap(24,18);pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#547287'),1.2))
    if kind in ('own','ais'):
        painter.setBrush(QColor('#1e3a5f' if kind=='own' else '#547287'))
        painter.drawPolygon(QPolygonF([QPointF(12,2),QPointF(17,15),QPointF(12,12),QPointF(7,15)]))
    elif kind=='platform':
        for a,b,c,d in ((4,11,20,11),(6,11,5,16),(18,11,19,16),(9,11,12,2),(12,2,15,11),(10,7,14,7),(12,2,21,6)):
            painter.drawLine(a,b,c,d)
    elif kind=='well':painter.drawEllipse(10,7,4,4)
    elif kind=='pipeline':
        painter.setPen(QPen(QColor('#78818a'),1,Qt.PenStyle.DashLine));painter.drawLine(2,9,22,9)
    elif kind=='aton':painter.drawPolygon(QPolygonF([QPointF(12,2),QPointF(17,9),QPointF(12,16),QPointF(7,9)]))
    elif kind=='field':
        fill=QColor('#6b8d86');fill.setAlpha(20);painter.setBrush(fill);painter.drawRoundedRect(3,4,18,10,2,2)
    elif kind=='squall':
        painter.setBrush(QColor('#b87b48'));painter.setPen(Qt.PenStyle.NoPen);painter.drawEllipse(8,5,8,8)
    painter.end();return pixmap


def populate_legend(layout):
    for kind,name in (('own','Own vessel'),('ais','AIS vessel'),('platform','Offshore installation'),('well','Well / well cluster'),('pipeline','Pipeline'),('aton','Aid to navigation'),('field','Oil / gas field'),('squall','Squall')):
        row=QHBoxLayout();icon=QLabel();icon.setPixmap(legend_symbol(kind));icon.setFixedWidth(25);row.addWidget(icon);row.addWidget(QLabel(name),1);layout.addLayout(row)
