from app.qt.QtWidgets import QFrame,QWidget,QVBoxLayout,QGridLayout,QLabel
from app.telemetry.diagnostics import derive_diagnostics

class DiagnosticsPanel(QFrame):
    def __init__(self,state):
        super().__init__(); self.setObjectName('card'); self.state=state; layout=QVBoxLayout(self); layout.setContentsMargins(22,20,22,20); layout.setSpacing(16); title=QLabel('SYSTEM HEALTH'); title.setObjectName('sectionTitle'); layout.addWidget(title); self.health={}; health_grid=QGridLayout(); health_grid.setHorizontalSpacing(28); health_grid.setVerticalSpacing(14)
        for index,key in enumerate(('USB','BLE','Telemetry','GPS','Heading','Weather','IMU','Power')):
            metric=QFrame(); metric.setObjectName('healthTile'); ml=QVBoxLayout(metric); ml.setContentsMargins(12,12,12,12); ml.setSpacing(5); label=QLabel(key.upper()); label.setObjectName('fieldLabelDark'); value=QLabel('○   UNAVAILABLE'); value.setObjectName('statusNeutral'); ml.addWidget(label); ml.addWidget(value); health_grid.addWidget(metric,index//4,index%4); self.health[key]=value
        for column in range(4): health_grid.setColumnStretch(column,1)
        layout.addLayout(health_grid); advanced=QLabel('ADVANCED DIAGNOSTICS'); advanced.setObjectName('cardTitle'); layout.addWidget(advanced); self.metrics={}; metric_grid=QGridLayout(); metric_grid.setHorizontalSpacing(24); metric_grid.setVerticalSpacing(12)
        for index,key in enumerate(('Frame Age','Frame Rate','Valid Frames','Invalid Frames','Reconnect Count','Active Source Since')):
            item=QWidget(); il=QVBoxLayout(item); il.setContentsMargins(0,0,0,0); il.setSpacing(5); label=QLabel(key.upper()); label.setObjectName('fieldLabelDark'); value=QLabel('—'); value.setObjectName('diagnosticValue'); il.addWidget(label); il.addWidget(value); metric_grid.addWidget(item,index//3,index%3); self.metrics[key]=value
        for column in range(3): metric_grid.setColumnStretch(column,1)
        layout.addLayout(metric_grid); self.refresh()
    def refresh(self):
        derived=derive_diagnostics(self.state.telemetry_status,self.state.latest_frame); derived.update({'USB':'CONNECTED' if self.state.active_source and self.state.active_source.value == 'USB' else 'NO DEVICE','BLE':'CONNECTED' if self.state.active_source and self.state.active_source.value == 'BLE' else 'NO DEVICE'})
        for key,value in derived.items():
            if key in self.health: self.health[key].setText(('●   ' if value in ('LIVE','CONNECTED','OK') else '○   ') + value)
        self.metrics['Frame Age'].setText('—' if self.state.frame_age is None else f'{self.state.frame_age:.1f} s'); self.metrics['Frame Rate'].setText('—'); self.metrics['Valid Frames'].setText(str(self.state.valid_frame_count)); self.metrics['Invalid Frames'].setText(str(self.state.invalid_frame_count)); self.metrics['Reconnect Count'].setText('—'); self.metrics['Active Source Since'].setText('—')
