from PySide6.QtCore import QObject, Signal, Slot
from app.nav.events.render_state import EventRenderStateBuilder
class MapBridge(QObject):
    eventSelected=Signal(str)
    eventSelectionCleared=Signal()
    telemetryChanged=Signal(dict); renderStateChanged=Signal(dict); spatialStateChanged=Signal(dict); eventStateChanged=Signal(dict); selectedSpatialFeatureChanged=Signal(dict); spatialViewChanged=Signal(bool); spatialFeatureClicked=Signal(str,str); commandRequested=Signal(str)
    def __init__(self, squall_event_service=None, parent=None):
        super().__init__(parent); self._event_render_state = EventRenderStateBuilder(squall_event_service) if squall_event_service else None
        self.squall_event_service = squall_event_service
        self._last_event_signature = None
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
