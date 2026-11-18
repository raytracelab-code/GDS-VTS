/* Basemap-only mode lifecycle. No style replacement, camera moves or overlay writes. */
const GdsSatellite=(()=>{
 const SOURCE='nasa-gibs-satellite',LAYER='nasa-gibs-satellite-raster',instances=new WeakMap();
 const BATHY='gebco-hybrid-bathymetry',SEA='hybrid-marine-sea-';
 const palettes={DAY:{sea:'#142f40',alpha:.93,relief:.16},TWILIGHT:{sea:'#0d2433',alpha:.95,relief:.12},NIGHT:{sea:'#091923',alpha:.97,relief:.08}};
 function isSatelliteError(event){
  return event.sourceId===SOURCE||event.sourceId===BATHY||(!event.sourceId&&/gibs\.earthdata\.nasa\.gov|wms\.gebco\.net/.test(String(event.error?.url||event.error?.message||'')));
 }
 function probeURL(template,center,zoom,maxzoom){
  const z=Math.max(0,Math.min(maxzoom,Math.floor(zoom))),n=2**z;
  const lon=((center.lng+180)%360+360)%360-180,lat=Math.max(-85.051128,Math.min(85.051128,center.lat));
  const x=Math.floor((lon+180)/360*n),r=lat*Math.PI/180;
  const y=Math.max(0,Math.min(n-1,Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*n)));
  return template.replace('{z}',z).replace('{x}',x).replace('{y}',y);
 }
 async function probe(url,signal){
  const response=await fetch(url,{signal});
  if(response.status===404||response.status===204)return false;
  if(!response.ok)throw Error('Satellite provider unavailable');
  if(!response.headers.get('content-type')?.startsWith('image/'))return false;
  // Missing regional swaths can be returned as successful, entirely black JPEGs.
  const bitmap=await createImageBitmap(await response.blob());
  try{
   const canvas=new OffscreenCanvas(16,16),ctx=canvas.getContext('2d',{willReadFrequently:true});
   ctx.drawImage(bitmap,0,0,16,16);const pixels=ctx.getImageData(0,0,16,16).data;
   for(let i=0;i<pixels.length;i+=4)if(pixels[i+3]>0&&Math.max(pixels[i],pixels[i+1],pixels[i+2])>3)return true;
   return false;
  }finally{bitmap.close()}
 }
 function attach(map,options){
  if(instances.has(map))return instances.get(map);
  let mode='MARINE',state='READY',date=null,generation=0,controller=null,watchdog=null,retryAt=0;
  let pinned=null,marineVisibility=new Map(),attempted=[],failureReason=null,failureDetail=null;
  let bathymetry='OFF',bathyFailed=false,bathyLoaded=false,bathyTimer=null,hybridLayers=[],currentPalette='DAY',lastConfig=null;
  let bathyEnabled=options.bathymetryVisible?.()!==false;
  const now=options.now||Date.now,notify=()=>options.onState?.({mode,state,date,bathymetry,attempted_dates:[...attempted]});
  const hybridVisibility=visible=>{
   for(const id of hybridLayers)if(map.getLayer(id))map.setLayoutProperty(id,'visibility',visible&&(id!==BATHY||bathyEnabled)?'visible':'none');
  };
  function applyPalette(payload){
   currentPalette=payload?.effective_state||currentPalette;
   const p=palettes[currentPalette]||palettes.DAY;
   for(const id of hybridLayers){
    if(!map.getLayer(id))continue;
    if(id.startsWith(SEA)){
     map.setPaintProperty(id,'fill-color',p.sea);map.setPaintProperty(id,'fill-opacity',p.alpha);
    }else if(id===BATHY){
     map.setPaintProperty(id,'raster-opacity',p.relief);
     map.setPaintProperty(id,'raster-brightness-max',currentPalette==='NIGHT'?.28:currentPalette==='TWILIGHT'?.55:.8);
     map.setPaintProperty(id,'raster-saturation',-.65);
    }else if(map.getLayer(id).type==='symbol'){
     map.setPaintProperty(id,'text-color',currentPalette==='DAY'?'#b5c8cd':'#93aeb9');
     map.setPaintProperty(id,'text-halo-color','#122834');
    }
   }
  }
  const bathyFailure=()=>{
   if(bathymetry==='UNAVAILABLE')return;
   clearTimeout(bathyTimer);bathyTimer=null;bathyFailed=true;bathymetry='UNAVAILABLE';
   // Remove a failed optional source so MapLibre cannot keep retrying its tiles.
   if(map.getLayer(BATHY))map.removeLayer(BATHY);
   if(map.getSource(BATHY))map.removeSource(BATHY);
   hybridLayers=hybridLayers.filter(id=>id!==BATHY);notify();
  };
  function installHybrid(config,before){
   lastConfig=config;
   if(!hybridLayers.length){
    const base=map.getStyle().layers.filter(l=>l.metadata?.['gds:owner']==='basemap');
    for(const layer of base){
     const water=layer.type==='fill'&&layer['source-layer']==='water';
     const label=layer.type==='symbol'&&['place','water_name'].includes(layer['source-layer'])&&!/village|other/.test(layer.id)&&layer.layout?.visibility!=='none';
     const coast=layer.type==='line'&&['water','boundary'].includes(layer['source-layer']);
     if(!water&&!label&&!coast)continue;
     const id=(water?SEA:'hybrid-reference-')+layer.id;
     map.addLayer({...JSON.parse(JSON.stringify(layer)),id,
      metadata:{'gds:owner':'hybrid','gds:hybrid-rank':water?11:13},
      layout:{...layer.layout,visibility:'visible'},
      paint:water?{'fill-color':palettes.DAY.sea,'fill-opacity':palettes.DAY.alpha}:layer.paint},before);
     hybridLayers.push(id);
    }
   }
   hybridVisibility(true);
   if(!bathyEnabled){bathymetry='OFF';applyPalette();return}
   if(!config.bathymetry||bathyFailed){bathymetry='UNAVAILABLE';applyPalette();return}
   if(!map.getSource(BATHY)){
    map.addSource(BATHY,config.bathymetry.source);
    const labels=hybridLayers.find(id=>id.startsWith('hybrid-reference-'));
    map.addLayer({id:BATHY,type:'raster',source:BATHY,
     metadata:{'gds:owner':'hybrid','gds:hybrid-rank':12},
     paint:{'raster-opacity':.16,'raster-fade-duration':200}},labels||before);
    hybridLayers.push(BATHY);
   }else if(map.getLayer(BATHY))map.setLayoutProperty(BATHY,'visibility','visible');
   bathymetry=bathyLoaded?'READY':'LOADING';
   if(!bathyLoaded&&!bathyTimer)bathyTimer=setTimeout(bathyFailure,12000);
   applyPalette();
  }
  const cancel=()=>{generation++;controller?.abort();controller=null;clearTimeout(watchdog);watchdog=null};
  const restore=()=>{for(const [id,visibility] of marineVisibility)if(map.getLayer(id))map.setLayoutProperty(id,'visibility',visibility);marineVisibility.clear()};
  const removeRaster=()=>{if(map.getLayer(LAYER))map.removeLayer(LAYER);if(map.getSource(SOURCE))map.removeSource(SOURCE)};
  const failure=(reason='TILE_ERROR',error=null)=>{
   if(mode!=='SATELLITE')return;
   failureReason=reason;failureDetail=error?String(error.message||error).slice(0,240):null;
   mode='MARINE';state='ERROR';cancel();restore();hybridVisibility(false);clearTimeout(bathyTimer);bathyTimer=null;
   bathymetry=bathyFailed?'UNAVAILABLE':'OFF';removeRaster();retryAt=now()+30000;notify();
  };
  const ready=()=>{
   if(mode!=='SATELLITE'||state!=='LOADING')return;
   clearTimeout(watchdog);watchdog=null;state='READY';
   // Preserve even intentionally hidden Marine layers (POI, buildings, etc.).
   for(const layer of map.getStyle().layers)if(layer.type!=='background'&&layer.metadata?.['gds:owner']==='basemap'){
    marineVisibility.set(layer.id,layer.layout?.visibility||'visible');map.setLayoutProperty(layer.id,'visibility','none');
   }
   hybridVisibility(true);applyPalette();notify();
  };
  async function select(name){
   if(name==='MARINE'){
    const wasLoading=state==='LOADING';mode='MARINE';state='READY';cancel();restore();hybridVisibility(false);
    clearTimeout(bathyTimer);bathyTimer=null;
    bathymetry=bathyFailed?'UNAVAILABLE':'OFF';
    if(wasLoading){removeRaster();pinned=null}
    else if(map.getLayer(LAYER))map.setLayoutProperty(LAYER,'visibility','none');
    notify();return;
   }
   if(name!=='SATELLITE')return;
   if(mode==='SATELLITE')return; // Do not restart a pending selection or its date search.
   if(now()<retryAt){notify();return}
   cancel();const token=generation;mode='SATELLITE';state='LOADING';attempted=[];failureReason=null;failureDetail=null;notify();
   controller=new AbortController();const signal=controller.signal;
   watchdog=setTimeout(()=>failure('TIMEOUT'),30000);
   try{
    const config=await options.getConfig();
    if(token!==generation)return;
    if(config.state!=='READY'||!Array.isArray(config.candidates)||!config.candidates.length)throw Error('Satellite not available');
    if(pinned&&pinned.today===config.dates[0]&&map.getLayer(LAYER)){
     date=pinned.date;map.setLayoutProperty(LAYER,'visibility','visible');installHybrid(config);ready();return;
    }
    removeRaster();pinned=null;
    for(const candidate of config.candidates.slice(0,4)){
     if(token!==generation)return;
     attempted.push(candidate.date);
     const timeout=setTimeout(()=>controller?.abort(),5000);
     let valid;
     try{valid=await (options.probe||probe)(probeURL(candidate.source.tiles[0],map.getCenter(),map.getZoom(),config.maxzoom),signal)}
     finally{clearTimeout(timeout)}
     if(token!==generation)return;
     if(!valid)continue;
     date=candidate.date;
     map.addSource(SOURCE,candidate.source);
     const before=map.getStyle().layers.find(l=>l.source&&l.metadata?.['gds:owner']!=='basemap')?.id;
     map.addLayer({id:LAYER,type:'raster',source:SOURCE,
      metadata:{'gds:owner':'satellite','gds:role':'SATELLITE'},
      paint:{'raster-opacity':1,'raster-brightness-min':0,'raster-brightness-max':1,
             'raster-saturation':0,'raster-contrast':0,'raster-fade-duration':200}},before);
     installHybrid(config,before);
     pinned={date,today:config.dates[0]};notify();return;
    }
    failure('NO_RECENT_IMAGERY');
   }catch(error){if(token===generation)failure('PROVIDER_ERROR',error)}
  }
  map.on('sourcedata',event=>{
   const loaded=event.tile?.state==='loaded'||event.sourceDataType==='idle'&&event.isSourceLoaded;
   if(event.sourceId===SOURCE&&loaded)ready();
   if(event.sourceId===BATHY&&loaded&&!bathyFailed){
    bathyLoaded=true;clearTimeout(bathyTimer);bathyTimer=null;
    if(mode==='SATELLITE'&&bathyEnabled&&bathymetry!=='READY'){bathymetry='READY';notify()}
   }
  });
  map.on('error',event=>{
   if(event.sourceId===BATHY||!event.sourceId&&String(event.error?.url||event.error?.message||'').includes('wms.gebco.net'))bathyFailure();
   else if(isSatelliteError(event))failure('TILE_ERROR',event.error);
  });
  map.on('remove',()=>{cancel();clearTimeout(bathyTimer)});
  function setBathymetry(enabled){
   bathyEnabled=Boolean(enabled);
   if(!enabled){clearTimeout(bathyTimer);bathyTimer=null;bathymetry=bathyFailed?'UNAVAILABLE':'OFF';hybridVisibility(mode==='SATELLITE')}
   else if(mode==='SATELLITE'&&lastConfig)installHybrid(lastConfig);
   notify();
  }
  const api={select,applyPalette,setBathymetry,get snapshot(){return {mode,state,date,bathymetry,depth_contours:'DEPTH CONTOUR VECTOR SOURCE NOT AVAILABLE',attempted_dates:[...attempted],failure_reason:failureReason,failure_detail:failureDetail}},sourceId:SOURCE,layerId:LAYER};
  instances.set(map,api);return api;
 }
 return {attach,isSatelliteError,probeURL,probe};
})();
