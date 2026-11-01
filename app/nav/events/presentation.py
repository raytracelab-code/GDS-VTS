def eta(value):return '—' if value is None else (f'{int(value//60)} min' if value>=60 else f'{int(value)} s')
def age(seconds,status=None):return 'STALE' if status=='STALE' else (f'{int(seconds//60)}m {int(seconds%60)}s' if seconds>=60 else f'{int(seconds)} s')
def summary(event):return {'event_id':event.event_id,'severity':event.severity or '—','status':event.status}
