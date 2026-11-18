// Real NAV, palette and satellite modules; public service responses are simulated.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const payload=JSON.parse(fs.readFileSync(0,'utf8')),scenario=process.argv[2];
const timers=new Map(),requests=[],events=[],warnings=[],camera={lng:104,lat:5.5,zoom:8,bearing:23,pitch:55};
let timerId=0,clock=100000,outcomes=[],pendingResolve=null;
class MapStub{
 constructor(options){this.sources={};this.layers={};this.order=[];this.handlers={};this.images={};this.cameraMoves=0;
  for(const [id,spec] of Object.entries(options.style.sources||{}))this.addSource(id,spec);
  for(const layer of options.style.layers||[])this.addLayer(layer)}
 on(event,callback){(this.handlers[event]??=[]).push(callback)}off(){}addControl(){}
 fire(event,data){for(const callback of this.handlers[event]||[])callback(data)}
 getSource(id){return this.sources[id]}getLayer(id){return this.layers[id]}
 getStyle(){return {layers:this.order.map(id=>this.layers[id]),sources:this.sources}}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={...s,setData(d){this.data=d}}}
 removeSource(id){assert(!this.order.some(key=>this.layers[key].source===id));delete this.sources[id]}
 addLayer(l,before){assert(!l.source||this.sources[l.source]);assert(!this.layers[l.id]);this.layers[l.id]=JSON.parse(JSON.stringify(l));const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,l.id)}
 moveLayer(id,before){this.order=this.order.filter(x=>x!==id);const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,id)}
 removeLayer(id){delete this.layers[id];this.order=this.order.filter(x=>x!==id)}
 setPaintProperty(id,k,v){this.layers[id].paint[k]=v}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 hasImage(id){return !!this.images[id]}addImage(id,image){this.images[id]=image}
 getCanvas(){return {style:{}}}getCenter(){return {lng:camera.lng,lat:camera.lat}}getZoom(){return camera.zoom}
 getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}
 setStyle(){throw Error('Unexpected style reload')}easeTo(){this.cameraMoves++}fitBounds(){this.cameraMoves++}
}
const status={style:{}},body={classList:{toggle(){}}};
const context=vm.createContext({payload,AbortController,Date:class extends Date{static now(){return clock}},
 setTimeout:(fn,delay)=>{timers.set(++timerId,{fn,delay});return timerId},clearTimeout:id=>timers.delete(id),
 console:{info(){},warn(...args){warnings.push(args)},error(...args){throw Error(args.join(' '))}},
 window:{},document:{body,getElementById:()=>status,documentElement:{style:{setProperty(){}}},addEventListener(){}},
 externalBridge:{getSatelliteMapConfig:callback=>callback(payload.satellite),reportBasemapState:(...args)=>events.push(args),reportMapStatus(){},reportMapCenter(){}},
 maplibregl:{Map:MapStub,NavigationControl:class{}},
 fetch:async(url,{signal}={})=>{
  requests.push(url);
  if(url==='https://tiles.openfreemap.org/styles/liberty')return {ok:true,json:async()=>({version:8,sources:{openmaptiles:{type:'vector'}},layers:[
   {id:'water',type:'fill',source:'openmaptiles','source-layer':'water',paint:{'fill-color':'#cddfe3'}},
   {id:'label_city',type:'symbol',source:'openmaptiles','source-layer':'place',paint:{'text-color':'#333333'}},
   {id:'poi',type:'symbol',source:'openmaptiles',layout:{visibility:'none'},paint:{'text-color':'#333333'}}]})};
  const outcome=outcomes.shift()||'valid';
  if(outcome==='network')throw Error('network offline');
  if(outcome==='pending')await new Promise(resolve=>{pendingResolve=resolve});
  if(signal?.aborted)throw Error('aborted');
  return {ok:!['404','403','500'].includes(outcome),status:Number(outcome)||200,
   headers:{get:()=> 'image/jpeg'},blob:async()=>({blank:outcome==='blank'})};
 },createImageBitmap:async blob=>({...blob,close(){}}),
 OffscreenCanvas:class{getContext(){let image;return {drawImage(b){image=b},getImageData(){return {data:Uint8ClampedArray.from(image.blank?[0,0,0,255]:[12,32,45,255])}}}}}});
