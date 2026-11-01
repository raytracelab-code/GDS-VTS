from math import asin,atan2,cos,degrees,radians,sin
R=6371008.8
def destination_point(lat,lon,bearing_deg,distance_nm):
 d=distance_nm*1852/R;b=radians(bearing_deg);p=radians(lat);l=radians(lon);q=asin(sin(p)*cos(d)+cos(p)*sin(d)*cos(b));g=l+atan2(sin(b)*sin(d)*cos(p),cos(d)-sin(p)*sin(q));return degrees(q),(degrees(g)+540)%360-180
def circle(lat,lon,radius_nm,n=64):
 points=[]
 for i in range(n):
  latitude,longitude=destination_point(lat,lon,i*360/n,radius_nm);points.append([longitude,latitude])
 return points+[points[0][:]]
def render(event):
 p={'event_id':event.event_id,'event_type':'squall','status':event.status,'severity':event.severity}
 cur={'type':'Feature','properties':p,'geometry':{'type':'Point','coordinates':[event.longitude,event.latitude]}}
 end=destination_point(event.latitude,event.longitude,event.direction_deg,2)
 direction={'type':'Feature','properties':p,'geometry':{'type':'LineString','coordinates':[[event.longitude,event.latitude],[end[1],end[0]]]}}
 coordinates=[[event.longitude,event.latitude]]+[[x.longitude,x.latitude] for x in event.predicted_path]
 path={'type':'Feature','properties':p,'geometry':{'type':'LineString','coordinates':coordinates}} if event.predicted_path else None
 return {'current':cur,'direction':direction,'trajectory':path,'impact':circle(event.latitude,event.longitude,event.impact_radius_nm) if event.impact_radius_nm else None,'surveillance':circle(event.latitude,event.longitude,event.surveillance_radius_nm) if event.surveillance_radius_nm else None}
