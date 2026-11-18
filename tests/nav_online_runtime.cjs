// Real NAV and palette scripts together, with an identity-preserving map double.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
class MapStub{
 constructor(options){this.options=options;this.sources={};this.layers={};this.order=[];this.handlers={};this.images={};this.writes=0;this.moves=0;for(const [id,spec] of Object.entries(options.style.sources||{}))this.addSource(id,spec);for(const layer of options.style.layers||[])this.addLayer(layer)}
 on(n,cb){this.handlers[n]=cb}off(){}addControl(){}
 getSource(id){return this.sources[id]}getLayer(id){return this.layers[id]}
 getStyle(){return {layers:this.order.map(id=>this.layers[id]),sources:this.sources}}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={...s,setData(d){this.data=d}}}
 addLayer(l,before){assert(!l.source||this.sources[l.source]);assert(!this.layers[l.id]);this.layers[l.id]=JSON.parse(JSON.stringify(l));const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,l.id)}
 moveLayer(id,before){this.moves++;this.order=this.order.filter(x=>x!==id);const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,id)}
 removeLayer(id){delete this.layers[id];this.order=this.order.filter(x=>x!==id)}
 setPaintProperty(id,k,v){this.writes++;this.layers[id].paint[k]=v}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 hasImage(id){return !!this.images[id]}addImage(id,image){this.images[id]=image}
 getCanvas(){return {style:{}}}getCenter(){return {lng:104,lat:5}}getZoom(){return 10}
 getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}
 setStyle(){throw Error('Unexpected style reload')}easeTo(){throw Error('Unexpected camera change')}fitBounds(){throw Error('Unexpected camera change')}
}

(async()=>{
for(const outcome of ['success','failure','invalid','timeout']){
 const warnings=[];
 const context=vm.createContext({console:{info(){},warn(...s){warnings.push(s)},error(){}},payload,
 window:{},AbortController,setTimeout:outcome==='timeout'?(fn)=>setTimeout(fn,0):setTimeout,clearTimeout,
 fetch:async(url,{signal})=>{
  assert.equal(url,'https://tiles.openfreemap.org/styles/liberty');
  if(outcome==='failure')throw Error('No Internet');
  if(outcome==='timeout')return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('timeout'))));
  return {ok:true,json:async()=>outcome==='invalid'?{}:{version:8,sources:{openmaptiles:{type:'vector',url:'https://example.test/tiles.json'},ne2:{type:'raster',tiles:['https://example.test/{z}/{x}/{y}.png']}},layers:[
   {id:'natural-earth',source:'ne2',type:'raster',paint:{'raster-opacity':1}},
   {id:'water',source:'openmaptiles','source-layer':'water',type:'fill',paint:{'fill-color':'#cddfe3'}},
   {id:'poi',source:'openmaptiles','source-layer':'poi',type:'symbol',paint:{'text-color':'#222222'}}]}};
 },document:{getElementById:()=>({style:{}}),documentElement:{style:{setProperty(){}}},addEventListener(){}},
 GdsRegions:{attach(){throw Error('Online NAV scanned regions')}},maplibregl:{Map:MapStub,NavigationControl:class{}}});
 const run=s=>vm.runInContext(s,context);
 for(const file of ['offline.js','nav.js'])run(fs.readFileSync('app/resources/map/'+file,'utf8'));
 run('offlineConfig=payload.config;applyMaritimeState(payload.maritime)');
 await run('startMap()');run('map.handlers["style.load"]()');
 assert(run('ready'));
 assert(run("!!map.getLayer('gis-malaysia_platform-point')"));
 assert.equal(run("map.getLayer('gis-malaysia_platform-point').layout['text-font'][0]"),'Noto Sans Regular');
 assert(run("!!map.getSource('track')&&!!map.getSource('maritime-vessels')&&!!map.getSource('squall-trajectories')"));
 const before=run('map.getSource("gis-malaysia_pipeline")');
 for(const effective_state of ['DAY','TWILIGHT','NIGHT'])run(`applyPalette({effective_state:'${effective_state}'})`);
 assert.equal(run('map.getSource("gis-malaysia_pipeline")'),before);
 assert(run('map.getLayer("gis-malaysia_pipeline-line-glow").paint["line-opacity"]>0'));
 assert.equal(run('offlineCoverageAt({lng:-75,lat:40})'),null);
 if(outcome==='success'){
  assert.equal(run('onlineUnavailable'),false);
  assert.equal(run('map.getLayer("poi").layout.visibility'),'none');
  assert.equal(run('map.getLayer("water").paint["fill-color"]'),'#101f29');
  assert.equal(run('map.getLayer("natural-earth").paint["raster-brightness-max"]'),.32);
 }else assert.equal(run('onlineUnavailable'),true);
 for(let i=0;i<20;i++)run('map.handlers.error({sourceId:"openmaptiles",error:Error("unavailable")})');
 assert(warnings.length<=1,'Errors must not spam logs');
 for(let i=0;i<20;i++)run('map.handlers.error({sourceId:"reference-gebco",error:Error("unavailable")})');
 assert(warnings.length<=2,'Reference failures must not spam logs');
 assert(run('ready&&!!map.getSource("gis-malaysia_pipeline")'));
}
console.log('Online success / safe failure / timeout / real Malaysia GIS / palette / night glow / no scan: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
