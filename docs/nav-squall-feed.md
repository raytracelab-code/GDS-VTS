# NAV squall feed: architecture, gap and states (GDS-AUDIT-021)

## Existing architecture (before this change)

| Part | Where | Role |
|---|---|---|
| Event model and validation | `app/nav/events/models.py`, `validator.py` | One squall event: position, direction, speed, severity, predicted path, impact and surveillance radii, source, expiry. Operations are CREATE, UPDATE and CLEAR. |
| Event store and lifecycle | `app/nav/events/service.py` (`SquallEventService`) | Holds events. An event turns **STALE** 120 s after it was received and **EXPIRED** (removed) after 600 s or at `expires_at`. |
| Ingest boundary | `MainWindow.ingest_squall_event(dict)` / `ingest_squall_json(text)` | The only entry point for squall data. |
| Map and panel payload | `app/nav/events/render_state.py`, `MapBridge.getEventState` / `publishEventState` | GeoJSON for the squall layers, plus the event list for the NAV panel. |
| Map layers | `app/resources/map/nav.js` (`ensureEventLayers`, `applyEventState`) | Current position, direction, trajectory, impact and surveillance zones, and ETA points. STALE events are drawn at reduced opacity. |
| Data source | **none in production** | Only `tools/dev_squall_events.py` (a synthetic development scenario) calls the ingest boundary. |

## The gap (from the audit and the code)

1. **No squall provider exists.** Nothing feeds the ingest boundary in production, so an empty list looked like an all-clear.
2. **No feed-level state.** Only individual events had a status. "No events" could not be told apart from "feed silent", "feed failed" or "no provider".
3. **No last-update time** for the feed.
4. **Impact judged against project site polygons only**, never against the vessel's own position.
5. **ETA did not count down.** It was measured from `observed_at` and was frozen at that value.
6. **No top-level alert.** The squall list sits deep inside the Layers panel.

## What was implemented (no new backend, no invented data)

- **Feed states.** `SquallEventService.feed_status()`:

  | State | Meaning |
  |---|---|
  | `LIVE` | A valid message or heartbeat arrived less than 120 s ago. |
  | `STALE` | The last message is 120 s old or older. |
  | `NO DATA` | A provider is attached but has not sent anything yet. |
  | `PROVIDER UNAVAILABLE` | No provider is configured (the state of this build), or the provider reported a failure. |

  The last update is the **receipt time** of the last valid message (`last_update`, `age_seconds`). Each event keeps its own source `observed_at`.
- **Provider interface for a future adapter.** No external service was added. A feed adapter calls:
  - `attach_provider(name)`;
  - `heartbeat()`;
  - `provider_failed(reason)`, which immediately marks every event **STALE** so none is shown as current. Events then expire through the normal 600 s lifecycle, which removes their shapes from the map.
  - `provider_recovered()`.

  Ingesting any valid message also marks the feed as delivering. Recovery therefore needs no restart.
- **Panel text.** The NAV squall panel shows the feed state and the time since the last update:
  - "SQUALL FEED LIVE · updated 12 s ago"
  - "SQUALL FEED STALE · last update 3 min 22 s ago … may be out of date"
  - "SQUALL PROVIDER UNAVAILABLE · no warnings are being received"

  An empty list reads as "no active warnings" only when the feed is LIVE.
- **Own-vessel impact.** `impact.evaluate_vessel` judges each event against the vessel's last known position:
  - **IMPACT** within the impact radius of the current or any predicted position;
  - **SURVEILLANCE** within the surveillance radius.

  The site-polygon result is kept, and the stronger of the two applies. Without a position nothing is assumed.
- **ETA countdown.** The ETA counts down from now. A passed point shows **PASSED**. The map is re-sent only when a visible label changes, so not every second.
- **Top-level alert.**
  - A red (IMPACT) or amber (SURVEILLANCE) banner appears over the map, e.g. "⚠ SQUALL IMPACT · SQ-1 · own vessel inside impact zone · ETA 9 min".
  - The NAV rail button shows **NAV ⚠** on every page.
  - Alerts based on a feed that is not LIVE are labelled "LAST RECEIVED DATA".

## Still needed (not software-fixable here)

- **A real squall data provider and its adapter.** This is a product and contract decision: which source, and over which transport. When one exists, it plugs into the interface above.
- **Validation of thresholds and geometry against real meteorological feeds.** This covers the 120 s staleness threshold, the 600 s expiry and the impact geometry.
