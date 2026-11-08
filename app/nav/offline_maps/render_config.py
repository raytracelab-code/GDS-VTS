"""Local maritime style using a documented OpenMapTiles subset."""
import html
import json
import os
from .mbtiles import MBTiles, MIME
from .manager import safe_file
from .schemas import vector_schema, shortbread_layers


def source_priority(role, spec):
    """Draw overview, region, then overlapping details from broadest to finest."""
    w, s, e, n = spec['bounds']
    tier = 0 if role == 'overview' else 1 if role == 'basemap' else 2 if role.startswith('detail-') else 3 if role == 'bathymetry' else 4
    return tier, spec['maxzoom'], -(e-w)*(n-s), role


def render_config(package):
    allow_online = os.environ.get('GDS_MAP_ALLOW_ONLINE_FALLBACK', '').lower() in ('1', 'true', 'yes')
    style = {'version': 8, 'name': 'GDS Maritime offline',
             'glyphs': 'gds://map/assets/glyphs/{fontstack}/{range}.pbf',
             'sources': {}, 'layers': [{'id': 'offline-background', 'type': 'background', 'paint': {'background-color': '#e8e8df'}, 'metadata': {'gds:owner': 'basemap', 'gds:role': 'LAND'}}]}
    result = {'installed': bool(package), 'allow_online_fallback': allow_online,
              'status': 'OFFLINE MAP NOT INSTALLED', 'style': style, 'tiles': {}}
    if not package:
        return result
    m = package.manifest
    if any(name.startswith('glyphs/') for name in m.get('asset_files', [])):
        style['glyphs'] = 'gds://package/glyphs/{fontstack}/{range}.pbf'
    result.update(package_id=m['package_id'], revision=m['revision'], status=f"OFFLINE MAP · {m['name']} · READY",
                  bathymetry_status='READY' if m.get('bathymetry_file') else 'NOT INSTALLED')
    result['bounds']=list(m['bounds'])
    result['revision']=m['revision']
    result['source_date']=m.get('source_date','')
    result['coverage']=[]
    # Overview first, then regional/detail layers, then bathymetry/satellite.
    files = package.files()
    ordered = sorted(files, key=lambda role: (0 if role == 'overview' else 1 if role == 'basemap' else 2 if role.startswith('detail') else 3 if role == 'bathymetry' else 4, role))
    for role in ordered:
        name = files[role]
        reader = MBTiles(safe_file(package.root, name), 0)
        try:
            source = 'offline-' + role
            extension = reader.format
            vector = extension in ('pbf', 'mvt')
            source_spec = {'type': 'vector' if vector else 'raster', 'tiles': [f'gds://tiles/{m["package_id"]}/{role}/{{z}}/{{x}}/{{y}}.{extension}'],
                           'bounds': list(reader.bounds), 'minzoom': reader.minzoom, 'maxzoom': reader.maxzoom,
                           'attribution': html.escape(reader.metadata['attribution'])}
            if not vector:
                source_spec['tileSize'] = 256
            style['sources'][source] = source_spec
            result['tiles'][role] = {'file': name, 'format': extension, 'mime': MIME[extension]}
            owner = 'basemap' if vector else 'bathymetry' if role == 'bathymetry' else 'satellite'
            def add(suffix, kind, paint, source_layer=None, layout=None, minzoom=None):
                layer = {'id': source + '-' + suffix, 'type': kind, 'source': source, 'paint': paint, 'metadata': {'gds:owner': owner}}
                if source_layer:
                    layer['source-layer'] = source_layer
                if layout:
                    layer['layout'] = layout
                if minzoom is not None:
                    layer['minzoom'] = minzoom
                style['layers'].append(layer)
            if not vector:
                add('raster', 'raster', {'raster-opacity': .38 if role == 'bathymetry' else 1}, layout={'visibility': 'visible' if role == 'bathymetry' else 'none'})
                continue
            result['coverage'].append({'role':role,'bounds':list(reader.bounds)})
            available = {item['id'] for item in json.loads(reader.metadata['json'])['vector_layers']}
            schema=vector_schema(reader.metadata,m.get('vector_schemas',{}).get(role))
            if schema=='shortbread-1.0':
                source_spec['attribution']=html.escape(m['attribution'])
                result['tiles'][role]['schema']=schema
                style['name']='GDS Shortbread Maritime'
                if role=='basemap':result['initial_bounds']=[[reader.bounds[0],reader.bounds[1]],[reader.bounds[2],reader.bounds[3]]]
                style['layers'].extend(shortbread_layers(source,reader.metadata))
                continue
            specs = [('landcover', 'fill', {'fill-color': '#e8e8df', 'fill-opacity': 1}),
                     ('water', 'fill', {'fill-color': '#cddfe3'}),
                     ('waterway', 'line', {'line-color': '#a5c5cd', 'line-width': 1}),
                     ('boundary', 'line', {'line-color': '#9babae', 'line-width': .6, 'line-dasharray': [4, 3]}),
                     ('transportation', 'line', {'line-color': '#b7b9ae', 'line-width': .7})]
            for layer, kind, paint in specs:
                if layer in available:
                    add(layer, kind, paint, layer)
                    if layer == 'water':
                        add('coastline','line',{'line-color':'#91abb3','line-width':.7},'water')
                    if layer == 'transportation':
                        style['layers'][-1].update(minzoom=9, filter=['in', 'class', 'motorway', 'trunk', 'primary', 'secondary'])
            for layer in ('place', 'poi'):
                if layer in available:
                    add(layer, 'symbol', {'text-color': '#596c73', 'text-halo-color': '#e8e8df', 'text-halo-width': 1}, layer,
                        {'text-field': ['coalesce', ['get', 'name:en'], ['get', 'name'], ''], 'text-font': ['KlokanTech Noto Sans Regular'], 'text-size': 11}, (1 if role == 'overview' else 5) if layer == 'place' else 10)
                    style['layers'][-1]['filter'] = ['in', 'class', 'country', 'state', 'city', 'town'] if layer == 'place' else ['in', 'class', 'harbor', 'port']
        finally:
            reader.close()
    # Composite independently bounded sources; fine detail draws above regional
    # data and the genuine global overview remains available underneath.
    priorities = {f'offline-{role}':source_priority(role,style['sources'][f'offline-{role}']) for role in files}
    background, *layers = style['layers']
    style['layers'] = [background] + sorted(layers,key=lambda layer:priorities[layer['source']])
    return result
