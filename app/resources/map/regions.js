/* Settled-viewport package lifecycle. No camera, operational data or style reload. */
const GdsRegions=(()=>{
 const states=new WeakMap();
 function intersects(a,b){
  if(a[1]>b[3]||a[3]<b[1])return false;
  return (a[0]<=a[2]?[[a[0],a[2]]]:[[a[0],180],[-180,a[2]]]).some(([w,e])=>w<=b[2]&&e>=b[0]);
 }
 function resolve(packages,view){
  const area=p=>(p.bounds[2]-p.bounds[0])*(p.bounds[3]-p.bounds[1]);
  const eligible=packages.filter(p=>p.enabled!==false&&intersects(view,p.bounds)).sort((a,b)=>(b.priority??100)-(a.priority??100)||area(a)-area(b)||a.package_id.localeCompare(b.package_id));
  for(const p of eligible.slice(0,1)){const [w,s,e,n]=p.bounds;if(view[0]<=view[2]&&w<=view[0]&&view[2]<=e&&s<=view[1]&&view[3]<=n)return [p]}
  if(eligible.length>6){
   const center=[((view[0]+view[2]+(view[0]>view[2]?360:0))/2+180)%360-180,(view[1]+view[3])/2],distance=p=>{const b=p.bounds,dx=(((b[0]+b[2])/2-center[0]+180)%360+360)%360-180;return dx*dx+((b[1]+b[3])/2-center[1])**2};
   const chosen=new Set([...eligible].sort((a,b)=>distance(a)-distance(b)).slice(0,6));return eligible.filter(p=>chosen.has(p));
  }
  return eligible;
 }
 function apply(map,config,view,notify){
  const ctx=states.get(map)||{known:new Map()};states.set(map,ctx);
  const packages=config.regional_packages||[],active=resolve(packages,view),ids=new Set(active.map(p=>p.package_id));
  for(const p of packages){const previous=ctx.known.get(p.package_id);if(previous&&(previous.revision!==p.revision||JSON.stringify(previous.style.sources)!==JSON.stringify(p.style.sources))){
   for(const l of [...previous.style.layers].reverse())if(l.source&&map.getLayer(l.id))map.removeLayer(l.id);
   for(const id of Object.keys(previous.style.sources))if(map.getSource(id))map.removeSource(id);
  }}
  for(const p of packages)ctx.known.set(p.package_id,p);
  const anchor=()=>map.getStyle().layers.find(l=>l.source&&!String(l.source).startsWith('offline-'))?.id;
  const overviewSource=spec=>(spec.tiles||[]).some(url=>url.includes('/overview/'));
  const overview=packages.find(p=>Object.values(p.style.sources).some(s=>overviewSource(s)&&intersects(view,s.bounds||p.bounds)));
  const wanted=new Set();
  for(const p of active)for(const [id,spec] of Object.entries(p.style.sources))if(!overviewSource(spec))wanted.add(id);
  if(overview)for(const [id,spec] of Object.entries(overview.style.sources))if(overviewSource(spec))wanted.add(id);
  // Remove inactive basemap layers first, then their now-unreferenced sources.
  for(const p of ctx.known.values()){
   for(const l of [...p.style.layers].reverse())if(l.source&&!wanted.has(l.source)&&map.getLayer(l.id))map.removeLayer(l.id);
   for(const id of Object.keys(p.style.sources))if(!wanted.has(id)&&map.getSource(id))map.removeSource(id);
  }
  const configured=new Set(packages.map(p=>p.package_id));for(const id of ctx.known.keys())if(!configured.has(id))ctx.known.delete(id);
  // Lower priority first; MapLibre collision placement suppresses shared labels.
  const render=[...active].reverse();if(overview&&!ids.has(overview.package_id))render.unshift(overview);
  for(const p of render){
   for(const [id,spec] of Object.entries(p.style.sources))if(wanted.has(id)&&map.getSource(id)){
    const existing=map.getStyle().sources[id];
    if(existing&&JSON.stringify(existing.tiles)!==JSON.stringify(spec.tiles)){
     for(const l of [...map.getStyle().layers].reverse())if(l.source===id)map.removeLayer(l.id);
     map.removeSource(id);
    }
   }
   for(const [id,spec] of Object.entries(p.style.sources))if(wanted.has(id)&&!map.getSource(id))map.addSource(id,spec);
   for(const layer of p.style.layers)if(layer.source&&wanted.has(layer.source)&&!map.getLayer(layer.id))map.addLayer(layer,anchor());
  }
  const isOverview=id=>render.some(p=>p.style.sources[id]&&overviewSource(p.style.sources[id]));
  const desired=render.flatMap(p=>p.style.layers.filter(l=>l.source&&wanted.has(l.source))).sort((a,b)=>(isOverview(a.source)?0:a.type==='raster'?2:1)-(isOverview(b.source)?0:b.type==='raster'?2:1));
  const current=map.getStyle().layers.filter(l=>wanted.has(l.source)).map(l=>l.id);
  if(map.moveLayer&&JSON.stringify(current)!==JSON.stringify(desired.map(l=>l.id)))for(const l of desired)map.moveLayer(l.id,anchor());
  if(typeof GdsOffline!=='undefined')GdsOffline.reorder(map);
  const longitude=((view[0]+view[2]+(view[0]>view[2]?360:0))/2+180)%360-180,latitude=(view[1]+view[3])/2;
  const labelDistance=p=>{const [w,s,e,n]=p.bounds,inside=w<=longitude&&longitude<=e&&s<=latitude&&latitude<=n;
   const dx=(((w+e)/2-longitude+180)%360+360)%360-180;
   return (inside?0:100000)+dx*dx+((s+n)/2-latitude)**2};
  const names=[...active].sort((a,b)=>labelDistance(a)-labelDistance(b)).map(p=>p.name||p.package_id);
  const label=names.length>2?names.slice(0,2).join(' + ')+' + '+(names.length-2)+' regions':names.join(' + ');
  const status=names.length?'OFFLINE MAP · '+label+' · READY':overview?'OFFLINE MAP · Overview · READY':'Outside installed offline map coverage';
  if(overview)ids.add(overview.package_id);
  if(notify)notify([...ids],status);
  return [...ids];
 }
 function attach(map,config,notify){
  if(!config?.regional_packages)return;
  if(states.get(map)?.attached){states.get(map).schedule();return}
  const ctx=states.get(map)||{known:new Map()};ctx.attached=true;ctx.timer=null;states.set(map,ctx);
  const settled=()=>{clearTimeout(ctx.timer);ctx.timer=setTimeout(()=>{
   const b=map.getBounds(),norm=x=>((x+180)%360+360)%360-180;
   apply(map,config,b.getEast()-b.getWest()>=360?[-180,b.getSouth(),180,b.getNorth()]:[norm(b.getWest()),b.getSouth(),norm(b.getEast()),b.getNorth()],notify);
  },700)};
  // NAV's existing reportPaletteCenter moveend hook calls this entry point.
  ctx.schedule=settled;settled();
 }
 return {attach,apply,resolve,intersects};
})();
