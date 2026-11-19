from app.qt.QtWidgets import QWidget,QFrame,QVBoxLayout,QGridLayout,QLabel
from app.core.models import TelemetryStatus

# Display units and precision; values are shown exactly as received, only formatted.
UNITS={'latitude':('°',5),'longitude':('°',5),'speed_knots':(' kn',1),'cog':('°',0),'heading':('°',0),
       'wind_speed_knots':(' kn',1),'wind_direction_deg':('°',0),'true_wind_speed_knots':(' kn',1),'true_wind_direction_deg':('°',0),
       'humidity_percent':(' %',0),'temperature_c':(' °C',1),'pressure_kpa':(' kPa',1),'illumination_lux':(' lx',0),
       'noise_db':(' dB',0),'pm25':(' µg/m³',0),'pm10':(' µg/m³',0),'rainfall_mm_min':(' mm/min',1),'solar_power_w_m2':(' W/m²',0),
       'roll':('°',1),'pitch':('°',1),'yaw':('°',1),'voltage':(' V',2)}


def format_value(field,value):
    """Zero is a real reading and is displayed; only a missing value shows '—'."""
    if value is None: return '—'
    if field in UNITS and isinstance(value,(int,float)):
        unit,places=UNITS[field]
        text=f'{value:0{3 if field in ("cog","heading","wind_direction_deg","true_wind_direction_deg") else 1}.{places}f}'
        return text+unit
    return str(value)


class TelemetryPanel(QWidget):
    GROUPS=[('POSITION',[('PID','pid'),('DATE','date'),('UTC','utc'),('LATITUDE','latitude'),('LONGITUDE','longitude')],2),('NAVIGATION',[('SPEED','speed_knots'),('COG','cog'),('HEADING','heading')],2),('WEATHER',[('WIND SPEED','wind_speed_knots'),('WIND DIRECTION','wind_direction_deg'),('TRUE WIND','true_wind_speed_knots'),('TRUE DIRECTION','true_wind_direction_deg'),('HUMIDITY','humidity_percent'),('TEMPERATURE','temperature_c'),('PRESSURE','pressure_kpa'),('ILLUMINATION','illumination_lux'),('NOISE','noise_db'),('PM2.5','pm25'),('PM10','pm10'),('RAINFALL','rainfall_mm_min'),('SOLAR POWER','solar_power_w_m2')],3),('ATTITUDE & POWER',[('ROLL','roll'),('PITCH','pitch'),('YAW','yaw'),('VOLTAGE','voltage'),('ERROR STATUS','error_status')],3)]
    def __init__(self):
        super().__init__(); layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(12); headings=QVBoxLayout(); headings.setSpacing(3); title=QLabel('LIVE TELEMETRY'); title.setObjectName('sectionTitle'); self.subtitle=QLabel('Vessel data received from the active connection.'); self.subtitle.setObjectName('sectionSubtitle'); headings.addWidget(title); headings.addWidget(self.subtitle); layout.addLayout(headings); cards=QGridLayout(); cards.setHorizontalSpacing(16); cards.setVerticalSpacing(16); self.labels={}
        for index,(name,fields,columns) in enumerate(self.GROUPS):
            card=QFrame(); card.setObjectName('card'); card_layout=QVBoxLayout(card); card_layout.setContentsMargins(22,20,22,20); card_layout.setSpacing(16); heading=QLabel(name); heading.setObjectName('cardTitle'); card_layout.addWidget(heading); metrics=QGridLayout(); metrics.setHorizontalSpacing(24); metrics.setVerticalSpacing(16)
            for i,(caption_text,field) in enumerate(fields):
                metric=QWidget(); metric_layout=QVBoxLayout(metric); metric_layout.setContentsMargins(0,0,0,0); metric_layout.setSpacing(4); caption=QLabel(caption_text); caption.setObjectName('fieldLabelDark'); value=QLabel('—'); value.setObjectName('operationalValue' if field in ('latitude','longitude','speed_knots','cog','heading','roll','pitch','yaw','voltage') else 'technicalValue'); metric_layout.addWidget(caption); metric_layout.addWidget(value); metrics.addWidget(metric,i//columns,i%columns); self.labels[field]=value
            card_layout.addLayout(metrics); row,col=(0,index) if index<2 else (index-1,0); cards.addWidget(card,row,col,1,1 if index<2 else 2)
        cards.setColumnStretch(0,1); cards.setColumnStretch(1,1); layout.addLayout(cards)
        self._last=None
    def update_frame(self,frame,status=None):
        """Show the latest frame. STALE/LOST values stay visible but are labelled as old;
        with no source every value is cleared rather than presented as current."""
        if status in (TelemetryStatus.NO_SOURCE,TelemetryStatus.CONNECTED_WAITING): frame=None
        key=(id(frame),status)
        if key==self._last: return
        self._last=key
        from app.core.plausibility import check_frame
        flagged=check_frame(frame) if frame is not None else {}
        for name,label in self.labels.items():
            text=format_value(name,getattr(frame,name,None) if frame is not None else None)
            level,message=flagged.get(name,(None,''))
            label.setText(text+('  ▲' if level else ''))
            label.setToolTip(('Outside the possible range — check the sensor: ' if level=='invalid' else 'Unusual value: ')+message if level else '')
            if label.property('plausibility')!=level:
                label.setProperty('plausibility',level); label.style().unpolish(label); label.style().polish(label)
            label.setEnabled(status not in (TelemetryStatus.STALE,TelemetryStatus.LOST))
        self.subtitle.setText({TelemetryStatus.STALE:'Telemetry is STALE — values below are the last received and may be out of date.',
                               TelemetryStatus.LOST:'Telemetry LOST — values below are the last received, not current.',
                               TelemetryStatus.CONNECTED_WAITING:'Connected — waiting for the first valid frame.'}.get(status,'Vessel data received from the active connection.'))
