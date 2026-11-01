from PySide6.QtWidgets import QWidget,QFrame,QVBoxLayout,QGridLayout,QLabel

class TelemetryPanel(QWidget):
    GROUPS=[('POSITION',[('PID','pid'),('DATE','date'),('UTC','utc'),('LATITUDE','latitude'),('LONGITUDE','longitude')],2),('NAVIGATION',[('SPEED','speed_knots'),('COG','cog'),('HEADING','heading')],2),('WEATHER',[('WIND SPEED','wind_speed_knots'),('WIND DIRECTION','wind_direction_deg'),('TRUE WIND','true_wind_speed_knots'),('TRUE DIRECTION','true_wind_direction_deg'),('HUMIDITY','humidity_percent'),('TEMPERATURE','temperature_c'),('PRESSURE','pressure_kpa'),('ILLUMINATION','illumination_lux'),('NOISE','noise_db'),('PM2.5','pm25'),('PM10','pm10'),('RAINFALL','rainfall_mm_min'),('SOLAR POWER','solar_power_w_m2')],3),('ATTITUDE & POWER',[('ROLL','roll'),('PITCH','pitch'),('YAW','yaw'),('VOLTAGE','voltage'),('ERROR STATUS','error_status')],3)]
    def __init__(self):
        super().__init__(); layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(12); headings=QVBoxLayout(); headings.setSpacing(3); title=QLabel('LIVE TELEMETRY'); title.setObjectName('sectionTitle'); subtitle=QLabel('Canonical vessel data received from the active transport.'); subtitle.setObjectName('sectionSubtitle'); headings.addWidget(title); headings.addWidget(subtitle); layout.addLayout(headings); cards=QGridLayout(); cards.setHorizontalSpacing(16); cards.setVerticalSpacing(16); self.labels={}
        for index,(name,fields,columns) in enumerate(self.GROUPS):
            card=QFrame(); card.setObjectName('card'); card_layout=QVBoxLayout(card); card_layout.setContentsMargins(22,20,22,20); card_layout.setSpacing(16); heading=QLabel(name); heading.setObjectName('cardTitle'); card_layout.addWidget(heading); metrics=QGridLayout(); metrics.setHorizontalSpacing(24); metrics.setVerticalSpacing(16)
            for i,(caption_text,field) in enumerate(fields):
                metric=QWidget(); metric_layout=QVBoxLayout(metric); metric_layout.setContentsMargins(0,0,0,0); metric_layout.setSpacing(4); caption=QLabel(caption_text); caption.setObjectName('fieldLabelDark'); value=QLabel('—'); value.setObjectName('operationalValue' if field in ('latitude','longitude','speed_knots','cog','heading','roll','pitch','yaw','voltage') else 'technicalValue'); metric_layout.addWidget(caption); metric_layout.addWidget(value); metrics.addWidget(metric,i//columns,i%columns); self.labels[field]=value
            card_layout.addLayout(metrics); row,col=(0,index) if index<2 else (index-1,0); cards.addWidget(card,row,col,1,1 if index<2 else 2)
        cards.setColumnStretch(0,1); cards.setColumnStretch(1,1); layout.addLayout(cards)
    def update_frame(self,frame):
        for name,label in self.labels.items():
            value=getattr(frame,name); label.setText('—' if value is None else str(value))
