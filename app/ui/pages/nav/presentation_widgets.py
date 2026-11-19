"""NAV-only presentation components. No provider or operational state is owned here."""
from app.core.compat import remove_prefix
from collections import Counter
from app.qt.QtCore import Qt, QSettings
from app.qt.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from app.qt.QtCore import QPointF
from app.qt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QSizePolicy
from app.ui.theme import COLORS, FONT_BODY, FONT_DISPLAY, FONT_DATA


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


# Native Qt uses the established system fallbacks; the map HUD uses vendored webfonts.
NAV_STYLE += f"""
QWidget#navSurface {{ background:{COLORS['darker']}; color:#c6d5dd; font-family:'{FONT_BODY}'; }}
QWidget#navSurface QLabel {{ color:#b7cad5; font-size:11px; }}
QWidget#navSurface QLabel#cardTitle {{ color:#e1e8e9; font-family:'{FONT_DISPLAY}'; font-size:10px; letter-spacing:1px; }}
QWidget#navSurface QLabel#navMuted {{ color:#7f97aa; font-size:10px; }}
QWidget#navSurface QFrame#navCapsule {{ background:rgba(18,26,36,245); border:1px solid #344454; border-radius:19px; }}
QWidget#navSurface QToolButton#mapTool {{ background:transparent; color:#c2d3dc; border:0; border-radius:11px; font-size:11px; font-weight:600; }}
QWidget#navSurface QToolButton#mapTool:hover {{ background:#253a4a; }}
QWidget#navSurface QToolButton#mapTool:checked {{ background:{COLORS['navy']}; border:1px solid #4d9d98; color:#b9f1e6; }}
QWidget#navSurface QToolButton#mapTool:disabled {{ color:#536577; background:transparent; }}
QWidget#navSurface QLineEdit#mapSearch {{ background:transparent; border:0; color:#dce7ea; font-size:12px; padding:3px; selection-background-color:{COLORS['navy']}; }}
QWidget#navSurface QListWidget#mapSearchResults {{ background:#121e2a; color:#c6d9e0; border:1px solid #344454; border-radius:12px; padding:7px; outline:0; }}
QWidget#navSurface QListWidget#mapSearchResults::item {{ padding:10px 5px; border-radius:5px; font-size:11px; }}
QWidget#navSurface QListWidget#mapSearchResults::item:selected {{ background:#1e3a5f; color:#c6f5ea; }}
QWidget#navSurface QLabel#onlineBadge {{ color:#91bcb4; font-size:9px; letter-spacing:1px; padding:0 5px; }}
QWidget#navSurface QComboBox {{ background:#192936; color:#c8d9df; border:1px solid #344454; border-radius:10px; min-height:32px; padding:0 18px 0 10px; font-size:10px; }}
QWidget#navSurface QComboBox QAbstractItemView {{ background:#142330; color:#cfdee3; selection-background-color:#1e3a5f; selection-color:#b9f1e6; }}
QWidget#navSurface QFrame#navPanel, QWidget#navSurface QFrame#navInspectorBox {{ background:#121e2a; border:1px solid #344454; border-radius:13px; }}
QWidget#navSurface QScrollArea#floatingLayers, QWidget#navSurface QScrollArea#selectionCard {{ border:0; background:transparent; }}
QWidget#navSurface QPushButton#secondaryButton, QWidget#navSurface QToolButton#detailsButton {{ background:#1a2d3c; color:#afcbd4; border:1px solid #344c5c; border-radius:9px; min-height:28px; padding:3px 9px; }}
QWidget#navSurface QPushButton#secondaryButton:hover {{ background:#223e4b; border-color:#4d8d88; }}
QWidget#navSurface QToolButton#navDisclosure {{ color:#a8c1cb; border-bottom:1px solid #293d4b; background:transparent; min-height:25px; }}
QWidget#navSurface QToolButton#navDisclosure:hover {{ color:#a9e2d4; background:#1a303c; }}
QWidget#navSurface QCheckBox {{ color:#b6c9d2; font-size:11px; min-height:23px; spacing:9px; }}
QWidget#navSurface QCheckBox::indicator {{ width:22px; height:12px; border:1px solid #4b6071; border-radius:6px; background:#263848; }}
QWidget#navSurface QCheckBox::indicator:checked {{ background:#478d86; border-color:#86c2b6; }}
QWidget#navSurface QScrollBar::handle:vertical {{ background:#385366; }}
QWidget#navSurface QLabel#floatingTrack {{ background:rgba(18,26,36,230); color:#95aebc; border:1px solid #344454; border-radius:10px; padding:0 9px; font-family:'{FONT_DATA}'; font-size:10px; }}
QWidget#navSurface QLabel#floatingTrack[freshness="STALE"] {{ color:#e3bd6d; border-color:#8a6a2c; }}
QWidget#navSurface QLabel#floatingTrack[freshness="NO_DATA"] {{ color:#b9c3ca; border-color:#56626d; }}
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
        rows.append(dict(key='copernicus',name='Copernicus',state=state,count=None,detail='\n'.join(remove_prefix(k, 'copernicus_')+': '+v['state'].replace('_',' ') for k,v in copernicus)))
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
        self.rows=[];self.summary='';self.compact=False

    def set_compact(self, compact):
        self.compact=compact
        for i,(host,_,_) in enumerate(self.rows):host.setVisible(i<len(self.summary.splitlines()) and (not compact or i<6))

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
        if self.compact:self.set_compact(True)


def legend_symbol(kind):
    """Small native vector swatches matching the map's operational hierarchy."""
    pixmap=QPixmap(24,18);pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#547287'),1.2))
    if kind in ('own','ais'):
        painter.setBrush(QColor('#1e3a5f' if kind=='own' else '#547287'))
        painter.drawPolygon(QPolygonF([QPointF(12,2),QPointF(17,15),QPointF(12,12),QPointF(7,15)]))
    elif kind=='platform':
        painter.setPen(QPen(QColor('#d9a35c'),1.5))
        for a,b,c,d in ((4,11,20,11),(6,11,5,16),(18,11,19,16),(9,11,12,2),(12,2,15,11),(10,7,14,7),(12,2,21,6)):
            painter.drawLine(a,b,c,d)
    elif kind=='well':painter.drawEllipse(10,7,4,4)
    elif kind=='pipeline':
        painter.setPen(QPen(QColor('#557d88'),1.4,Qt.PenStyle.DashLine));painter.drawLine(2,9,22,9)
    elif kind=='aton':painter.drawPolygon(QPolygonF([QPointF(12,2),QPointF(17,9),QPointF(12,16),QPointF(7,9)]))
    elif kind in ('field','production'):
        color=QColor('#b97d66' if kind=='production' else '#6faba5')
        painter.setPen(QPen(color,1.4 if kind=='production' else 1))
        fill=QColor(color);fill.setAlpha(32 if kind=='production' else 20);painter.setBrush(fill);painter.drawRoundedRect(3,4,18,10,2,2)
    elif kind=='squall':
        painter.setBrush(QColor('#b87b48'));painter.setPen(Qt.PenStyle.NoPen);painter.drawEllipse(8,5,8,8)
    painter.end();return pixmap


def populate_legend(layout):
    for kind,name in (('own','Own vessel'),('ais','AIS vessel'),('platform','Offshore installation'),('well','Well / well cluster'),('pipeline','Pipeline'),('aton','Aid to navigation'),('field','Oil / gas field'),('production','Producing area'),('squall','Squall')):
        row=QHBoxLayout();icon=QLabel();icon.setPixmap(legend_symbol(kind));icon.setFixedWidth(25);row.addWidget(icon);row.addWidget(QLabel(name),1);layout.addLayout(row)
