from pathlib import Path
import logging
from app.qt.QtCore import QUrl,QSettings,QTimer,Qt
from app.qt.QtGui import QColor
from app.qt.QtWidgets import QSizePolicy,QComboBox
from app.qt.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QCheckBox,QFileDialog,QMessageBox,QScrollArea
from app.qt.QtWebChannel import QWebChannel
from app.qt.QtWebEngineWidgets import QWebEngineView
from app.qt.QtWebEngineCore import QWebEnginePage,QWebEngineSettings
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
from .presentation_widgets import NAV_STYLE, Disclosure, SourceStatusPanel, InspectorRows, populate_legend
from .floating_controls import FloatingControls
from app.nav.maritime.render_state import LAYER_GROUPS, GIS_GROUPS, GIS_DEFAULTS, GIS_LAYERS
log=logging.getLogger(__name__)
class NavMapPage(QWebEnginePage):
 def javaScriptConsoleMessage(self,l,m,line,s): print(f'NAV JS [{l}] {s}:{line} {m}',flush=True)
class NavPage(FloatingControls,QWidget):
 def __init__(self,state,squall_event_service=None,maritime_runtime=None):
  self.maritime_runtime=maritime_runtime
  print('NAVPY 1: entered',flush=True)
  super().__init__();self.setObjectName('navSurface');self.setStyleSheet(NAV_STYLE)
  self.state,self.squall_event_service,self.config,self.vessel,self.track=state,squall_event_service,VesselConfig(),VesselState(),TrackManager()
  self.follow=FollowController();self.layer_checks={};self.spatial=SpatialStateService()
  root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
  self.status=QLabel(state.telemetry_status.value)
  self.web=QWebEngineView();root.addWidget(self.web)
  self.web_profile=create_nav_profile(self);self.web.setPage(NavMapPage(self.web_profile,self.web))
  self.web.page().setBackgroundColor(QColor('#101f29'))
  settings=self.web.settings();a=QWebEngineSettings.WebAttribute
  settings.setAttribute(a.JavascriptEnabled,True);settings.setAttribute(a.WebGLEnabled,True)
  self._gds_scheme_handler=GdsMapSchemeHandler(self.web)
  self.web_profile.installUrlSchemeHandler(b'gds',self._gds_scheme_handler)
  self.bridge=MapBridge(self.squall_event_service,maritime_service=maritime_runtime.service if maritime_runtime else None)
  self.trackbar=QLabel('TRACK IDLE')
  self._init_floating()
  if self.squall_event_service is not None:
   self.squall_event_service.add_listener(
    self._on_squall_event_state_changed
   )
  self.spatial.spatialStateChanged.connect(self.bridge.spatialStateChanged);self.spatial.selectedSpatialFeatureChanged.connect(self.bridge.selectedSpatialFeatureChanged);self.spatial.selectedSpatialFeatureChanged.connect(self._show_feature_info);self.bridge.spatialFeatureClicked.connect(self._select_spatial_feature);self.bridge.spatialViewChanged.connect(self._set_spatial_view_hint)
  channel=QWebChannel(self.web.page());channel.registerObject('bridge',self.bridge);self.web.page().setWebChannel(channel)
  self.web.loadFinished.connect(self._map_loaded)
  from app.qt import LEGACY
  if LEGACY:
   from app.nav.legacy_resources import LegacyResourceServer
   self._gds_scheme_handler._legacy_server=LegacyResourceServer(self._gds_scheme_handler)
   self.web.setUrl(QUrl(self._gds_scheme_handler._legacy_server.url))
  else:self.web.setUrl(QUrl('gds://map/index.html'))
  self._setup_events()
  self._setup_maritime()
  self._setup_offline_maps()
 def _setup_offline_maps(self):
  from app.nav.offline_maps.controller import PaletteController
  self.bridge.offline_config=self._gds_scheme_handler.config
  self.bridge.offline_config['map_view']='MARINE' if self.bridge.offline_config.get('preferred_source')=='online' else QSettings('GDS','VTS').value('nav/map_view','MARINE')
  self.bridge.basemapStateChanged.connect(self._basemap_state_changed)
  self.palette=PaletteController(self.state,self)
  self.bridge.offlineRegionsActive.connect(self._gds_scheme_handler.regional.retain)
  self.bridge.offlineRegionsChanged.connect(self._map_status_changed)
  self.bridge.mapCenterChanged.connect(self.palette.map_center)
  self.palette.changed.connect(self._palette_changed)
  self.palette_control.currentIndexChanged.connect(lambda _:self.palette.set_mode(self.palette_control.currentData()))
  self.palette_control.setCurrentIndex(self.palette_control.findData(self.palette.engine.mode))
  self._palette_changed(self.palette.payload)
  config=self.bridge.offline_config
  satellite=config.get('preferred_source')=='online' or any(layer.get('metadata',{}).get('gds:owner')=='satellite' for layer in config['style']['layers'])
  self.control_buttons['SATELLITE'].setEnabled(satellite)
  self.control_buttons['SATELLITE'].setToolTip('NASA GIBS · VIIRS True Color · No API key\nRegional Earth-observation context; detailed infrastructure comes from local GIS.' if config.get('preferred_source')=='online' else 'Satellite imagery' if satellite else 'Satellite · Not configured')
  self.map_package_status.setText(config['status']+('\nBATHYMETRY · '+config['bathymetry_status'] if config['installed'] else ''))
  if config.get('source_date'):self.map_package_status.setText(self.map_package_status.text()+'\nSource '+config['source_date'][:10])
  self.map_package_status.setToolTip('OpenFreeMap / OpenStreetMap: global online context. Primary region: Bangladesh + Southeast Asia. Offline map: NOT INSTALLED.' if config.get('preferred_source')=='online' else 'Optional offline map package installed.')
  settings=QSettings('GDS','VTS')
  if config.get('package_id'):settings.setValue('nav/map_package',config['package_id'])
  else:settings.remove('nav/map_package')
 def _basemap_state_changed(self,mode,state,date):
  for name in ('MARINE','SATELLITE'):self.control_buttons[name].setChecked(mode==name)
  detail='Satellite unavailable · Marine retained' if state=='ERROR' else 'NASA GIBS · '+state+(' · '+date if date else '')
  self.control_buttons['SATELLITE'].setToolTip(detail+'\nEarth-observation context; local GIS provides infrastructure detail.')
 def _map_regions(self):
  from .map_regions_dialog import MapRegionsDialog
  def changed():
   config=self._gds_scheme_handler.reload_packages();self.bridge.offline_config=config
   self.bridge.offlineConfigChanged.emit(config)
  MapRegionsDialog(self,changed=changed,release=self._gds_scheme_handler.regional.pause).exec()
 def showEvent(self,event):
  super().showEvent(event)
  if hasattr(self,'web'):QTimer.singleShot(0,lambda:self.web.page().runJavaScript('window.navMap&&navMap.resize()'))
 def _palette_changed(self,payload):
  self.bridge.palette_state=payload;self.bridge.paletteChanged.emit(payload)
  self.palette_control.setItemText(0,'AUTO · '+payload['computed_solar_state'])
  self.palette_control.setToolTip('Reference: '+payload['reference_type'].replace('_',' ').title())
 def _on_squall_event_state_changed(self):
  self.bridge.publishEventState()
 def _setup_events(self):
  self._event_buttons={}
  self.bridge.commandRequested.connect(self._bridge_command)
  self.spatial_summary.setWordWrap(True)
  self.feature_info.setWordWrap(True);self.feature_info.setTextFormat(Qt.TextFormat.PlainText)
  self.bridge.eventStateChanged.connect(self._update_events)
  self.bridge.eventSelected.connect(lambda _:self.spatial.clear_selection())
  self.bridge.eventSelected.connect(self.reopen_selection)
  if self.bridge._event_render_state:self.bridge._event_render_state.spatial=self.spatial
  self.spatial.spatialStateChanged.connect(lambda _:self.bridge.publishEventState())
  self._update_events(self.bridge.getEventState())
 def _update_events(self,payload):
  self.event_count.setText(f'ACTIVE EVENTS  {payload["active_count"]}' if payload['active_count'] else 'No active events')
  ids=[event['event_id'] for event in payload['events']]
  if list(self._event_buttons)!=ids:
   while self.event_cards.count():
    item=self.event_cards.takeAt(0)
    if item.widget():item.widget().deleteLater()
   self._event_buttons={}
   for event_id in ids:
    button=QPushButton();button.setObjectName('secondaryButton');button.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
    button.clicked.connect(lambda _=False,eid=event_id:self.bridge.selectEvent(eid));self.event_cards.addWidget(button);self._event_buttons[event_id]=button
  for event in payload['events']:
   self._event_buttons[event['event_id']].setText(f'{event["event_id"]}  {event["status"]}\n{event["severity"] or "—"} · {event["impact_state"]}\nETA {event["eta_label"]} · Updated {event["age_label"]}')
  selected=next((e for e in payload['events'] if e['event_id']==payload['selected_event_id']),None)
  self.event_heading.setVisible(selected is not None);self.event_info.setVisible(selected is not None);self.show_event_button.setVisible(selected is not None)
  if selected:
   self.maritime_heading.hide();self.maritime_info.hide();self.show_object_button.hide()
   self.feature_heading.hide();self.feature_info.hide();self.zoom_feature_button.hide()
   self.event_info.setText('\n'.join(f'{key.replace("_"," ").upper()}  {selected.get(key) if selected.get(key) is not None else "—"}' for key in ('event_id','status','severity','impact_state','observed_at','age_label','latitude','longitude','direction_deg','speed_knots','eta_label','source','notes')))
  if hasattr(self,'_sync_inspector'):self._sync_inspector(payload.get('selected_event_id'))
 def _map_loaded(self, ok):
  print(f'NAV LOAD FINISHED: {ok}',flush=True)
  if ok:self._send_map_state()
 def _bridge_command(self,name):
  if name=='ready':self._send_map_state()
 def _send_map_state(self):
  self.bridge.spatialStateChanged.emit(self.spatial.payload());self.bridge.eventStateChanged.emit(self.bridge.getEventState());self.bridge.publishMaritimeState()
  for name,checkbox in self.layer_checks.items():self.set_layer_visibility(name,checkbox.isChecked())
 def _layer_toggle(self,layout,name,caption=None):
  settings=QSettings('GDS','VTS');c=QCheckBox(caption or name)
  c.setChecked(settings.value(f'nav/layers/{name}',GIS_DEFAULTS.get(name,True),type=bool))
  self.layer_checks[name]=c;c.toggled.connect(lambda visible,n=name:self.set_layer_visibility(n,visible));layout.addWidget(c)
  return c
 def _side(self):
  panel=QScrollArea();self.nav_scroll=panel;panel.setFixedWidth(292)
  panel.setWidgetResizable(True);panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);panel.setFrameShape(QFrame.Shape.NoFrame)
  host=QFrame();host.setObjectName('navPanel');panel.setWidget(host)
  l=QVBoxLayout(host);l.setContentsMargins(11,10,11,10);l.setSpacing(6)
  self.map_package_status=QLabel('MAP / ONLINE / CONNECTING');self.map_package_status.setWordWrap(True);self.map_package_status.setObjectName('fieldLabelDark');l.addWidget(self.map_package_status)
  self.inspector_box=QFrame();self.inspector_box.setObjectName('navInspectorBox');inspector=QVBoxLayout(self.inspector_box)
  inspector.setContentsMargins(9,8,9,8);inspector.setSpacing(5);l.addWidget(self.inspector_box);self.inspector_box.hide()
  def inspector_section(title,command):
   heading=QLabel(title);heading.setObjectName('cardTitle')
   info=InspectorRows();info.setObjectName('navInspector');info.setWordWrap(True);info.setTextFormat(Qt.TextFormat.PlainText)
   info.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
   button=QPushButton(command);button.setObjectName('secondaryButton')
   for widget in (heading,info,button):inspector.addWidget(widget);widget.hide()
   return heading,info,button
  self.maritime_heading,self.maritime_info,self.show_object_button=inspector_section('MARITIME FEATURE','Show object')
  self.show_object_button.clicked.connect(lambda:self.web.page().runJavaScript('window.navMap&&navMap.showMaritimeObject()'))
  self.event_heading,self.event_info,self.show_event_button=inspector_section('EVENT INFO','Show event')
  self.show_event_button.clicked.connect(lambda:self.web.page().runJavaScript('window.navMap&&navMap.showEvent()'))
  self.feature_heading,self.feature_info,self.zoom_feature_button=inspector_section('FEATURE INFO','Zoom to feature')
  self.zoom_feature_button.clicked.connect(lambda:self.web.page().runJavaScript('window.navMap&&navMap.zoomToSelectedFeature()'))
  self._inspector_active=False;self._inspector_key=None;self.nav_groups={}
  close=QPushButton('LAYERS                                      ×');close.setAccessibleName('Close layers');close.setObjectName('secondaryButton');close.clicked.connect(lambda:self.toggle_layers() if getattr(self,'_floating',False) else None);l.addWidget(close)
  def group(title,key,expanded=False,parent_layout=l):
   section=Disclosure(title,key,expanded);self.nav_groups[key]=section;parent_layout.addWidget(section);return section
  own=group('OWN VESSEL','own-vessel',True)
  for name in ('Vessel','Track','Heading / COG'):self._layer_toggle(own.content,name)
  live=group('LIVE','live',True)
  for name in ('AIS Vessels','Squall Alerts','Nav Warnings','MetOcean'):self._layer_toggle(live.content,name)
  marine=group('MARITIME','maritime',True)
  world=group('Global reference','global-maritime',False,marine.content)
  for name in LAYER_GROUPS:
   if name not in GIS_GROUPS and name not in ('AIS Vessels','Nav Warnings','MetOcean'):self._layer_toggle(world.content,name)
  malaysia=group('MALAYSIA OFFSHORE','malaysia-offshore',True,marine.content)
  layer_groups={layer['dataset_id']:name for name in GIS_GROUPS for layer in GIS_LAYERS if GIS_GROUPS[name]==layer['dataset_id']}
  core_order={'platform':0,'pipeline':1,'field':2,'production':3,'well':4}
  core=sorted((layer for layer in GIS_LAYERS if layer['style_class'] in core_order),key=lambda layer:core_order[layer['style_class']])
  for layer in core:self._layer_toggle(malaysia.content,layer_groups[layer['dataset_id']],layer['display_name'])
  for title,key,predicate in (
   ('PSC / Blocks','malaysia-blocks',lambda x:x['style_class']=='block'),
   ('Seismic / Surveys','malaysia-surveys',lambda x:x['style_class']=='survey'),
   ('Development / Status','malaysia-status',lambda x:x['canonical_category']=='development_areas' and x['style_class']!='production'),
   ('Facility details','malaysia-details',lambda x:x['style_class']=='platform_detail')):
   section=group(title,key,False,malaysia.content)
   for layer in GIS_LAYERS:
    if predicate(layer):self._layer_toggle(section.content,layer_groups[layer['dataset_id']],layer['display_name'])
  for layer in GIS_LAYERS:
   if layer['style_class']=='basin':self._layer_toggle(malaysia.content,layer_groups[layer['dataset_id']],layer['display_name'])
  fit=QPushButton('Fit data');fit.setAccessibleName('FIT MALAYSIA GIS');fit.setObjectName('secondaryButton');fit.clicked.connect(lambda:self.command('FIT MALAYSIA GIS'));malaysia.content.addWidget(fit)
  project=group('PROJECT','project',False)
  for name in ('Site Boundary','Anchor Pattern','Pipelines','Survey Areas','Operational Zones'):self._layer_toggle(project.content,name)
  self.spatial_summary=QLabel();self.spatial_summary.setObjectName('navMuted');self.spatial_summary.setWordWrap(True);project.content.addWidget(self.spatial_summary)
  self.spatial_view_hint=QLabel('Project data outside view');self.spatial_view_hint.setObjectName('navMuted');self.spatial_view_hint.hide();project.content.addWidget(self.spatial_view_hint)
  self.show_spatial_button=QPushButton('Show project data');self.show_spatial_button.setObjectName('secondaryButton');self.show_spatial_button.clicked.connect(lambda:self.command('FIT SPATIAL DATA'));self.show_spatial_button.hide();project.content.addWidget(self.show_spatial_button)
  fit_project=QPushButton('Fit spatial data');fit_project.setObjectName('secondaryButton');fit_project.clicked.connect(lambda:self.command('FIT SPATIAL DATA'));project.content.addWidget(fit_project)
  import_button=QPushButton('Import spatial package');import_button.setObjectName('secondaryButton');import_button.clicked.connect(self.import_spatial_package);project.content.addWidget(import_button);self._update_spatial_summary()
  squall_row=QHBoxLayout();squall_label=QLabel('SQUALL');squall_label.setObjectName('cardTitle');squall_row.addWidget(squall_label)
  self.event_count=QLabel('No active events');self.event_count.setObjectName('navMuted');squall_row.addWidget(self.event_count,1,Qt.AlignmentFlag.AlignRight);l.addLayout(squall_row)
  self.event_cards=QVBoxLayout();self.event_cards.setSpacing(4);l.addLayout(self.event_cards)
  self.sources_section=group('DATA SOURCES','sources',False);self.source_info=SourceStatusPanel();self.sources_section.content.addWidget(self.source_info)
  legend=group('LEGEND','legend',False);populate_legend(legend.content)
  self.telemetry_section=group('VESSEL TELEMETRY','vessel-telemetry',False)
  self.readout=QLabel('Position ?\nSOG ? kn   COG ??\nHeading ??\nSource ?');self.readout.setObjectName('navReadout');self.readout.setWordWrap(True);self.telemetry_section.content.addWidget(self.readout)
  l.addStretch();return panel
 def _sync_inspector(self,key=None):
  if not hasattr(self,'inspector_box'):return
  active=any(not label.isHidden() for label in (self.maritime_heading,self.event_heading,self.feature_heading))
  if getattr(self,'_floating',False):
   new_selection=key and key!=self._inspector_key
   if new_selection:self._details=False;self._dismissed_selection=None
   if key:self._inspector_key=key
   self.inspector_box.setVisible(active)
   if not active:self.selection_panel.hide()
   elif new_selection or not self._inspector_active:
    self.selection_panel.setVisible(self._dismissed_selection!=self._inspector_key)
   if active:
    if new_selection:self.layers_panel.hide();self.layers_button.setChecked(False)
    self.details_button.setText('LESS' if self._details else 'DETAILS')
    for info in (self.maritime_info,self.event_info,self.feature_info):info.set_compact(not self._details)
   self._inspector_active=active;self._position_floating();return
  self.inspector_box.setVisible(active)
  if active!=self._inspector_active:
   for section in (self.sources_section,self.telemetry_section):
    if active:section.set_expanded(False,persist=False)
    else:section.restore_preference()
  if active and (not self._inspector_active or key and key!=self._inspector_key):
   QTimer.singleShot(0,lambda:self.nav_scroll.ensureWidgetVisible(self.inspector_box,0,6))
  self._inspector_active=active
  if key:self._inspector_key=key
 def command(self,name):
  if getattr(self,'_floating',False) and name=='MARINE':self.control_buttons['MARINE'].setChecked(True)
  if getattr(self,'_floating',False) and name in ('2D','3D'):
   for mode in ('2D','3D'):self.control_buttons[mode].setChecked(mode==name)
  if name=='VESSEL CONFIG':
   d=VesselConfigDialog(self.config,self)
   if d.exec(): d.apply()
  elif name=='FOLLOW':
   enabled=self.follow.toggle();self.follow_button.setChecked(enabled);self.follow_button.setToolTip('Follow vessel · '+('On' if enabled else 'Off'));self.web.page().runJavaScript(f'window.navMap&&navMap.setFollow({str(enabled).lower()})')
   if hasattr(self,'palette'):self.palette.update(follow=enabled)
  else:self.web.page().runJavaScript(f"window.navMap&&navMap.command('{name}')")
 def set_layer_visibility(self,name,visible):
  if name in LAYER_GROUPS and hasattr(self,'bridge'):
   self.bridge.setMaritimeVisibility(LAYER_GROUPS[name],visible)
  QSettings('GDS','VTS').setValue(f'nav/layers/{name}',visible)
  categories={'Site Boundary':'site-boundary','Anchor Pattern':'anchor-pattern','Pipelines':'pipeline','Survey Areas':'survey-area','Operational Zones':'operational-zone'}
  selected=self.spatial.selection.feature
  if not visible and selected and selected.get('properties',{}).get('category')==categories.get(name): self.spatial.clear_selection()
  self.web.page().runJavaScript(f"window.navMap&&navMap.setLayerVisibility({name!r},{str(visible).lower()})")
 def _update_spatial_summary(self):
  metadata=self.spatial.state.metadata or {};counts=self.spatial.state.feature_counts
  self.spatial_summary.setText('No project package loaded' if not metadata else f'Package  {metadata.get("name")}\nRevision  {metadata.get("revision")}\nFeatures  {counts["total"]}   ?   Status  Active')
 def _set_spatial_view_hint(self, out_of_view):
  self.spatial_view_hint.setVisible(out_of_view);self.show_spatial_button.setVisible(out_of_view)
 def _show_feature_info(self, feature):
  data=feature_info(feature if 'properties' in feature else {'properties':feature})
  if not data:
   self.feature_heading.hide();self.feature_info.hide();self.zoom_feature_button.hide()
   if hasattr(self,'_sync_inspector'):self._sync_inspector()
   return
  labels={'name':'NAME','category':'CATEGORY','feature_id':'FEATURE ID','status':'STATUS','description':'DESCRIPTION','source':'SOURCE','revision':'REVISION','valid_from':'VALID FROM','valid_to':'VALID TO','notes':'NOTES'}
  self.feature_info.setText('\n'.join(f'{labels[key]}\n{value}' for key,value in data.items()));self.feature_heading.show();self.feature_info.show();self.zoom_feature_button.show()
  if getattr(self,'_floating',False):self._dismissed_selection=None;self._inspector_active=False
  if hasattr(self,'_sync_inspector'):self._sync_inspector(data.get('feature_id'))
 def _select_spatial_feature(self, category, feature_id):
  self.bridge.clearEventSelection()
  if hasattr(self.bridge,'clearMaritimeSelection'):self.bridge.clearMaritimeSelection()
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
  if hasattr(self,'palette'):self.palette.update(follow=self.follow.enabled)
  if f and f.valid and self.vessel.update(f,self.config):
   if self.maritime_runtime:self.maritime_runtime.own_position(self.vessel.latitude,self.vessel.longitude)
   from app.nav.track_manager import TrackPoint
   accepted=self.track.append(TrackPoint(f.received_at,self.vessel.latitude,self.vessel.longitude,f.heading,f.cog,f.speed_knots))
   if accepted:
    self.bridge.telemetryChanged.emit({'latitude':self.vessel.latitude,'longitude':self.vessel.longitude,'heading':self.vessel.heading or 0})
    self.bridge.renderStateChanged.emit({'track':self.track.geojson_segments(),'start':self.track.start_geojson(),'heading':vector_geojson(self.vessel.latitude,self.vessel.longitude,f.heading),'cog':vector_geojson(self.vessel.latitude,self.vessel.longitude,f.cog)})
   self.trackbar.setVisible(True)
   m=track_metrics(self.track);self.readout.setText(f'POSITION\n{self.vessel.latitude:.6f}, {self.vessel.longitude:.6f}\n\nSOG\n{f.speed_knots or "—"} kn\n\nCOG\n{f.cog or "—"}°\n\nHEADING\n{f.heading or "—"}°\n\nSOURCE\n{f.source or "—"}\n\nTELEMETRY AGE\n{telemetry_age(f,__import__("datetime").datetime.now(__import__("datetime").timezone.utc))}');self.trackbar.setText(f'TRACK  {m["status"]}     DISTANCE  {m["distance_nm"]}     DURATION  {m["duration"]}     POINTS  {m["points"]}')

 def _setup_maritime(self):
  for label in (self.source_info,self.maritime_info):label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
  self.bridge.maritimeStateChanged.connect(self._update_maritime)
  self.bridge.maritimeObjectSelected.connect(lambda _:self.spatial.clear_selection())
  self.bridge.maritimeObjectSelected.connect(self.reopen_selection)
  if self.maritime_runtime:
   self.maritime_runtime.changed.connect(self.bridge.publishMaritimeState)
   self.bridge.maritimeViewportChanged.connect(self.maritime_runtime.viewport)
  self._update_maritime(self.bridge.getMaritimeState())
 def _update_maritime(self,payload):
  rows=[]
  for key,source in payload['sources'].items():
   age=source.get('age_seconds');suffix=f' | {int(age)}s since contact' if age is not None else ''
   state='CURRENT DATASET' if key in ('chart','offshore') and source['state']=='LIVE' else source['state'].replace('_',' ')
   count=sum(o['source']==key for o in payload['objects'])
   reason=f" | {source['error']}" if source.get('error') else ''
   show_count=count or (key=='overpass' and state=='READY')
   if key=='malaysia_gis':
    data=payload.get('gis_dataset',{});rows.append(f"MALAYSIA GIS  {state} | LOCAL GIS\n{data.get('total_features',0):,} TOTAL | {data.get('in_view',0):,} IN VIEW"+reason+(f"\n{data['invalid_features']} rejected (including {data.get('null_geometries',0)} null geometries)" if data.get('invalid_features') else ''));continue
   rows.append(f"{key.upper()}  {state}{' | CACHED' if source.get('cached') else ''}{suffix}{reason}"+(f' | {count} objects' if show_count else ''))
  rows.append('AIS  '+str(payload['counts'].get('vessels',0))+'   OFFSHORE  '+str(payload['counts'].get('offshore',0))+'   ATON  '+str(payload['counts'].get('aton',0)))
  area=payload.get('area')
  if area:rows.append(f"{'CURRENT VIEW' if area['origin']=='viewport' else 'OWN VESSEL AREA'}  {area['radius_nm']:.0f} NM")
  self.source_info.setText('\n'.join(rows))
  if hasattr(self.source_info,'set_payload'):self.source_info.set_payload(payload)
  selected=next((o for o in payload['objects'] if o['object_id']==payload['selected_object_id']),None)
  for widget in (self.maritime_heading,self.maritime_info,self.show_object_button):widget.setVisible(selected is not None)
  if not selected:
   if hasattr(self,'_sync_inspector'):self._sync_inspector()
   return
  if selected['properties'].get('gis_layer'):
   from app.nav.maritime.inspector import gis_inspector
   title,fields=gis_inspector(selected,payload.get('gis_layers',[]))
   dataset=next((layer for layer in payload.get('gis_layers',[]) if layer['dataset_id']==selected['properties']['gis_layer']),{})
   if dataset.get('style_class') in ('platform','platform_detail'):
    title='OFFSHORE INSTALLATION'
    priority=('Name','Type','Operator','Status','Water Depth (m)','Position')
    values=dict(fields)
    fields=[(key,values[key]) for key in priority if key in values]+[(key,value) for key,value in fields if key not in priority]
   self.maritime_heading.setText(title);self.maritime_info.setText('\n'.join(f'{key}  {value}' for key,value in fields))
   for widget in (self.feature_heading,self.feature_info,self.zoom_feature_button,self.event_heading,self.event_info,self.show_event_button):widget.hide()
   if hasattr(self,'_sync_inspector'):self._sync_inspector(selected['object_id'])
   return
  titles={'vessels':'VESSEL INFO','offshore':'OFFSHORE INSTALLATION','aton':'AID TO NAVIGATION','warnings':'NAV WARNING'}
  self.maritime_heading.setText(titles.get(selected['category'],'MARITIME FEATURE'))
  fields={k:selected[k] for k in ('object_type','source','source_id','status','freshness','observed_at','dataset_at','received_at','age_seconds') if selected.get(k) is not None}
  props=selected['properties']
  for key in ('name','mmsi','imo','call_sign','ship_type','sog','cog','heading','navigation_status','draught','destination','eta','operator','characteristic','title','warning_id','issued_at','description','severity','confidence','quality','source_tier','dataset_version','attribution','classification','depth_m','value','unit','wind_speed_knots','wind_direction_deg','wave_height_m','wave_direction_deg','current_knots','sst','sea_level_m','tide_m','visibility_nm','rain_mm_h','pressure_hpa'):
   if props.get(key) is not None:fields[key]=props[key]
  if selected['geometry']['type']=='Point':
   lon,lat=selected['geometry']['coordinates'][:2];fields['position']=f'{lat:.6f}, {lon:.6f}'
  for key in ('distance_nm','bearing_deg'):
   if key in selected:fields[key]=f"{selected[key]:.1f}"
  self.maritime_info.setText('\n'.join(f"{k.replace('_',' ').upper()}  {v}" for k,v in fields.items()))
  for widget in (self.feature_heading,self.feature_info,self.zoom_feature_button,self.event_heading,self.event_info,self.show_event_button):widget.hide()
  if hasattr(self,'_sync_inspector'):self._sync_inspector(selected['object_id'])
