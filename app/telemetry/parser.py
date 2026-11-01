import json
class TelemetryParser:
    def parse(self, line: str) -> dict | None:
        try:
            value = json.loads(line)
            return value if isinstance(value, dict) else None
        except (json.JSONDecodeError, TypeError): return None
