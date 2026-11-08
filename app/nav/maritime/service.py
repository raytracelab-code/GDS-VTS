"""One canonical store. AIS is a category facade, not a second target database."""
from dataclasses import replace
from copy import deepcopy
from .models import Category, MaritimeObject, normalize_ais, utcnow, MaritimeDataError
from .source_health import SourceHealth, SourceState

AIS_STALE_SECONDS = 120
AIS_EXPIRE_SECONDS = 600


class MaritimeObjectService:
    def __init__(self, clock=utcnow, stale_seconds=AIS_STALE_SECONDS, expire_seconds=AIS_EXPIRE_SECONDS, own_mmsi=None):
        if not 0 < stale_seconds < expire_seconds:
            raise MaritimeDataError('invalid stale/expire thresholds')
        self.clock, self.stale_seconds, self.expire_seconds = clock, stale_seconds, expire_seconds
        self.own_mmsi = str(own_mmsi) if own_mmsi else None
        self._objects, self._listeners = {}, []
        self.sources = {key: SourceHealth() for key in ('ais', 'chart', 'offshore', 'warnings', 'metocean')}
        self.visibility = {str(c): True for c in Category}
        self.selected_object_id, self.area, self.own_position = None, None, None
        self.reference_layers = {}
        self.gis_layers = {}
        self.gis_dataset = {}
        self.offshore_source_priority = ()
        self.revision = 0

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _changed(self):
        self.revision += 1
        for callback in tuple(self._listeners):
            callback()

    def snapshot(self):
        return tuple(deepcopy(list(self._objects.values())))

    def render_snapshot(self):
        """Internal read-only records; payload() copies values at the UI boundary."""
        return tuple(self._objects.values())

    def ingest(self, objects, replace_source=None, *, copy_objects=True):
        objects = list(objects)
        if len(objects) > 50000 or any(not isinstance(o, MaritimeObject) for o in objects):
            raise MaritimeDataError('invalid canonical object batch')
        updated = dict(self._objects)
        if replace_source:
            updated = {k: v for k, v in updated.items() if v.source != replace_source or v.category == Category.VESSEL}
        for obj in objects:
            if obj.category == Category.VESSEL and self.own_mmsi and obj.properties.get('mmsi') == self.own_mmsi:
                continue
            stamp = obj.observed_at or obj.received_at
            if (obj.expires_at and self.clock() >= obj.expires_at) or (obj.category == Category.VESSEL and stamp and (self.clock()-stamp).total_seconds() >= self.expire_seconds):
                continue
            previous = updated.get(obj.object_id) or self._objects.get(obj.object_id)
            if previous is obj:
                updated[obj.object_id] = previous
                continue
            if previous and previous.source != obj.source and obj.category != Category.VESSEL:
                tiers={'OFFICIAL_GOVERNMENT':0,'OFFICIAL_SERVICE':1,'SATELLITE_DERIVED':2,'COMMUNITY':3}
                if tiers.get(previous.properties.get('source_tier'),99)<tiers.get(obj.properties.get('source_tier'),99):
                    updated[obj.object_id]=previous
                    continue
            stamp, old_stamp = obj.observed_at or obj.dataset_at, (previous.observed_at or previous.dataset_at) if previous else None
            if previous and old_stamp and (stamp is None or stamp < old_stamp):
                updated[obj.object_id] = previous
                continue
            if previous and obj.category == Category.VESSEL:
                obj = replace(obj, properties={**previous.properties, **obj.properties})
                if obj.observed_at is None and obj.received_at != previous.received_at:
                    updated[obj.object_id] = deepcopy(obj)
                    continue
            if previous:
                comparable = replace(obj, received_at=previous.received_at)
                if obj.category == Category.VESSEL:
                    comparable = replace(comparable, status=previous.status, freshness=previous.freshness)
                if comparable == previous:
                    updated[obj.object_id] = previous
                    continue
            updated[obj.object_id] = deepcopy(obj) if copy_objects else obj
        if updated == self._objects:
            return False
        self._objects = updated
        self._reconcile_selection()
        self._changed()
        return True

    def _reconcile_selection(self):
        if self.selected_object_id not in self._objects:
            self.selected_object_id = None

    def evaluate_time(self, now=None):
        now, changed = now or self.clock(), False
        for key, obj in list(self._objects.items()):
            stamp = obj.observed_at or obj.received_at
            seconds = max(0, (now-stamp).total_seconds()) if stamp else None
            if (obj.expires_at and now >= obj.expires_at) or (obj.category == Category.VESSEL and seconds is not None and seconds >= self.expire_seconds):
                del self._objects[key]; changed = True
            elif (obj.category == Category.VESSEL or (obj.source=='aisstream' and obj.category==Category.AID_TO_NAVIGATION)) and seconds is not None:
                state = 'STALE' if seconds >= self.stale_seconds else 'LIVE'
                freshness = state if obj.observed_at or state == 'STALE' else 'UNKNOWN'
                if obj.status != state or obj.freshness != freshness:
                    self._objects[key] = replace(obj, status=state, freshness=freshness); changed = True
        for key, source in self.sources.items():
            if (key in ('ais', 'warnings', 'metocean') or source.dynamic) and source.last_success_at and source.state == SourceState.LIVE and (now-source.last_success_at).total_seconds() >= self.stale_seconds:
                source.state = SourceState.STALE; changed = True
        if changed:
            self._reconcile_selection(); self._changed()
        return changed

    def select(self, object_id):
        object_id = self.offshore_duplicates().get(object_id,object_id)
        obj = self._objects.get(object_id)
        if not obj or not self.object_visible(obj):
            return False
        self.selected_object_id = object_id; self._changed(); return True

    def clear_selection(self):
        if self.selected_object_id is not None:
            self.selected_object_id = None; self._changed()

    def set_visibility(self, category, visible):
        category = category if category in self.gis_layers else str(Category(category))
        if self.visibility[category] != bool(visible):
            self.visibility[category] = bool(visible)
            obj = self._objects.get(self.selected_object_id)
            if not visible and obj and (str(obj.category) == category or obj.properties.get('gis_layer') == category):
                self.selected_object_id = None
            self._changed()

    def object_visible(self, obj):
        layer = obj.properties.get('gis_layer')
        return self.visibility[str(obj.category)] and self.visibility.get(layer, True)

    def set_gis_result(self, result):
        self.gis_layers = {layer['dataset_id']: layer for layer in result.layers}
        for key, layer in self.gis_layers.items():
            self.visibility.setdefault(key, layer['default_visibility'])
        self.gis_dataset = result.metadata
        # The local worker owns immutable, validated snapshots. Reuse those
        # records instead of copying dense facility drawings on the GUI thread.
        self.ingest(result.objects, replace_source='malaysia_gis',copy_objects=False)
        self.selected_object_id = self.offshore_duplicates().get(self.selected_object_id,self.selected_object_id)
        self._changed()

    def offshore_duplicates(self):
        """Conservative display-only priority; both original provider records remain."""
        priority = self.offshore_source_priority
        if 'malaysia_gis' not in priority or 'overpass' not in priority or priority.index('malaysia_gis')>priority.index('overpass'):
            return {}
        alias = lambda value: ''.join(str(value or '').upper().split())
        local = {}
        for obj in self._objects.values():
            if obj.source=='malaysia_gis' and obj.properties.get('gis_layer')=='malaysia_platform' and self.object_visible(obj):
                raw = obj.properties.get('source_attributes',{})
                for name in (obj.properties.get('name'),raw.get('PLAT_ABBREV_NAME')):
                    if name:local.setdefault(alias(name),[]).append(obj)
        duplicates = {}
        for obj in self._objects.values():
            if obj.source!='overpass' or obj.category!=Category.OFFSHORE_INSTALLATION or obj.geometry['type']!='Point':
                continue
            x,y = obj.geometry['coordinates'][:2]
            for preferred in local.get(alias(obj.properties.get('name')),[]):
                px,py = preferred.geometry['coordinates'][:2]
                if (px-x)**2+(py-y)**2<.0005**2:
                    duplicates[obj.object_id] = preferred.object_id
                    break
        return duplicates

    def set_source(self, key, state, *, error=None, cached=False, success=False):
        health = self.sources[key]
        health.state, health.error, health.cached = SourceState(state), error, cached
        health.area = self.area.payload() if self.area else None
        if success:
            health.last_message_at = health.last_success_at = self.clock()
        self._changed()


class AISService:
    def __init__(self, store):
        self.store = store

    def ingest(self, records, source='ais'):
        return self.store.ingest([normalize_ais(r, source, self.store.clock()) for r in records])


class MaritimeChartService:
    def __init__(self, store):
        self.store = store

    def ingest(self, features, source='chart', dataset_at=None):
        from .models import normalize_maritime_feature
        return self.store.ingest([normalize_maritime_feature(f, source, dataset_at) for f in features], replace_source=source)


# Category adapters feed one store; there are no independent duplicate registries.
OffshoreAssetService = MaritimeChartService
AidsToNavigationService = MaritimeChartService
InfrastructureService = MaritimeChartService
WarningService = MaritimeChartService
MetOceanService = MaritimeChartService
