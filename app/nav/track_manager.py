from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import radians,sin,cos,asin,sqrt

@dataclass(frozen=True)
class TrackPoint: timestamp: datetime; latitude: float; longitude: float; heading: float|None; cog: float|None; speed_knots: float|None
class TrackManager:
    """Bounded track: recent points at full resolution, older history thinned.

    Distance is accumulated on append from every accepted point, so thinning
    the stored geometry never changes the reported distance or duration.
    """
    MAX_POINTS=6000      # retained geometry cap (~1.7 h at 1 Hz before thinning starts)
    RECENT_POINTS=1800   # newest points never thinned (30 min at 1 Hz)
    def __init__(self,gap_seconds=10,max_points=None,recent_points=None):
        self.gap_seconds=gap_seconds; self.segments=[]; self._distance=0.0; self.total_points=0
        self.max_points=max_points or self.MAX_POINTS; self.recent_points=min(recent_points or self.RECENT_POINTS,self.max_points//2)
        self._retained=0
    def append(self,point):
        if not (-90<=point.latitude<=90 and -180<=point.longitude<=180) or (point.latitude==0 and point.longitude==0): return False
        if self.segments and self.segments[-1] and self.segments[-1][-1].timestamp==point.timestamp: return False
        if not self.segments or (point.timestamp-self.segments[-1][-1].timestamp).total_seconds()>self.gap_seconds: self.segments.append([])
        elif self.segments[-1]:
            last=self.segments[-1][-1];self._distance+=haversine_nm(last.latitude,last.longitude,point.latitude,point.longitude)
        self.segments[-1].append(point);self.total_points+=1;self._retained+=1
        if self._retained>self.max_points:self._thin()
        return True
    def _thin(self):
        """Drop every second older point; segment end points and recent points are kept."""
        older=self._retained-self.recent_points;index=0;segments=[]
        for segment in self.segments:
            kept=[]
            for position,point in enumerate(segment):
                if index>=older or position==0 or position==len(segment)-1 or index%2==0:kept.append(point)
                index+=1
            segments.append(kept)
        self.segments=segments;self._retained=sum(len(s) for s in segments)
    @property
    def start(self): return self.segments[0][0] if self.segments else None
    def bounds(self):
        points=[p for segment in self.segments for p in segment]
        return None if not points else (min(p.longitude for p in points),min(p.latitude for p in points),max(p.longitude for p in points),max(p.latitude for p in points))
    def geojson_segments(self): return {'type':'Feature','geometry':{'type':'MultiLineString','coordinates':[[[p.longitude,p.latitude] for p in s] for s in self.segments]}}
    def start_geojson(self): return None if not self.start else {'type':'Feature','geometry':{'type':'Point','coordinates':[self.start.longitude,self.start.latitude]}}
    @property
    def point_count(self): return self._retained
    @property
    def duration(self):
        return None if not self.segments else self.segments[-1][-1].timestamp-self.segments[0][0].timestamp
    @property
    def distance_nm(self): return self._distance
def haversine_nm(a,b,c,d):
 p=radians; x=sin(p(c-a)/2)**2+cos(p(a))*cos(p(c))*sin(p(d-b)/2)**2; return 3440.065*2*asin(sqrt(x))
def destination_point(lat,lon,bearing_deg,distance_nm):
 r=3440.065; d=distance_nm/r; b=radians(bearing_deg); a=radians(lat); o=radians(lon); n=asin(sin(a)*cos(d)+cos(a)*sin(d)*cos(b)); e=o+__import__('math').atan2(sin(b)*sin(d)*cos(a),cos(d)-sin(a)*sin(n)); return (__import__('math').degrees(n),(__import__('math').degrees(e)+540)%360-180)
