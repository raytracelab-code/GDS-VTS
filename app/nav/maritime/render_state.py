from .models import Category, utcnow
from .area_controller import distance_bearing


LAYER_GROUPS = {
    'AIS Vessels': 'vessels', 'Offshore Installations': 'offshore', 'Aids to Navigation': 'aton',
    'Ports / Harbours': 'ports', 'Routes / TSS': 'routes', 'Anchorages': 'anchorages',
    'Restricted Areas': 'restricted', 'Subsea Infrastructure': 'subsea', 'Hazards': 'hazards',
    'Bathymetry': 'bathymetry', 'Nav Warnings': 'warnings', 'MetOcean': 'metocean',
}

from .malaysia_config import read_manifest
try:
    GIS_LAYERS = sorted(read_manifest()['layers'],key=lambda layer:layer.get('control_order',100))
except (OSError, ValueError, KeyError):
    GIS_LAYERS = []
GIS_GROUPS = {'Malaysia ' + layer['display_name']: layer['dataset_id'] for layer in GIS_LAYERS}
GIS_DEFAULTS = {'Malaysia ' + layer['display_name']: layer['default_visibility'] for layer in GIS_LAYERS}
LAYER_GROUPS.update(GIS_GROUPS)


def empty():
    return {'type': 'FeatureCollection', 'features': []}


def build_render_state(service):
    geojson = {str(c): empty() for c in Category}
    geojson['selection'] = empty()
    objects, counts = [], {str(c): 0 for c in Category}
    if service is None:
        return dict(objects=[],counts=counts,sources={},selected_object_id=None,
                    visibility={str(c):True for c in Category},geojson=geojson,area=None)
    now = service.clock()
    duplicates = service.offshore_duplicates()
    for key in service.gis_layers:
        geojson[key] = empty()
    for obj in sorted(service.render_snapshot(), key=lambda o: o.object_id):
        category = str(obj.category)
        counts[category] += 1
        if obj.object_id in duplicates:
            continue
        # Hidden GIS drawings stay indexed and in the canonical service, but
        # their potentially dense coordinates need not cross QWebChannel.
        if obj.properties.get('gis_layer') and not service.object_visible(obj):
            continue
        item = obj.payload(now)
        if service.own_position and obj.object_id == service.selected_object_id and obj.geometry['type'] == 'Point':
            lon, lat = obj.geometry['coordinates'][:2]
            item['distance_nm'], item['bearing_deg'] = distance_bearing(*service.own_position, lat, lon)
        objects.append(item)
        props = obj.properties
        def direction(value):
            return isinstance(value,(int,float)) and not isinstance(value,bool) and 0 <= value < 360
        heading, cog = props.get('heading'), props.get('cog')
        rotation = heading if direction(heading) else cog if direction(cog) else 0
        feature = dict(type='Feature', id=obj.object_id, geometry=item['geometry'], properties={
            'object_id': obj.object_id, 'category': category, 'object_type': obj.object_type,
            'name': props.get('name') or props.get('mmsi') or obj.source_id or obj.object_id,
            'rotation': rotation, 'oriented': direction(heading) or direction(cog),
            'status': obj.status, 'ship_type': props.get('ship_type', 'other')})
        layer_key = props.get('gis_layer', category)
        feature['properties']['gis_layer'] = props.get('gis_layer', '')
        if service.object_visible(obj):
            geojson[layer_key]['features'].append(feature)
            if category=='metocean' and props.get('current_knots',0)>0 and direction(heading) and obj.geometry['type']=='Point':
                from app.nav.render_geometry import vector_geojson
                from app.nav.track_manager import destination_point
                lon,lat=obj.geometry['coordinates'][:2]
                vector=vector_geojson(lat,lon,heading,min(1.5,.35*props['current_knots']))
                start,end=vector['geometry']['coordinates']
                wings=[destination_point(end[1],end[0],heading+offset,.1) for offset in (150,210)]
                flow={'type':'MultiLineString','coordinates':[[start,end]]+[[end,[p[1],p[0]]] for p in wings]}
                geojson[category]['features'].append({**feature,'id':obj.object_id+'/flow','geometry':flow})
            if obj.object_id == service.selected_object_id:
                geojson['selection']['features'].append(feature)
    return dict(objects=objects, counts=counts, sources={k: v.payload(now) for k, v in service.sources.items()},
                selected_object_id=service.selected_object_id, visibility=dict(service.visibility), geojson=geojson,
                area=service.area.payload() if service.area else None, reference_layers=dict(service.reference_layers),
                gis_layers=list(service.gis_layers.values()), gis_dataset=dict(service.gis_dataset))
