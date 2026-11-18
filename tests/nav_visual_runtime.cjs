// Real NAV and palette scripts together, with an identity-preserving map double.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
class MapStub{
 constructor(){this.sources={};this.layers={};this.order=[];this.handlers={};this.images={};this.writes=0;this.moves=0}
 on(n,cb){this.handlers[n]=cb}off(){}addControl(){}
 getSource(id){return this.sources[id]}getLayer(id){return this.layers[id]}
 getStyle(){return {layers:this.order.map(id=>this.layers[id]),sources:this.sources}}
 addSource(id,s){assert(!this.sources[id]);this.sources[id]={...s,setData(d){this.data=d}}}
 addLayer(l,before){assert(this.sources[l.source]);assert(!this.layers[l.id]);this.layers[l.id]=JSON.parse(JSON.stringify(l));const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,l.id)}
 moveLayer(id,before){this.moves++;this.order=this.order.filter(x=>x!==id);const i=this.order.indexOf(before);this.order.splice(i<0?this.order.length:i,0,id)}
 removeLayer(id){delete this.layers[id];this.order=this.order.filter(x=>x!==id)}
 setPaintProperty(id,k,v){this.writes++;this.layers[id].paint[k]=v}
 setLayoutProperty(id,k,v){this.layers[id].layout={...this.layers[id].layout,[k]:v}}
 hasImage(id){return !!this.images[id]}addImage(id,image){this.images[id]=image}
 getCanvas(){return {style:{}}}getCenter(){return {lng:104,lat:5}}getZoom(){return 10}
 getBounds(){return {getWest:()=>103,getSouth:()=>4,getEast:()=>105,getNorth:()=>8}}
 setStyle(){throw Error('Unexpected style reload')}easeTo(){throw Error('Unexpected camera change')}fitBounds(){throw Error('Unexpected camera change')}
}
const context=vm.createContext({console:{info(){},warn(){},error(){}},payload,window:{},document:{getElementById:()=>({style:{}}),documentElement:{style:{setProperty(){}}},addEventListener(){}},maplibregl:{Map:MapStub,NavigationControl:class{}}});
const run=s=>vm.runInContext(s,context);
for(const file of ['offline.js','nav.js'])run(fs.readFileSync('app/resources/map/'+file,'utf8'));
run('applyMaritimeState(payload);createMap();map.handlers["style.load"]();applyPalette({effective_state:"DAY"})');
const layer=id=>run(`map.getLayer('${id}')`),core='gis-malaysia_pipeline-line';
const scenario=process.argv[2];
if(scenario==='glow'){
 for(const id of [core,'heading-vector','cog-vector','track','site-boundary-outline','maritime-routes-line','spatial-selection-outline','squall-trajectories','squall-impact-zones-outline','squall-surveillance-zones-outline','gis-malaysia_fields_all-boundary','gis-malaysia_production_within_psc_area-boundary']){
  const glow=layer(id+'-glow');assert(glow,id);assert.equal(glow.source,layer(id).source);assert(glow.paint['line-blur']>0);assert.equal(glow.paint['line-opacity'],0);
  assert.deepEqual(glow.filter,layer(id).filter);assert.equal(glow.minzoom,layer(id).minzoom);
 }
 const alpha=[];for(const state of ['DAY','TWILIGHT','NIGHT']){run(`applyPalette({effective_state:'${state}'})`);alpha.push(layer(core+'-glow').paint['line-opacity'])}
 assert(alpha[0]===0&&alpha[1]>0&&alpha[1]<alpha[2]&&alpha[2]<.3);
 assert(layer('heading-vector-glow').paint['line-opacity']>layer('track-glow').paint['line-opacity']);
 assert(layer('gis-malaysia_fields_all-boundary-glow').paint['line-opacity']<alpha[2]);
 assert(!layer('gis-malaysia_basin-boundary-glow'));
}else if(scenario==='order'){
 const order=run('map.order');
 for(const id of order.filter(id=>layer(id).metadata?.['gds:effect']))assert.equal(order.indexOf(id)+1,order.indexOf(layer(id).metadata['gds:core']),id);
 const chain=['gis-malaysia_basin-fill','gis-malaysia_fields_all-fill','gis-malaysia_production_within_psc_area-fill',core,'gis-malaysia_well_location-point','gis-malaysia_platform-point','maritime-aton-point','site-boundary-outline','maritime-vessels-point','squall-trajectories','track','heading-vector','squall-current','spatial-selection-outline'];
 for(let i=1;i<chain.length;i++)assert(order.indexOf(chain[i-1])<order.indexOf(chain[i]),chain[i]);
}else if(scenario==='visibility'){
 for(const [group,id] of [['Malaysia Platforms','gis-malaysia_platform-point'],['Malaysia Pipelines',core],['Track','track'],['Heading / COG','heading-vector'],['Squall Alerts','squall-trajectories']]){
  for(const visible of [false,true]){run(`setLayerVisibility('${group}',${visible})`);const extra=layer(id+'-glow')||layer(id+'-halo');assert(extra);assert.equal(extra.layout.visibility,visible?'visible':'none')}
 }
 for(const id of ['gis-malaysia_well_location-point','gis-malaysia_awarded_block-boundary'])assert.equal(layer(id).layout.visibility,'none');
}else if(scenario==='symbols'){
 const platform=layer('gis-malaysia_platform-point');assert.equal(platform.layout['icon-image'],'maritime-platform');assert.equal(platform.layout['icon-allow-overlap'],false);assert.equal(platform.layout['text-allow-overlap'],false);assert.equal(platform.layout['text-optional'],true);
 assert(platform.layout['text-field'][3]>=11);assert.equal(layer('gis-malaysia_well_location-point').minzoom,11);
 const image=run("map.images['maritime-platform']");assert.equal(image.width,32);const alpha=[];for(let i=3;i<image.data.length;i+=4)alpha.push(image.data[i]);assert(new Set(alpha).size>20,'smooth local SDF');
 assert.notDeepEqual(run("map.images['maritime-platform'].data"),run("map.images['maritime-vessel'].data"));
 assert(layer('gis-malaysia_platform-point-halo'));assert(layer('maritime-vessels-point-halo'));assert(layer('maritime-aton-point-halo'));assert(layer('gis-malaysia_well_location-point-halo').paint['circle-opacity']===0);
}else if(scenario==='stability'){
 const sources=run('Object.values(map.sources)'),layers=run('Object.values(map.layers)'),order=JSON.stringify(run('map.order'));
 run('followEnabled=true;setLayerVisibility("Malaysia Platforms",false)');
 const data=sources.map(s=>s.data),count=layers.length;
 for(const state of ['NIGHT','DAY','TWILIGHT','NIGHT'])run(`applyPalette({effective_state:'${state}'})`);
 assert.equal(run('followEnabled'),true);assert.equal(layer('gis-malaysia_platform-point').layout.visibility,'none');assert.equal(JSON.stringify(run('map.order')),order);
 assert.equal(run('Object.keys(map.layers).length'),count);
 sources.forEach((s,i)=>{assert.strictEqual(run('Object.values(map.sources)')[i],s);assert.strictEqual(s.data,data[i])});layers.forEach((l,i)=>assert.strictEqual(run('Object.values(map.layers)')[i],l));
 const writes=run('map.writes'),moves=run('map.moves');run('applyPalette({effective_state:"NIGHT"});applyMaritimeState(payload)');assert.equal(run('map.writes'),writes);assert.equal(run('map.moves'),moves);
}else if(scenario==='selection'){
 const color=layer('spatial-selection-outline').paint['line-color'],severity=JSON.stringify(layer('squall-trajectories').paint['line-color']);
 run('applyPalette({effective_state:"NIGHT"})');assert.equal(layer('spatial-selection-outline').paint['line-color'],color);assert.equal(JSON.stringify(layer('squall-trajectories').paint['line-color']),severity);
 assert(layer('spatial-selection-outline-glow').paint['line-opacity']>.3);assert(layer('maritime-selection-point-halo').paint['circle-opacity']>.2);
 assert.deepEqual(layer('squall-trajectories-glow').paint['line-dasharray'],layer('squall-trajectories').paint['line-dasharray']);
}else if(scenario==='restore'){
 const ids=[core,'gis-malaysia_fields_all-fill','gis-malaysia_production_within_psc_area-fill','gis-malaysia_platform-point'];
 const before=ids.map(id=>JSON.stringify(layer(id).paint));run('applyPalette({effective_state:"NIGHT"})');
 assert.notEqual(layer(core).paint['line-color'],'#557d88');assert.equal(layer('gis-malaysia_basin-fill').paint['fill-opacity'],0);
 run('applyPalette({effective_state:"DAY"})');ids.forEach((id,i)=>assert.equal(JSON.stringify(layer(id).paint),before[i]));
}else throw Error('Unknown scenario '+scenario);
console.log(scenario+': PASS');
