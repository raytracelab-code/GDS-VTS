// Real Python provider -> canonical service -> MapBridge -> real NAV JavaScript.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class MapStub {
 constructor(){this.sources={};this.layers={};this.order=[];this.handlers={};this.images={};this.moves=[];this.hits=[]}
 on(n,cb){this.handlers[n]=cb} off(){} addControl(){}
 getSource(id){return this.sources[id]} getLayer(id){return this.layers[id]}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={...s,data:s.data,setData(data){this.data=data}}}
 addLayer(l,before){assert(this.sources[l.source]);this.layers[l.id]=l;const i=this.order.indexOf(before);if(i>=0)this.order.splice(i,0,l.id);else this.order.push(l.id)}
 moveLayer(id,before){this.order=this.order.filter(x=>x!==id);const i=this.order.indexOf(before);if(i>=0)this.order.splice(i,0,id);else this.order.push(id)}
 hasImage(id){return !!this.images[id]} addImage(id,d){this.images[id]=d}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 getCanvas(){return {style:{}}}
 queryRenderedFeatures(p,{layers}){return this.hits.filter(f=>layers.includes(f.layer.id))}
 getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}
 easeTo(p){this.moves.push(p)} fitBounds(b,o){this.moves.push({b,o})}
 getZoom(){return 11}
}
class Bounds{constructor(a,b){this.points=[a,b]}extend(p){this.points.push(p);return this}}
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
const calls=[];
const ctx=vm.createContext({payload,console,window:{},document:{getElementById:()=>({}),addEventListener(){}},maplibregl:{Map:MapStub,NavigationControl:class{},LngLatBounds:Bounds},bridgeMock:{selectMaritimeObject:id=>calls.push(['maritime',id]),selectSpatialFeature:()=>calls.push(['spatial']),selectEvent:id=>calls.push(['event',id]),clearMaritimeSelection(){},clearEventSelection(){},clearSpatialFeature(){},reportSpatialView(){},reportMaritimeViewport(){}}});
const run=s=>vm.runInContext(s,ctx);
run(fs.readFileSync('app/resources/map/nav.js','utf8'));
run('applyMaritimeState(payload);createMap();bridge=bridgeMock;map.handlers["style.load"]()');
const gisSources=()=>run('Object.keys(map.sources).filter(k=>k.startsWith("gis-"))');
assert.equal(gisSources().length,payload.gis_layers.length);
for(const key of ['malaysia_platform','malaysia_pipeline','malaysia_fields_all']){
 assert(run(`map.getSource('gis-${key}').data.features.length>0`));
 assert(run(`map.order.indexOf('gis-${key}-point')<map.order.indexOf('site-boundary-fill')`));
}
assert.equal(run("map.getLayer('gis-malaysia_well_location-point').layout.visibility"),'none');
assert.equal(run("map.getLayer('gis-malaysia_well_location-point').minzoom"),11);
assert.equal(run("map.getLayer('gis-malaysia_well_location-label').minzoom"),14);
assert(run("map.getLayer('gis-malaysia_platform-point').type==='symbol'"));
assert(run("map.getLayer('gis-malaysia_platform-point').layout['text-optional']===true"));
assert(run("map.getLayer('gis-malaysia_platform-point').layout['icon-allow-overlap']===false"));
// Fill opacity may now be a zoom expression; retain the original readability
// requirement at every operational zoom instead of comparing an array to .1.
function atZoom(value,zoom){
 if(!Array.isArray(value))return value;
 assert.equal(value[0],'interpolate');assert.equal(value[1][0],'linear');assert.equal(value[2][0],'zoom');
 const stops=value.slice(3);
 if(zoom<=stops[0])return stops[1];
 for(let i=2;i<stops.length;i+=2){if(zoom<=stops[i])return stops[i-1]+(stops[i+1]-stops[i-1])*(zoom-stops[i-2])/(stops[i]-stops[i-2]);}
 return stops[stops.length-1];
}
const fieldOpacity=run("map.getLayer('gis-malaysia_fields_all-fill').paint['fill-opacity']");
for(let z=0;z<=20;z+=.5)assert(atZoom(fieldOpacity,z)>=0&&atZoom(fieldOpacity,z)<.1);
assert.equal(run("map.getSource('gis-malaysia_well_location').cluster"),true);
// A late GEBCO response must never overpaint already installed customer GIS.
run("payload.reference_layers={gebco:{kind:'raster',tiles:['https://example.invalid/{z}/{x}/{y}'],opacity:.8,group:'Bathymetry'}};applyMaritimeState(payload)");
assert(run("map.order.indexOf('reference-gebco')<map.order.indexOf('gis-malaysia_basin-fill')"));
const sourceCount=run('Object.keys(map.sources).length'),layerCount=run('Object.keys(map.layers).length');
run('applyMaritimeState(payload);applyMaritimeState(payload)');
assert.equal(run('Object.keys(map.sources).length'),sourceCount);
assert.equal(run('Object.keys(map.layers).length'),layerCount);
run("setLayerVisibility('Malaysia Platforms',false)");
assert.equal(run("map.getLayer('gis-malaysia_platform-point').layout.visibility"),'none');
run("setLayerVisibility('Malaysia Platforms',true)");
assert.equal(run("map.getLayer('gis-malaysia_platform-point').layout.visibility"),'visible');
const platform=payload.geojson.malaysia_platform.features[0];ctx.platform=platform;
run("map.hits=[{...platform,layer:{id:'gis-malaysia_platform-point'}},{layer:{id:'site-boundary-fill'},properties:{category:'site-boundary',feature_id:'S'}}];handleMapClick({point:{}})");
assert.deepEqual(calls.pop(),['maritime',platform.properties.object_id]);
const field=payload.geojson.malaysia_fields_all.features[0];ctx.field=field;
run("map.hits=[{...field,layer:{id:'gis-malaysia_fields_all-fill'}},{layer:{id:'site-boundary-fill'},properties:{category:'site-boundary',feature_id:'S'}}];handleMapClick({point:{}})");
assert.deepEqual(calls.pop(),['spatial']);
// Aggregates must remain reachable above reference field polygons.
run("map.hits=[{...field,layer:{id:'gis-malaysia_fields_all-fill'}},{layer:{id:'gis-malaysia_well_location-clusters'},properties:{cluster_id:1,point_count:25},geometry:{type:'Point',coordinates:[104,5]}}];handleMapClick({point:{}})");
assert.deepEqual(JSON.parse(run('JSON.stringify(map.moves[map.moves.length-1])')),{center:[104,5],zoom:13});
run("map.hits=[{...platform,layer:{id:'gis-malaysia_platform-point'}},{layer:{id:'squall-current'},properties:{event_id:'SQ'}}];handleMapClick({point:{}})");
assert.deepEqual(calls.pop(),['event','SQ']);
run("payload.selected_object_id=platform.properties.object_id;payload.geojson.selection={type:'FeatureCollection',features:[platform]};applyMaritimeState(payload);followEnabled=false;window.navMap.showMaritimeObject()");
assert.equal(run('followEnabled'),false);assert(run('map.moves.length>0'));
run("window.navMap.command('FIT MALAYSIA GIS')");assert.equal(run('followEnabled'),false);
run('map.sources={};map.layers={};map.order=[];map.handlers["style.load"]()');
assert.equal(gisSources().length,payload.gis_layers.length);
assert(run("map.getSource('gis-malaysia_platform').data.features.length>0"));
console.log('Malaysia GIS MapLibre payload, sources, defaults, zoom, ordering, selection and style reload: PASS');
