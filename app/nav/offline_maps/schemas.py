"""Explicit schema detection; never translate or rewrite stored vector tiles."""
import json
from .mbtiles import MapPackageError

SHORTBREAD = {'ocean','water_polygons','water_lines','boundaries','place_labels','streets'}
OPENMAPTILES = {'water','landcover'}


def vector_schema(metadata, declared=None):
    try:
        layers=json.loads(metadata['json'])['vector_layers']
        names={layer['id'] for layer in layers}
        detected='shortbread-1.0' if SHORTBREAD.issubset(names) else 'openmaptiles' if OPENMAPTILES.issubset(names) else None
        if not detected:raise MapPackageError('Unsupported vector schema: expected OpenMapTiles or Shortbread layers')
        if declared is not None and declared!=detected:raise MapPackageError('Declared vector schema differs from MBTiles metadata')
        return detected
    except (KeyError,TypeError,ValueError) as error:
        if isinstance(error,MapPackageError):raise
        raise MapPackageError('Invalid vector schema metadata') from error


def shortbread_layers(source, metadata):
    """Maritime subset of actual Shortbread 1.0 layers/properties."""
    available={layer['id'] for layer in json.loads(metadata['json'])['vector_layers']}
    layers=[]
    def add(suffix,kind,role,paint,source_layer,minimum=0,filter=None,layout=None):
        if source_layer not in available:return
        layer={'id':source+'-'+suffix,'type':kind,'source':source,'source-layer':source_layer,
               'minzoom':minimum,'paint':paint,'metadata':{'gds:owner':'basemap','gds:role':role}}
        if filter is not None:layer['filter']=filter
        if layout:layer['layout']=layout
        layers.append(layer)
    add('land','fill','LAND',{'fill-color':'#e8e8df'},'land')
    add('ocean','fill','WATER',{'fill-color':'#cddfe3'},'ocean')
    add('water','fill','WATER',{'fill-color':'#cddfe3'},'water_polygons',filter=['!=','kind','glacier'])
    # The ocean polygon edge is the coastline. Drawing polygon tile edges as
    # lines would produce tile-boundary grids, so no fabricated coast lines.
    add('waterways','line','COAST',{'line-color':'#a5c5cd','line-width':1},'water_lines',7,['in','kind','river','canal'])
    add('boundaries','line','BOUNDARY',{'line-color':'#9babae','line-width':.7,'line-dasharray':[4,3]},'boundaries',0,['<=','admin_level',4])
    add('roads','line','ROAD',{'line-color':'#b7b9ae','line-width':['interpolate',['linear'],['zoom'],7,.45,14,1.2]},'streets',7,['in','kind','motorway','trunk','primary','secondary'])
    add('piers','fill','LAND',{'fill-color':'#e8e8df'},'pier_polygons',12)
    add('pier-lines','line','COAST',{'line-color':'#91abb3','line-width':1.4},'pier_lines',12)
    text={'text-field':['case',['!=',['coalesce',['get','name_en'],''],''],['get','name_en'],['coalesce',['get','name'],'']],
          'text-font':['KlokanTech Noto Sans Regular'],'text-size':11}
    paint={'text-color':'#596c73','text-halo-color':'#e8e8df','text-halo-width':1}
    add('countries','symbol','LABEL',dict(paint),'boundary_labels',3,['==','admin_level',2],dict(text))
    add('places','symbol','LABEL',dict(paint),'place_labels',4,['in','kind','capital','state_capital','city','town'],dict(text))
    add('water-labels','symbol','LABEL',dict(paint),'water_polygons_labels',9,None,dict(text))
    # Shortbread POIs use source OSM attributes, not OpenMapTiles class names.
    add('ports','symbol','LABEL',dict(paint),'pois',12,['any',['in','man_made','pier','harbour','port'],['==','leisure','marina']],dict(text))
    return layers
