/* Development provider only; operational geometry arrives from Python. */
const provider={style:'https://tiles.openfreemap.org/styles/liberty'},status=document.getElementById('map-status'),empty={type:'FeatureCollection',features:[]};
let offlineConfig=null,latestPalette=null,initialRegionFramed=false;
let map,marker,bridge,ready=false,latestRenderState=null,latestSpatialState=null,latestSelection=null,followEnabled=false;
const visibility={Vessel:true,Track:true,'Heading / COG':true,'Site Boundary':true,Pipelines:true,'Anchor Pattern':true,'Survey Areas':true,'Operational Zones':true};
const setStatus=t=>status.textContent=t;
let latestEventState=null;
const eventSourceKeys={current:'squall-current',direction:'squall-direction',trajectories:'squall-trajectories',impact_zones:'squall-impact-zones',surveillance_zones:'squall-surveillance-zones',prediction_points:'squall-prediction-points',selection:'squall-selection'};
const eventLayerIds=[];
function ensureEventLayers(){
 Object.values(eventSourceKeys).forEach(id=>{if(!map.getSource(id))map.addSource(id,{type:'geojson',data:empty})});
 const color=['match',['coalesce',['get','severity'],'unknown'],'critical','#b7463e','high','#c77b35','moderate','#b79048','#7f8d9e'];
 const opacity=['case',['==',['get','status'],'STALE'],.35,.9];
 const polygon=['==',['geometry-type'],'Polygon'],line=['==',['geometry-type'],'LineString'],point=['==',['geometry-type'],'Point'];
 const add=(id,type,source,paint,filter,layout)=>{if(!eventLayerIds.includes(id))eventLayerIds.push(id);if(!map.getLayer(id)){const layer={id,type,source,paint};if(filter)layer.filter=filter;if(layout)layer.layout=layout;map.addLayer(layer)}};
 for(const [id,alpha,width] of [['squall-surveillance-zones',.045,1],['squall-impact-zones',.12,2]]){
  add(id+'-fill','fill',id,{'fill-color':color,'fill-opacity':['case',['==',['get','status'],'STALE'],alpha/2,alpha]},polygon);
  add(id+'-outline','line',id,{'line-color':color,'line-width':width,'line-opacity':opacity},polygon);
 }
 add('squall-trajectories','line','squall-trajectories',{'line-color':color,'line-width':3,'line-dasharray':[3,2],'line-opacity':opacity},line);
 add('squall-direction','line','squall-direction',{'line-color':'#0f2440','line-width':2,'line-opacity':opacity},line);
 add('squall-prediction-points','circle','squall-prediction-points',{'circle-color':color,'circle-radius':4,'circle-opacity':opacity,'circle-stroke-color':'#fff','circle-stroke-width':1},point);
 add('squall-eta','symbol','squall-prediction-points',{'text-color':'#0f2440','text-halo-color':'#fff','text-halo-width':1},point,{'text-field':['coalesce',['get','eta_label'],''],'text-font':['KlokanTech Noto Sans Regular'],'text-size':11,'text-offset':[0,1.3],'text-allow-overlap':false});
 add('squall-current','circle','squall-current',{'circle-radius':8,'circle-color':color,'circle-opacity':opacity,'circle-stroke-color':['case',['==',['get','impact_state'],'IMPACT'],'#0a1628','#fff'],'circle-stroke-width':['case',['==',['get','impact_state'],'IMPACT'],3,2]},point);
 add('squall-selection-outline','line','squall-selection',{'line-color':'#d9b26f','line-width':3},polygon);
 add('squall-selection-line','line','squall-selection',{'line-color':'#d9b26f','line-width':4,'line-dasharray':[3,2]},line);
 add('squall-selection-point','circle','squall-selection',{'circle-radius':12,'circle-color':'#d9b26f','circle-opacity':.15,'circle-stroke-color':'#d9b26f','circle-stroke-width':3},point);
 eventLayerIds.forEach(id=>map.setLayoutProperty(id,'visibility',visibility['Squall Alerts']===false?'none':'visible'));
}
function applyEventState(payload){latestEventState=payload;if(!ready||!map.getSource('track'))return;ensureEventLayers();Object.entries(eventSourceKeys).forEach(([key,id])=>setSource(id,payload&&payload.geojson&&payload.geojson[key]||empty,'event '+key));console.info(`NAV events updated count=${payload&&payload.active_count||0}`)}
const eventHitPriority=['squall-current','squall-trajectories','squall-impact-zones-fill','squall-impact-zones-outline','squall-surveillance-zones-fill','squall-surveillance-zones-outline'];
function pickEvent(point){const layers=eventHitPriority.filter(id=>map.getLayer(id));if(!layers.length)return null;return map.queryRenderedFeatures(point,{layers}).filter(f=>f.properties&&f.properties.event_id).sort((a,b)=>eventHitPriority.indexOf(a.layer.id)-eventHitPriority.indexOf(b.layer.id)||String(a.properties.event_id).localeCompare(String(b.properties.event_id)))[0]}
function handleMapClick(e){
 if(!bridge)return;
 const event=pickEvent(e.point),world=pickMaritime(e.point),spatial=pickSpatialFeature(e.point),cluster=pickWellCluster(e.point);
 if(event&&event.layer.id==='squall-current'){bridge.selectEvent(String(event.properties.event_id));return}
 if(world&&(!spatial||maritimeHitPriority(world)<8)&&(!cluster||maritimeHitPriority(world)<8)){bridge.selectMaritimeObject(String(world.properties.object_id));return}
 if(event){bridge.selectEvent(String(event.properties.event_id));return}
 if(spatial){bridge.selectSpatialFeature(spatial.category,String(spatial.feature.properties.feature_id));return}
 if(cluster){if(bridge.clearMaritimeSelection)bridge.clearMaritimeSelection();bridge.clearEventSelection();bridge.clearSpatialFeature();map.easeTo({center:cluster.geometry.coordinates,zoom:Math.min(13,map.getZoom()+2)});return}
 if(world){bridge.selectMaritimeObject(String(world.properties.object_id));return}
 if(bridge.clearMaritimeSelection)bridge.clearMaritimeSelection();bridge.clearEventSelection();bridge.clearSpatialFeature();
}
function handleMapHover(e){map.getCanvas().style.cursor=pickEvent(e.point)||pickMaritime(e.point)||pickSpatialFeature(e.point)||pickWellCluster(e.point)?'pointer':''}
function setSource(id,data,label){const s=map&&map.getSource(id);if(s){s.setData(data||empty);console.info(`NAV ${label} updated`)}}
function applyRenderState(p){latestRenderState=p;if(!ready||!p)return;setSource('track',p.track,'track');setSource('track-start',p.start,'START');setSource('heading-vector',p.heading,'heading');setSource('cog-vector',p.cog,'COG')}
function ensureSpatialLayers(){const polygon=['==',['geometry-type'],'Polygon'],line=['==',['geometry-type'],'LineString'],point=['==',['geometry-type'],'Point'];const specs=[['site-boundary','#315a7d','#18344f'],['pipelines','#5f738b','#d5a45b'],['anchor-patterns','#319b91','#176c68'],['survey-areas','#6d7890','#536274'],['operational-zones','#9b7a46','#75552f']];specs.forEach(([id,fill,stroke])=>{if(!map.getSource(id))map.addSource(id,{type:'geojson',data:empty});if(!map.getLayer(`${id}-fill`)){map.addLayer({id:`${id}-fill`,type:'fill',source:id,filter:polygon,paint:{'fill-color':fill,'fill-opacity':id==='operational-zones'?.22:.18}});map.addLayer({id:`${id}-line`,type:'line',source:id,filter:line,paint:{'line-color':stroke,'line-width':id==='pipelines'?5:id==='anchor-patterns'?4:3}});map.addLayer({id:`${id}-outline`,type:'line',source:id,filter:polygon,paint:{'line-color':stroke,'line-width':3}});if(id==='anchor-patterns')map.addLayer({id:`${id}-point`,type:'circle',source:id,filter:point,paint:{'circle-radius':8,'circle-color':fill,'circle-stroke-color':'#fff','circle-stroke-width':2}})}});if(!map.getSource('spatial-selection'))map.addSource('spatial-selection',{type:'geojson',data:empty});if(!map.getLayer('spatial-selection-fill')){map.addLayer({id:'spatial-selection-fill',type:'fill',source:'spatial-selection',filter:polygon,paint:{'fill-color':'#d9b26f','fill-opacity':.20}});map.addLayer({id:'spatial-selection-outline',type:'line',source:'spatial-selection',filter:polygon,paint:{'line-color':'#d9b26f','line-width':3}});map.addLayer({id:'spatial-selection-line',type:'line',source:'spatial-selection',filter:line,paint:{'line-color':'#d9b26f','line-width':5}});map.addLayer({id:'spatial-selection-point',type:'circle',source:'spatial-selection',filter:point,paint:{'circle-radius':9,'circle-color':'#d9b26f','circle-opacity':.8,'circle-stroke-color':'#fff','circle-stroke-width':2}})}}
function applySpatialState(p){latestSpatialState=p;if(!ready||!p)return;ensureSpatialLayers();[['site-boundary','siteBoundary'],['pipelines','pipelines'],['anchor-patterns','anchorPatterns'],['survey-areas','surveyAreas'],['operational-zones','operationalZones']].forEach(([id,key])=>setSource(id,p[key],id));Object.entries(visibility).forEach(([g,v])=>setLayerVisibility(g,v));updateSpatialViewHint()}
let spatialOutOfView=null;
function spatialPoints(){return Object.values(latestSpatialState||{}).filter(v=>v&&v.features).flatMap(v=>v.features).flatMap(f=>pointsOf(f.geometry))}
function updateSpatialViewHint(){if(!map||!bridge)return;const points=spatialPoints(),bounds=map.getBounds();let out=false;if(points.length){const west=Math.min(...points.map(p=>p[0])),east=Math.max(...points.map(p=>p[0])),south=Math.min(...points.map(p=>p[1])),north=Math.max(...points.map(p=>p[1]));out=east<bounds.getWest()||west>bounds.getEast()||north<bounds.getSouth()||south>bounds.getNorth()}if(out!==spatialOutOfView){spatialOutOfView=out;bridge.reportSpatialView(out)}}
function applySpatialSelection(p){latestSelection=p;const geometry=p&&p.geometry;const points=pointsOf(geometry);const valid=points.every(point=>Number.isFinite(point[0])&&Number.isFinite(point[1]));console.info(`NAV selection updated category=${p&&p.category||'none'} feature_id=${p&&p.feature_id||'none'} geometry=${geometry&&geometry.type||'none'} finite_coordinates=${valid}`);if(ready)setSource('spatial-selection',geometry&&valid?{type:'Feature',properties:{},geometry}:empty,'selection')}
const selectableLayers=['site-boundary-fill','site-boundary-line','pipelines-line','anchor-patterns-fill','anchor-patterns-line','anchor-patterns-point','survey-areas-fill','survey-areas-line','operational-zones-fill','operational-zones-line'];
const layerCategory={'site-boundary-fill':'site-boundary','site-boundary-line':'site-boundary','pipelines-line':'pipeline','anchor-patterns-fill':'anchor-pattern','anchor-patterns-line':'anchor-pattern','anchor-patterns-point':'anchor-pattern','survey-areas-fill':'survey-area','survey-areas-line':'survey-area','operational-zones-fill':'operational-zone','operational-zones-line':'operational-zone'},selectionPriority={'operational-zone':0,'anchor-pattern':1,pipeline:2,'survey-area':3,'site-boundary':4};
function pickSpatialFeature(point){const candidates=map.queryRenderedFeatures(point,{layers:selectableLayers}).map(f=>({feature:f,category:layerCategory[f.layer.id]||f.properties.category})).filter(x=>x.category&&x.feature.properties&&x.feature.properties.feature_id);candidates.sort((a,b)=>(selectionPriority[a.category]??99)-(selectionPriority[b.category]??99)||String(a.feature.properties.feature_id).localeCompare(String(b.feature.properties.feature_id)));return candidates[0]}
function createMap(){map=new maplibregl.Map({container:'map',style:offlineConfig&&(offlineConfig.installed||!offlineConfig.allow_online_fallback)?offlineConfig.style:provider.style,...(offlineConfig&&offlineConfig.initial_bounds?{bounds:offlineConfig.initial_bounds,fitBoundsOptions:{padding:25,maxZoom:7}}:{center:[90.3563,22.3569],zoom:6}),bearing:0,pitch:0});if(typeof GdsOffline!=='undefined')GdsOffline.attach(map);map.addControl(new maplibregl.NavigationControl(),'top-right');map.on('style.load',()=>{map.addSource('track',{type:'geojson',data:{type:'Feature',properties:{},geometry:{type:'MultiLineString',coordinates:[]}}});map.addLayer({id:'track',type:'line',source:'track',paint:{'line-color':'#1e3a5f','line-width':3}});[['heading-vector','#1e3a5f'],['cog-vector','#14b8a6',[2,2]]].forEach(([id,color,dash])=>{map.addSource(id,{type:'geojson',data:empty});const paint={'line-color':color,'line-width':3};if(dash)paint['line-dasharray']=dash;map.addLayer({id,type:'line',source:id,paint})});map.addSource('track-start',{type:'geojson',data:empty});map.addLayer({id:'track-start',type:'circle',source:'track-start',paint:{'circle-radius':6,'circle-color':'#2dd4bf','circle-stroke-color':'#fff','circle-stroke-width':2}});ready=true;ensureSpatialLayers();Object.keys(layerCategory).concat(['site-boundary-outline','anchor-patterns-outline','survey-areas-outline','operational-zones-outline']).forEach(id=>{if(map.getLayer(id))map.moveLayer(id,'track')});ensureMaritimeLayers();if(applyMaritimeState(latestMaritimeState))return;ensureEventLayers();applyEventState(latestEventState);Object.entries(visibility).forEach(([g,v])=>setLayerVisibility(g,v));applyRenderState(latestRenderState);applySpatialState(latestSpatialState);applySpatialSelection(latestSelection);setStatus(offlineConfig?(offlineConfig.installed?offlineConfig.status:offlineConfig.allow_online_fallback?'ONLINE DEVELOPMENT FALLBACK / OFFLINE MAP NOT INSTALLED':'OFFLINE MAP NOT INSTALLED'):'Marine situational map / development provider');if(typeof GdsOffline!=='undefined'&&latestPalette)GdsOffline.apply(map,latestPalette);map.on('moveend',reportPaletteCenter);reportPaletteCenter();if(offlineConfig&&offlineConfig.installed&&offlineConfig.map_view==='SATELLITE')navMap.command('SATELLITE');map.off('click',handleMapClick);map.on('click',handleMapClick);map.off('mousemove',handleMapHover);map.on('mousemove',handleMapHover);map.off('moveend',updateSpatialViewHint);map.on('moveend',updateSpatialViewHint);map.off('moveend',reportMaritimeView);map.on('moveend',reportMaritimeView);if(!latestMaritimeState||!latestMaritimeState.area)reportMaritimeView()});map.on('error',e=>{if(e.sourceId&&e.sourceId.startsWith('offline-')){console.warn('NAV offline tile unavailable',e.sourceId);setStatus('Offline map tile unavailable / operational overlays active');return}if(e.sourceId&&e.sourceId.startsWith('reference-')){if(bridge&&bridge.reportReferenceError)bridge.reportReferenceError(Object.keys(latestMaritimeState&&latestMaritimeState.reference_layers||{}).find(key=>e.sourceId==='reference-'+key||e.sourceId.startsWith('reference-'+key+'-'))||e.sourceId.slice(10));console.warn('NAV reference source unavailable',e.sourceId);return}console.error('NAV map error',e.error&&e.error.message||String(e.error));setStatus('Map unavailable')})}
function setLayerVisibility(group,visible){visibility[group]=Boolean(visible);if(group==='Bathymetry'&&offlineConfig)for(const l of offlineConfig.style.layers)if(l.metadata&&l.metadata['gds:owner']==='bathymetry'&&map&&map.getLayer(l.id))map.setLayoutProperty(l.id,'visibility',visible?'visible':'none');if(group.startsWith('Malaysia ')){applyMalaysiaVisibility();return}if(maritimeGroups[group]){applyMaritimeVisibility();if(latestMaritimeState)applyReferenceLayers(latestMaritimeState.reference_layers||{});return}if(group==='Squall Alerts'){eventLayerIds.forEach(id=>{if(map&&map.getLayer(id))map.setLayoutProperty(id,'visibility',visible?'visible':'none')});return}const layers={Vessel:[],Track:['track','track-start'],'Heading / COG':['heading-vector','cog-vector'],'Site Boundary':['site-boundary-fill','site-boundary-line','site-boundary-outline'],Pipelines:['pipelines-fill','pipelines-line','pipelines-outline'],'Anchor Pattern':['anchor-patterns-fill','anchor-patterns-line','anchor-patterns-outline','anchor-patterns-point'],'Survey Areas':['survey-areas-fill','survey-areas-line','survey-areas-outline'],'Operational Zones':['operational-zones-fill','operational-zones-line','operational-zones-outline']}[group]||[];if(group==='Vessel'&&marker)marker.getElement().style.display=visible?'':'none';layers.forEach(id=>{if(map&&map.getLayer(id))map.setLayoutProperty(id,'visibility',visible?'visible':'none')})}
function pointsOf(geometry){const result=[];const walk=x=>{if(Array.isArray(x)&&x.length>=2&&Number.isFinite(x[0])&&Number.isFinite(x[1]))result.push(x);else if(Array.isArray(x))x.forEach(walk)};walk(geometry&&geometry.coordinates);return result}
function fit(points){if(points.length===1)map.easeTo({center:points[0],zoom:14});else if(points.length>1)map.fitBounds(points.reduce((b,p)=>b.extend(p),new maplibregl.LngLatBounds(points[0],points[0])),{padding:60,maxZoom:14})}
function authoritativePoints(){return pointsOf(latestRenderState&&latestRenderState.track&&latestRenderState.track.geometry)}
window.navMap={showMaritimeObject(){if(map&&latestMaritimeState)fit((latestMaritimeState.geojson.selection.features||[]).flatMap(f=>pointsOf(f.geometry)))},command(name){if(!map)return;if(name==='NORTH UP')map.easeTo({bearing:0});if(name==='2D')map.easeTo({pitch:0,bearing:0});if(name==='3D')map.easeTo({pitch:55});if(name==='CENTER VESSEL'&&marker)map.easeTo({center:marker.getLngLat()});if(name==='FIT TRACK')fit(authoritativePoints());if(name==='FIT MALAYSIA GIS'){const b=latestMaritimeState&&latestMaritimeState.gis_dataset&&latestMaritimeState.gis_dataset.bounds;if(b)fit([[b[0],b[1]],[b[2],b[3]]])}if(name==='FIT SPATIAL DATA'){const points=spatialPoints();console.info('SPATIAL FIT JS received');if(points.length){const west=Math.min(...points.map(p=>p[0])),south=Math.min(...points.map(p=>p[1])),east=Math.max(...points.map(p=>p[0])),north=Math.max(...points.map(p=>p[1]));console.info(`SPATIAL FIT applied ${west},${south},${east},${north}`);fit(points)}}if(name==='SATELLITE'||name==='MARINE'){if(offlineConfig)offlineConfig.map_view=name;if(bridge&&bridge.setMapView)bridge.setMapView(name);const layers=offlineConfig&&offlineConfig.style&&offlineConfig.style.layers.filter(l=>l.metadata&&l.metadata['gds:owner']==='satellite')||[];layers.forEach(l=>map.setLayoutProperty(l.id,'visibility',name==='SATELLITE'?'visible':'none'));setStatus(name==='SATELLITE'&&!layers.length?'Offline satellite imagery is not installed':offlineConfig?offlineConfig.status:'Marine situational map ? development provider')}},showEvent(){if(map&&latestEventState&&latestEventState.geojson)fit(Object.entries(latestEventState.geojson).filter(([key])=>key!=='selection').flatMap(([,collection])=>collection.features).filter(f=>f.properties.event_id===latestEventState.selected_event_id).flatMap(f=>pointsOf(f.geometry)))},zoomToSelectedFeature(){if(map&&latestSelection)fit(pointsOf(latestSelection.geometry))},setLayerVisibility,setFollow(e){followEnabled=Boolean(e)},update(data){if(!map||data.latitude===undefined)return;const point=[data.longitude,data.latitude];if(!marker){const el=document.createElement('div');el.className='vessel';el.addEventListener('click',e=>e.stopPropagation());el.innerHTML='<svg width="28" height="42" viewBox="0 0 28 42"><path d="M14 1 L27 39 L14 33 L1 39 Z" fill="#1e3a5f" stroke="white" stroke-width="2"/></svg>';marker=new maplibregl.Marker({element:el,rotationAlignment:'map'}).setLngLat(point).addTo(map);setLayerVisibility('Vessel',visibility.Vessel)}else marker.setLngLat(point);marker.setRotation(data.heading||0);if(followEnabled)map.easeTo({center:point})}};
document.addEventListener('DOMContentLoaded',()=>{if(window.qt&&window.QWebChannel)new QWebChannel(qt.webChannelTransport,c=>{bridge=c.objects.bridge;if(bridge.getOfflineMapConfig){bridge.getOfflineMapConfig(config=>{offlineConfig=config;createMap()});bridge.paletteChanged.connect(applyPalette);bridge.getPalette(applyPalette)}else createMap();bridge.telemetryChanged.connect(navMap.update);bridge.renderStateChanged.connect(applyRenderState);bridge.spatialStateChanged.connect(applySpatialState);bridge.selectedSpatialFeatureChanged.connect(applySpatialSelection);bridge.maritimeStateChanged.connect(applyMaritimeState);bridge.getMaritimeState(applyMaritimeState);bridge.eventStateChanged.connect(applyEventState);bridge.getEventState(applyEventState);bridge.mapReady()});else {offlineConfig={installed:false,allow_online_fallback:false,style:{version:8,sources:{},layers:[{id:'offline-background',type:'background',paint:{'background-color':'#cddfe3'},metadata:{'gds:owner':'basemap'}}]}};createMap()}});

