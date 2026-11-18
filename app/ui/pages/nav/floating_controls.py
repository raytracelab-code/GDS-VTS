"""Map-first Qt presentation. Uses existing commands and read-only loaded records."""
import json
import re
from app.qt.QtCore import Qt, QEvent, QSize, QTimer
from app.qt.QtWidgets import (QApplication, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QToolButton, QLineEdit, QListWidget, QListWidgetItem, QComboBox, QScrollArea)
from app.ui.components.nav_icons import nav_icon


class FloatingControls:
    def _capsule(self, name):
        frame=QFrame(self);frame.setObjectName('navCapsule');frame.setAccessibleName(name)
        layout=QHBoxLayout(frame);layout.setContentsMargins(7,5,7,5);layout.setSpacing(3)
        return frame,layout

    def _tool(self, layout, name, callback=None, *, text='', checkable=False):
        button=QToolButton();button.setObjectName('mapTool');button.setAccessibleName(name)
        button.setIcon(nav_icon(name));button.setIconSize(QSize(20,20));button.setFixedSize(36,36)
        button.setToolTip(name.replace('_',' ').title());button.setCheckable(checkable)
        if text:
            button.setText(text);button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.clicked.connect(callback or (lambda _:self.command(name)))
        layout.addWidget(button);return button

    def _init_floating(self):
        self._floating=True;self._dismissed_selection=None;self._details=False
        self.control_groups=[];self.control_buttons={}
        for title,names in [('Navigation',('CENTER VESSEL','FOLLOW','NORTH UP')),
                            ('Map mode',('MARINE','SATELLITE')),
                            ('Operation',('LAYERS','WEATHER')),
                            ('View',('2D','3D','FIT TRACK','VESSEL CONFIG'))]:
            frame,layout=self._capsule(title);self.control_groups.append(frame)
            for name in names:
                callback=(lambda _:self.toggle_layers()) if name=='LAYERS' else (lambda _:self.toggle_weather()) if name=='WEATHER' else None
                button=self._tool(layout,name,callback,text=name if name in ('2D','3D') else '',checkable=name in ('FOLLOW','LAYERS','MARINE','SATELLITE','2D','3D'))
                self.control_buttons[name]=button
                if name=='FOLLOW':self.follow_button=button
        self.layers_button=self.control_buttons['LAYERS']
        self.control_buttons['MARINE'].setChecked(True);self.control_buttons['2D'].setChecked(True)
        self.control_buttons['SATELLITE'].setEnabled(False)
        self.control_buttons['SATELLITE'].setToolTip('Satellite · Not configured')
        self.search_capsule,layout=self._capsule('Map search')
        icon=QLabel();icon.setPixmap(nav_icon('SEARCH').pixmap(20,20));layout.addWidget(icon)
        self.search=QLineEdit();self.search.setObjectName('mapSearch');self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Search vessel, platform, field, location…')
        self.search.setAccessibleName('Search loaded map data or latitude, longitude')
        self.search.setToolTip('Loaded platforms, fields, pipelines and AIS / MMSI. Coordinates: latitude, longitude. No remote geocoding.')
        layout.addWidget(self.search,1)
        self.search_results=QListWidget(self);self.search_results.setObjectName('mapSearchResults');self.search_results.hide()
        self.search_results.setAccessibleName('Map search results')
        self.search_timer=QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._search_loaded)
        self.search.textChanged.connect(lambda _:self.search_timer.start())
        self.search.returnPressed.connect(self._activate_first_result)
        self.search_results.itemActivated.connect(self._activate_search)
        self.search_results.itemClicked.connect(self._activate_search)
        self.utility,layout=self._capsule('Map status and palette')
        self.online_status=QLabel('CONNECTING');self.online_status.setObjectName('onlineBadge');layout.addWidget(self.online_status)
        self.palette_control=QComboBox();self.palette_control.setAccessibleName('Map palette');self.palette_control.setFixedWidth(142)
        for mode in ('AUTO','DAY','NIGHT'):self.palette_control.addItem(mode,mode)
        layout.addWidget(self.palette_control)
        self.layers_panel=self._side();self.layers_panel.setParent(self);self.layers_panel.hide()
        self.layers_panel.setFixedWidth(312);self.layers_panel.setObjectName('floatingLayers')
        self.inspector_box.setParent(None)
        self.selection_panel=QScrollArea(self);self.selection_panel.setObjectName('selectionCard');self.selection_panel.setWidgetResizable(True)
        self.selection_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.selection_panel.setWidget(self.inspector_box);self.selection_panel.hide()
        self.inspector_box.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        controls=QHBoxLayout();self.inspector_box.layout().insertLayout(0,controls)
        label=QLabel('SELECTED OBJECT');label.setObjectName('navMuted');controls.addWidget(label);controls.addStretch()
        self._tool(controls,'CLOSE',lambda _:self.dismiss_selection())
        actions=QHBoxLayout();self.inspector_box.layout().addLayout(actions)
        for button in (self.show_object_button,self.show_event_button,self.zoom_feature_button):
            self.inspector_box.layout().removeWidget(button);actions.addWidget(button)
        self.show_object_button.setText('CENTER')
        self.details_button=QToolButton();self.details_button.setText('DETAILS');self.details_button.setObjectName('detailsButton')
        self.details_button.clicked.connect(self.toggle_details);actions.addWidget(self.details_button)
        self.trackbar.setParent(self);self.trackbar.setObjectName('floatingTrack');self.trackbar.hide()
        self.status.setParent(self.utility);self.status.hide()  # Full telemetry remains in Layers.
        QApplication.instance().installEventFilter(self)
        self._position_floating()

    def _map_status_changed(self, message):
        self.map_package_status.setText(message)
        if hasattr(self,'online_status'):
            label='LOCAL ONLY' if 'UNAVAILABLE' in message else 'SATELLITE' if 'SATELLITE' in message and 'READY' in message else 'LOADING' if 'SATELLITE' in message else 'ONLINE' if 'READY' in message else 'CONNECTING'
            self.online_status.setText(label);self.online_status.setToolTip(message)

    def _position_floating(self):
        if not getattr(self,'_floating',False):return
        w,h=self.width(),self.height();gap=12
        self.online_status.setVisible(w>=650)
        utility_width=254 if w>=650 else 162
        self.utility.setGeometry(max(12,w-utility_width-16),16,utility_width,48)
        search_width=max(120,min(360,w-utility_width-48))
        self.search_capsule.setGeometry(16,16,search_width,48)
        x,y=16,76
        for group in self.control_groups:
            width=group.sizeHint().width()
            if x+width>w-16:x,y=16,y+58
            group.setGeometry(x,y,width,48);group.raise_();x+=width+gap
        panel_top=y+60
        self.layers_panel.setGeometry(16,panel_top,min(312,w-32),max(100,min(600,h-panel_top-44)))
        card_height=min(self.inspector_box.sizeHint().height()+4,490 if self._details else 340)
        self.selection_panel.setGeometry(max(16,w-328),panel_top,min(312,w-32),max(100,min(card_height,h-panel_top-152)))
        result_height=min(320,max(50,self.search_results.count()*39+14))
        self.search_results.setGeometry(16,68,search_width,min(result_height,max(50,h-100)))
        self.trackbar.setGeometry(16,h-64,max(200,min(w-270,660)),26)
        for widget in (self.utility,self.search_capsule,self.layers_panel,self.selection_panel,self.search_results,self.trackbar):widget.raise_()

    def resizeEvent(self,event):
        super().resizeEvent(event);self._position_floating()

    def toggle_layers(self):
        visible=self.layers_panel.isHidden();self.layers_panel.setVisible(visible);self.layers_button.setChecked(visible)
        if visible:self.selection_panel.hide();self.search_results.hide()
        self._position_floating()

    def toggle_weather(self):
        if self.layers_panel.isHidden():self.toggle_layers()
        self.nav_scroll.ensureWidgetVisible(self.event_count,0,20)

    def close_overlays(self):
        if not getattr(self,'_floating',False):return
        self.layers_panel.hide();self.layers_button.setChecked(False);self.search_results.hide();self.dismiss_selection()

    def dismiss_selection(self):
        self.selection_panel.hide();self._dismissed_selection=self._inspector_key

    def reopen_selection(self,key):
        self._dismissed_selection=None;self._inspector_active=False
        self.layers_panel.hide();self.layers_button.setChecked(False)
        self._sync_inspector(key)

    def toggle_details(self):
        self._details=not self._details
        self.details_button.setText('LESS' if self._details else 'DETAILS')
        for info in (self.maritime_info,self.event_info,self.feature_info):info.set_compact(not self._details)
        self._position_floating()

    def eventFilter(self,watched,event):
        if not getattr(self,'_floating',False) or not self.isVisible():return False
        if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape:
            self.close_overlays();self.search.clearFocus();return True
        if event.type()==QEvent.Type.MouseButtonPress:
            if watched in (self.control_buttons['MARINE'],self.control_buttons['SATELLITE']):return False
            point=self.mapFromGlobal(event.globalPosition().toPoint())
            if not self.layers_panel.isHidden() and not self.layers_panel.geometry().contains(point):
                if not self.layers_button.rect().contains(self.layers_button.mapFromGlobal(event.globalPosition().toPoint())):
                    self.layers_panel.hide();self.layers_button.setChecked(False)
            if not self.search_capsule.geometry().contains(point) and not self.search_results.geometry().contains(point):self.search_results.hide()
        return super().eventFilter(watched,event)

    def _search_loaded(self):
        query=self.search.text().strip();self.search_results.clear()
        if len(query)<2:self.search_results.hide();return
        coordinate=re.fullmatch(r'\s*([+-]?\d+(?:\.\d+)?)\s*[,;]\s*([+-]?\d+(?:\.\d+)?)\s*',query)
        if coordinate:
            lat,lon=map(float,coordinate.groups())
            if -90<=lat<=90 and -180<=lon<=180:
                self._result(f'COORDINATES  ·  {lat:.4f}, {lon:.4f}',dict(geometry=dict(type='Point',coordinates=[lon,lat])))
        else:
            service=getattr(getattr(self,'bridge',None),'maritime_service',None)
            if service:
                for obj in service.render_snapshot():
                    props=obj.properties
                    if hasattr(service,'object_visible') and not service.object_visible(obj):continue
                    if query.casefold() not in ' '.join(str(props.get(k,'')) for k in ('name','mmsi','field','from','to')).casefold():continue
                    name=props.get('name') or props.get('mmsi') or obj.source_id
                    layer=props.get('gis_layer','')
                    category=next((label for token,label in (('platform','PLATFORMS'),('pipeline','PIPELINES'),('field','FIELDS'),('well','WELLS')) if token in layer),
                        {'vessels':'AIS','oil_gas_fields':'FIELDS','offshore':'INSTALLATIONS','subsea':'INFRASTRUCTURE'}.get(str(obj.category),str(obj.category).replace('_',' ').upper()))
                    self._result(f'{category}  ·  {name}',dict(object_id=obj.object_id,geometry=obj.geometry))
                    if self.search_results.count()>=12:break
        if not self.search_results.count():
            item=QListWidgetItem('No loaded matches · try latitude, longitude');item.setFlags(Qt.ItemFlag.NoItemFlags);self.search_results.addItem(item)
        self.search_results.setCurrentRow(0);self.search_results.show();self._position_floating()

    def _result(self,label,data):
        item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,data);self.search_results.addItem(item)

    def _activate_first_result(self):
        self.search_timer.stop();self._search_loaded()
        item=self.search_results.currentItem()
        if item:self._activate_search(item)

    def _activate_search(self,item):
        data=item.data(Qt.ItemDataRole.UserRole)
        if not data:return
        if data.get('object_id'):self.bridge.selectMaritimeObject(data['object_id'])
        self.web.page().runJavaScript('window.navMap&&navMap.focusGeometry('+json.dumps(data['geometry'])+')')
        self.search_results.hide();self.search.clearFocus()
