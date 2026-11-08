"""Readable local GIS rows; retain raw attributes in the provider, not the UI."""
from .adapters.malaysia import available

LABELS = {
    'name':'Name', 'type':'Type', 'status':'Status', 'operator':'Operator',
    'field':'Field', 'psc_block':'PSC / Block', 'installation_year':'Installation Year',
    'water_depth_m':'Water Depth (m)', 'number_of_wells':'Number of Wells',
    'content':'Content', 'from':'From', 'to':'To', 'from_facility':'From Facility',
    'to_facility':'To Facility', 'length_km':'Length (km)', 'outer_diameter_inch':'Outer Diameter (inch)',
    'maximum_pressure':'Maximum Pressure (source units)', 'depth_m':'Depth TVD (m)',
    'region':'Region', 'area_sqkm':'Area (km²)', 'acquisition_year':'Acquisition Year',
    'processing_year':'Processing Year', 'contractor':'Contractor', 'discovery_year':'Discovery Year',
}


def gis_inspector(selected, layers):
    props = selected['properties']
    layer = next((l for l in layers if l['dataset_id']==props.get('gis_layer')), {})
    rows = [(label,props[key]) for key,label in LABELS.items() if available(props.get(key))]
    if selected['geometry']['type'] == 'Point':
        lon,lat = selected['geometry']['coordinates'][:2]
        rows.append(('Position',f'{lat:.6f}, {lon:.6f}'))
    rows.append(('Source','MALAYSIA OFFSHORE GIS'))
    return layer.get('inspector_title','MARITIME REFERENCE GIS'), rows
