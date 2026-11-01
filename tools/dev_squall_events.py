r"""Local synthetic scenario using MainWindow's production ingest boundary.

Run: .venv\Scripts\python.exe tools/dev_squall_events.py
Use --auto for timed CREATE/UPDATE/CLEAR; --hold keeps two events visible.
No network, production demo controls, forecast generation, or JS injection.
"""
import argparse
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.nav.web_scheme import register_gds_scheme
register_gds_scheme()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def event(event_id='SQ-001',**changes):
 now=datetime.now(timezone.utc)
 return dict(operation='CREATE',event_type='squall',event_id=event_id,observed_at=now.isoformat(),latitude=22.12,longitude=91.72,direction_deg=45,speed_knots=25,severity='moderate',impact_radius_nm=5,surveillance_radius_nm=15,predicted_path=[dict(latitude=22.14,longitude=91.74,eta_seconds=300),dict(latitude=22.17,longitude=91.78,eta_seconds=600),dict(latitude=22.20,longitude=91.81,eta_seconds=900)],source='SYNTHETIC DEVELOPMENT SCENARIO',notes='Not real meteorological data')|changes

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--auto',action='store_true');parser.add_argument('--hold',action='store_true');parser.add_argument('--baseline',action='store_true',help='No events; fit the active static package as a basemap warning control');parser.add_argument('--lifecycle-fast',action='store_true',help='Evaluate synthetic future time for stale/expiry without changing production thresholds');parser.add_argument('--impact-cycle',action='store_true',help='Publish SQ-003 through NONE/SURVEILLANCE/IMPACT near the sample site');parser.add_argument('--quit-after',type=int,default=0);args=parser.parse_args()
 app=QApplication(sys.argv[:1]);app.setApplicationName('GDS VTS');window=MainWindow();window.showMaximized();window.navigate('Nav')
 def ingest(payload):
  window.ingest_squall_event(payload);p=window.nav.bridge.getEventState();print('DEV',payload['operation'],payload['event_id'],'active_count=',p['active_count'],'impact=',[(e['event_id'],e['impact_state']) for e in p['events']],flush=True)
 def start():
  if args.baseline:window.nav.command('FIT SPATIAL DATA');return
  ingest(event());ingest(event('SQ-002',latitude=22.5,longitude=92.0,direction_deg=240,severity='low',impact_radius_nm=2,surveillance_radius_nm=8,predicted_path=[dict(latitude=22.4,longitude=91.95,eta_seconds=600)]))
  window.nav.bridge.selectEvent('SQ-001');window.nav.show_event_button.click()
 QTimer.singleShot(5000,start)
 if args.auto:
  QTimer.singleShot(10000,lambda:ingest(event(operation='UPDATE',latitude=22.15,longitude=91.76,predicted_path=[dict(latitude=22.19,longitude=91.8,eta_seconds=240)])))
  QTimer.singleShot(15000,lambda:ingest(event(operation='CLEAR')))
 if args.impact_cycle and not args.baseline:
  QTimer.singleShot(6000,lambda:ingest(event('SQ-003',longitude=92.5,impact_radius_nm=1,surveillance_radius_nm=10,predicted_path=[])))
  QTimer.singleShot(9000,lambda:ingest(event('SQ-003',operation='UPDATE',longitude=91.95,impact_radius_nm=1,surveillance_radius_nm=10,predicted_path=[])))
  QTimer.singleShot(12000,lambda:ingest(event('SQ-003',operation='UPDATE',longitude=91.76,impact_radius_nm=1,surveillance_radius_nm=10,predicted_path=[])))
 if args.lifecycle_fast and not args.baseline:
  def lifecycle(seconds):
   window.squall_event_service.evaluate_time(datetime.now(timezone.utc)+timedelta(seconds=seconds));print('DEV lifecycle',seconds,[(e['event_id'],e['status']) for e in window.nav.bridge.getEventState()['events']],flush=True)
  QTimer.singleShot(18000,lambda:lifecycle(121));QTimer.singleShot(21000,lambda:lifecycle(601))
 if args.quit_after:QTimer.singleShot(args.quit_after*1000,app.quit)
 return app.exec()
if __name__=='__main__':raise SystemExit(main())
