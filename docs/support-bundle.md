# Support bundle

**Where:** Configure → Support & maintenance → **Export support bundle…**

A native Save dialog chooses where to put it. When it's saved, a short confirmation shows the file name and folder.

**Format:** a single ZIP named `GDS-VTS-support-YYYYMMDD-HHMMSS.zip`. It is written atomically: temp file, then rename.

## Contents

| File | What it contains |
|---|---|
| `README.txt` | What the bundle is, and what it does not contain |
| `build_and_runtime.json` | GDS VTS version and stage; edition (Modern / Legacy Compatibility); git commit; Python version; Qt binding and version; OS; architecture; packaged or source; `BUILD_INFO.txt` for packaged builds |
| `settings_sanitized.json` | Every QSettings key (`HKCU\Software\GDS\VTS`) with redaction applied (see below) |
| `diagnostics.json` | Live counters and states (see below) |
| `logs/*.log` | The last 512 KB of each log in `%LOCALAPPDATA%\GDS VTS\logs`, redacted |

**`diagnostics.json` fields:**

| Group | Fields |
|---|---|
| Telemetry | status; active source; valid and invalid frame counts; last valid frame time |
| Connection | packets and bytes per connection; last packet time; connects and reconnects; device port or address; connected flags |
| Capabilities | Native Bluetooth LE |
| Other states | Map renderer state; squall feed state |

## Never included

- VDR or VJR report contents, archived voyages, photos or attachments
- Passwords, API keys, tokens, credentials and cookies
- The vessel's position or track history

## Redaction rules (`app/core/support_bundle.py`)

**Settings and diagnostics:**
- A key containing `password`, `secret`, `token`, `api key`, `credential`, `auth`, `cookie` or `session` → `[redacted]`.
- A key naming a position (`lat`, `lon`, `latitude`, `longitude`, `position`, `track`, `coord…`) → `[omitted: position]`.

**Log text:**
- `password=…`, `token: …`, `api_key=…` and `Authorization: Bearer …` → the value becomes `[redacted]`.
- URL query strings → `?[redacted]`.
- The Windows user-profile path → `%USERPROFILE%`.

**Shown as recorded:** vessel name, IMO, client and Date of Hire. Support needs these to match a bundle to a vessel. Remove them from `settings_sanitized.json` before sending if a contract requires it.
