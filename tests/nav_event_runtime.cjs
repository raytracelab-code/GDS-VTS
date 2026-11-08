// Exercise the real NAV script's state cache, click priority and visibility
// with a MapLibre API double; no browser or synthetic production events.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class MapStub{
 constructor(){this.sources={};this.layers={};this.handlers={};this.order=[];this.moves=[];this.images={}}
 on(name,cb){this.handlers[name]=cb} off(name,cb){if(this.handlers[name]===cb)delete this.handlers[name]}
 addControl(){} getSource(id){return this.sources[id]} getLayer(id){return this.layers[id]}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={...s,data:s.data,setData(data){this.data=data}}}
 addLayer(l,before){assert(this.sources[l.source]);assert(!this.layers[l.id]);this.layers[l.id]=l;if(before&&this.order.includes(before))this.order.splice(this.order.indexOf(before),0,l.id);else this.order.push(l.id)}
 hasImage(id){return Boolean(this.images[id])} addImage(id,data){this.images[id]=data}
 moveLayer(id,before){this.order=this.order.filter(x=>x!==id);this.order.splice(this.order.indexOf(before),0,id)}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 getBounds(){return {getWest:()=>80,getEast:()=>100,getSouth:()=>10,getNorth:()=>30}}
 getCanvas(){return {style:{}}} queryRenderedFeatures(p,{layers}){return (this.hits||[]).filter(x=>layers.includes(x.layer.id))}
 easeTo(x){this.moves.push(x)} fitBounds(b,o){this.moves.push({b,o})}
}
class Bounds{constructor(a,b){this.points=[a,b]}extend(p){this.points.push(p);return this}}
const calls=[],ctx=vm.createContext({console:{info(){},error(){},warn(){}},window:{},document:{getElementById:()=>({}),addEventListener(){}},maplibregl:{Map:MapStub,NavigationControl:class{},LngLatBounds:Bounds}});
vm.runInContext(fs.readFileSync('app/resources/map/nav.js','utf8'),ctx);
const run=x=>vm.runInContext(x,ctx);
const payload={active_count:1,selected_event_id:'SQ-001',geojson:{}};
for(const key of ['current','direction','trajectories','impact_zones','surveillance_zones','prediction_points','selection'])payload.geojson[key]={type:'FeatureCollection',features:[]};
payload.geojson.current.features.push({type:'Feature',properties:{event_id:'SQ-001',severity:null,status:'ACTIVE',impact_state:'NONE'},geometry:{type:'Point',coordinates:[91.72,22.12]}});
payload.geojson.selection=payload.geojson.current;ctx.payload=payload;
run('applyEventState(payload);createMap();map.handlers["style.load"]()');
assert.equal(run('map.getSource("squall-current").data.features.length'),1);
assert(run('map.order.indexOf("site-boundary-fill")<map.order.indexOf("track")'));
assert(run('map.order.indexOf("track")<map.order.indexOf("squall-current")'));
run('setLayerVisibility("Squall Alerts",false)');
assert(run('eventLayerIds.every(id=>map.layers[id].layout.visibility==="none")'));
assert.equal(run('latestEventState.active_count'),1);
run('setLayerVisibility("Squall Alerts",true)');assert(run('eventLayerIds.every(id=>map.layers[id].layout.visibility==="visible")'));
run('map.sources={};map.layers={};map.order=[];map.handlers["style.load"]()');
assert.equal(run('map.getSource("squall-current").data.features.length'),1);
ctx.bridgeMock={selectEvent:id=>calls.push(['event',id]),selectSpatialFeature:()=>calls.push(['spatial']),clearEventSelection:()=>calls.push(['clear-event']),clearSpatialFeature:()=>calls.push(['clear-spatial']),reportSpatialView(){}};
run('bridge=bridgeMock;map.hits=[{layer:{id:"site-boundary-fill"},properties:{category:"site-boundary",feature_id:"S"}},{layer:{id:"squall-impact-zones-fill"},properties:{event_id:"SQ-Z"}},{layer:{id:"squall-current"},properties:{event_id:"SQ-001"}}];handleMapClick({point:{}})');
assert.deepEqual(calls.pop(),['event','SQ-001']);
run('map.hits=[];handleMapClick({point:{}})');assert.deepEqual(calls.slice(-2),[['clear-event'],['clear-spatial']]);
run('followEnabled=true;window.navMap.showEvent()');assert.equal(run('followEnabled'),true);assert(run('map.moves.length>0'));
console.log('NAV event JS cache/reload/visibility/priority/Show Event: PASS');

