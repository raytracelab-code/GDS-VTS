"""Small-region planar intersections over geodesically generated event zones.

Site polygons retain interior holes. This is operational geometry, not a
meteorological probability or an antimeridian/global GIS engine.
"""
from .models import ImpactState
from .geometry import circle

def _cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def _on_segment(p,a,b):
 return abs(_cross(a,b,p))<1e-10 and min(a[0],b[0])-1e-10<=p[0]<=max(a[0],b[0])+1e-10 and min(a[1],b[1])-1e-10<=p[1]<=max(a[1],b[1])+1e-10
def segments_intersect(a,b,c,d):
 return (_cross(a,b,c)*_cross(a,b,d)<0 and _cross(c,d,a)*_cross(c,d,b)<0) or any((_on_segment(c,a,b),_on_segment(d,a,b),_on_segment(a,c,d),_on_segment(b,c,d)))
def point_in_polygon(point,ring):
 x,y=point;inside=False
 for a,b in zip(ring,ring[1:]+ring[:1]):
  if _on_segment(point,a,b):return True
  x1,y1=a[:2];x2,y2=b[:2]
  if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:inside=not inside
 return inside
def _inside(point,polygon):return point_in_polygon(point,polygon[0]) and not any(point_in_polygon(point,hole) for hole in polygon[1:])
def _edges(polygon):return [(a,b) for ring in polygon for a,b in zip(ring,ring[1:]+ring[:1])]
def _line_intersects(points,polygon):
 return any(_inside(p,polygon) for p in points) or any(segments_intersect(a,b,c,d) for a,b in zip(points,points[1:]) for c,d in _edges(polygon))
def _polygons_intersect(a,b):
 return any(_inside(p,b) for p in a[0]) or any(_inside(p,a) for p in b[0]) or any(segments_intersect(*ab,*cd) for ab in _edges(a) for cd in _edges(b))
def site_polygons(state):
 """Consume normalized SpatialState only; never read package files."""
 if state is None:return []
 collection=state.collections.get('site-boundary',{})
 result=[]
 for feature in collection.get('features',[]):
  geometry=feature['geometry']
  if geometry['type']=='Polygon':result.append(geometry['coordinates'])
  elif geometry['type']=='MultiPolygon':result.extend(geometry['coordinates'])
 return result
def distance_nm(lat1,lon1,lat2,lon2):
 """Great-circle distance in nautical miles."""
 from math import asin,cos,radians,sin,sqrt
 p1,p2=radians(lat1),radians(lat2);dp,dl=p2-p1,radians(lon2-lon1)
 return 2*3440.065*asin(sqrt(sin(dp/2)**2+cos(p1)*cos(p2)*sin(dl/2)**2))
def evaluate_vessel(event,position):
 """GDS-AUDIT-021: judge the event against the own vessel's last known position.
 IMPACT when the vessel is within the impact radius of the current or any predicted position,
 SURVEILLANCE when within the surveillance radius. NONE without a position (never invented)."""
 if not position or position[0] is None or position[1] is None:return ImpactState.NONE
 lat,lon=position
 points=[(event.latitude,event.longitude)]+[(p.latitude,p.longitude) for p in event.predicted_path]
 nearest=min(distance_nm(lat,lon,a,b) for a,b in points)
 if event.impact_radius_nm and nearest<=event.impact_radius_nm:return ImpactState.IMPACT
 if event.surveillance_radius_nm and distance_nm(lat,lon,event.latitude,event.longitude)<=event.surveillance_radius_nm:return ImpactState.SURVEILLANCE
 return ImpactState.NONE
def evaluate(event,site_boundary):
 """Accept normalized SpatialState or legacy Polygon coordinate arrays."""
 polygons=site_polygons(site_boundary) if hasattr(site_boundary,'collections') or site_boundary is None else ([site_boundary] if site_boundary and isinstance(site_boundary[0][0][0],(int,float)) else site_boundary)
 if not polygons:return ImpactState.NONE
 current=[event.longitude,event.latitude]
 trajectory=[current]+[[p.longitude,p.latitude] for p in event.predicted_path]
 for polygon in polygons:
  if _inside(current,polygon) or (event.predicted_path and _line_intersects(trajectory,polygon)):return ImpactState.IMPACT
  if event.impact_radius_nm and _polygons_intersect([circle(event.latitude,event.longitude,event.impact_radius_nm)],polygon):return ImpactState.IMPACT
 if event.surveillance_radius_nm and any(_polygons_intersect([circle(event.latitude,event.longitude,event.surveillance_radius_nm)],polygon) for polygon in polygons):return ImpactState.SURVEILLANCE
 return ImpactState.NONE