// Maritime-world data is distinct from project overlays and Squall events.
let latestMaritimeState=null;
const maritimeGroups={'AIS Vessels':'vessels','Offshore Installations':'offshore','Aids to Navigation':'aton','Ports / Harbours':'ports','Routes / TSS':'routes','Anchorages':'anchorages','Restricted Areas':'restricted','Subsea Infrastructure':'subsea','Hazards':'hazards','Bathymetry':'bathymetry','Nav Warnings':'warnings','MetOcean':'metocean'};
const maritimePriority={vessels:3,warnings:4,offshore:5,aton:6,hazards:7,routes:9,restricted:9,anchorages:9,ports:10,bathymetry:10,subsea:10,metocean:10};
const maritimeLayers=[],maritimeSourceData=new WeakMap();
function maritimeCategories(){
 const gis=new Set((latestMaritimeState&&latestMaritimeState.gis_layers||[]).map(l=>l.dataset_id));
 return [...new Set([...Object.values(maritimeGroups),...Object.keys(latestMaritimeState&&latestMaritimeState.geojson||{}),'selection'])].filter(k=>!gis.has(k));
}
let referenceStyleURL=null;
const referenceIds=new Set();
function addMaritimeIcons(){
 if(!map.hasImage)return;
 for(const kind of ['vessel','neutral','platform','aton','hazard']){
  const name='maritime-'+kind;if(map.hasImage(name))continue;
  const size=32,data=new Uint8Array(size*size*4);
  // A light deck, derrick, legs and crane boom, defined as vector segments.
  const rig=[[5,19,27,19],[8,19,7,27],[24,19,25,27],[12,19,16,5],[16,5,20,19],[13,14,19,14],[14,10,18,10],[16,5,26,10],[26,10,26,14]];
  const nearSegment=(x,y,[a,b,c,d])=>{const dx=c-a,dy=d-b,t=Math.max(0,Math.min(1,((x-a)*dx+(y-b)*dy)/(dx*dx+dy*dy)));return Math.hypot(x-a-t*dx,y-b-t*dy)<1.15};
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
   const dx=x-16,dy=y-16;
   const inside=kind==='vessel'?((y>=2&&y<28&&Math.abs(dx)<=Math.min(9,(y-2)*.5))&&!(y>23&&Math.abs(dx)<(y-23)*1.1)):
    kind==='platform'?rig.some(segment=>nearSegment(x,y,segment)):
    kind==='aton'?(Math.abs(dx)/7+Math.abs(dy)/13<=1):
    kind==='hazard'?(Math.abs(dx-dy)<3||Math.abs(dx+dy)<3)&&Math.abs(dx)<11&&Math.abs(dy)<11:dx*dx+dy*dy<=70;
   if(inside){const i=(y*size+x)*4;data[i]=245;data[i+1]=245;data[i+2]=245;data[i+3]=255}
  }
  try{map.addImage(name,{width:size,height:size,data},{sdf:true})}catch(error){console.warn('NAV maritime icon unavailable',name)}
 }
}
function ensureMaritimeLayers(){
 addMaritimeIcons();
 const point=['==',['geometry-type'],'Point'],line=['==',['geometry-type'],'LineString'],poly=['==',['geometry-type'],'Polygon'];
 const colors={vessels:'#42566b',offshore:'#4f6472',aton:'#287c73',ports:'#607b87',routes:'#76647b',anchorages:'#526c88',restricted:'#aa7754',subsea:'#7b6d85',hazards:'#a46f50',bathymetry:'#6696ac',warnings:'#ae6c4c',metocean:'#508f9a'};
 const add=(category,suffix,type,paint,filter,layout)=>{
  const id='maritime-'+category+'-'+suffix;
  if(!maritimeLayers.some(l=>l.id===id))maritimeLayers.push({id,category});
  if(!map.getLayer(id)){const layer={id,type,source:'maritime-'+category,paint,filter};if(layout)layer.layout=layout;map.addLayer(layer,category==='selection'?undefined:'track')}
 };
 for(const category of maritimeCategories()){
  const source='maritime-'+category;if(!map.getSource(source))map.addSource(source,{type:'geojson',data:empty});
  const selected=category==='selection',color=selected?'#b58a42':colors[category]||'#758895';
  const alpha=selected?.95:['case',['==',['get','status'],'STALE'],.35,.85];
  add(category,'fill','fill',{'fill-color':color,'fill-opacity':selected?.12:.07},poly);
  add(category,'outline','line',{'line-color':color,'line-width':selected?3:1.5,'line-opacity':alpha},poly);
  add(category,'line','line',{'line-color':color,'line-width':selected?4:2,'line-opacity':alpha,...(category==='subsea'?{'line-dasharray':[5,2]}:{})},category==='subsea'?['all',line,['!=',['get','object_type'],'submarine_cable']]:line);
  if(category==='subsea')add(category,'cable','line',{'line-color':color,'line-width':2,'line-dasharray':[1,2]},['all',line,['==',['get','object_type'],'submarine_cable']]);
  if(selected){
   add(category,'point','circle',{'circle-radius':11,'circle-color':color,'circle-opacity':.1,'circle-stroke-color':color,'circle-stroke-width':2},point);
   add(category,'installation','symbol',{'icon-color':'#264d65','icon-halo-color':'#fff','icon-halo-width':1},['all',point,['==',['get','category'],'offshore']],{'icon-image':'maritime-platform','icon-size':.73,'icon-allow-overlap':true});continue
  }
  // Independent of sprites/SDF registration; real targets retain a visible core.
  add(category,'fallback','circle',{'circle-radius':3.5,'circle-color':color,'circle-opacity':alpha,'circle-stroke-color':'#fff','circle-stroke-width':1},point);
  add(category,'point','symbol',{'icon-color':color,'icon-opacity':alpha,'icon-halo-color':'#fff','icon-halo-width':1},point,{
   'icon-image':['match',['get','category'],'vessels',['case',['==',['get','oriented'],true],'maritime-vessel','maritime-neutral'],'offshore','maritime-platform','aton','maritime-aton','hazards','maritime-hazard','maritime-neutral'],
   'icon-size':['interpolate',['linear'],['zoom'],5,['case',['==',['get','category'],'offshore'],.45,.8],13,['case',['==',['get','category'],'offshore'],.64,.8]],'icon-rotate':['number',['get','rotation'],0],'icon-rotation-alignment':'map','icon-allow-overlap':true});
  add(category,'label','symbol',{'text-color':color,'text-halo-color':'#fff','text-halo-width':1},point,{
   'text-field':['step',['zoom'],'',10,['coalesce',['get','name'],'']],
   'text-font':['KlokanTech Noto Sans Regular'],'text-size':11,'text-offset':[0,1.7],'text-allow-overlap':false});
 }
 applyMaritimeVisibility();
}
function applyMaritimeVisibility(){
 const selected=latestMaritimeState&&latestMaritimeState.objects.find(o=>o.object_id===latestMaritimeState.selected_object_id);
 for(const layer of maritimeLayers){
  const category=layer.category==='selection'&&selected?selected.category:layer.category;
  const group=Object.keys(maritimeGroups).find(g=>maritimeGroups[g]===category);
  const visible=visibility[group]!==false&&(!latestMaritimeState||latestMaritimeState.visibility[category]!==false);
  if(map&&map.getLayer(layer.id))map.setLayoutProperty(layer.id,'visibility',visible?'visible':'none');
 }
 applyMalaysiaVisibility();
}
function applyMaritimeState(payload){
 latestMaritimeState=payload;if(!ready||!payload)return;if(applyReferenceLayers(payload.reference_layers||{}))return true;ensureMaritimeLayers();
 for(const key of maritimeCategories()){const source=map.getSource('maritime-'+key);if(source){const data=payload.geojson[key]||empty,signature=JSON.stringify(data);if(maritimeSourceData.get(source)!==signature){source.setData(data);maritimeSourceData.set(source,signature)}}}
 ensureMalaysiaLayers(payload);
 applyMaritimeVisibility();
}
function pickMaritime(point){
 const layers=maritimeLayers.filter(l=>l.category!=='selection'&&map.getLayer(l.id)).map(l=>l.id).concat(malaysiaLayers.filter(l=>map.getLayer(l.id)).map(l=>l.id));
 if(!layers.length)return null;
 return map.queryRenderedFeatures([[point.x-5,point.y-5],[point.x+5,point.y+5]],{layers}).filter(f=>f.properties&&f.properties.object_id).sort((a,b)=>maritimeHitPriority(a)-maritimeHitPriority(b)||String(a.properties.object_id).localeCompare(String(b.properties.object_id)))[0];
}

