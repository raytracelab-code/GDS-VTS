class TelemetryValidator:
    def valid(self, payload: dict) -> bool:
        if not isinstance(payload, dict): return False
        for key in ('Latitude', 'Longitude'):
            value = payload.get(key)
            if value not in (None, '', 'N/A'):
                try: float(value)
                except (TypeError, ValueError): return False
        return True
