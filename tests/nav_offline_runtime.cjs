const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context=vm.createContext({console,document:{documentElement:{style:{setProperty(){}}},getElementById(){return {style:{}}}}});
vm.runInContext(fs.readFileSync('app/resources/map/offline.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
run(`
const map={layers:{},sources:{operational:{data:{selected:'real-state'}}},camera:{center:[104,4],zoom:11,pitch:55,bearing:30},
getLayer(id){return this.layers[id]},getStyle(){return {layers:Object.values(this.layers)}},
addLayer(layer){this.layers[layer.id]=JSON.parse(JSON.stringify(layer))},
setPaintProperty(id,key,value){this.layers[id].paint[key]=value},
setStyle(){throw Error('Palette reloaded style')},addSource(){throw Error('Palette recreated source')},
easeTo(){throw Error('Palette moved camera')},fitBounds(){throw Error('Palette fitted camera')}};
GdsOffline.attach(map);
map.addLayer({id:'offline-background',type:'background',metadata:{'gds:owner':'basemap'},paint:{'background-color':'#cddfe3'}});
map.addLayer({id:'gis-platforms-icon',type:'symbol',source:'gis-platforms',layout:{visibility:'none'},paint:{'icon-color':'#506d7e'}});
map.addLayer({id:'track',type:'line',source:'track',paint:{'line-color':'#1e3a5f'}});
map.addLayer({id:'squall-current',type:'circle',source:'squall-current',paint:{'circle-color':['match',['get','severity'],'high','#c77b35','#7f8d9e']}});
map.addLayer({id:'selection',type:'line',source:'spatial-selection',paint:{'line-color':'#d9b26f'}});
map.addLayer({id:'offline-bathymetry-raster',type:'raster',metadata:{'gds:owner':'bathymetry'},paint:{'raster-opacity':.38}});
map.addLayer({id:'offline-satellite-raster',type:'raster',metadata:{'gds:owner':'satellite'},paint:{'raster-opacity':1}});
const source=map.sources.operational,camera=JSON.stringify(map.camera),severity=JSON.stringify(map.layers['squall-current'].paint);
for(const state of ['NIGHT','TWILIGHT','DAY','NIGHT'])GdsOffline.apply(map,{effective_state:state});
`);
assert.equal(run('map.sources.operational===source'),true);
assert.equal(run('JSON.stringify(map.camera)===camera'),true);
assert.equal(run("map.layers['gis-platforms-icon'].layout.visibility"),'none');
assert.equal(run("JSON.stringify(map.layers['squall-current'].paint)===severity"),true);
assert.equal(run("map.layers.selection.paint['line-color']"),'#d9b26f');
assert.equal(run("map.layers['offline-background'].paint['background-color']"),'#101f29');
assert.equal(run("map.layers['offline-satellite-raster'].paint['raster-brightness-max']"),.32);
run("map.addLayer({id:'gis-late-boundary',source:'gis-late',type:'line',paint:{'line-color':'#718c86'}})");
assert.notEqual(run("map.layers['gis-late-boundary'].paint['line-color']"),'#718c86');
run("GdsOffline.apply(map,{effective_state:'DAY'})");
assert.equal(run("map.layers.track.paint['line-color']"),'#1e3a5f');
assert.equal(run("map.layers['offline-satellite-raster'].paint['raster-brightness-max']"),1);
console.log('Palette ownership / source identity / camera / visibility / late GIS / raster / restore: PASS');

run(`
const roleLayers=[
 {id:'water-test',type:'fill',metadata:{'gds:role':'WATER'},paint:{'fill-color':'#cddfe3'}},
 {id:'land-test',type:'fill',metadata:{'gds:role':'LAND'},paint:{'fill-color':'#e8e8df'}},
 {id:'coast-test',type:'line',metadata:{'gds:role':'COAST'},paint:{'line-color':'#91abb3'}},
 {id:'road-test',type:'line',metadata:{'gds:role':'ROAD'},paint:{'line-color':'#b7b9ae'}},
 {id:'boundary-test',type:'line',metadata:{'gds:role':'BOUNDARY'},paint:{'line-color':'#9babae'}},
 {id:'label-test',type:'symbol',metadata:{'gds:role':'LABEL'},paint:{'text-color':'#596c73','text-halo-color':'#e8e8df'}},
 {id:'unowned',source:'external',type:'line',paint:{'line-color':'#112233'}},
 {id:'gis-pipeline',source:'gis-malaysia_pipeline',type:'line',layout:{visibility:'none'},paint:{'line-color':'#78818a','line-opacity':.57}},
 {id:'gis-fields',source:'gis-malaysia_fields_all',type:'fill',paint:{'fill-color':'#718c86','fill-opacity':['interpolate',['linear'],['zoom'],6,0,10,.014,14,.032]}},
 {id:'reference-gebco',source:'reference-gebco',type:'raster',paint:{'raster-opacity':.8,'raster-brightness-max':.9,'raster-saturation':-.1}},
 {id:'maritime-warnings',source:'maritime-warnings',type:'circle',paint:{'circle-color':['match',['get','severity'],'high','#c77b35','#7f8d9e']}}
];
for(const layer of roleLayers)map.addLayer(layer);
const sourceIdentity=map.sources.operational,layerIdentity=map.layers.track,layerCount=Object.keys(map.layers).length;
const warningsBefore=JSON.stringify(map.layers['maritime-warnings'].paint['circle-color']);
const fieldsBefore=JSON.stringify(map.layers['gis-fields'].paint);
let paintWrites=0;
const setPaint=map.setPaintProperty.bind(map);
map.setPaintProperty=(...args)=>{paintWrites++;return setPaint(...args)};
for(const effective_state of ['DAY','TWILIGHT','NIGHT','DAY','NIGHT'])GdsOffline.apply(map,{effective_state});
const afterChange=paintWrites;
GdsOffline.apply(map,{effective_state:'NIGHT'});
`);
assert.equal(run('paintWrites'),run('afterChange'),'same-state minute ticks must not repaint');
assert.equal(run('map.sources.operational===sourceIdentity'),true);
assert.equal(run('map.layers.track===layerIdentity'),true);
assert.equal(run('Object.keys(map.layers).length'),run('layerCount'));
assert.equal(run('JSON.stringify(map.camera)===camera'),true);
assert.equal(run("map.layers['gis-pipeline'].layout.visibility"),'none');
assert.equal(run("map.layers['gis-pipeline'].paint['line-opacity']"),.57);
assert.equal(run("map.layers.unowned.paint['line-color']"),'#112233');
assert.equal(run("JSON.stringify(map.layers['maritime-warnings'].paint['circle-color'])===warningsBefore"),true);
assert.equal(run("JSON.stringify(map.layers['gis-fields'].paint)===fieldsBefore"),true);
assert.equal(run("map.layers['reference-gebco'].paint['raster-opacity']"),.8);
for(const [id,role] of [['water-test','WATER'],['land-test','LAND'],['coast-test','COAST'],['road-test','ROAD'],['boundary-test','BOUNDARY'],['label-test','LABEL'],['gis-pipeline','REFERENCE_GIS'],['track','OPERATIONAL'],['reference-gebco','BATHYMETRY'],['offline-satellite-raster','SATELLITE']]){
 assert.equal(run(`GdsOffline.registry.get('${id}').role`),role);
}
run("GdsOffline.apply(map,{effective_state:'DAY'})");
assert.equal(run("map.layers['reference-gebco'].paint['raster-brightness-max']"),.9);
assert.equal(run("map.layers['reference-gebco'].paint['raster-saturation']"),-.1);
run(`
const second={layers:{},getLayer(id){return this.layers[id]},getStyle(){return {layers:Object.values(this.layers)}},
addLayer(layer){this.layers[layer.id]=JSON.parse(JSON.stringify(layer))},setPaintProperty(id,k,v){this.layers[id].paint[k]=v}};
GdsOffline.attach(second);
const attached=second.addLayer;GdsOffline.attach(second);
second.addLayer({id:'track',type:'line',source:'track',paint:{'line-color':'#123456'}});
GdsOffline.apply(second,{effective_state:'NIGHT'});GdsOffline.apply(second,{effective_state:'DAY'});
`);
assert.equal(run('second.addLayer===attached'),true);
assert.equal(run("second.layers.track.paint['line-color']"),'#123456');
assert.equal(run("map.layers.track.paint['line-color']"),'#1e3a5f');
console.log('Explicit roles / independent maps / unchanged severity, selection, visibility, opacity / no redundant paints: PASS');