// Layer semantics, defaults and colors arrive from the Python manifest contract.
// Each dataset has one source, independent of its feature count.
const malaysiaLayers=[];
function maritimeHitPriority(feature){
 const layer=latestMaritimeState&&(latestMaritimeState.gis_layers||[]).find(l=>l.dataset_id===feature.properties.gis_layer);
 return layer?layer.selection_priority:(maritimePriority[feature.properties.category]??99);
}
function ensureMalaysiaLayers(payload){
 const before=map.getLayer('site-boundary-fill')?'site-boundary-fill':'track';
 for(const layer of payload.gis_layers||[]){
  const key=layer.dataset_id,source='gis-'+key,kind=layer.style_class;
  const palette={platform:'#506d7e',pipeline:'#78818a',well:'#718a95',field:'#718c86',production:'#77948a',block:'#899399',basin:'#93a2a6',survey:'#93a2a6'};
  const color=palette[kind]||layer.color,reference=['basin','survey','block'].includes(kind);
  if(!map.getSource(source))map.addSource(source,{type:'geojson',data:empty,...(kind==='well'?{cluster:true,clusterRadius:32,clusterMaxZoom:12}:{})});
  const add=(suffix,type,paint,filter,layout,minzoom=layer.minimum_zoom)=>{
   const id=source+'-'+suffix;
   if(!malaysiaLayers.some(l=>l.id===id))malaysiaLayers.push({id,key});
   if(!map.getLayer(id))map.addLayer({id,type,source,minzoom,paint,filter,...(layout?{layout}:{})},before);
  };
  const point=kind==='well'?['all',['==',['geometry-type'],'Point'],['!', ['has','point_count']]]:['==',['geometry-type'],'Point'];
  const poly=['==',['geometry-type'],'Polygon'],line=['==',['geometry-type'],'LineString'];
  add('fill','fill',{'fill-color':color,'fill-opacity':reference?.006:['interpolate',['linear'],['zoom'],6,0,10,.014,14,.032]},poly);
  add('boundary','line',{'line-color':color,'line-width':reference?.45:['interpolate',['linear'],['zoom'],6,.45,13,.75], 'line-opacity':reference?.24:kind==='production'?.27:.38},poly);
  add('line','line',{'line-color':color,'line-width':kind==='pipeline'?['interpolate',['linear'],['zoom'],6,.65,11,1.05,16,1.4]:.7,'line-opacity':kind==='pipeline'?.57:.4,...(kind==='pipeline'?{'line-dasharray':[3,2]}:{})},line);
  if(kind==='platform'){
   // Keep the icon and its optional label in one collision placement, so a
   // close-zoom name cannot displace its own installation symbol.
   add('point','symbol',{'icon-color':color,'icon-opacity':['interpolate',['linear'],['zoom'],6,.55,10,.82,14,.9],'icon-halo-color':'#fff','icon-halo-width':.65,'text-color':color,'text-halo-color':'#fff','text-halo-width':1},point,{
    'icon-image':'maritime-platform','icon-size':['interpolate',['linear'],['zoom'],6,.46,10,.58,15,.68],'icon-allow-overlap':false,
    'text-field':['step',['zoom'],'',Math.max(11,layer.label_zoom),['coalesce',['get','name'],'']],
    'text-font':['KlokanTech Noto Sans Regular'],'text-size':10,'text-offset':[0,1.5],'text-allow-overlap':false,'text-optional':true});
  }else{
   add('point','circle',{'circle-radius':kind==='well'?2:1.7,'circle-color':color,'circle-opacity':.75,'circle-stroke-color':'#fff','circle-stroke-width':.6},point);
  }
  if(kind==='well'){
   const cluster=['has','point_count'];
   add('clusters','circle',{'circle-color':color,'circle-opacity':.45,'circle-radius':['step',['get','point_count'],7,25,9,100,12],'circle-stroke-color':'#fff','circle-stroke-width':1},cluster,null,9);
   add('cluster-count','symbol',{'text-color':'#29475a'},cluster,{'text-field':['get','point_count_abbreviated'],'text-font':['KlokanTech Noto Sans Regular'],'text-size':10,'text-allow-overlap':false},9);
  }
  if(kind!=='platform'&&layer.label_enabled!==false)add('label','symbol',{'text-color':color,'text-halo-color':'#fff','text-halo-width':1},kind==='well'||kind==='platform_detail'?point:poly,{
   'text-field':['coalesce',['get','name'],''],'text-font':['KlokanTech Noto Sans Regular'],'text-size':10,'text-offset':[0,1.5],'text-allow-overlap':false
  },kind==='well'?layer.label_zoom:Math.max(11,layer.label_zoom));
  const data=payload.geojson[key]||empty,src=map.getSource(source),signature=JSON.stringify(data);
  if(maritimeSourceData.get(src)!==signature){src.setData(data);maritimeSourceData.set(src,signature)}
 }
 applyMalaysiaVisibility();
}
function pickWellCluster(point){
 const layers=malaysiaLayers.filter(l=>l.id.endsWith('-clusters')&&map.getLayer(l.id)).map(l=>l.id);
 return layers.length?map.queryRenderedFeatures([[point.x-4,point.y-4],[point.x+4,point.y+4]],{layers}).find(f=>f.properties&&f.properties.cluster_id!==undefined):null;
}
function applyMalaysiaVisibility(){
 if(!latestMaritimeState)return;
 for(const {id,key} of malaysiaLayers){
  const layer=(latestMaritimeState.gis_layers||[]).find(l=>l.dataset_id===key);
  const show=layer&&latestMaritimeState.visibility[key]!==false&&latestMaritimeState.visibility[layer.canonical_category]!==false&&visibility['Malaysia '+layer.display_name]!==false;
  if(map&&map.getLayer(id))map.setLayoutProperty(id,'visibility',show?'visible':'none');
 }
}
function reportMaritimeView(e){
 // Programmatic moves (initial display, resize and operator commands) also
 // establish an area without own telemetry. Only automatic Follow is excluded.
 if(e&&!e.originalEvent&&followEnabled&&marker)return;
 if(!map||!bridge||!bridge.reportMaritimeViewport)return;
 const b=map.getBounds();const norm=x=>((x+180)%360+360)%360-180;
 if(b.getEast()-b.getWest()>=360)return;
 bridge.reportMaritimeViewport(norm(b.getWest()),Math.max(-90,b.getSouth()),norm(b.getEast()),Math.min(90,b.getNorth()));
}

