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
 function role(layer){
  if(/selection/.test(layer.id)||/selection/.test(layer.source||''))return null;
  const explicit=layer.metadata&&layer.metadata['gds:role'];
  if(roles.has(explicit))return explicit;
  const owner=layer.metadata&&layer.metadata['gds:owner'],source=layer.source||'';
  if(owner==='bathymetry')return 'BATHYMETRY';
  if(owner==='satellite')return 'SATELLITE';
  if(source.startsWith('gis-'))return 'REFERENCE_GIS';
  if(['track','track-start','heading-vector','cog-vector','site-boundary','pipelines','anchor-patterns','survey-areas','operational-zones'].includes(source)||source.startsWith('maritime-')||source.startsWith('squall-'))return 'OPERATIONAL';
  if(layer.id.startsWith('reference-')&&layer.type==='raster')return 'BATHYMETRY';
  const sourceLayer=layer['source-layer'];
  if(owner==='basemap'||['background','water','waterway','landcover','landuse','boundary','transportation','transportation_name','place','water_name'].includes(layer.id)){
   if(layer.type==='background')return 'WATER';
   if(layer.type==='symbol')return 'LABEL';
   if(sourceLayer==='transportation')return 'ROAD';
   if(sourceLayer==='boundary')return 'BOUNDARY';
   if(layer.type==='line'&&['water','waterway'].includes(sourceLayer))return 'COAST';
   return sourceLayer==='water'?'WATER':'LAND';
  }
  return null;
 }
 function state(map){
  if(!contexts.has(map))contexts.set(map,{registry:new Map(),current:'DAY',attached:false,applied:null});
  return contexts.get(map);
 }
 function brighten(color,current){
  if(typeof color!=='string'||!/^#[0-9a-f]{6}$/i.test(color))return color;
  const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16));
  if(Math.max(...rgb)>155)return color; // Preserve existing warning/severity colors.
  return '#'+rgb.map(v=>Math.round(v+(255-v)*(current==='NIGHT'?.48:.25)).toString(16).padStart(2,'0')).join('');
 }
 function paint(map,id,entry,current){
  if(!map.getLayer(id)||!entry.role||!map.setPaintProperty)return;
  const p=palettes[current],r=entry.role;
  for(const [key,value] of Object.entries(entry.paint)){
   let next=value;
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
  const ctx=state(map),entry={role:role(layer),paint:clone(layer.paint||{})};
  ctx.registry.set(layer.id,entry);paint(map,layer.id,entry,ctx.current);
 }
 function attach(map){
  const ctx=state(map);latestRegistry=ctx.registry;
  if(ctx.attached)return;
  ctx.attached=true;
  const add=map.addLayer.bind(map);
  map.addLayer=(layer,before)=>{const result=add(layer,before);register(map,layer);return result};
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
  if(typeof document!=='undefined'){
   const el=document.getElementById('map');if(el)el.style.background=palettes[ctx.current].sea;
   document.documentElement.style.setProperty('--vessel-color',ctx.current==='DAY'?'#1e3a5f':'#b4d6d4');
  }
 }
 return {attach,apply,get registry(){return latestRegistry},palettes,role};
})();
