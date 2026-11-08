"""Bounded operating area, distance hysteresis and debounced viewport requests."""
from dataclasses import dataclass, asdict
import math
import time
from .models import number


def distance_bearing(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b-a, math.radians((lon2-lon1+180) % 360-180)
    h = min(1, math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2)
    distance = 3440.065 * 2 * math.asin(math.sqrt(h))
    bearing = math.degrees(math.atan2(math.sin(dlon)*math.cos(b), math.cos(a)*math.sin(b)-math.sin(a)*math.cos(b)*math.cos(dlon))) % 360
    return distance, bearing


@dataclass(frozen=True)
class OperatingArea:
    latitude: float
    longitude: float
    radius_nm: float = 50
    origin: str = 'own_vessel'
    viewport_bounds: tuple | None = None
    local_bounds: tuple | None = None

    def __post_init__(self):
        number(self.latitude, -90, 90, 'area latitude')
        number(self.longitude, -180, 180, 'area longitude')
        number(self.radius_nm, 1, 250, 'area radius')
        if self.viewport_bounds is not None:
            w,s,e,n=self.viewport_bounds
            number(w,-180,180,'west');number(e,-180,180,'east')
            number(s,-90,90,'south');number(n,-90,90,'north')
            if s>=n or not 0<(e-w)%360<=20:raise ValueError('invalid viewport bounds')
        if self.local_bounds is not None:
            w,s,e,n=self.local_bounds
            number(w,-180,180,'west');number(e,-180,180,'east')
            number(s,-90,90,'south');number(n,-90,90,'north')
            if s>=n or not 0<(e-w)%360<=30:raise ValueError('invalid local viewport bounds')

    def contains(self, lat, lon):
        return distance_bearing(self.latitude, self.longitude, lat, lon)[0] <= self.radius_nm

    def payload(self):
        payload=asdict(self)
        if self.viewport_bounds is None:payload.pop('viewport_bounds')
        else:payload['viewport_bounds']=list(self.viewport_bounds)
        if self.local_bounds is None:payload.pop('local_bounds')
        else:payload['local_bounds']=list(self.local_bounds)
        return payload


class MaritimeAreaController:
    def __init__(self, radius_nm=50, movement_nm=10, debounce_seconds=3, clock=time.monotonic):
        self.radius_nm = number(radius_nm, 1, 250, 'radius')
        self.movement_nm = number(movement_nm, .1, radius_nm, 'movement threshold')
        self.debounce_seconds = number(debounce_seconds, 0, 600, 'debounce')
        self.clock, self.area, self._last = clock, None, float('-inf')

    def request(self, lat, lon, origin='own_vessel', radius_nm=None, viewport_bounds=None, local_bounds=None):
        candidate = OperatingArea(lat, lon, radius_nm or self.radius_nm, origin, viewport_bounds,local_bounds)
        now = self.clock()
        if self.area:
            distance = distance_bearing(self.area.latitude, self.area.longitude, lat, lon)[0]
            covered = distance + candidate.radius_nm <= self.area.radius_nm * 1.1
            candidate_bounds=local_bounds or viewport_bounds
            previous_bounds=self.area.local_bounds or self.area.viewport_bounds
            if candidate_bounds and previous_bounds:
                w,s,e,n=candidate_bounds;ow,os,oe,on=previous_bounds
                span,old_span=(e-w)%360,(oe-ow)%360
                covered=s>=os and n<=on and (w-ow)%360+span<=old_span+1e-9
                shrunk=span<old_span*.5 or n-s<(on-os)*.5
                offset=(w-ow+180)%360-180
                overlap=max(0,min(old_span,offset+span)-max(0,offset))*max(0,min(n,on)-max(s,os))
                similar=overlap/max(span*(n-s),old_span*(on-os))>=.8 and distance<self.movement_nm
                unchanged=(covered or similar) and not shrunk
            else:
                unchanged=(origin == self.area.origin and distance < self.movement_nm and candidate.radius_nm <= self.area.radius_nm * 1.2) or (origin == 'viewport' and covered)
                # A bounded view must replace an earlier broad circular query.
                if viewport_bounds and self.area.origin=='viewport' and not self.area.viewport_bounds:unchanged=False
            if unchanged:
                return None
            if now-self._last < self.debounce_seconds:
                return None
        self.area, self._last = candidate, now
        return candidate

    def viewport(self, west, south, east, north):
        number(west, -180, 180, 'west'); number(east, -180, 180, 'east')
        number(south, -90, 90, 'south'); number(north, -90, 90, 'north')
        if south >= north:
            return None
        span = (east-west) % 360
        if span == 0 or span > 30 or north-south > 30:
            return None  # Do not load the world at startup zoom.
        lat, lon = (south+north)/2, (west+span/2+180) % 360-180
        corner_distance=distance_bearing(lat, lon, north, east)[0]
        radius = min(250, max(self.radius_nm, corner_distance))
        # Retain exact bounded view for provider queries, rather than expanding a
        # harbour-scale viewport to the minimum own-vessel operating radius.
        bounds=(west,south,east,north) if corner_distance<=250 and span<=20 else None
        # Local indexed data can cover a broader settled view without widening
        # network provider requests. Both bounds belong to the same controller state.
        return self.request(lat, lon, 'viewport', radius, bounds,(west,south,east,north))