function applyReferenceLayers(references){
 for(const [key,ref] of Object.entries(references)){
  if(offlineConfig&&(!offlineConfig.allow_online_fallback||offlineConfig.installed))continue;
  if(ref.kind==='overlay'){
   for(const [source,spec] of Object.entries(ref.sources||{})){const id='reference-'+key+'-'+source;if(!map.getSource(id))map.addSource(id,spec)}
   for(const layer of ref.layers||[]){const id='reference-'+key+'-'+layer.id;if(!map.getLayer(id))map.addLayer({...layer,id,source:'reference-'+key+'-'+layer.source},map.getLayer('site-boundary-fill')?'site-boundary-fill':'track');map.setLayoutProperty(id,'visibility',visibility[ref.group]===false?'none':'visible')}
   continue;
  }
  if(ref.kind==='style'&&ref.url!==referenceStyleURL){referenceStyleURL=ref.url;ready=false;map.setStyle(ref.url);return true}
  if(ref.kind!=='raster')continue;
  const id='reference-'+key;referenceIds.add(id);
  if(!map.getSource(id))map.addSource(id,{type:'raster',tiles:ref.tiles,tileSize:256,attribution:ref.attribution});
  // A raster can arrive after the local GIS sources. Keep it below those
  // existing layers as well as below project geometry.
  const anchor=malaysiaLayers.find(layer=>map.getLayer(layer.id));
  if(!map.getLayer(id))map.addLayer({id,type:'raster',source:id,paint:{'raster-opacity':ref.opacity}},anchor?anchor.id:map.getLayer('site-boundary-fill')?'site-boundary-fill':'track');
  map.setLayoutProperty(id,'visibility',visibility[ref.group]===false?'none':'visible');
 }
 return false;
}

