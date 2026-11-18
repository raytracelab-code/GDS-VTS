"""Qt coordinator: worker-only I/O, queued results, one batched publication timer."""
import logging
import time
from app.core.compat import ThreadPoolExecutor
from app.qt.QtCore import QObject, Signal, Slot, QTimer, Qt
from .config import MaritimeConfig
from .service import MaritimeObjectService
from .area_controller import MaritimeAreaController
from .adapters.base import JsonPollingAdapter, StaticCache
from .source_health import SourceState

log = logging.getLogger(__name__)


class MaritimeRuntime(QObject):
    changed = Signal()
    _completed = Signal(str, int, object, object, bool)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or MaritimeConfig()
        self.service = MaritimeObjectService(stale_seconds=self.config.stale_seconds,
            expire_seconds=self.config.expire_seconds, own_mmsi=self.config.own_mmsi)
        self.controller = MaritimeAreaController(self.config.radius_nm, self.config.movement_nm, self.config.debounce_seconds)
        self.adapters = {key: JsonPollingAdapter(c) for key, c in self.config.sources.items()}
        self.cache = StaticCache(self.config.cache_directory)
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='maritime')
        self._generation, self._busy, self._next = 0, set(), {}
        self._dirty, self._closed, self._pending_view = False, False, None
        self._last_own_query = None
        self._last_age_publish = 0
        self._failures = {}
        self._last_started = {}
        self._retry_until = {}
        self.aisstream = None
        self.malaysia_gis = None
        self._ais_transport_state = None
        self.service.add_listener(self._mark_dirty)
        self._completed.connect(self._receive, Qt.ConnectionType.QueuedConnection)
        for key in self.adapters:
            self.service.set_source(key, SourceState.CONNECTING)
        if self.config.provider_env is not None:
            from .providers import install
            install(self,self.config.provider_env)
        for key,health in self.service.sources.items():log.info('MARITIME SOURCE %s %s instantiated=%s',key.upper(),health.state,key in self.adapters or (key=='aisstream' and self.aisstream is not None) or (key=='malaysia_gis' and self.malaysia_gis is not None))
        self.timer = QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.tick); self.timer.start()

    def _mark_dirty(self):
        self._dirty = True

    def own_position(self, latitude, longitude):
        from .models import number, MaritimeDataError
        try:
            number(latitude, -90, 90, 'own latitude'); number(longitude, -180, 180, 'own longitude')
        except MaritimeDataError:
            return
        position = (latitude, longitude)
        if position != self.service.own_position and self.service.selected_object_id:
            self._dirty = True
        self.service.own_position = position
        from .area_controller import distance_bearing
        if self._last_own_query and distance_bearing(*self._last_own_query, latitude, longitude)[0] < self.config.movement_nm:
            return
        area = self.controller.request(latitude, longitude)
        if area:
            self._last_own_query = (latitude, longitude)
            self._set_area(area)

    def viewport(self, west, south, east, north):
        # GUI sends settled moveend only. Keep final request if debounce is active.
        self._pending_view = (west, south, east, north)

    def _set_area(self, area):
        self.service.area = area; self._generation += 1; self._next.clear()
        for source in self.service.sources.values():
            source.area = area.payload()
        self.service._changed()
        if self.aisstream:self.aisstream.start(area)
        log.info('MARITIME AREA UPDATED origin=%s radius_nm=%.1f', area.origin, area.radius_nm)

    def tick(self):
        if self._closed:
            return
        if self._pending_view:
            area = self.controller.viewport(*self._pending_view)
            if area:
                self._set_area(area); self._pending_view = None
            elif self.controller.clock()-self.controller._last >= self.controller.debounce_seconds:
                self._pending_view = None
        self.service.evaluate_time()
        if self.aisstream:
            messages,state,confirmed=self.aisstream.drain()
            staged={}
            from .adapters.base import intersects_area
            for message in messages:
                try:
                    meta=message.get('MetaData',{});eid='ais:'+str(meta.get('MMSI',''))
                    obj=self.ais_normalizer.normalize(message,staged.get(eid,self.service._objects.get(eid)))
                    if obj and self.service.area and intersects_area(obj.geometry,self.service.area):staged[obj.object_id]=obj
                except (ValueError,TypeError,KeyError,AttributeError):continue
            if staged:self.service.ingest(staged.values())
            health=self.service.sources['aisstream']
            if messages or self._ais_transport_state!=state:
                self.service.set_source('aisstream',state,success=confirmed)
                self._ais_transport_state=state
        now = time.monotonic()
        # Local disk parsing and indexing stay on the existing worker pool. Stat-only
        # refresh every 30s also catches replaced datasets without a map movement.
        if self.malaysia_gis and 'malaysia_gis' not in self._busy and now >= self._next.get('malaysia_gis',0):
            self._busy.add('malaysia_gis')
            if self.malaysia_gis.load_count == 0:
                self.service.set_source('malaysia_gis',SourceState.LOADING)
            self.executor.submit(self._fetch_malaysia, self._generation, self.service.area)
        if now-self._last_age_publish >= 1 and any(o.category.value=='vessels' or o.source=='aisstream' for o in self.service.render_snapshot()):
            self._last_age_publish = now; self._dirty = True
        if self.service.area:
            for key, adapter in self.adapters.items():
                if key not in self._busy and now >= self._next.get(key, 0):
                    self._busy.add(key)
                    generation, area = self._generation, self.service.area
                    self.executor.submit(self._fetch, key, adapter, generation, area)
        if self._dirty:
            self._dirty = False; self.changed.emit()

    def _fetch(self, key, adapter, generation, area):
        objects, error, cached = None, None, False
        retry_after=0
        try:
            objects = self.cache.load_fresh(adapter.config,area)
            cached = objects is not None
            if objects is None:
                from .adapters.provider_common import ProviderRequestError
                now=time.monotonic()
                deadline=max(self._retry_until.get(key,0),self._last_started.get(key,float('-inf'))+60 if key=='overpass' else 0)
                if now<deadline:raise ProviderRequestError('PROVIDER BACKOFF',deadline-now)
                self._last_started[key]=now
                objects = adapter.fetch(area)
            try:
                from .adapters.provider_common import ProviderResult
                if not cached:self.cache.save(adapter.config, area, objects.objects if isinstance(objects,ProviderResult) else objects)
            except OSError:
                log.warning('MARITIME cache write unavailable source=%s', key)
        except Exception as exc:
            # Exception messages may contain credentials/URLs; expose class only.
            error = getattr(exc,'state',type(exc).__name__)
            retry_after=getattr(exc,'retry_after',0)
            objects = None
            if error not in ('OUT_OF_COVERAGE','DISABLED','DISABLED_LICENSE','NOT_CONFIGURED','NO_STABLE_MACHINE_API'):
                try:
                    objects = self.cache.load(adapter.config, area)
                except OSError:
                    log.warning('MARITIME cache read unavailable source=%s', key)
            cached = objects is not None
        if not self._closed:
            self._completed.emit(key, generation, objects, (error,retry_after) if retry_after else error, cached)

    def _fetch_malaysia(self, generation, area):
        result, error = None, None
        try:
            from .adapters.malaysia import GISResult
            self.malaysia_gis.load()
            result = self.malaysia_gis.fetch(area) if area else GISResult((),self.malaysia_gis.metadata,self.malaysia_gis.layers)
            if result.metadata['file_count'] == 0:
                error = 'NOT_CONFIGURED'
            elif result.metadata['errors']:
                error = '; '.join(result.metadata['errors'])
            elif result.metadata['invalid_features']:
                # Partial feature rejection is visible, but valid reference data is READY.
                log.warning('MALAYSIA GIS rejected features=%s',result.metadata['invalid_features'])
        except Exception as exc:
            error = str(exc)
        if not self._closed:
            self._completed.emit('malaysia_gis',generation,result,error,False)

    @Slot(str, int, object, object, bool)
    def _receive(self, key, generation, objects, error, cached):
        self._busy.discard(key)
        if isinstance(error,tuple):
            error,delay=error
            self._retry_until[key]=time.monotonic()+delay
        if self._closed or generation != self._generation:
            return
        if key == 'malaysia_gis':
            self._next[key] = time.monotonic()+30
            if objects is not None:
                self.service.set_gis_result(objects)
            state = SourceState.NOT_CONFIGURED if error == 'NOT_CONFIGURED' else SourceState.ERROR if error else SourceState.READY
            self.service.set_source(key,state,error=error,success=not error)
            return
        self._next[key] = time.monotonic()+self.config.sources[key].interval_seconds
        if error and error not in ('OUT_OF_COVERAGE','DISABLED','DISABLED_LICENSE','NOT_CONFIGURED','NO_STABLE_MACHINE_API'):
            self._failures[key]=self._failures.get(key,0)+1
            self._next[key]=time.monotonic()+min(900,30*2**min(5,self._failures[key]-1))
        elif error is None:self._failures.pop(key,None)
        from .adapters.provider_common import ProviderResult
        if isinstance(objects,ProviderResult):
            self.service.reference_layers.update(objects.reference_layers)
            objects=objects.objects
        if objects is not None:
            try:
                if cached:
                    from dataclasses import replace
                    objects = [replace(obj, freshness='CACHED') for obj in objects]
                self.service.ingest(objects, replace_source=key if key != 'ais' else None)
            except ValueError as exc:
                error = type(exc).__name__
        special={'OUT_OF_COVERAGE','DISABLED','DISABLED_LICENSE','NOT_CONFIGURED','NO_STABLE_MACHINE_API'}
        state = SourceState(error) if error in special else SourceState.DEGRADED if error and (objects is not None or any(o.source == key for o in self.service.render_snapshot())) else SourceState.ERROR if error else SourceState.READY if key in ('overpass','boem','emodnet','gfw','gebco','openwaters','openseamap') else SourceState.LIVE
        if state==SourceState.OUT_OF_COVERAGE:self.service.ingest([],replace_source=key)
        self.service.set_source(key, state, error=error, cached=cached, success=error is None and not cached)
        log.info('MARITIME SOURCE %s %s objects=%s error=%s', key.upper(), state,sum(o.source==key for o in self.service.render_snapshot()),error or 'NONE')

    def close(self):
        self._closed = True; self.timer.stop()
        if self.aisstream:self.aisstream.stop()
        if self.malaysia_gis:self.malaysia_gis.stop()
        for adapter in self.adapters.values():
            adapter.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
