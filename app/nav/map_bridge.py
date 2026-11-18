from app.qt.QtCore import QObject, Signal, Slot
from app.nav.events.render_state import EventRenderStateBuilder
from app.nav.maritime.render_state import build_render_state
class MapBridge(QObject):
    basemapStateChanged=Signal(str,str,str)
    @Slot(result=dict)
    def getSatelliteMapConfig(self):
        from app.nav.satellite_map import satellite_config
        return satellite_config()
    @Slot(str,str,str)
    def reportBasemapState(self,mode,state,date):
        if mode not in ('MARINE','SATELLITE') or state not in ('READY','LOADING','ERROR'):return
        from datetime import date as calendar_date
        try:
            if date:calendar_date.fromisoformat(date)
        except ValueError:return
        self.satellite_state=dict(mode=mode,state=state,date=date)
        self.basemapStateChanged.emit(mode,state,date)
    offlineConfigChanged=Signal(dict)
    offlineRegionsChanged=Signal(str)
    offlineRegionsActive=Signal(list)
    @Slot(str)
    def reportMapStatus(self,status):
        self.offlineRegionsChanged.emit(status[:160])
    @Slot(str,str)
    def reportOfflineRegions(self,ids,status):
        import json
        try:
            keys=json.loads(ids)
            if not isinstance(keys,list) or len(keys)>256 or any(not isinstance(k,str) for k in keys):return
        except ValueError:return
        self.offlineRegionsActive.emit(keys);self.offlineRegionsChanged.emit(status)
    paletteChanged=Signal(dict)
    mapCenterChanged=Signal(float,float)
    @Slot(result=dict)
    def getOfflineMapConfig(self):
        return getattr(self,'offline_config',{})
    @Slot(result=dict)
    def getPalette(self):
        return getattr(self,'palette_state',{})
    @Slot(float,float)
    def reportMapCenter(self,latitude,longitude):
        from app.nav.offline_maps.palette import position
        if position((latitude,longitude)):self.mapCenterChanged.emit(latitude,longitude)
    @Slot(str)
    def setMapView(self,mode):
        if mode in ('MARINE','SATELLITE'):
            from app.qt.QtCore import QSettings
            QSettings('GDS','VTS').setValue('nav/map_view',mode)
    maritimeStateChanged=Signal(dict)
    maritimeObjectSelected=Signal(str)
    maritimeViewportChanged=Signal(float,float,float,float)
    eventSelected=Signal(str)
    eventSelectionCleared=Signal()
    telemetryChanged=Signal(dict); renderStateChanged=Signal(dict); spatialStateChanged=Signal(dict); eventStateChanged=Signal(dict); selectedSpatialFeatureChanged=Signal(dict); spatialViewChanged=Signal(bool); spatialFeatureClicked=Signal(str,str); commandRequested=Signal(str)
    def __init__(self, squall_event_service=None, parent=None, maritime_service=None):
        super().__init__(parent); self._event_render_state = EventRenderStateBuilder(squall_event_service) if squall_event_service else None
        self.squall_event_service = squall_event_service
        self._last_event_signature = None
        self.maritime_service = maritime_service
    def publishMaritimeState(self):
        self.maritimeStateChanged.emit(self.getMaritimeState())
    @Slot(result=dict)
    def getMaritimeState(self):
        return build_render_state(self.maritime_service)
    @Slot(str)
    def reportReferenceError(self,provider):
        if self.maritime_service and provider in self.maritime_service.reference_layers:
            from app.nav.maritime.source_health import SourceState
            if self.maritime_service.sources[provider].state!=SourceState.DEGRADED:
                self.maritime_service.set_source(provider,SourceState.DEGRADED,error='Reference tile unavailable')
                self.publishMaritimeState()
    @Slot(str)
    def selectMaritimeObject(self,object_id):
        if self.maritime_service and self.maritime_service.select(object_id):
            self.clearEventSelection()
            self.maritimeObjectSelected.emit(object_id)
            self.publishMaritimeState()
    @Slot()
    def clearMaritimeSelection(self):
        if self.maritime_service and self.maritime_service.selected_object_id is not None:
            self.maritime_service.clear_selection();self.publishMaritimeState()
    @Slot(str,bool)
    def setMaritimeVisibility(self,category,visible):
        if self.maritime_service:
            self.maritime_service.set_visibility(category,visible);self.publishMaritimeState()
    @Slot(float,float,float,float)
    def reportMaritimeViewport(self,west,south,east,north):
        from app.nav.maritime.models import number,MaritimeDataError
        try:
            for value,low,high in [(west,-180,180),(east,-180,180),(south,-90,90),(north,-90,90)]:number(value,low,high,'viewport')
        except MaritimeDataError:return
        self.maritimeViewportChanged.emit(west,south,east,north)
    def publishEventState(self):
        payload=self.getEventState()
        # Age labels/clock alone must not resend full event geometry each tick.
        signature={**payload,'updated_at':None,'events':[{**e,'age_label':None} for e in payload['events']]}
        if signature!=self._last_event_signature:
            self._last_event_signature=signature
            self.eventStateChanged.emit(payload)
    @Slot(str)
    def selectEvent(self,event_id):
        if self._event_render_state and self._event_render_state.select_event(event_id):
            self.clearMaritimeSelection()
            self.eventSelected.emit(event_id);self.publishEventState()
    @Slot()
    def clearEventSelection(self):
        if self._event_render_state and self._event_render_state.selected_event_id is not None:
            self._event_render_state.clear_event_selection();self.eventSelectionCleared.emit();self.publishEventState()
    @Slot(result=dict)
    def getEventState(self):
        return self._event_render_state.payload() if self._event_render_state else {'events':[],'active_count':0,'selected_event_id':None,'updated_at':None,'geojson':{key:{'type':'FeatureCollection','features':[]} for key in ('current','direction','trajectories','impact_zones','surveillance_zones','prediction_points','selection')}}
    @Slot()
    def mapReady(self): self.commandRequested.emit('ready')
    @Slot(str)
    def mapInteraction(self,name): self.commandRequested.emit(name)
    @Slot(str,str)
    def selectSpatialFeature(self, category, feature_id): self.spatialFeatureClicked.emit(category, feature_id)
    @Slot()
    def clearSpatialFeature(self): self.spatialFeatureClicked.emit('', '')
    @Slot(bool)
    def reportSpatialView(self,out_of_view): self.spatialViewChanged.emit(out_of_view)
