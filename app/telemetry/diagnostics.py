from app.core.models import TelemetryStatus
def derive_diagnostics(status, frame):
    return {'Telemetry': status.value, 'GPS': 'LIVE' if frame and frame.latitude is not None else 'UNAVAILABLE', 'Heading': 'LIVE' if frame and frame.heading is not None else 'UNAVAILABLE', 'Weather': 'LIVE' if frame and frame.temperature_c is not None else 'UNAVAILABLE', 'IMU': 'LIVE' if frame and frame.roll is not None else 'UNAVAILABLE', 'Power': 'LIVE' if frame and frame.voltage is not None else 'UNAVAILABLE'}
