from datetime import datetime,timezone,timedelta
import pytest
from app.nav.events import SquallEventService
from app.nav.events.exceptions import SquallEventError
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def msg(op='CREATE',**x):return {'operation':op,'event_type':'squall','event_id':'SQ-1','observed_at':'2026-01-01T00:00:00Z','latitude':22.1,'longitude':91.7,'direction_deg':360,**x}
def test_lifecycle_and_multi_event():
 s=SquallEventService(lambda:NOW);assert s.ingest_mapping(msg()) and s.active_count==1
 with pytest.raises(SquallEventError):s.ingest_mapping(msg())
 assert not s.ingest_mapping(msg('UPDATE'))
 assert s.ingest_mapping(msg('CREATE',event_id='SQ-2')) and s.active_count==2
 assert s.ingest_mapping(msg('CLEAR')) and s.active_count==1 and not s.ingest_mapping(msg('CLEAR'))
def test_validation_and_time():
 s=SquallEventService(lambda:NOW)
 with pytest.raises(SquallEventError):s.ingest_mapping(msg(latitude=91))
 with pytest.raises(SquallEventError):s.ingest_mapping(msg(speed_knots=-1))
 s.ingest_mapping(msg());s.evaluate_time(NOW+timedelta(seconds=121));assert s.snapshot()['events'][0].status=='STALE';s.evaluate_time(NOW+timedelta(seconds=601));assert s.active_count==0
