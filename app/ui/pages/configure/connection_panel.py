import queue
from app.qt.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QComboBox
from app.core.models import ConnectionMode, Source
from app.core.platform_capabilities import native_ble_available, BLE_UNAVAILABLE

class ConnectionPanel(QFrame):
    """Connection UI. Transport callbacks may fire on worker threads, so they only
    enqueue events; the GUI thread drains them in refresh() (every 500 ms)."""
    def __init__(self, usb, ble, state, monitor=None):
        super().__init__(); self.setObjectName('connectionArea'); self.usb,self.ble,self.state,self.monitor=usb,ble,state,monitor; outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(12)
        self.events=queue.Queue(); self.connected={'USB':False,'BLE':False}
        for kind,transport in (('USB',usb),('BLE',ble)):
            transport.on_error=lambda message,k=kind: self.events.put((k,'error',message))
            transport.on_state=lambda up,k=kind: self.events.put((k,'state',bool(up)))
        head=QHBoxLayout(); headings=QVBoxLayout(); headings.setSpacing(3); title=QLabel('PATROLLER-I CONNECTION'); title.setObjectName('sectionTitle'); subtitle=QLabel('Connect the Patroller-I sensor unit by USB cable or Bluetooth LE to receive live telemetry.'); subtitle.setObjectName('sectionSubtitle'); headings.addWidget(title); headings.addWidget(subtitle); head.addLayout(headings); head.addStretch(); label=QLabel('CONNECTION MODE'); label.setObjectName('fieldLabelDark'); head.addWidget(label); self.mode=QComboBox(); self.mode.addItems([m.value for m in ConnectionMode]); self.mode.currentTextChanged.connect(self._mode); self.mode.setFixedWidth(150); head.addWidget(self.mode); outer.addLayout(head)
        cards=QGridLayout(); cards.setHorizontalSpacing(16); self.usb_card=QFrame(); self.usb_card.setObjectName('card'); self.ble_card=QFrame(); self.ble_card.setObjectName('card'); cards.addWidget(self.usb_card,0,0); cards.addWidget(self.ble_card,0,1); cards.setColumnStretch(0,1); cards.setColumnStretch(1,1); outer.addLayout(cards)
        self.usb_devices=[]; self.ble_devices=[]; self._build_transport(self.usb_card,'USB',('Device','Port','VID:PID','Serial')); self._build_transport(self.ble_card,'BLUETOOTH',('Device','Address','RSSI'))
        self.summary=QFrame(); self.summary.setObjectName('summary'); sl=QHBoxLayout(self.summary); sl.setContentsMargins(20,10,20,10); sl.setSpacing(32); self.summary_values={}
        for key,initial in (('ACTIVE SOURCE','NONE'),('STANDBY','NONE'),('TELEMETRY','WAITING')):
            b=QVBoxLayout(); c=QLabel(key); c.setObjectName('fieldLabelDark'); v=QLabel(initial); v.setObjectName('summaryValue'); b.addWidget(c); b.addWidget(v); sl.addLayout(b); self.summary_values[key]=v
        sl.addStretch(); outer.addWidget(self.summary)
    def _build_transport(self, card, kind, fields):
        l=QVBoxLayout(card); l.setContentsMargins(20,18,20,18); l.setSpacing(12); header=QHBoxLayout(); t=QLabel(kind); t.setObjectName('cardTitle'); header.addWidget(t); header.addStretch(); info=QLabel('○  NO DEVICE'); info.setObjectName('statusNeutral'); header.addWidget(info); l.addLayout(header); g=QGridLayout(); g.setVerticalSpacing(10); details={}
        for row,key in enumerate(fields):
            g.addWidget(QLabel(key),row,0); value=QLabel('—'); value.setObjectName('technicalValue'); g.addWidget(value,row,1); details[key]=value
        l.addLayout(g); selector_label=QLabel('SELECT DEVICE'); selector_label.setObjectName('fieldLabelDark'); l.addWidget(selector_label); selector=QComboBox(); selector.addItem('No device selected'); selector.setEnabled(False); l.addWidget(selector); buttons=QHBoxLayout(); scan=QPushButton(f'SCAN {"BLE" if kind == "BLUETOOTH" else "USB"}'); scan.setObjectName('secondaryButton'); connect=QPushButton('CONNECT'); connect.setEnabled(False)
        disconnect=QPushButton('DISCONNECT'); disconnect.setObjectName('secondaryButton'); disconnect.setEnabled(False)
        buttons.addWidget(scan); buttons.addWidget(connect); buttons.addWidget(disconnect); buttons.addStretch(); l.addLayout(buttons)
        link=QLabel(''); link.setObjectName('linkDetail'); link.setWordWrap(True); link.hide(); l.addWidget(link)
        message=QLabel(''); message.setObjectName('connectionMessage'); message.setWordWrap(True); message.hide(); l.addWidget(message)
        name='USB' if kind=='USB' else 'BLE'; selector.currentIndexChanged.connect(lambda _i,k=name: self._show_selected(k))
        if kind == 'USB':
            self.usb_info,self.usb_detail,self.usb_select,self.usb_connect,self.usb_disconnect,self.usb_message,self.usb_link=info,details,selector,connect,disconnect,message,link
            scan.clicked.connect(self.scan_usb); connect.clicked.connect(self.connect_usb); disconnect.clicked.connect(lambda: self.disconnect('USB'))
        else:
            self.ble_info,self.ble_detail,self.ble_select,self.ble_connect,self.ble_disconnect,self.ble_message,self.ble_link=info,details,selector,connect,disconnect,message,link
            scan.clicked.connect(self.scan_ble); connect.clicked.connect(self.connect_ble); disconnect.clicked.connect(lambda: self.disconnect('BLE'))
            if not native_ble_available():
                scan.setEnabled(False); scan.setToolTip(BLE_UNAVAILABLE); connect.setToolTip(BLE_UNAVAILABLE)
                selector.setItemText(0,BLE_UNAVAILABLE); info.setText('UNAVAILABLE'); card.setToolTip(BLE_UNAVAILABLE)
    def _mode(self,value): self.state.arbiter.mode=ConnectionMode(value)
    def _set_details(self, details, values):
        for key,label in details.items(): label.setText(values.get(key,'—'))
    def _parts(self,kind):
        if kind=='USB': return self.usb,self.usb_devices,self.usb_select,self.usb_info,self.usb_connect,self.usb_disconnect,self.usb_message
        return self.ble,self.ble_devices,self.ble_select,self.ble_info,self.ble_connect,self.ble_disconnect,self.ble_message
    def scan_usb(self):
        self._message('USB',''); self.usb_devices=self.usb.scan(); self._drain(); self.usb_select.clear(); self.usb_select.addItems([d.label for d in self.usb_devices] or ['No device selected']); self.usb_select.setEnabled(bool(self.usb_devices)); self._set_connected('USB',self.connected['USB'])
        self._show_selected('USB')
        if not self.usb_devices and not self.usb_message.text(): self._message('USB','No serial devices found. Plug in the USB cable, wait a few seconds, then press SCAN USB again.')
    def scan_ble(self):
        self._message('BLE',''); self.ble_devices=self.ble.scan(); self._drain(); self.ble_select.clear(); self.ble_select.addItems([d.label for d in self.ble_devices] or ['No device selected']); self.ble_select.setEnabled(bool(self.ble_devices)); self._set_connected('BLE',self.connected['BLE'])
        self._show_selected('BLE')
        if not self.ble_devices and native_ble_available() and not self.ble_message.text(): self._message('BLE','No Bluetooth LE devices found. Make sure the device is powered and in range, then scan again.')
    def _show_selected(self,kind):
        _t,devices,selector,*_rest=self._parts(kind); i=selector.currentIndex(); d=devices[i] if 0<=i<len(devices) else None
        if kind=='USB': self._set_details(self.usb_detail, {} if not d else {'Device':d.description or d.product or 'Serial device','Port':d.port,'VID:PID':f'{d.vid:04X}:{d.pid:04X}' if d.vid is not None and d.pid is not None else '—','Serial':d.serial_number or '—'})
        else: self._set_details(self.ble_detail, {} if not d else {'Device':d.name or 'Unnamed BLE device','Address':d.address,'RSSI':'—' if d.rssi is None else f'{d.rssi} dBm'})
    def _status(self,label,text,live):
        # Shared badge vocabulary (app/ui/status.py): shape marker + text, colour only reinforces.
        from app.ui.status import set_badge
        label.setObjectName('statusBadge'); set_badge(label,text.strip('●○… ').strip())
    def _message(self,kind,text):
        label=self._parts(kind)[6]; label.setText(text); label.setVisible(bool(text))
    def _set_connected(self,kind,up):
        _t,devices,_s,info,connect,disconnect,_m=self._parts(kind); was=self.connected[kind]; self.connected[kind]=up
        if kind=='BLE' and not native_ble_available(): return
        self._status(info,'●  CONNECTED' if up else ('○  DISCONNECTED' if devices else '○  NO DEVICE'),up)
        disconnect.setEnabled(up); connect.setEnabled(bool(devices) and not up)
        if was and not up: self.state.mark_disconnected(Source.USB if kind=='USB' else Source.BLE)
        if self.monitor is not None and was!=up:
            devices,selector=(self.usb_devices,self.usb_select) if kind=='USB' else (self.ble_devices,self.ble_select); i=selector.currentIndex()
            device=devices[i] if 0<=i<len(devices) else None
            self.monitor.connection_changed(kind,up,getattr(device,'port',None) or getattr(device,'address','') or '')
    def _connect(self,kind):
        transport,devices,selector,info,*_rest=self._parts(kind); i=selector.currentIndex()
        if not 0<=i<len(devices): return False
        if self.connected[kind] or transport.is_connected():
            try: transport.disconnect()
            except Exception: pass
            self._drain(); self._set_connected(kind,False)
        self._message(kind,''); self._status(info,'…  CONNECTING',False)
        ok=bool(transport.connect(devices[i])); self._drain(); self._set_connected(kind,ok)
        if not ok and not self._parts(kind)[6].text(): self._message(kind,'Connection failed. Check the device and cable, then try again.')
        return ok
    def connect_usb(self): return self._connect('USB')
    def connect_ble(self): return self._connect('BLE')
    def disconnect(self,kind):
        try: self._parts(kind)[0].disconnect()
        finally:
            self._drain(); self._set_connected(kind,False); self._message(kind,'Disconnected.')
    def disconnect_all(self):
        """Release every open port/device (used when the application closes)."""
        for kind in ('USB','BLE'):
            if self.connected[kind]:
                try: self._parts(kind)[0].disconnect()
                except Exception: pass
                self.connected[kind]=False
    def _drain(self):
        while True:
            try: kind,event,value=self.events.get_nowait()
            except queue.Empty: return
            if event=='error': self._message(kind,value)
            elif event=='state' and not value and self.connected[kind]:
                # Release the dead handle through the transport's own disconnect().
                try: self._parts(kind)[0].disconnect()
                except Exception: pass
                self._set_connected(kind,False)
                if not self._parts(kind)[6].text(): self._message(kind,'Device disconnected. Reconnect the cable or device, then press CONNECT.')
    def _link_details(self):
        """Per connected card: plain-language link state + secondary counters (existing metrics only)."""
        from datetime import datetime,timezone
        from app.telemetry.link_monitor import link_state
        now=datetime.now(timezone.utc)
        for kind,label in (('USB',self.usb_link),('BLE',self.ble_link)):
            if not self.connected[kind] or self.monitor is None: label.hide(); continue
            snap=self.monitor.snapshot(); packets=snap['packets'].get(kind,0); last=self.monitor.last_packet_at.get(kind)
            valid_at=self.state.source_last_valid.get(Source.USB if kind=='USB' else Source.BLE)
            age=None if valid_at is None else (now-valid_at).total_seconds()
            # Per-connection state from this source's own last valid frame (same 3 s / 10 s thresholds as telemetry).
            status='WAITING' if age is None else 'LIVE' if age<3 else 'STALE' if age<10 else 'LOST'
            text,tone,why=link_state(status,packets,self.state.valid_frame_count,self.state.invalid_frame_count,age)
            detail=f'{why}\nPackets {packets} · valid frames {self.state.valid_frame_count} · invalid {self.state.invalid_frame_count}'
            detail+=f' · last packet {(now-last).total_seconds():.0f} s ago' if last else ' · no packet yet'
            detail+=f' · reconnects {self.monitor.reconnects(kind)}'
            label.setText(f'{text} — {detail}'); label.setProperty('tone',tone); label.style().unpolish(label); label.style().polish(label); label.show()
    def refresh(self):
        self._drain(); self._link_details()
        self.summary_values['ACTIVE SOURCE'].setText(self.state.active_source.value if self.state.active_source else 'NONE'); self.summary_values['STANDBY'].setText(self.state.standby_source.value if self.state.standby_source else 'NONE'); self.summary_values['TELEMETRY'].setText(self.state.telemetry_status.value)