const run=code=>vm.runInContext(code,context),flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};
async function chooseSatellite(){run('window.navMap.command("SATELLITE")');await flush()}
function loaded(){run('map.fire("sourcedata",{sourceId:"nasa-gibs-satellite",tile:{state:"loaded"},isSourceLoaded:false})')}
function marine(){run('window.navMap.command("MARINE")')}
function snapshot(){return run('basemapModes.snapshot')}
function failTile(){run('map.fire("error",{sourceId:"nasa-gibs-satellite",error:Error("404 missing tile")})')}
function retained(before){
 for(const [id,source] of Object.entries(before.sources))assert.strictEqual(run(`map.getSource(${JSON.stringify(id)})`),source,id);
 assert.equal(JSON.stringify(camera),before.camera);assert.equal(run('map.cameraMoves'),0);
 assert.equal(run('latestSelection.feature_id'),'selected-project');assert.equal(run('followEnabled'),true);
 assert.equal(run("map.getLayer('gis-malaysia_well_location-point').layout.visibility"),'none');
}
(async()=>{
 for(const file of ['offline.js','satellite.js','nav.js'])run(fs.readFileSync('app/resources/map/'+file,'utf8'));
 run('bridge=externalBridge;offlineConfig=payload.config;applyMaritimeState(payload.maritime)');
 await run('startMap()');run('map.fire("style.load");applyPalette({effective_state:"DAY"});followEnabled=true;latestSelection={feature_id:"selected-project"}');
 const before={sources:{...run('map.sources')},camera:JSON.stringify(camera)};
 assert.equal(snapshot().mode,'MARINE');assert.equal(requests.length,1,'Marine must not preload NASA requests');
 assert(!run('map.getSource("nasa-gibs-satellite")'));
 if(scenario==='switch'){
  await chooseSatellite();assert.equal(snapshot().state,'LOADING');
  assert.equal(run("map.getLayer('water').layout?.visibility||'visible'"),'visible','Marine remains during loading');loaded();
  assert.equal(snapshot().mode,'SATELLITE');assert.equal(snapshot().state,'READY');retained(before);
  const source=run('map.getSource("nasa-gibs-satellite")');
  for(const id of ['gis-malaysia_platform-point','gis-malaysia_pipeline-line','maritime-vessels-point','squall-current','track','heading-vector','spatial-selection-outline'])
   assert(run(`map.order.indexOf('nasa-gibs-satellite-raster')<map.order.indexOf('${id}')`),id);
  const brightness=[];
  for(const state of ['DAY','TWILIGHT','NIGHT']){run(`applyPalette({effective_state:'${state}'})`);brightness.push(run("map.getLayer('nasa-gibs-satellite-raster').paint['raster-brightness-max']"));assert.strictEqual(run('map.getSource("nasa-gibs-satellite")'),source)}
  assert(brightness[0]>brightness[1]&&brightness[1]>brightness[2]);
  assert(run("map.getLayer('gis-malaysia_pipeline-line-glow').paint['line-opacity']>0"));
  for(let i=0;i<5;i++){
   marine();assert.equal(run("map.getLayer('water').layout.visibility"),'visible');assert.equal(run("map.getLayer('poi').layout.visibility"),'none');
   await chooseSatellite();assert.strictEqual(run('map.getSource("nasa-gibs-satellite")'),source);retained(before);
  }
  assert.equal(requests.filter(url=>url.includes('gibs.earthdata')).length,1,'Reuse pinned date and hidden source');
 }else if(scenario==='dates'){
  outcomes=['404','blank','valid'];await chooseSatellite();loaded();
  assert.equal(snapshot().date,'2026-11-07');assert.equal(snapshot().attempted_dates.length,3);
  assert(run('map.getSource("nasa-gibs-satellite").tiles[0]').includes('/2026-11-07/'));
 }else if(scenario==='unavailable'){
  outcomes=['404','blank','404','blank'];await chooseSatellite();assert.equal(snapshot().mode,'MARINE');assert.equal(snapshot().state,'ERROR');
  assert.equal(snapshot().attempted_dates.length,4);assert(!run('map.getSource("nasa-gibs-satellite")'));
  const count=requests.length;await chooseSatellite();assert.equal(requests.length,count,'Back off after bounded failure');retained(before);
 }else if(scenario==='tile-error'){
  await chooseSatellite();loaded();for(let i=0;i<20;i++)failTile();
  assert.equal(snapshot().mode,'MARINE');assert.equal(snapshot().state,'ERROR');assert(!run('map.getSource("nasa-gibs-satellite")'));retained(before);
  assert.equal(events.filter(e=>e[1]==='ERROR').length,1,'No error notification flood');
 }else if(scenario==='timeout'){
  await chooseSatellite();const watchdog=[...timers.values()].find(t=>t.delay===30000);assert(watchdog);watchdog.fn();
  assert.equal(snapshot().mode,'MARINE');retained(before);
 }else if(scenario==='cancel'){
  outcomes=['pending'];run('window.navMap.command("SATELLITE")');await flush();assert(pendingResolve);marine();pendingResolve();await flush();
  assert.equal(snapshot().mode,'MARINE');assert(!run('map.getSource("nasa-gibs-satellite")'));retained(before);
 }else if(scenario==='network'){
  outcomes=['network'];await chooseSatellite();assert.equal(snapshot().state,'ERROR');assert.equal(requests.length,2);retained(before);
  clock+=30001;await chooseSatellite();loaded();assert.equal(snapshot().mode,'SATELLITE');retained(before);
 }else if(scenario==='probe'){
  assert.equal(run("GdsSatellite.probeURL('/{z}/{y}/{x}.jpeg',{lng:0,lat:0},2,9)"),'/2/2/2.jpeg');
  outcomes=['403'];await chooseSatellite();assert.equal(snapshot().state,'ERROR');retained(before);
 }else if(['hybrid','gebco-error','both-error','bathy-toggle'].includes(scenario)){
  await chooseSatellite();loaded();
  const sea='hybrid-marine-sea-water',bathy='gebco-hybrid-bathymetry';
  assert.equal(run(`map.getLayer('${sea}')['source-layer']`),'water');
  const seaColors=[],relief=[];
  for(const state of ['DAY','TWILIGHT','NIGHT']){
   run(`applyPalette({effective_state:'${state}'})`);
   for(const [lower,upper] of [['nasa-gibs-satellite-raster',sea],[sea,bathy],[bathy,'hybrid-reference-label_city'],['hybrid-reference-label_city','gis-malaysia_fields_all-boundary']])
    assert(run(`map.order.indexOf('${lower}')<map.order.indexOf('${upper}')`),`${lower} below ${upper}`);
   seaColors.push(run(`map.getLayer('${sea}').paint['fill-color']`));
   relief.push(run(`map.getLayer('${bathy}').paint['raster-opacity']`));
   retained(before);
  }
  assert.equal(new Set(seaColors).size,3);assert(relief[0]>relief[1]&&relief[1]>relief[2]);
  assert(snapshot().depth_contours.includes('NOT AVAILABLE'));
  if(scenario==='gebco-error'||scenario==='both-error'){
   for(let i=0;i<10;i++)run(`map.fire('error',{sourceId:'${bathy}',error:Error('GEBCO offline')})`);
   assert.equal(snapshot().mode,'SATELLITE');assert.equal(snapshot().bathymetry,'UNAVAILABLE');
   assert(!run(`map.getSource('${bathy}')`));
   if(scenario==='both-error'){failTile();assert.equal(snapshot().mode,'MARINE')}
  }else if(scenario==='bathy-toggle'){
   run(`map.fire('sourcedata',{sourceId:'${bathy}',tile:{state:'loaded'}})`);
   const src=run(`map.getSource('${bathy}')`);
   run("setLayerVisibility('Bathymetry',false)");assert.equal(snapshot().bathymetry,'OFF');
   assert.equal(run(`map.getLayer('${bathy}').layout.visibility`),'none');
   run("setLayerVisibility('Bathymetry',true)");assert.strictEqual(run(`map.getSource('${bathy}')`),src);
   assert.equal(snapshot().bathymetry,'READY');
  }
  marine();assert.equal(run(`map.getLayer('${sea}').layout.visibility`),'none');retained(before);
 }else throw Error('Unknown scenario');
 marine();assert.equal(warnings.length,0,'NASA errors stay controlled');
 console.log(scenario+': PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
