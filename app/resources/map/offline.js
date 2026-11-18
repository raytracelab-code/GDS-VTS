/* NAV-only paint changes. Never changes sources, data, visibility or camera. */
const GdsOffline=(()=>{
 const palettes={
  DAY:{sea:'#cddfe3',land:'#e8e8df',coast:'#91abb3',road:'#b7b9ae',boundary:'#9babae',text:'#596c73',halo:'#e8e8df',brightness:1,saturation:0,contrast:0},
  TWILIGHT:{sea:'#334952',land:'#465154',coast:'#71898d',road:'#748082',boundary:'#7c9095',text:'#b3c1c3',halo:'#39484d',brightness:.68,saturation:-.25,contrast:-.08},
  NIGHT:{sea:'#101f29',land:'#202e34',coast:'#405d6b',road:'#46555e',boundary:'#526970',text:'#9bafb4',halo:'#16262e',brightness:.32,saturation:-.45,contrast:-.12}
 };
 const contexts=new WeakMap();
 let latestRegistry=new Map();
 const clone=v=>JSON.parse(JSON.stringify(v));
 const roles=new Set(['WATER','LAND','COAST','ROAD','BOUNDARY','LABEL','BATHYMETRY','SATELLITE','REFERENCE_GIS','OPERATIONAL']);
 // Shared category effects: one companion per eligible layer, never per object.
 const effects={vector:{extra:5,alpha:.32,blur:1.2},warning:{extra:5,alpha:.3,blur:1.1},
  surveillance:{extra:3,alpha:.16,blur:1},selection:{extra:6,alpha:.34,blur:1.2},
  track:{extra:3,alpha:.22,blur:1},pipeline:{extra:3,alpha:.25,blur:1},
  project:{extra:3,alpha:.2,blur:1},route:{extra:3,alpha:.18,blur:1},
  field:{extra:2,alpha:.14,blur:.8},production:{extra:3,alpha:.2,blur:1},block:{extra:2,alpha:.09,blur:.7}};
 const tones={platform:['#b77d35','#d5a466','#e6b46f'],pipeline:['#557d88','#83aeb5','#8dbcc2'],
  field:['#6e9690','#87aaa2','#98b8ab'],production:['#ad7260','#be8873','#d09b7d'],
  block:['#8d8c80','#92978b','#a4a798'],well:['#b28e5a','#c5a36f','#d6b784'],
  ais:['#42566b','#a9c2c7','#c0d3d7'],aton:['#337e72','#8cb8a8','#a8cbbb'],
  vector:['#34697a','#8cbfbc','#b0d7cc'],track:['#1e3a5f','#8eb6bc','#93c3c4'],
  project:['#527e7c','#8bafa7','#9bbfb4'],route:['#657f8c','#8da6b1','#9bb8c2']};
 function visual(layer){
  if(layer.metadata&&layer.metadata['gds:visual'])return layer.metadata['gds:visual'];
  const id=layer.id,source=layer.source||'';
  if(/selection/.test(id)||/selection/.test(source))return 'selection';
  if(['heading-vector','cog-vector'].includes(source))return 'vector';
  if(source==='track')return 'track';
  if(source.startsWith('squall-'))return source.includes('surveillance')?'surveillance':'warning';
  if(['site-boundary','pipelines','anchor-patterns','operational-zones'].includes(source))return 'project';
  if(source==='maritime-routes'||source==='maritime-subsea')return 'route';
  if(source==='maritime-offshore')return 'platform';
  if(source==='maritime-vessels')return 'ais';
  if(source==='maritime-aton')return 'aton';
  return null;
 }
 function numeric(value,op,amount){
  if(op==='*'&&amount===0)return 0;
  if(typeof value==='number')return op==='*'?value*amount:value+amount;
  if(Array.isArray(value)&&['interpolate','step'].includes(value[0])){
   const result=clone(value),start=value[0]==='step'?2:4;
   for(let i=start;i<result.length;i+=2)result[i]=numeric(result[i],op,amount);
   return result; // Keep zoom expressions at their required top level.
  }
  return [op,value,amount];
 }
 function tone(kind,current,fallback){
  return tones[kind]?tones[kind][['DAY','TWILIGHT','NIGHT'].indexOf(current)]:fallback;
 }
 function role(layer){
  if(/selection/.test(layer.id)||/selection/.test(layer.source||''))return null;
  const explicit=layer.metadata&&layer.metadata['gds:role'];
  if(roles.has(explicit))return explicit;
  const owner=layer.metadata&&layer.metadata['gds:owner'],source=layer.source||'';
  if(owner==='bathymetry')return 'BATHYMETRY';
  if(owner==='satellite')return 'SATELLITE';
  if(owner==='basemap'&&layer.type==='raster')return 'SATELLITE';
  if(source.startsWith('gis-'))return 'REFERENCE_GIS';
  if(['track','track-start','heading-vector','cog-vector','site-boundary','pipelines','anchor-patterns','survey-areas','operational-zones'].includes(source)||source.startsWith('maritime-')||source.startsWith('squall-'))return 'OPERATIONAL';
  if(layer.id.startsWith('reference-')&&layer.type==='raster')return 'BATHYMETRY';
  const sourceLayer=layer['source-layer'];
  if(owner==='basemap'||['background','water','waterway','landcover','landuse','boundary','transportation','transportation_name','place','water_name'].includes(layer.id)){
   if(layer.type==='background')return 'WATER';
   if(layer.type==='symbol')return 'LABEL';
   if(['transportation','transportation_name'].includes(sourceLayer))return 'ROAD';
   if(sourceLayer==='boundary')return 'BOUNDARY';
   if(sourceLayer==='waterway')return 'COAST';
   if(layer.type==='line'&&['water','waterway'].includes(sourceLayer))return 'COAST';
   return sourceLayer==='water'?'WATER':'LAND';
  }
  return null;
 }
 function state(map){
  if(!contexts.has(map))contexts.set(map,{registry:new Map(),companions:new Map(),current:'DAY',attached:false,applied:null,orderDirty:false});
  return contexts.get(map);
 }
 function brighten(color,current){
  if(typeof color!=='string'||!/^#[0-9a-f]{6}$/i.test(color))return color;
  const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16));
  if(Math.max(...rgb)>155)return color; // Preserve existing warning/severity colors.
  return '#'+rgb.map(v=>Math.round(v+(255-v)*(current==='NIGHT'?.48:.25)).toString(16).padStart(2,'0')).join('');
 }
 function paint(map,id,entry,current){
  if(!map.getLayer(id)||(!entry.role&&!entry.effect&&entry.visual!=='selection')||!map.setPaintProperty)return;
  if(entry.effect){
   const night=current==='NIGHT',twilight=current==='TWILIGHT',p=entry.paint;
   const key=entry.effect==='glow'?'line':'circle',profile=effects[entry.visual];
   const color=p[key+'-color'];
   map.setPaintProperty(id,key+'-color',typeof color==='string'?tone(entry.visual,current,color):color);
   const alpha=entry.effect==='glow'?(night?profile.alpha:twilight?profile.alpha*.28:0):
    (night?entry.haloAlpha:twilight?entry.haloAlpha*.55:entry.visual==='platform'?.05:0);
   map.setPaintProperty(id,key+'-opacity',numeric(entry.opacity,'*',alpha));
   return;
  }
  const p=palettes[current],r=entry.role;
  for(const [key,value] of Object.entries(entry.paint)){
   let next=value;
   if(entry.visual==='selection'&&key==='icon-color'&&current!=='DAY')next='#d6e3d4';
   if(['WATER','LAND','COAST','ROAD','BOUNDARY','LABEL'].includes(r)){
    if(key==='background-color'||key==='fill-color')next=r==='WATER'?p.sea:p.land;
    if(key==='line-color')next=r==='ROAD'?p.road:r==='BOUNDARY'?p.boundary:p.coast;
    if(key==='text-color')next=p.text;
    if(key==='text-halo-color')next=p.halo;
   }else if(current!=='DAY'&&['REFERENCE_GIS','OPERATIONAL'].includes(r)&&typeof value==='string'){
    // Leave severity expressions and selection styles intact. Polygon fills
    // retain their restrained original opacity/color; points and lines lighten.
    if(key==='text-halo-color'||key==='icon-halo-color')next=p.halo;
    else if(key.endsWith('-color')&&key!=='fill-color')next=brighten(value,current);
   }
   if(current!=='DAY'&&entry.visual&&tones[entry.visual]&&key.endsWith('-color')&&typeof value==='string'){
    if(key==='text-halo-color'||key==='icon-halo-color')next=current==='DAY'?'#edf2ee':p.halo;
    else if(key!=='circle-stroke-color')next=tone(entry.visual,current,value);
   }
   if(entry.visual==='field'||entry.visual==='production'){
    if(key==='fill-opacity'&&current!=='DAY')next=numeric(value,'*',current==='NIGHT'?.65:.8);
    if(key==='fill-color'&&current!=='DAY')next=entry.visual==='production'?'#63463e':'#3c4d48';
   }
   if(['basin','survey'].includes(entry.visual)&&key==='fill-opacity'&&current!=='DAY')next=0;
   if(key.endsWith('-color'))map.setPaintProperty(id,key+'-transition',{duration:250,delay:0});
   map.setPaintProperty(id,key,next);
  }
  if(r==='BATHYMETRY'||r==='SATELLITE'){
   for(const [key,value] of Object.entries({'raster-brightness-max':p.brightness,'raster-saturation':p.saturation,'raster-contrast':p.contrast})){
    map.setPaintProperty(id,key+'-transition',{duration:250,delay:0});
    map.setPaintProperty(id,key,current==='DAY'?(entry.paint[key]??value):value);
   }
  }
 }
 function register(map,layer){
  const ctx=state(map),meta=layer.metadata||{},entry={role:role(layer),visual:visual(layer),paint:clone(layer.paint||{}),
   effect:meta['gds:effect'],haloAlpha:meta['gds:alpha'],opacity:meta['gds:opacity']??1};
  ctx.registry.set(layer.id,entry);paint(map,layer.id,entry,ctx.current);
 }
 function companion(layer){
  const kind=visual(layer),profile=effects[kind],p=layer.paint||{};
  if(layer.type==='line'&&profile){
   // GIS points also have empty line layers; only operational geometry glows.
   if(layer.source?.startsWith('gis-')&&!((kind==='pipeline'&&layer.id.endsWith('-line'))||(['field','production','block'].includes(kind)&&layer.id.endsWith('-boundary'))))return null;
   return {...clone(layer),id:layer.id+'-glow',metadata:{...layer.metadata,'gds:effect':'glow','gds:visual':kind,'gds:core':layer.id,'gds:opacity':p['line-opacity']??1},
    paint:{'line-color':p['line-color']||'#94c1b9','line-width':numeric(p['line-width']??1,'+',profile.extra),
     'line-blur':profile.blur,'line-opacity':0,...(p['line-dasharray']?{'line-dasharray':clone(p['line-dasharray'])}:{})}};
  }
  const pointHalo=(layer.type==='symbol'&&layer.id.endsWith('-point')&&['platform','ais','aton'].includes(kind))||
   (layer.type==='circle'&&layer.id.endsWith('-point')&&['selection','well'].includes(kind));
  if(!pointHalo)return null;
  const radius={platform:9,ais:6.5,aton:6,selection:16,well:3.5}[kind];
  return {...clone(layer),id:layer.id+'-halo',type:'circle',layout:{visibility:layer.layout?.visibility||'visible'},
   metadata:{...layer.metadata,'gds:effect':'halo','gds:visual':kind,'gds:core':layer.id,'gds:alpha':{platform:.24,ais:.11,aton:.17,selection:.25,well:.09}[kind]},
   paint:{'circle-color':kind==='selection'?'#d9b26f':tone(kind,'NIGHT','#9bc6bb'),'circle-radius':radius,'circle-blur':.45,'circle-opacity':0}};
 }
 function rank(layer){
  const id=layer.id,source=layer.source||'',kind=visual(layer);
  if(layer.metadata?.['gds:hybrid-rank'])return layer.metadata['gds:hybrid-rank'];
  if(kind==='selection')return 110;
  if(layer.metadata?.['gds:owner']==='basemap'||!source)return 0;
  if(layer.type==='raster')return 10;
  if(source.startsWith('gis-'))return {basin:20,survey:21,block:24,field:30,production:35,pipeline:40,well:45,platform:50,platform_detail:50}[kind]??25;
  if(source==='track'||source==='track-start')return 95;
  if(kind==='vector')return 100;
  if(source.startsWith('squall-'))return id==='squall-current'?105:85;
  if(source.startsWith('maritime-'))return {platform:50,aton:55,ais:75,route:25,warning:85}[kind]??25;
  return 60; // Project spatial overlays above the reference infrastructure.
 }
 function reorder(map){
  const ctx=state(map);
  if(!ctx.orderDirty||!ctx.move||!map.getStyle)return;
  const layers=map.getStyle().layers||[],index=new Map(layers.map((l,i)=>[l.id,i]));
  const core=l=>l.metadata?.['gds:core']||l.id;
  layers.sort((a,b)=>rank(a)-rank(b)||(index.get(core(a))??0)-(index.get(core(b))??0)||Number(!a.metadata?.['gds:effect'])-Number(!b.metadata?.['gds:effect']));
  for(const layer of layers)ctx.move(layer.id);
  ctx.orderDirty=false;
 }
 function attach(map){
  const ctx=state(map);latestRegistry=ctx.registry;
  if(ctx.attached)return;
  ctx.attached=true;
  const add=map.addLayer.bind(map);
  ctx.move=map.moveLayer?.bind(map);
  map.addLayer=(layer,before)=>{
   const extra=companion(layer);
   if(extra&&!map.getLayer(extra.id)){add(extra,before);register(map,extra);ctx.companions.set(layer.id,[extra.id])}
   const result=add(layer,before);register(map,layer);ctx.orderDirty=true;return result;
  };
  if(ctx.move)map.moveLayer=(id,before)=>{for(const extra of ctx.companions.get(id)||[])if(map.getLayer(extra))ctx.move(extra,before);return ctx.move(id,before)};
  if(map.setLayoutProperty){
   const layout=map.setLayoutProperty.bind(map);
   map.setLayoutProperty=(id,key,value)=>{const result=layout(id,key,value);if(key==='visibility')for(const extra of ctx.companions.get(id)||[])if(map.getLayer(extra))layout(extra,key,value);return result};
  }
  if(map.removeLayer){
   const remove=map.removeLayer.bind(map);
   map.removeLayer=id=>{for(const extra of ctx.companions.get(id)||[]){if(map.getLayer(extra))remove(extra);ctx.registry.delete(extra)}ctx.companions.delete(id);const result=remove(id);ctx.registry.delete(id);return result};
  }
 }
 function apply(map,payload){
  if(!map||!palettes[payload&&payload.effective_state])return;
  const ctx=state(map),changed=ctx.applied!==payload.effective_state;
  ctx.current=payload.effective_state;latestRegistry=ctx.registry;
  if(map.getStyle){
   const layers=map.getStyle().layers||[],ids=new Set(layers.map(l=>l.id));
   for(const id of ctx.registry.keys())if(!ids.has(id))ctx.registry.delete(id);
   for(const layer of layers)if(!ctx.registry.has(layer.id))register(map,layer);
  }
  if(changed)for(const [id,entry] of ctx.registry)paint(map,id,entry,ctx.current);
  ctx.applied=ctx.current;
  reorder(map);
  if(typeof document!=='undefined'){
   const el=document.getElementById('map');if(el)el.style.background=palettes[ctx.current].sea;
   document.documentElement.style.setProperty('--vessel-color',ctx.current==='DAY'?'#167a73':'#83ddcb');
   document.documentElement.style.setProperty('--vessel-glow',ctx.current==='NIGHT'?'3px':ctx.current==='TWILIGHT'?'1px':'0px');
   document.documentElement.style.setProperty('--vessel-glow-color','#8dbfb3');
  }
 }
 return {attach,apply,reorder,get registry(){return latestRegistry},palettes,role,numeric};
})();
