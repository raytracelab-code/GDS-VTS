"""Development-only canonical telemetry route for NAV Phase 1 validation.

Run this file directly; it opens the normal application and feeds JSON through
``TelemetryStateService.ingest`` exactly as a USB transport would.  It does not
add a production demo mode, UI control, or alternate map path.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# Direct execution starts with ``tools`` as sys.path[0], not the repository.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.models import Source
from app.ui.main_window import MainWindow


ROUTE = (
    (0, 22.2000, 91.7500, 7.2, 145, 138),
    (1, 22.1988, 91.7513, 7.4, 146, 139),
    (2, 22.1975, 91.7527, 7.5, 147, 140),
    # The 18-second gap after T+2 exceeds NAV's ten-second gap threshold.
    (20, 22.1920, 91.7590, 7.3, 150, 143),
    (21, 22.1908, 91.7604, 7.4, 151, 144),
)


def payload(latitude: float, longitude: float, sog: float, cog: int, heading: int) -> bytes:
    # USB payloads use the normalizer's existing DDMM.mmm transport convention.
    # The NavPage therefore receives the requested decimal-degree canonical frame.
    def transport_coordinate(value: float) -> float:
        sign = -1 if value < 0 else 1
        absolute = abs(value)
        degrees = int(absolute)
        return sign * (degrees * 100 + (absolute - degrees) * 60)

    return (json.dumps({
        "Latitude": transport_coordinate(latitude),
        "Longitude": transport_coordinate(longitude),
        "Speed_Knots": sog,
        "COG": cog,
        "Heading": heading,
    }) + "\n").encode("utf-8")


def inject_route(window: MainWindow) -> None:
    """Schedule the fixed route through the real canonical ingest path."""
    route_start = datetime.now(timezone.utc)
    for seconds, latitude, longitude, sog, cog, heading in ROUTE:
        def ingest(offset=seconds, lat=latitude, lon=longitude, speed=sog, course=cog, hdg=heading):
            published = window.state.ingest(Source.USB, payload(lat, lon, speed, course, hdg))
            # Preserve deterministic route timing after the normal parser,
            # validator, normalizer, arbitration, and ingest pipeline ran.
            if published:
                frame = replace(published[-1], received_at=route_start + timedelta(seconds=offset))
                window.state.latest_frame = frame
                window.state.last_valid_frame_time = frame.received_at
        QTimer.singleShot(
            seconds * 1000,
            ingest,
        )
    def report() -> None:
        track = window.nav.track
        print(
            "DEV NAV ROUTE "
            f"points={track.point_count} segments={[len(segment) for segment in track.segments]} "
            f"duration={track.duration} distance_nm={track.distance_nm:.3f} "
            f"start={(track.start.latitude, track.start.longitude) if track.start else None}",
            flush=True,
        )
    QTimer.singleShot(22000, report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Development-only NAV canonical telemetry injector")
    parser.add_argument("--quit-after", type=float, default=0, metavar="SECONDS",
                        help="close after the route; 0 keeps the normal app open")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.navigate("Nav")
    inject_route(window)
    if args.quit_after > 0:
        QTimer.singleShot(round(args.quit_after * 1000), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
