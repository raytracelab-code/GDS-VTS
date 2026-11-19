# NAV: external data services and vessel-position privacy

This page lists every external (internet) service the NAV map can contact: what each one receives, whether it is on by default, and how to turn it off. It was written for GDS-AUDIT-022, which found that the exact vessel position was being sent to public Overpass servers without disclosure.

## The rule

- **The exact own-vessel position never leaves the PC.** It is used locally for the map marker, the track, and distance/bearing to objects.
- **Requests to providers use a generalised area** (`app/nav/maritime/privacy.py`):
  - **Own-vessel operating area:** the centre is snapped to the nearest **0.5° grid node** (about 30 NM). The radius is enlarged by 22 NM, the worst-case snap offset, so the configured coverage around the real position is still requested in full.
  - **Bounding boxes** in request URLs or bodies are widened **outward** to a **0.05° grid** (about 3 NM). They are never narrowed, so results are not lost. This also covers map-view queries while FOLLOW keeps the view centred on the vessel.
  - **Generic JSON polling feeds** (`latitude` / `longitude` / `radius_nm` parameters) receive a centre snapped to 0.05°, with the radius widened by 3 NM.
- A new own-vessel query is only made when the vessel moves into a different grid cell, after at least 10 NM of movement. That also means fewer requests and more cache hits.

## Services

| Service | Default | What it receives | How to turn it off |
|---|---|---|---|
| OpenFreeMap online basemap (`tiles.openfreemap.org`) | On | Standard map tile requests for the area being viewed, like any web map | Install offline regions (**Map regions…**) and run with `GDS_MAP_SOURCE=offline` |
| NASA GIBS satellite (SATELLITE mode) | On demand | Tile requests for the viewed area | Do not select SATELLITE |
| OpenStreetMap Overpass (`overpass-api.de`, fallback `overpass.private.coffee`) | On | A generalised query box (see above); User-Agent `GDS-VTS-Maritime/4R` | `GDS_OVERPASS_ENABLED=false` |
| GEBCO WMS bathymetry (`wms.gebco.net`) | On | GetCapabilities request plus WMS tiles for the viewed area | `GDS_GEBCO_ENABLED=false` |
| AISStream | Off (needs `AISSTREAM_API_KEY`) | Generalised subscription bounding boxes | Leave the key unset, or set `AISSTREAM_ENABLED=false` |
| Copernicus Marine | Off (needs dataset, user and password; unavailable on the Windows 7/8 build) | Generalised subset box | Leave unconfigured |
| BOEM, EMODnet, Global Fishing Watch, OpenSeaMap, OpenWaters | Off | Generalised boxes or tiles | Off unless explicitly enabled |
| Malaysia offshore GIS | Local files only | Nothing is sent | Not applicable |

Tile requests for the area the operator is viewing are inherent to any online map: the tile server learns which area is displayed, but it is not told the vessel position. For no internet traffic at all, use installed offline regions.

## In the application

**Layers → DATA SOURCES** shows a short notice with the same information.

## Timeouts and shutdown (GDS-AUDIT-023)

- **Socket timeouts:** provider HTTP requests time out after 20 s on connect and on each read. Overpass uses 35 s, because its server-side query budget is 25 s.
- **Copernicus:** a Copernicus subset is limited to 120 s overall.
- **Closing the app:** shutdown waits at most 2 s for in-flight provider requests, then abandons them. Those requests run on daemon worker threads, and the cache is written atomically (temporary file, then replace), so abandoning a request cannot corrupt data.
- **Measured** with a server that accepts connections and never answers: close went from 32.3 s to 2.0 s. See `docs/evidence/non-hardware-fixes/nav/shutdown_stalled_output.txt`.
