from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import radians,sin,cos,asin,sqrt

@dataclass(frozen=True)
class TrackPoint: timestamp: datetime; latitude: float; longitude: float; heading: float|None; cog: float|None; speed_knots: float|None
class TrackManager:
    def __init__(self,gap_seconds=10): self.gap_seconds=gap_seconds; self.segments=[]
    def append(self,point):
        if not (-90<=point.latitude<=90 and -180<=point.longitude<=180) or (point.latitude==0 and point.longitude==0): return False
        if self.segments and self.segments[-1] and self.segments[-1][-1].timestamp==point.timestamp: return False
        if not self.segments or (point.timestamp-self.segments[-1][-1].timestamp).total_seconds()>self.gap_seconds: self.segments.append([])
        self.segments[-1].append(point); return True
    @property
    def start(self): return self.segments[0][0] if self.segments else None
    def bounds(self):
        points=[p for segment in self.segments for p in segment]
        return None if not points else (min(p.longitude for p in points),min(p.latitude for p in points),max(p.longitude for p in points),max(p.latitude for p in points))
    def geojson_segments(self): return {'type':'Feature','geometry':{'type':'MultiLineString','coordinates':[[[p.longitude,p.latitude] for p in s] for s in self.segments]}}
    def start_geojson(self): return None if not self.start else {'type':'Feature','geometry':{'type':'Point','coordinates':[self.start.longitude,self.start.latitude]}}
    @property
    def point_count(self): return sum(len(s) for s in self.segments)
    @property
    def duration(self):
        points=[p for s in self.segments for p in s]; return None if not points else points[-1].timestamp-points[0].timestamp
    @property
    def distance_nm(self):
        total=0
        for segment in self.segments:
            for a,b in zip(segment,segment[1:]): total+=haversine_nm(a.latitude,a.longitude,b.latitude,b.longitude)
        return total
def haversine_nm(a,b,c,d):
 p=radians; x=sin(p(c-a)/2)**2+cos(p(a))*cos(p(c))*sin(p(d-b)/2)**2; return 3440.065*2*asin(sqrt(x))
def destination_point(lat,lon,bearing_deg,distance_nm):
 r=3440.065; d=distance_nm/r; b=radians(bearing_deg); a=radians(lat); o=radians(lon); n=asin(sin(a)*cos(d)+cos(a)*sin(d)*cos(b)); e=o+__import__('math').atan2(sin(b)*sin(d)*cos(a),cos(d)-sin(a)*sin(n)); return (__import__('math').degrees(n),(__import__('math').degrees(e)+540)%360-180)
