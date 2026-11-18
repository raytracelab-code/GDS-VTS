const fs=require('fs'),vm=require('vm'),assert=require('assert');
const c=vm.createContext({console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync('app/resources/map/regions.js','utf8'),c);
const run=s=>vm.runInContext(s,c);
run(`
const operational={id:'track',type:'line',source:'track',paint:{'line-color':'#123456'}};
const map={sources:{track:{selected:true}},layers:[operational],writes:0,
 getStyle(){return {layers:this.layers,sources:this.sources}},getLayer(id){return this.layers.find(l=>l.id===id)},getSource(id){return this.sources[id]},
 addSource(id,s){if(this.sources[id])throw Error('duplicate source');this.sources[id]=s},
 removeSource(id){if(this.layers.some(l=>l.source===id))throw Error('source still referenced');delete this.sources[id]},
 addLayer(l,before){if(this.getLayer(l.id))throw Error('duplicate layer');const i=this.layers.findIndex(x=>x.id===before);this.layers.splice(i<0?this.layers.length:i,0,l)},
 removeLayer(id){this.layers=this.layers.filter(l=>l.id!==id)},setStyle(){throw Error('style reload')},easeTo(){throw Error('camera change')}};
map.moveLayer=function(id,before){const layer=this.getLayer(id);this.removeLayer(id);this.addLayer(layer,before)};
function pack(id,bounds){const source='offline-'+id;return {package_id:id,bounds,name:id,style:{sources:{[source]:{type:'vector',tiles:['gds://tiles/'+id+'/basemap/{z}/{x}/{y}.pbf']}},layers:[{id:source+'-water',source,type:'fill',paint:{'fill-color':'#cddfe3'}}]}}}
const malaysia=pack('malaysia',[99,0,120,8]),thailand=pack('thailand',[97,5,106,21]),australia=pack('australia',[110,-44,155,-10]);
const config={regional_packages:[malaysia,thailand,australia]},trackSource=map.sources.track;
let reported=[];const notify=(ids,status)=>reported.push({ids,status});
`);
for(let i=0;i<20;i++){
 run('GdsRegions.apply(map,config,[103,2,105,4],notify)');assert.equal(run('Object.keys(map.sources).length'),2);
 run('GdsRegions.apply(map,config,[99,12,103,18],notify)');assert.equal(run("Boolean(map.sources['offline-malaysia'])"),false);
 run('GdsRegions.apply(map,config,[120,-35,140,-20],notify)');assert.equal(run('Object.keys(map.sources).length'),2);
 run('GdsRegions.apply(map,config,[20,40,30,50],notify)');assert.equal(run('Object.keys(map.sources).length'),1);
 assert.equal(run('map.layers[0]===operational&&map.sources.track===trackSource'),true);
}
run('GdsRegions.apply(map,config,[100,4,108,10],notify)');assert.equal(run('Object.keys(map.sources).length'),3);
assert(run("map.layers.findIndex(l=>l.id==='offline-malaysia-water')<map.layers.findIndex(l=>l.id==='offline-thailand-water')"));
run('thailand.enabled=false;GdsRegions.apply(map,config,[99,12,103,18],notify)');assert.equal(run('Object.keys(map.sources).length'),1);
assert(run("reported.at(-1).status.includes('Outside')"));
run('config.regional_packages=[malaysia];GdsRegions.apply(map,config,[103,2,105,4],notify)');
assert.equal(run('Object.keys(map.sources).length'),2);
run(`
const world='offline-world';malaysia.style.sources[world]={type:'vector',bounds:[-180,-85,180,85],tiles:['gds://tiles/malaysia/overview/{z}/{x}/{y}.pbf']};
malaysia.style.layers.unshift({id:world+'-water',source:world,type:'fill',paint:{'fill-color':'#cddfe3'}});
GdsRegions.apply(map,config,[20,40,30,50],notify);
`);
assert.equal(run('Object.keys(map.sources).length'),2);assert(run("reported.at(-1).status.includes('Overview')"));
run('GdsRegions.apply(map,config,[103,2,105,4],notify)');
assert(run("map.layers.findIndex(l=>l.id==='offline-world-water')<map.layers.findIndex(l=>l.id==='offline-malaysia-water')"));
run(`
const thaiPrimary=pack('thailand',[97,5,106,21]);thaiPrimary.style.sources={'offline-malaysia':thaiPrimary.style.sources['offline-thailand']};
thaiPrimary.style.layers=[{id:'offline-malaysia-water',source:'offline-malaysia',type:'fill',paint:{'fill-color':'#cddfe3'}}];
config.regional_packages=[thaiPrimary];GdsRegions.apply(map,config,[99,12,103,18],notify);
`);
assert(run("map.sources['offline-malaysia'].tiles[0].includes('/thailand/')"),'Disabling the old primary must not reuse its cached source URL');
assert.equal(run('Object.keys(map.sources).length'),2);
assert(run('map.sources.track===trackSource&&map.layers.includes(operational)'));
console.log('Repeated regional activation, cleanup, overlap, disable, outside fallback and operational identity: PASS');
