def format_duration(delta):
 if delta is None:return '—'
 seconds=max(0,int(delta.total_seconds()));return f'{seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}'
def track_metrics(track): return {'status':'RECORDING' if track.point_count else 'IDLE','distance_nm':f'{track.distance_nm:.2f} NM' if track.point_count else '—','duration':format_duration(track.duration),'points':track.point_count}
def telemetry_age(frame,now): return '—' if not frame or not frame.received_at else f'{max(0,(now-frame.received_at).total_seconds()):.1f} s'
