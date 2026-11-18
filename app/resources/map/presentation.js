/* Geographic HUD only. Listens to camera events; never changes map state. */
const GdsMapHud=(()=>{
 const attached=new WeakMap();
 function attach(map){
  if(attached.has(map))return attached.get(map);
  const hud=document.createElement('section');hud.id='geographic-hud';hud.setAttribute('aria-label','Map coordinates and bearing');
  const compass=document.createElement('div');compass.className='hud-compass';
  const north=document.createElement('span');north.textContent='N';compass.appendChild(north);
  const needle=document.createElement('span');needle.className='compass-needle';needle.textContent='▲';compass.appendChild(needle);
  const coordinates=document.createElement('div');coordinates.className='hud-coordinates';
  const lat=document.createElement('div'),lon=document.createElement('div'),zoom=document.createElement('div');
  coordinates.appendChild(lat);coordinates.appendChild(lon);coordinates.appendChild(zoom);
  hud.appendChild(compass);hud.appendChild(coordinates);document.body.appendChild(hud);
  const update=()=>{
   const p=map.getCenter(),longitude=((p.lng+180)%360+360)%360-180,bearing=map.getBearing();
   lat.textContent='LAT  '+p.lat.toFixed(4)+'°';lon.textContent='LON  '+longitude.toFixed(4)+'°';zoom.textContent='ZOOM '+map.getZoom().toFixed(2);
   needle.style.transform=`rotate(${-bearing}deg)`;compass.setAttribute('aria-label','North · bearing '+bearing.toFixed(0)+' degrees');
  };
  map.on('move',update);map.on('rotate',update);update();
  map.addControl(new maplibregl.ScaleControl({maxWidth:100,unit:'nautical'}),'bottom-left');
  const result={hud,update};attached.set(map,result);
  map.on('remove',()=>hud.remove());return result;
 }
 return {attach};
})();
