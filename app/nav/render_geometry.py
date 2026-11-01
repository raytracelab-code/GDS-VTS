from .track_manager import destination_point
def vector_geojson(latitude,longitude,bearing,distance_nm=.35):
 if bearing is None or latitude is None or longitude is None:return {'type':'FeatureCollection','features':[]}
 end=destination_point(latitude,longitude,bearing,distance_nm)
 return {'type':'Feature','properties':{},'geometry':{'type':'LineString','coordinates':[[longitude,latitude],[end[1],end[0]]]}}
