from PySide6.QtCore import QObject, Signal, Slot
class MapBridge(QObject):
    telemetryChanged=Signal(dict); renderStateChanged=Signal(dict); spatialStateChanged=Signal(dict); selectedSpatialFeatureChanged=Signal(dict); spatialViewChanged=Signal(bool); spatialFeatureClicked=Signal(str,str); commandRequested=Signal(str)
    @Slot()
    def mapReady(self): self.commandRequested.emit('ready')
    @Slot(str)
    def mapInteraction(self,name): self.commandRequested.emit(name)
    @Slot(str,str)
    def selectSpatialFeature(self, category, feature_id): self.spatialFeatureClicked.emit(category, feature_id)
    @Slot()
    def clearSpatialFeature(self): self.spatialFeatureClicked.emit('', '')
