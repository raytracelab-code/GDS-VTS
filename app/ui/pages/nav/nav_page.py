from pathlib import Path
import logging
from PySide6.QtCore import QUrl,QSettings,QTimer,Qt
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QCheckBox,QFileDialog,QMessageBox,QScrollArea
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineSettings
from app.nav import VesselConfig,VesselState,TrackManager
from app.nav.map_controls import FollowController, LAYER_VISIBILITY
from app.nav.map_bridge import MapBridge
from app.nav.render_geometry import vector_geojson
from app.nav.presentation import track_metrics,telemetry_age
from app.nav.web_scheme import GdsMapSchemeHandler
from app.nav.web_profile import create_nav_profile
from app.nav.spatial import SpatialStateService
from app.nav.spatial.interaction import feature_info
from .vessel_config_dialog import VesselConfigDialog
log=logging.getLogger(__name__)
class NavMapPage(QWebEnginePage):
 def javaScriptConsoleMessage(self,l,m,line,s): print(f'NAV JS [{l}] {s}:{line} {m}',flush=True)
class NavPage(QWidget):
 def __init__(self,state,squall_event_service=None):
  print('NAVPY 1: entered',flush=True);super().__init__();self.state,self.squall_event_service,self.config,self.vessel,self.track=state,squall_event_service,VesselConfig(),VesselState(),TrackManager();self.follow=FollowController();self.layer_checks={};self.spatial=SpatialStateService();root=QVBoxLayout(self);root.setContentsMargins(20,14,20,14);root.setSpacing(10);head=QHBoxLayout();title=QLabel('NAVIGATION');title.setObjectName('sectionTitle');self.status=QLabel(f'● {state.telemetry_status.value}');self.status.setObjectName('statusNeutral');head.addWidget(title);head.addStretch();head.addWidget(self.status);root.addLayout(head);root.addLayout(self._toolbar());body=QHBoxLayout();self.web=QWebEngineView();self.web_profile=create_nav_profile(self);self.web.setPage(NavMapPage(self.web_profile,self.web));settings=self.web.settings();a=QWebEngineSettings.WebAttribute;settings.setAttribute(a.JavascriptEnabled,True);settings.setAttribute(a.WebGLEnabled,True);self._gds_scheme_handler=GdsMapSchemeHandler(self.web);self.web_profile.installUrlSchemeHandler(b'gds',self._gds_scheme_handler);print('WEB 3 scheme handler installed',flush=True);self.bridge=MapBridge(self.squall_event_service);
  if self.squall_event_service is not None:
   self.squall_event_service.add_listener(
    self._on_squall_event_state_changed
   )
  self.spatial.spatialStateChanged.connect(self.bridge.spatialStateChanged);self.spatial.selectedSpatialFeatureChanged.connect(self.bridge.selectedSpatialFeatureChanged);self.spatial.selectedSpatialFeatureChanged.connect(self._show_feature_info);self.bridge.spatialFeatureClicked.connect(self._select_spatial_feature);self.bridge.spatialViewChanged.connect(self._set_spatial_view_hint);channel=QWebChannel(self.web.page());channel.registerObject('bridge',self.bridge);self.web.page().setWebChannel(channel);print('WEB 4 page created',flush=True);self.web.loadStarted.connect(lambda:print('WEB 6 load started',flush=True));self.web.loadFinished.connect(self._map_loaded);url=QUrl('gds://map/index.html');print(f'WEB 5 URL requested {url.toString()}',flush=True);self.web.setUrl(url);body.addWidget(self.web,4);body.addWidget(self._side(),1);root.addLayout(body,1);self.trackbar=QLabel('TRACK  IDLE     DISTANCE  — NM     DURATION  —     POINTS  0');self.trackbar.setObjectName('technicalValue');root.addWidget(self.trackbar);print('NAVPY complete',flush=True)
  self._setup_events()
 def _on_squall_event_state_changed(self):
  self.bridge.publishEventState()
 def _setup_events(self):
  self._event_buttons={}
  self.bridge.commandRequested.connect(self._bridge_command)
  self.spatial_summary.setWordWrap(True)
  self.feature_info.setWordWrap(True);self.feature_info.setTextFormat(Qt.TextFormat.PlainText)
  self.bridge.eventStateChanged.connect(self._update_events)
  self.bridge.eventSelected.connect(lambda _:self.spatial.clear_selection())
  if self.bridge._event_render_state:self.bridge._event_render_state.spatial=self.spatial
  self.spatial.spatialStateChanged.connect(lambda _:self.bridge.publishEventState())
  self._update_events(self.bridge.getEventState())
 def _update_events(self,payload):
  self.event_count.setText(f'ACTIVE EVENTS  {payload["active_count"]}' if payload['active_count'] else 'NO ACTIVE EVENTS')
  ids=[event['event_id'] for event in payload['events']]
  if list(self._event_buttons)!=ids:
   while self.event_cards.count():
    item=self.event_cards.takeAt(0)
    if item.widget():item.widget().deleteLater()
   self._event_buttons={}
   for event_id in ids:
    button=QPushButton();button.setObjectName('secondaryButton');button.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
    button.clicked.connect(lambda _,eid=event_id:self.bridge.selectEvent(eid));self.event_cards.addWidget(button);self._event_buttons[event_id]=button
  for event in payload['events']:
   self._event_buttons[event['event_id']].setText(f'{event["event_id"]}  {event["status"]}\n{event["severity"] or "—"} · {event["impact_state"]}\nETA {event["eta_label"]} · Updated {event["age_label"]}')
  selected=next((e for e in payload['events'] if e['event_id']==payload['selected_event_id']),None)
  self.event_heading.setVisible(selected is not None);self.event_info.setVisible(selected is not None);self.show_event_button.setVisible(selected is not None)
  if selected:
   self.feature_heading.hide();self.feature_info.hide();self.zoom_feature_button.hide()
   self.event_info.setText('\n'.join(f'{key.replace("_"," ").upper()}  {selected.get(key) if selected.get(key) is not None else "—"}' for key in ('event_id','status','severity','impact_state','observed_at','age_label','latitude','longitude','direction_deg','speed_knots','eta_label','source','notes')))
 def _map_loaded(self, ok):
  print(f'NAV LOAD FINISHED: {ok}',flush=True)
  if ok:self._send_map_state()
 def _bridge_command(self,name):
  if name=='ready':self._send_map_state()
 def _send_map_state(self):
  self.bridge.spatialStateChanged.emit(self.spatial.payload());self.bridge.eventStateChanged.emit(self.bridge.getEventState())
  for name,checkbox in self.layer_checks.items():self.set_layer_visibility(name,checkbox.isChecked())
 def _toolbar(self):
  bar=QHBoxLayout()
  for caption,names in [('VESSEL',('CENTER VESSEL','FOLLOW','NORTH UP','FIT TRACK')),('MAP',('MARINE','SATELLITE')),('VIEW',('2D','3D')),('CONFIG',('VESSEL CONFIG',))]:
   group=QHBoxLayout();label=QLabel(caption);label.setObjectName('fieldLabelDark');group.addWidget(label)
   for name in names:
    b=QPushButton(name);b.setObjectName('secondaryButton');
    if name=='FOLLOW': self.follow_button=b;b.setCheckable(True)
    b.clicked.connect(lambda _,n=name:self.command(n));group.addWidget(b)
   bar.addLayout(group)
  bar.addStretch();return bar
 def _side(self):
  panel=QScrollArea();panel.setWidgetResizable(True);panel.setFrameShape(QFrame.Shape.NoFrame);host=QFrame();host.setObjectName('card');panel.setWidget(host);l=QVBoxLayout(host);l.setContentsMargins(16,16,16,16);layers=QLabel('LAYERS');layers.setObjectName('cardTitle');l.addWidget(layers)
  settings=QSettings('GDS','VTS')
  for name,enabled in [('Vessel',True),('Track',True),('Heading / COG',True),('Site Boundary',True),('Anchor Pattern',True),('Pipelines',True),('Survey Areas',True),('Operational Zones',True),('Squall Alerts',True)]:
   c=QCheckBox(name);c.setChecked(settings.value(f'nav/layers/{name}',enabled,type=bool));c.setEnabled(enabled)
   if name in LAYER_VISIBILITY: self.layer_checks[name]=c;c.toggled.connect(lambda visible,n=name:self.set_layer_visibility(n,visible))
   l.addWidget(c)
  self.spatial_summary=QLabel();self.spatial_summary.setObjectName('technicalValue');l.addSpacing(8);l.addWidget(QLabel('SPATIAL DATA'));l.addWidget(self.spatial_summary);self.spatial_view_hint=QLabel('SPATIAL DATA OUT OF VIEW');self.spatial_view_hint.setObjectName('technicalValue');self.spatial_view_hint.hide();self.show_spatial_button=QPushButton('SHOW DATA');self.show_spatial_button.setObjectName('secondaryButton');self.show_spatial_button.clicked.connect(lambda:self.command('FIT SPATIAL DATA'));self.show_spatial_button.hide();l.addWidget(self.spatial_view_hint);l.addWidget(self.show_spatial_button);fit_button=QPushButton('FIT SPATIAL DATA');fit_button.setObjectName('secondaryButton');fit_button.clicked.connect(lambda:self.command('FIT SPATIAL DATA'));l.addWidget(fit_button);import_button=QPushButton('IMPORT SPATIAL PACKAGE');import_button.setObjectName('secondaryButton');import_button.clicked.connect(self.import_spatial_package);l.addWidget(import_button);self._update_spatial_summary()
  l.addWidget(QLabel('SQUALL EVENTS'));self.event_count=QLabel('NO ACTIVE EVENTS');self.event_count.setObjectName('technicalValue');l.addWidget(self.event_count);self.event_cards=QVBoxLayout();l.addLayout(self.event_cards)
  self.event_heading=QLabel('EVENT INFO');self.event_heading.setObjectName('cardTitle');self.event_info=QLabel();self.event_info.setObjectName('technicalValue');self.event_info.setWordWrap(True);self.event_info.setTextFormat(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.TextFormat.PlainText);self.show_event_button=QPushButton('SHOW EVENT');self.show_event_button.setObjectName('secondaryButton');self.show_event_button.clicked.connect(lambda:self.web.page().runJavaScript('window.navMap&&navMap.showEvent()'));l.addWidget(self.event_heading);l.addWidget(self.event_info);l.addWidget(self.show_event_button)
  self.feature_heading=QLabel('FEATURE INFO');self.feature_heading.setObjectName('cardTitle');self.feature_info=QLabel('');self.feature_info.setObjectName('technicalValue');self.feature_info.hide();self.feature_heading.hide();self.zoom_feature_button=QPushButton('ZOOM TO FEATURE');self.zoom_feature_button.setObjectName('secondaryButton');self.zoom_feature_button.clicked.connect(lambda:self.web.page().runJavaScript('window.navMap&&navMap.zoomToSelectedFeature()'));self.zoom_feature_button.hide();l.addWidget(self.feature_heading);l.addWidget(self.feature_info);l.addWidget(self.zoom_feature_button)
  vessel=QLabel('VESSEL');vessel.setObjectName('cardTitle');l.addSpacing(10);l.addWidget(vessel);self.readout=QLabel('POSITION\n—\n\nSOG\n— kn\n\nCOG\n—°\n\nHEADING\n—°\n\nSOURCE\n—\n\nTELEMETRY AGE\n—');self.readout.setObjectName('technicalValue');l.addWidget(self.readout);l.addStretch();return panel
 def command(self,name):
  if name=='VESSEL CONFIG':
   d=VesselConfigDialog(self.config,self)
   if d.exec(): d.apply()
  elif name=='FOLLOW':
   enabled=self.follow.toggle();self.follow_button.setChecked(enabled);self.follow_button.setText(f'FOLLOW {"ON" if enabled else "OFF"}');self.web.page().runJavaScript(f'window.navMap&&navMap.setFollow({str(enabled).lower()})')
  else:self.web.page().runJavaScript(f"window.navMap&&navMap.command('{name}')")
 def set_layer_visibility(self,name,visible):
  QSettings('GDS','VTS').setValue(f'nav/layers/{name}',visible)
  categories={'Site Boundary':'site-boundary','Anchor Pattern':'anchor-pattern','Pipelines':'pipeline','Survey Areas':'survey-area','Operational Zones':'operational-zone'}
  selected=self.spatial.selection.feature
  if not visible and selected and selected.get('properties',{}).get('category')==categories.get(name): self.spatial.clear_selection()
  self.web.page().runJavaScript(f"window.navMap&&navMap.setLayerVisibility({name!r},{str(visible).lower()})")
 def _update_spatial_summary(self):
  metadata=self.spatial.state.metadata or {};counts=self.spatial.state.feature_counts
  self.spatial_summary.setText('NO DATA' if not metadata else f'Package\n{metadata.get("name")}\nRevision  {metadata.get("revision")}\nFeatures  {counts["total"]}\nStatus  ACTIVE')
 def _set_spatial_view_hint(self, out_of_view):
  self.spatial_view_hint.setVisible(out_of_view);self.show_spatial_button.setVisible(out_of_view)
 def _show_feature_info(self, feature):
  data=feature_info(feature if 'properties' in feature else {'properties':feature})
  if not data:
   self.feature_heading.hide();self.feature_info.hide();self.zoom_feature_button.hide();return
  labels={'name':'NAME','category':'CATEGORY','feature_id':'FEATURE ID','status':'STATUS','description':'DESCRIPTION','source':'SOURCE','revision':'REVISION','valid_from':'VALID FROM','valid_to':'VALID TO','notes':'NOTES'}
  self.feature_info.setText('\n'.join(f'{labels[key]}\n{value}' for key,value in data.items()));self.feature_heading.show();self.feature_info.show();self.zoom_feature_button.show()
 def _select_spatial_feature(self, category, feature_id):
  self.bridge.clearEventSelection()
  if category and feature_id:self.spatial.select_feature(category,feature_id)
  else:self.spatial.clear_selection()
 def import_spatial_package(self):
  path,_=QFileDialog.getOpenFileName(self,'Import Spatial Package','','GDS Spatial Package (*.gdsspatial)')
  if not path:return
  try:
   state=self.spatial.import_package(path);self._update_spatial_summary();QTimer.singleShot(0,lambda:self.command('FIT SPATIAL DATA'));QMessageBox.information(self,'Spatial package activated',f'{state.metadata["name"]}\nRevision {state.metadata["revision"]}\nFeatures {state.feature_counts["total"]}')
  except Exception as error: QMessageBox.warning(self,'Invalid spatial package',str(error))
 def refresh(self):
  f=self.state.latest_frame;self.status.setText(f'● {self.state.telemetry_status.value}')
  if f and f.valid and self.vessel.update(f,self.config):
   from app.nav.track_manager import TrackPoint
   accepted=self.track.append(TrackPoint(f.received_at,self.vessel.latitude,self.vessel.longitude,f.heading,f.cog,f.speed_knots))
   if accepted:
    self.bridge.telemetryChanged.emit({'latitude':self.vessel.latitude,'longitude':self.vessel.longitude,'heading':self.vessel.heading or 0})
    self.bridge.renderStateChanged.emit({'track':self.track.geojson_segments(),'start':self.track.start_geojson(),'heading':vector_geojson(self.vessel.latitude,self.vessel.longitude,f.heading),'cog':vector_geojson(self.vessel.latitude,self.vessel.longitude,f.cog)})
   m=track_metrics(self.track);self.readout.setText(f'POSITION\n{self.vessel.latitude:.6f}, {self.vessel.longitude:.6f}\n\nSOG\n{f.speed_knots or "—"} kn\n\nCOG\n{f.cog or "—"}°\n\nHEADING\n{f.heading or "—"}°\n\nSOURCE\n{f.source or "—"}\n\nTELEMETRY AGE\n{telemetry_age(f,__import__("datetime").datetime.now(__import__("datetime").timezone.utc))}');self.trackbar.setText(f'TRACK  {m["status"]}     DISTANCE  {m["distance_nm"]}     DURATION  {m["duration"]}     POINTS  {m["points"]}')
