// Exercise the real NAV script's state cache, click priority and visibility
// with a MapLibre API double; no browser or synthetic production events.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class MapStub{
 constructor(){this.sources={};this.layers={};this.handlers={};this.order=[];this.moves=[]}
 on(name,cb){this.handlers[name]=cb} off(name,cb){if(this.handlers[name]===cb)delete this.handlers[name]}
 addControl(){} getSource(id){return this.sources[id]} getLayer(id){return this.layers[id]}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={data:s.data,setData(data){this.data=data}}}
 addLayer(l){assert(this.sources[l.source]);assert(!this.layers[l.id]);this.layers[l.id]=l;this.order.push(l.id)}
 moveLayer(id,before){this.order=this.order.filter(x=>x!==id);this.order.splice(this.order.indexOf(before),0,id)}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 getBounds(){return {getWest:()=>80,getEast:()=>100,getSouth:()=>10,getNorth:()=>30}}
 getCanvas(){return {style:{}}} queryRenderedFeatures(p,{layers}){return (this.hits||[]).filter(x=>layers.includes(x.layer.id))}
 easeTo(x){this.moves.push(x)} fitBounds(b,o){this.moves.push({b,o})}
}
class Bounds{constructor(a,b){this.points=[a,b]}extend(p){this.points.push(p);return this}}
const calls=[],ctx=vm.createContext({console:{info(){},error(){}},window:{},document:{getElementById:()=>({}),addEventListener(){}},maplibregl:{Map:MapStub,NavigationControl:class{},LngLatBounds:Bounds}});
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
