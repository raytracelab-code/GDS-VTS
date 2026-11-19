from app.qt.QtWidgets import QDialog,QFormLayout,QLineEdit,QDoubleSpinBox,QComboBox,QDialogButtonBox,QLabel
from app.nav.vessel_config import VesselConfig
class VesselConfigDialog(QDialog):
 def __init__(self,config,parent=None):
  super().__init__(parent);self.setWindowTitle('Vessel Configuration');from app.ui import dialogs;self.setObjectName('gdsDialog');self.setStyleSheet(dialogs.STYLE);self.config=config;f=QFormLayout(self);self.name=QLineEdit(config.name);self.length=QDoubleSpinBox();self.beam=QDoubleSpinBox();self.x=QDoubleSpinBox();self.y=QDoubleSpinBox()
  for w,v in ((self.length,config.length_m),(self.beam,config.beam_m),(self.x,config.antenna_offset_x_m),(self.y,config.antenna_offset_y_m)): w.setRange(-10000,10000);w.setValue(v);w.setDecimals(2)
  self.shape=QComboBox();self.shape.addItems(VesselConfig.SHAPES);self.shape.setCurrentText(config.shape);f.addRow('Vessel Name',self.name);f.addRow('Length (m)',self.length);f.addRow('Beam (m)',self.beam);f.addRow('GPS Antenna X (m)',self.x);f.addRow('GPS Antenna Y (m)',self.y);f.addRow('Vessel Shape',self.shape);f.addRow(QLabel('+X FORWARD  •  -X AFT  •  +Y STARBOARD  •  -Y PORT'))
  b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
 def apply(self):
  self.config.name=self.name.text().strip() or 'Unnamed Vessel';self.config.length_m=self.length.value();self.config.beam_m=self.beam.value();self.config.antenna_offset_x_m=self.x.value();self.config.antenna_offset_y_m=self.y.value();self.config.shape=self.shape.currentText();self.config.validate()