function applyPalette(payload){latestPalette=payload;if(ready&&typeof GdsOffline!=='undefined')GdsOffline.apply(map,payload)}
function offlineCoverageAt(center,config=offlineConfig){
 if(!config||!config.installed)return null;
 const longitude=((center.lng+180)%360+360)%360-180;
 const coverage=config.coverage||[{bounds:config.bounds}];
 return coverage.some(({bounds:b})=>b&&b[0]<=longitude&&longitude<=b[2]&&b[1]<=center.lat&&center.lat<=b[3]);
}
function resizeMap(){
 if(!map||!map.resize)return;
 map.resize();
 if(offlineConfig&&offlineConfig.initial_bounds&&!initialRegionFramed){
  initialRegionFramed=true;
  map.fitBounds(offlineConfig.initial_bounds,{duration:0,padding:25,maxZoom:7});
 }
}
window.navMap.resize=resizeMap;
function reportPaletteCenter(){
 if(!map||!map.getCenter)return;
 const p=map.getCenter();
 if(bridge&&bridge.reportMapCenter)bridge.reportMapCenter(p.lat,((p.lng+180)%360+360)%360-180);
 const covered=offlineCoverageAt(p);
 if(covered!==null)setStatus(covered?offlineConfig.status:'Outside installed offline map coverage');
}