// Phase 4 runs the same real script, with no changes to Phase 3 assertions above.
const maritimePayload={objects:[{object_id:'ais:999000001',category:'vessels'}],selected_object_id:'ais:999000001',visibility:{},geojson:{vessels:{type:'FeatureCollection',features:[{type:'Feature',properties:{object_id:'ais:999000001',category:'vessels',rotation:45,oriented:true,status:'LIVE',name:'TEST'},geometry:{type:'Point',coordinates:[91.7,22.1]}}]}}};
maritimePayload.geojson.selection=maritimePayload.geojson.vessels;ctx.maritimePayload=maritimePayload;
run('applyMaritimeState(maritimePayload)');
assert.equal(run('map.getSource("maritime-vessels").data.features.length'),1);
assert.equal(run('Object.keys(map.images).length'),5);
assert(run('map.order.indexOf("maritime-routes-fill")<map.order.indexOf("track")'));
const cameraCount=run('map.moves.length');
run('applyMaritimeState(maritimePayload)');assert.equal(run('map.moves.length'),cameraCount);
run('setLayerVisibility("AIS Vessels",false)');assert.equal(run('map.getLayer("maritime-vessels-point").layout.visibility'),'none');
assert.equal(run('latestMaritimeState.objects.length'),1);
run('setLayerVisibility("AIS Vessels",true)');assert.equal(run('map.getLayer("maritime-vessels-point").layout.visibility'),'visible');
ctx.bridgeMock.selectMaritimeObject=id=>calls.push(['maritime',id]);ctx.bridgeMock.clearMaritimeSelection=()=>calls.push(['clear-maritime']);
run('map.hits=[{layer:{id:"maritime-vessels-point"},properties:{object_id:"ais:999000001",category:"vessels"}},{layer:{id:"squall-impact-zones-fill"},properties:{event_id:"SQ-001"}}];handleMapClick({point:{}})');
assert.deepEqual(calls.pop(),['maritime','ais:999000001']);
run('map.hits.push({layer:{id:"squall-current"},properties:{event_id:"SQ-001"}});handleMapClick({point:{}})');assert.deepEqual(calls.pop(),['event','SQ-001']);
run('map.hits=[];handleMapClick({point:{}})');assert.deepEqual(calls.slice(-3),[['clear-maritime'],['clear-event'],['clear-spatial']]);
run('map.sources={};map.layers={};map.order=[];map.handlers["style.load"]()');assert.equal(run('map.getSource("maritime-vessels").data.features.length'),1);
run('followEnabled=true;window.navMap.showMaritimeObject()');assert.equal(run('followEnabled'),true);
assert.equal(run('Object.keys(map.sources).filter(id=>id.startsWith("maritime-")).length'),13);
console.log('NAV maritime cache/reload/visibility/priority/no-camera-update: PASS');

ctx.document.createElement=()=>({style:{},addEventListener(){}});
ctx.maplibregl.Marker=class{
 constructor({element}){this.element=element;this.rotation=0}
 setLngLat(point){this.point=point;this.element.style.transform='map-position-transform';return this}
 addTo(){return this} getElement(){return this.element}
 setRotation(deg){this.rotation=deg;return this} getLngLat(){return this.point}
};
run('window.navMap.update({latitude:22,longitude:91,heading:40})');
assert.equal(run('marker.rotation'),40);
assert.equal(run('marker.element.style.transform'),'map-position-transform');
run('window.navMap.update({latitude:23,longitude:92,heading:0})');assert.equal(run('marker.rotation'),0);assert.equal(run('marker.point[0]'),92);
console.log('NAV own-vessel rotation preserves map positioning: PASS');
ctx.bridgeMock.reportMaritimeViewport=(...bounds)=>calls.push(['viewport',...bounds]);
const countBeforeView=calls.length;
run('reportMaritimeView({})');assert.equal(calls.length,countBeforeView); // Automatic own-vessel Follow is ignored.
run('marker=null;reportMaritimeView({})');assert.equal(calls[calls.length-1][0],'viewport');
const beforeInitialView=calls.length;
run('latestMaritimeState=null;map.sources={};map.layers={};map.order=[];map.handlers["style.load"]()');
assert.equal(calls.length,beforeInitialView+1);assert.equal(calls[calls.length-1][0],'viewport');
run('reportMaritimeView({originalEvent:{}})');assert.equal(calls[calls.length-1][0],'viewport');
ctx.maritimePayload.reference_layers={gebco:{kind:'raster',group:'Bathymetry',tiles:['https://example.invalid/wms?bbox={bbox-epsg-3857}'],opacity:.4,attribution:'GEBCO'}};
const beforeRaster=run('map.moves.length');run('applyMaritimeState(maritimePayload)');
assert.equal(run('map.getSource("reference-gebco").type'),'raster');
assert(run('map.order.indexOf("reference-gebco")<map.order.indexOf("track")'));
assert.equal(run('map.moves.length'),beforeRaster);
run('setLayerVisibility("Bathymetry",false)');assert.equal(run('map.getLayer("reference-gebco").layout.visibility'),'none');
assert.equal(run('latestMaritimeState.objects.length'),1);
run('setLayerVisibility("Bathymetry",true)');assert.equal(run('map.getLayer("reference-gebco").layout.visibility'),'visible');
ctx.bridgeMock.reportReferenceError=key=>calls.push(['reference-error',key]);
run('map.handlers.error({sourceId:"reference-gebco",error:"tile failed"})');assert.deepEqual(calls.pop(),['reference-error','gebco']);
assert.notEqual(run('status.textContent'),'Map unavailable');
console.log('NAV real-provider raster/visibility/no-camera/failure isolation: PASS');
run('map.setStyle=function(url){this.styleURL=url;this.sources={};this.layers={};this.order=[];this.images={}}');
ctx.maritimePayload.reference_layers.openwaters={kind:'style',url:'https://example.invalid/style.json'};
const beforeStyle=run('map.moves.length');run('applyMaritimeState(maritimePayload)');
assert.equal(run('ready'),false);assert.equal(run('map.styleURL'),'https://example.invalid/style.json');
run('map.handlers["style.load"]()');
assert.equal(run('ready'),true);assert.equal(run('map.getSource("maritime-vessels").data.features.length'),1);
assert.equal(run('map.moves.length'),beforeStyle);
console.log('NAV optional reference-style reload restores operational sources without camera movement: PASS');

