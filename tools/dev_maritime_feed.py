r"""Explicit TEST/SYNTHETIC Phase 4 scenario. Never loaded by production startup.

Run: .venv\Scripts\python.exe tools/dev_maritime_feed.py --auto --quit-after 90
--telemetry sends test frames through the canonical telemetry ingestion path.
--lifecycle-fast advances only this development store's clock (production thresholds unchanged).
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def ais_records(now=None, step=0):
    now = now or datetime.now(timezone.utc)
    return [dict(mmsi=str(999000001+i), name='TEST '+kind.upper(), ship_type=kind,
                 latitude=22.12+i*.055+step*.008, longitude=91.68+i*.035+step*.01,
                 heading=(30+i*40+step*20) % 360, cog=(35+i*40+step*25) % 360,
                 sog=6+i*2, position_timestamp=now.isoformat(), destination='TEST ONLY')
            for i, kind in enumerate(('cargo', 'tanker', 'tug', 'fishing', 'offshore_support'))]


def static_features():
    def point(lon, lat):
        return dict(type='Point', coordinates=[lon, lat])
    def line(lon, lat):
        return dict(type='LineString', coordinates=[[lon, lat], [lon+.09, lat+.04], [lon+.16, lat+.02]])
    def polygon(lon, lat):
        return dict(type='Polygon', coordinates=[[[lon, lat], [lon+.05, lat], [lon+.05, lat+.04], [lon, lat+.04], [lon, lat]]])
    specs = [
        ('offshore', 'oil_platform', point(91.58, 22.16)),
        ('offshore', 'fpso', point(91.60, 22.23)),
        ('offshore', 'spm', point(91.56, 22.29)),
        ('offshore', 'wellhead', point(91.61, 22.35)),
        ('aton', 'buoy', point(91.75, 22.14)),
        ('aton', 'beacon', point(91.78, 22.2)),
        ('anchorages', 'anchorage', polygon(91.78, 22.24)),
        ('routes', 'tss', polygon(91.46, 22.10)),
        ('subsea', 'submarine_pipeline', line(91.45, 22.28)),
        ('subsea', 'submarine_cable', line(91.47, 22.35)),
        ('hazards', 'wreck', point(91.7, 22.3)),
        ('restricted', 'safety_zone', polygon(91.48, 22.20)),
        ('warnings', 'navigation_warning', polygon(91.64, 22.4)),
        ('bathymetry', 'depth_contour', line(91.42, 22.4)),
        ('ports', 'terminal', point(91.81, 22.35)),
        ('metocean', 'wind', point(91.55, 22.43)),
    ]
    return [dict(type='Feature', id='TEST-'+str(i), geometry=g,
                 properties=dict(category=c, object_type=t, name='TEST '+t.upper(),
                                 description='SYNTHETIC DEVELOPMENT DATA — NOT FOR NAVIGATION'))
            for i, (c, t, g) in enumerate(specs)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auto', action='store_true')
    parser.add_argument('--telemetry', action='store_true')
    parser.add_argument('--lifecycle-fast', action='store_true')
    parser.add_argument('--squalls', action='store_true', help='Also use the existing Phase 3 development injector')
    parser.add_argument('--quit-after', type=int, default=0)
    args = parser.parse_args()
    from app.nav.web_scheme import register_gds_scheme
    register_gds_scheme()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow
    from app.nav.maritime.service import AISService, MaritimeChartService
    from app.nav.maritime.source_health import SourceState
    from app.core.models import Source
    app = QApplication(sys.argv[:1]); app.setApplicationName('GDS VTS')
    window = MainWindow(); window.showMaximized(); window.navigate('Nav')
    runtime = window.maritime_runtime; service = runtime.service
    last_area = [None]
    def report_area():
        if service.area != last_area[0]:
            last_area[0] = service.area
            print('TEST maritime AREA', service.area.payload() if service.area else None, flush=True)
    runtime.changed.connect(report_area)
    # This tool owns its development clock; production never advances this clock.
    offset = [0]
    service.clock = lambda: datetime.now(timezone.utc)+timedelta(seconds=offset[0])
    def load():
        AISService(service).ingest(ais_records(service.clock()))
        MaritimeChartService(service).ingest(static_features(), source='TEST-SYNTHETIC')
        service.set_source('ais', SourceState.LIVE, success=True)
        service.set_source('chart', SourceState.LIVE, success=True)
        print('TEST maritime CREATE vessels=5 static=16', flush=True)
        if args.squalls:
            from tools.dev_squall_events import event
            window.ingest_squall_event(event())
            window.ingest_squall_event(event('SQ-002', latitude=22.5, longitude=92.0))
    def update():
        AISService(service).ingest(ais_records(service.clock(), step=2))
        service.set_source('ais', SourceState.LIVE, success=True)
        print('TEST maritime UPDATE vessels=5 heading/COG/position changed', flush=True)
    def lifecycle(seconds):
        offset[0] = seconds; service.evaluate_time()
        print('TEST maritime lifecycle', seconds, 'vessels=', sum(o.category == 'vessels' for o in service.snapshot()), flush=True)
    telemetry_step = [0]
    def telemetry():
        # NMEA-like DDMM values are intentionally normalized by the existing telemetry service.
        lat = 22.18 + (.25 if telemetry_step[0] >= 20 else 0)
        telemetry_step[0] += 1
        raw = dict(PID='TEST-SYNTHETIC-OWN', Latitude=(int(lat)*100+(lat % 1)*60), Longitude=9142,
                   Heading=40, COG=45, Speed_Knots=8)
        window.state.ingest(Source.USB, (json.dumps(raw)+'\n').encode())
    QTimer.singleShot(5000, load)
    if args.auto:
        QTimer.singleShot(15000, update)
    if args.lifecycle_fast:
        QTimer.singleShot(30000, lambda: lifecycle(121))
        QTimer.singleShot(45000, lambda: lifecycle(601))
    if args.telemetry:
        timer = QTimer(window); timer.timeout.connect(telemetry); timer.start(1000)
    if args.quit_after:
        QTimer.singleShot(args.quit_after*1000, window.close)
        QTimer.singleShot(args.quit_after*1000+100, app.quit)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
