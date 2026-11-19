// NAV truthfulness in the real nav.js: honest own-vessel marker, freshness
// styling and online-basemap retry/recovery. Map/DOM are minimal doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
class ClassList{constructor(){this.set=new Set()}toggle(n,on){on?this.set.add(n):this.set.delete(n)}contains(n){return this.set.has(n)}}
class Element{constructor(){this.style={};this.classList=new ClassList();this.innerHTML=''}addEventListener(){}}
class MapStub{
 constructor(options){this.options=options;this.sources={};this.layers={};this.order=[];this.handlers={};this.images={}}
 on(n,cb){this.handlers[n]=cb}off(){}addControl(){}
 getSource(id){return this.sources[id]}getLayer(id){return this.layers[id]}
 getStyle(){return {layers:this.order.map(id=>this.layers[id]),sources:this.sources}}
 addSource(id,s){this.sources[id]={...s,setData(d){this.data=d}}}
 addLayer(l){this.layers[l.id]=JSON.parse(JSON.stringify(l));this.order.push(l.id)}
 moveLayer(){}removeLayer(id){delete this.layers[id]}
 setPaintProperty(id,k,v){this.layers[id].paint={...this.layers[id].paint,[k]:v}}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 hasImage(id){return !!this.images[id]}addImage(id,image){this.images[id]=image}
 getCanvas(){return {style:{}}}getCenter(){return {lng:104,lat:5}}getZoom(){return 10}
 getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}
 easeTo(){}fitBounds(){}
}
class Marker{constructor({element}){this.element=element;this.rotation=null}setLngLat(p){this.point=p;return this}addTo(){return this}setRotation(d){this.rotation=d;return this}getElement(){return this.element}getLngLat(){return this.point}}
const style={version:8,sources:{omt:{type:'vector',url:'https://example.test/tiles.json'}},layers:[{id:'water',source:'omt','source-layer':'water',type:'fill',paint:{'fill-color':'#cddfe3'}}]};

function context(fetchImpl,timers,interactions){
 const status={style:{},textContent:''};
 const ctx=vm.createContext({console:{info(){},warn(){},error(){},log(){}},payload,
  window:{setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length},location:{reload(){interactions.push('reload')}}},
  AbortController,setTimeout,clearTimeout,fetch:fetchImpl,
  document:{getElementById:()=>status,createElement:()=>new Element(),documentElement:{style:{setProperty(){}}},addEventListener(){},body:{classList:new ClassList()}},
  maplibregl:{Map:MapStub,NavigationControl:class{},Marker}});
 const run=s=>vm.runInContext(s,ctx);
 for(const file of ['offline.js','nav.js'])run(fs.readFileSync('app/resources/map/'+file,'utf8'));
 run('offlineConfig=payload.config');
 // Renderer-health messages (renderer-*) are covered by nav_renderer_runtime.cjs.
 ctx.bridge={mapInteraction:n=>{if(!n.startsWith('renderer-'))interactions.push(n)},reportMapStatus(){}};
 run('bridge=globalThis.bridge');
 return {run,status};
}

(async()=>{
 // 1. Startup without internet: local shell, honest status, retry scheduled with backoff.
 {
  let online=false;const timers=[],interactions=[];
  const {run,status}=context(async()=>{if(!online)throw Error('No Internet');return {ok:true,json:async()=>JSON.parse(JSON.stringify(style))}},timers,interactions);
  await run('startMap()');run('map.handlers["style.load"]()');
  assert.equal(run('onlineUnavailable'),true);
  assert.deepEqual(interactions,['online-unavailable']);
  assert.equal(timers.length,1);assert.equal(timers[0].ms,10000);
  assert(/UNAVAILABLE/.test(status.textContent)&&/RETRYING/.test(status.textContent),status.textContent);
  // Still offline at the first retry: backoff doubles, capped at 5 minutes.
  await timers[0].fn();assert.equal(timers.length,2);assert.equal(timers[1].ms,20000);
  for(let i=1;i<8;i++)await timers[i].fn();
  assert.equal(timers[timers.length-1].ms,300000,'backoff is capped at 5 minutes');
  // Network returns: the never-loaded online style triggers a map-surface restart (no app restart).
  online=true;await timers[timers.length-1].fn();
  assert.deepEqual(interactions,['online-unavailable','online-available']);
  assert.equal(run('onlineRetryDelay'),10000,'backoff resets after recovery');
 }
 // 2. Online style loaded, tiles fail later: probe clears the latched UNAVAILABLE flag in place.
 {
  let online=true;const timers=[],interactions=[];
  const {run,status}=context(async()=>{if(!online)throw Error('No Internet');return {ok:true,json:async()=>JSON.parse(JSON.stringify(style))}},timers,interactions);
  await run('startMap()');run('map.handlers["style.load"]()');
  assert.equal(run('onlineUnavailable'),false);
  online=false;run('map.handlers.error({sourceId:"omt",error:Error("tile failed")})');
  assert.equal(run('onlineUnavailable'),true);assert.equal(timers.length,1);
  online=true;await timers[0].fn();
  assert.equal(run('onlineUnavailable'),false);assert.equal(status.textContent,'MAP / ONLINE / READY');
  assert(!interactions.includes('online-available'),'a loaded style recovers without reloading the page');
 }
 // 3. Offline-region fallback probes the online style and asks Python to switch back.
 {
  const timers=[],interactions=[];
  const {run}=context(async()=>({ok:true,json:async()=>JSON.parse(JSON.stringify(style))}),timers,interactions);
  run("offlineConfig={...payload.config,preferred_source:'offline',online_style_url:undefined,online_probe_url:'https://tiles.openfreemap.org/styles/liberty'}");
  await run('startMap()');
  assert.equal(timers.length,1);await timers[0].fn();
  assert.deepEqual(interactions,['online-available']);
 }
 // 4. Honest marker: missing heading is neutral (never 000), 0 is a real heading, stale is dimmed.
 {
  const timers=[],interactions=[];
  const {run}=context(async()=>({ok:true,json:async()=>JSON.parse(JSON.stringify(style))}),timers,interactions);
  await run('startMap()');run('map.handlers["style.load"]()');
  run("window.navMap.update({latitude:5,longitude:104,heading:null,heading_source:null,freshness:'LIVE'})");
  assert(run("marker.getElement().classList.contains('heading-unknown')"),'unknown heading uses the neutral marker');
  assert(run("marker.getElement().innerHTML.includes('HDG UNKNOWN')"));
  run("window.navMap.update({latitude:5,longitude:104,heading:0,heading_source:'HDG',freshness:'LIVE'})");
  assert.equal(run("marker.getElement().classList.contains('heading-unknown')"),false);
  assert.equal(run('marker.rotation'),0);
  run("window.navMap.update({latitude:5,longitude:104,heading:271.5,heading_source:'HDG',freshness:'LIVE'})");
  assert.equal(run('marker.rotation'),271.5);
  run("window.navMap.setFreshness('STALE')");
  assert(run("marker.getElement().classList.contains('stale')"));
  run("window.navMap.setFreshness('NO DATA')");
  assert(run("marker.getElement().classList.contains('no-data')")&&!run("marker.getElement().classList.contains('stale')"));
  run("window.navMap.setFreshness('LIVE')");
  assert(!run("marker.getElement().classList.contains('no-data')")&&!run("marker.getElement().classList.contains('stale')"));
 }
 console.log('NAV offline retry/backoff/recovery, fallback probe, honest heading and freshness marker: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