// GL geometry-type expressions return simple types for their Multi* equivalents.
function filterValue(expression,type,properties={}){
 if(!Array.isArray(expression))return expression;
 const [op,...args]=expression;
 if(op==='geometry-type')return {MultiPoint:'Point',MultiLineString:'LineString',MultiPolygon:'Polygon'}[type]||type;
 if(op==='get')return properties[args[0]];
 if(op==='==')return filterValue(args[0],type,properties)===filterValue(args[1],type,properties);
 if(op==='!=')return filterValue(args[0],type,properties)!==filterValue(args[1],type,properties);
 if(op==='all')return args.every(x=>filterValue(x,type,properties));
 throw Error('Unexpected geometry filter operator '+op);
}
for(const type of ['Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon']){
 for(const [layer,simple] of [['maritime-aton-point','Point'],['maritime-subsea-line','LineString'],['maritime-hazards-fill','Polygon']]){
  assert.equal(filterValue(run(`map.getLayer('${layer}').filter`),type),type.replace('Multi','')===simple);
 }
}
const originalAddImage=run('map.addImage');ctx.originalAddImage=originalAddImage;
run('map.images={};map.addImage=()=>{throw Error("unavailable icon")};ensureMaritimeLayers()');
for(const category of ['vessels','offshore','aton','hazards']){
 assert.equal(run(`map.getLayer('maritime-${category}-fallback').type`),'circle');
 assert.equal(run(`map.getLayer('maritime-${category}-fallback').layout.visibility`),'visible');
 assert.equal(run(`map.getLayer('maritime-${category}-fallback').minzoom`),undefined);
}
run('map.addImage=originalAddImage;ensureMaritimeLayers()');
ctx.maritimePayload.reference_layers.openwaters={kind:'overlay',group:'Aids to Navigation',sources:{nautical:{type:'vector',url:'https://example.invalid/tiles.json'}},layers:[{id:'buoys',type:'circle',source:'nautical','source-layer':'buoys',paint:{'circle-radius':3}}]};
const overlayCamera=run('map.moves.length'),overlayStyle=run('map.styleURL');
run('applyMaritimeState(maritimePayload)');
assert.equal(run('map.getSource("reference-openwaters-nautical").type'),'vector');
assert.equal(run('map.getSource("maritime-vessels").data.features.length'),1);
assert.equal(run('map.styleURL'),overlayStyle);assert.equal(run('map.moves.length'),overlayCamera);
run('setLayerVisibility("Aids to Navigation",false)');assert.equal(run('map.getLayer("reference-openwaters-buoys").layout.visibility'),'none');
run('setLayerVisibility("Aids to Navigation",true)');
console.log('NAV six geometry types, missing-icon circles, nautical overlay/no camera jump: PASS');

// An optional stdin payload is produced by the real Python normalizer/store/bridge
// regression. Verify its exact features survive the JS boundary and setData.
if(process.argv.includes('--bridge-payload')){
 const incoming=JSON.parse(fs.readFileSync(0,'utf8'));ctx.bridgePayload=incoming;
 run('applyMaritimeState(bridgePayload)');
 let count=0;
 for(const [category,collection] of Object.entries(incoming.geojson)){
  const actual=run(`map.getSource('maritime-${category}').data`);
  assert.deepEqual(JSON.parse(JSON.stringify(actual)),collection);
  if(category!=='selection')count+=actual.features.length;
 }
 assert.equal(count,incoming.objects.length);
 console.log(`Python bridge to JS maritime setData: PASS count=${count}`);
}
