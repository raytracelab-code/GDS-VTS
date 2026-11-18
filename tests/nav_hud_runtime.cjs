const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(){this.children=[];this.style={};this.attributes={}}
 appendChild(child){this.children.push(child)}setAttribute(k,v){this.attributes[k]=v}remove(){this.removed=true}
}
const body=new Element(),handlers={},controls=[],camera={lng:104.25,lat:5.2198,zoom:6.25,bearing:35};
const sources={track:{},gis:{}};
const map={getCenter:()=>camera,getZoom:()=>camera.zoom,getBearing:()=>camera.bearing,
 on:(event,callback)=>{(handlers[event]??=[]).push(callback)},addControl:(control,position)=>controls.push({control,position}),
 setStyle(){throw Error('HUD reloaded style')},easeTo(){throw Error('HUD moved camera')},sources};
const context=vm.createContext({WeakMap,document:{body,createElement:()=>new Element()},maplibregl:{ScaleControl:class{constructor(options){this.options=options}}}});
vm.runInContext(fs.readFileSync('app/resources/map/presentation.js','utf8'),context);
context.map=map;
const run=code=>vm.runInContext(code,context);
const hud=run('GdsMapHud.attach(map)');run('GdsMapHud.attach(map)');
assert.equal(body.children.length,1);assert.equal(controls.length,1);
assert.equal(controls[0].control.options.unit,'nautical');
assert.equal(hud.hud.children[1].children[0].textContent,'LAT  5.2198°');
assert.equal(hud.hud.children[1].children[2].textContent,'ZOOM 6.25');
assert.equal(hud.hud.children[0].children[1].style.transform,'rotate(-35deg)');
const before=JSON.stringify(camera);for(let i=0;i<100;i++)hud.update();
assert.equal(JSON.stringify(camera),before);assert.strictEqual(map.sources,sources);
camera.lng=190;handlers.move.forEach(fn=>fn());assert.equal(hud.hud.children[1].children[1].textContent,'LON  -170.0000°');
handlers.remove.forEach(fn=>fn());assert(hud.hud.removed);
console.log('HUD initialization / no duplicates / camera / sources / coordinates / bearing / nautical scale: PASS');
