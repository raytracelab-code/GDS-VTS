from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QComboBox
from app.core.models import ConnectionMode

class ConnectionPanel(QFrame):
    def __init__(self, usb, ble, state):
        super().__init__(); self.setObjectName('connectionArea'); self.usb,self.ble,self.state=usb,ble,state; outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(12)
        head=QHBoxLayout(); headings=QVBoxLayout(); headings.setSpacing(3); title=QLabel('PATROLLER-I CONNECTION'); title.setObjectName('sectionTitle'); subtitle=QLabel('Select a transport and establish live telemetry from Patroller-I.'); subtitle.setObjectName('sectionSubtitle'); headings.addWidget(title); headings.addWidget(subtitle); head.addLayout(headings); head.addStretch(); label=QLabel('CONNECTION MODE'); label.setObjectName('fieldLabelDark'); head.addWidget(label); self.mode=QComboBox(); self.mode.addItems([m.value for m in ConnectionMode]); self.mode.currentTextChanged.connect(self._mode); self.mode.setFixedWidth(150); head.addWidget(self.mode); outer.addLayout(head)
        cards=QGridLayout(); cards.setHorizontalSpacing(16); self.usb_card=QFrame(); self.usb_card.setObjectName('card'); self.ble_card=QFrame(); self.ble_card.setObjectName('card'); cards.addWidget(self.usb_card,0,0); cards.addWidget(self.ble_card,0,1); cards.setColumnStretch(0,1); cards.setColumnStretch(1,1); outer.addLayout(cards)
        self.usb_devices=[]; self.ble_devices=[]; self._build_transport(self.usb_card,'USB',('Device','Port','VID:PID','Serial')); self._build_transport(self.ble_card,'BLUETOOTH',('Device','Address','RSSI'))
        self.summary=QFrame(); self.summary.setObjectName('summary'); sl=QHBoxLayout(self.summary); sl.setContentsMargins(20,10,20,10); self.summary_values={}
        for key,initial in (('ACTIVE SOURCE','NONE'),('STANDBY','NONE'),('TELEMETRY','WAITING')):
            b=QVBoxLayout(); c=QLabel(key); c.setObjectName('fieldLabelDark'); v=QLabel(initial); v.setObjectName('summaryValue'); b.addWidget(c); b.addWidget(v); sl.addLayout(b); self.summary_values[key]=v
        sl.addStretch(); outer.addWidget(self.summary)
    def _build_transport(self, card, kind, fields):
        l=QVBoxLayout(card); l.setContentsMargins(20,18,20,18); l.setSpacing(12); header=QHBoxLayout(); t=QLabel(kind); t.setObjectName('cardTitle'); header.addWidget(t); header.addStretch(); info=QLabel('○  NO DEVICE'); info.setObjectName('statusNeutral'); header.addWidget(info); l.addLayout(header); g=QGridLayout(); g.setVerticalSpacing(10); details={}
        for row,key in enumerate(fields):
            g.addWidget(QLabel(key),row,0); value=QLabel('—'); value.setObjectName('technicalValue'); g.addWidget(value,row,1); details[key]=value
        l.addLayout(g); selector_label=QLabel('SELECT DEVICE'); selector_label.setObjectName('fieldLabelDark'); l.addWidget(selector_label); selector=QComboBox(); selector.addItem('No device selected'); selector.setEnabled(False); l.addWidget(selector); buttons=QHBoxLayout(); scan=QPushButton(f'SCAN {"BLE" if kind == "BLUETOOTH" else "USB"}'); scan.setObjectName('secondaryButton'); connect=QPushButton('CONNECT'); connect.setEnabled(False); buttons.addWidget(scan); buttons.addWidget(connect); buttons.addStretch(); l.addLayout(buttons)
        if kind == 'USB': self.usb_info,self.usb_detail,self.usb_select,self.usb_connect=info,details,selector,connect; scan.clicked.connect(self.scan_usb); connect.clicked.connect(self.connect_usb)
        else: self.ble_info,self.ble_detail,self.ble_select,self.ble_connect=info,details,selector,connect; scan.clicked.connect(self.scan_ble); connect.clicked.connect(self.connect_ble)
    def _mode(self,value): self.state.arbiter.mode=ConnectionMode(value)
    def _set_details(self, details, values):
        for key,label in details.items(): label.setText(values.get(key,'—'))
    def scan_usb(self):
        self.usb_devices=self.usb.scan(); self.usb_select.clear(); self.usb_select.addItems([d.label for d in self.usb_devices] or ['No device selected']); self.usb_select.setEnabled(bool(self.usb_devices)); self.usb_connect.setEnabled(bool(self.usb_devices)); self.usb_info.setText('○  DISCONNECTED' if self.usb_devices else '○  NO DEVICE')
        d=self.usb_devices[0] if self.usb_devices else None; self._set_details(self.usb_detail, {} if not d else {'Device':d.description or d.product or 'Serial device','Port':d.port,'VID:PID':f'{d.vid:04X}:{d.pid:04X}' if d.vid is not None and d.pid is not None else '—','Serial':d.serial_number or '—'})
    def scan_ble(self):
        self.ble_devices=self.ble.scan(); self.ble_select.clear(); self.ble_select.addItems([d.label for d in self.ble_devices] or ['No device selected']); self.ble_select.setEnabled(bool(self.ble_devices)); self.ble_connect.setEnabled(bool(self.ble_devices)); self.ble_info.setText('○  DISCONNECTED' if self.ble_devices else '○  NO DEVICE')
        d=self.ble_devices[0] if self.ble_devices else None; self._set_details(self.ble_detail, {} if not d else {'Device':d.name or 'Unnamed BLE device','Address':d.address,'RSSI':'—' if d.rssi is None else f'{d.rssi} dBm'})
    def _connected(self,label):
        label.setText('●  CONNECTED'); label.setObjectName('statusLive'); label.style().unpolish(label); label.style().polish(label)
    def connect_usb(self):
        i=self.usb_select.currentIndex()
        if i>=0 and self.usb.connect(self.usb_devices[i]): self._connected(self.usb_info)
    def connect_ble(self):
        i=self.ble_select.currentIndex()
        if i>=0 and self.ble.connect(self.ble_devices[i]): self._connected(self.ble_info)
    def refresh(self):
        self.summary_values['ACTIVE SOURCE'].setText(self.state.active_source.value if self.state.active_source else 'NONE'); self.summary_values['STANDBY'].setText(self.state.standby_source.value if self.state.standby_source else 'NONE'); self.summary_values['TELEMETRY'].setText(self.state.telemetry_status.value)
