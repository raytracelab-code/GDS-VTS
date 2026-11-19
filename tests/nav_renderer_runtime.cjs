// GDS-AUDIT-019 in the real nav.js: WebGL start failure, context loss and a drawn style are reported.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{constructor(){this.style={};this.classList={toggle(){},add(){},remove(){},contains(){return false}};this.innerHTML=''}addEventListener(){}}
function context(MapImpl){
 const sent=[],status={style:{},textContent:''};
 const ctx=vm.createContext({console:{info(){},warn(){},error(){},log(){}},window:{setTimeout(){},location:{reload(){}}},
  AbortController,setTimeout,clearTimeout,fetch:async()=>{throw Error('offline')},
  document:{getElementById:()=>status,createElement:()=>new Element(),documentElement:{style:{setProperty(){}}},addEventListener(){},body:{classList:{toggle(){},add(){},remove(){}}}},
  maplibregl:{Map:MapImpl,NavigationControl:class{},Marker:class{setLngLat(){return this}addTo(){return this}setRotation(){return this}getElement(){return new Element()}}}});
 const run=s=>vm.runInContext(s,ctx);
 for(const file of ['offline.js','nav.js'])run(fs.readFileSync('app/resources/map/'+file,'utf8'));
 run("offlineConfig={preferred_source:'local',installed:false,allow_online_fallback:false,status:'MAP / LOCAL',style:{version:8,sources:{},layers:[]}}");
 ctx.bridge={mapInteraction:n=>sent.push(n),reportMapStatus(){}};run('bridge=globalThis.bridge');
 return {run,sent,status};
}
// 1. WebGL cannot start: constructor throws -> renderer-webgl-unavailable, honest status, no crash.
{
 const {run,sent,status}=context(class{constructor(){throw Error('Failed to initialize WebGL')}});
 run('createMap()');
 assert.deepEqual(sent,['renderer-webgl-unavailable']);assert.equal(status.textContent,'Map unavailable');assert.equal(run('map'),null);
}
// 2. Map starts, style draws -> renderer-ok; later the WebGL context is lost -> renderer-webgl-lost.
{
 const listeners={};
 class MapStub{constructor(){this.handlers={};this.sources={};this.layers={}}on(n,cb){this.handlers[n]=cb}off(){}addControl(){}
  getCanvas(){return {style:{},addEventListener:(n,cb)=>{listeners[n]=cb}}}getSource(id){return this.sources[id]}getLayer(id){return this.layers[id]}
  addSource(id,s){this.sources[id]={...s,setData(){}}}addLayer(l){this.layers[l.id]=l}moveLayer(){}setLayoutProperty(){}setPaintProperty(){}
  getStyle(){return {layers:[],sources:{}}}hasImage(){return false}addImage(){}getCenter(){return {lng:104,lat:5}}getZoom(){return 6}
  getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}easeTo(){}fitBounds(){}}
 const {run,sent}=context(MapStub);
 run('createMap()');assert(listeners.webglcontextlost,'context-loss listener installed');
 try{run('map.handlers["style.load"]()')}catch(error){/* later overlay setup may need more doubles; the report comes first */}
 assert.equal(sent[0],'renderer-ok');
 listeners.webglcontextlost();assert.equal(sent[sent.length-1],'renderer-webgl-lost');
}
console.log('renderer runtime ok');
