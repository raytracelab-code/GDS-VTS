"""Pure NAV presentation helpers: never invent values, never hide valid zeros."""
LIVE_SECONDS=3.0
LIVE,STALE,NO_DATA='LIVE','STALE','NO DATA'
def format_duration(delta):
 if delta is None:return '—'
 seconds=max(0,int(delta.total_seconds()));return f'{seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}'
def track_metrics(track,freshness=LIVE):
 status='IDLE' if not track.point_count else 'RECORDING' if freshness==LIVE else 'PAUSED'
 return {'status':status,'distance_nm':f'{track.distance_nm:.2f} NM' if track.point_count else '—','duration':format_duration(track.duration),'points':getattr(track,'total_points',track.point_count)}
def telemetry_age(frame,now): return '—' if not frame or not frame.received_at else f'{max(0,(now-frame.received_at).total_seconds()):.1f} s'
def telemetry_freshness(frame,now,live_seconds=LIVE_SECONDS):
 """(state, age_seconds) from the last accepted frame time; NO DATA when none."""
 if not frame or not getattr(frame,'received_at',None):return NO_DATA,None
 age=max(0.0,(now-frame.received_at).total_seconds())
 return (LIVE if age<live_seconds else STALE),age
def format_age(age):
 if age is None:return '—'
 age=int(age)
 if age<60:return f'{age} s ago'
 if age<3600:return f'{age//60} min {age%60:02d} s ago'
 return f'{age//3600} h {age%3600//60:02d} min ago'
def format_speed(value): return '—' if value is None else f'{float(value):.1f} kn'
def format_angle(value): return '—' if value is None else f'{round(float(value),1)%360:05.1f}°'
def heading_source(frame):
 if frame is None:return None
 if getattr(frame,'heading',None) is not None:return 'HDG'
 if getattr(frame,'cog',None) is not None:return 'COG'
 return None
def marker_payload(vessel,frame,freshness=LIVE,age=None):
 """Map marker data. heading is None (not 0) when no orientation was received."""
 source=heading_source(frame)
 return {'latitude':vessel.latitude,'longitude':vessel.longitude,
         'heading':vessel.heading if source else None,'heading_source':source,
         'freshness':freshness,'age_seconds':None if age is None else round(age,1)}
def freshness_banner(freshness,age):
 if freshness==NO_DATA:return 'NO TELEMETRY DATA · vessel position unknown'
 if freshness==STALE:return f'TELEMETRY STALE · last update {format_age(age)}'
 return f'TELEMETRY LIVE · last update {format_age(age)}'
def readout_text(vessel,frame,freshness,age):
 if frame is None or vessel.latitude is None:
  return f'POSITION\n—\n\nSTATUS\n{freshness}\n\nLAST UPDATE\n{format_age(age)}'
 heading=format_angle(frame.heading) if frame.heading is not None else 'UNKNOWN'+(' (marker by COG)' if frame.cog is not None else '')
 return (f'POSITION\n{vessel.latitude:.6f}, {vessel.longitude:.6f}\n\nSOG\n{format_speed(frame.speed_knots)}\n\nCOG\n{format_angle(frame.cog)}'
         f'\n\nHEADING\n{heading}\n\nSOURCE\n{frame.source or "—"}\n\nSTATUS\n{freshness}\n\nLAST UPDATE\n{format_age(age)}')
