# VJR mobile photo upload

## Use

Open VJR, then Departure report or Arrival report. At the Back Deck Photo card,
select the PC's Wi-Fi/Ethernet address and press **Generate QR**. Connect the phone
to the same LAN, scan the QR, and use **Take Photo** or **Choose Photo**, then
**Upload Photo**. The desktop preview appears automatically after autosave succeeds.
Departure and Arrival have independent sessions and attachments. Replace via QR
keeps the existing photo until the replacement saves successfully. Delete Photo
asks for confirmation and supports the existing report undo/redo actions.

The page supports JPEG/JPG and PNG up to 15 MiB. Camera/gallery choices depend on
the phone browser. HEIC, WebP, GIF and videos are not supported; choose JPEG/PNG
when the phone offers format options. Decodable images up to 120 megapixels are
accepted. Original bytes are retained, and a correctly EXIF-oriented JPEG preview
is generated at up to 2400 pixels on its longest edge. PNG transparency is flattened
onto white. Excel receives a separate proportional JPEG optimized for its region.

## LAN and troubleshooting

Uploading needs no internet, cloud account, public IP, port forwarding or mobile
application. Select the same physical Wi-Fi/Ethernet network as the phone. Active
physical interfaces are listed ahead of likely VPN/VirtualBox interfaces; loopback,
disconnected, public and link-local addresses are excluded. Refresh rescans adapters.
The card shows the selected address, actual port, full URL, target and countdown.

Use **Can't connect?** for guidance. Check same Wi-Fi/LAN, the selected adapter,
guest-network/client isolation, and Windows Firewall. Allow GDS VTS according to
your organization's policy for trusted Private networks. GDS VTS never edits
firewall rules or requests administrator privileges. Network changes require a new
QR. A Windows security prompt must be handled by the user.

The connection uses local HTTP, without transport encryption. Use a trusted LAN;
anyone with the live QR URL can submit a photo into its single target slot. Do not
publish the QR. A VPN adapter can be selected deliberately, but its reachability
depends on routing and firewall policy.

## Architecture and session boundary

`PhotoController` starts the embedded standard-library HTTP server only on the first
Generate QR action. It binds to the selected RFC1918 IPv4 address and an OS-selected
free port. The service API also accepts a preferred port and falls back to a free
port when occupied. It does not bind to every interface. Four bounded request
workers have socket timeouts; decoding is serialized to bound memory pressure.
Shutdown cancels sessions and pending deliveries, closes connections, joins workers
and releases the listener. No separate server process is created.

Each Generate/Regenerate creates a cryptographically random 256-bit bearer token
bound to one hidden report identity and one slot. Regeneration cancels that slot's
older token. Sessions expire after ten minutes and become unusable after successful
upload, cancellation, or three failed attempts. Changing reports cancels old sessions;
a late delivery is checked again before attaching it. Expiry uses a monotonic clock.

Only `GET /vjr-photo/<token>` and `POST /vjr-photo/<token>` are application endpoints.
POST contains the raw image file rather than multipart data. The server checks the
local peer, exact Host, same-origin headers, token, declared length, extension, MIME
type, actual image format and complete decoding. Oversize bodies are rejected before
storage. Filenames never become disk paths. Responses disable caching and referrers,
restrict page resources, and show friendly errors without stack traces. There are
no browsing, arbitrary download, shell, cloud or remote-control endpoints. Logs
record event type, slot and port, never full tokens, image bytes or report contents.

The worker emits a queued Qt signal. The GUI thread checks report/session identity,
atomically saves through `VjrStore.mutate`, updates the card and acknowledges success.
The phone receives success only after that commit. Timed-out/cancelled deliveries
cannot commit later. Failed deliveries discard their staged image.

## Persistence and Excel

Existing writable `AppLocalDataLocation/vjr/report.json` gains only optional
`photo_report_id` and `photos` fields. The two allowed keys are
`departure_back_deck_photo` and `arrival_back_deck_photo`. Each value is a relative
immutable attachment reference:

```
vjr/attachments/<random-report-id>/photos/<random-attachment-id>/
    original.jpg (or original.png)
    photo.jpg
    info.json
```

Original and preview files are written before the atomic report update. References
survive restart; missing images show a replace/delete instruction and block export
with a clear error rather than silently omitting an expected photo. Cleanup retains
current, undo, redo and pending references. Removed files are reclaimed when safe;
other report directories and attachments belonging to an unreadable report are
preserved. Move/back up the JSON and attachment tree together. Nothing is stored in
Program Files or a hardcoded user directory.

The original immutable workbook is still the source for every export. Departure
and Arrival photos replace only the original photo drawing anchor within L10:U27
on `4. Departure Report` and `5. Arrival Report`. The heading at row 9 stays intact.
Images are centered, fitted proportionally, scaled down only, and never change row
or column dimensions. Original logos, sheet order, formatting, merges, formulas,
labels, guides and print settings are preserved. Without an uploaded photo, the
original drawing parts remain byte-for-byte unchanged (including any original
template illustration). Unrelated cell mappings are unchanged. The exporter patches
OOXML parts directly, retaining original archive media rather than rewriting the
workbook with openpyxl.

## Dependencies and compatibility

Both dependency sets pin `qrcode==7.4.2`, `pypng==0.20220715.0` and
`colorama==0.4.6`. QR generation is local. Pillow is pinned to 13.0.0 in the modern
environment and remains 9.5.0 in the Python 3.8 legacy environment. The implementation
uses Python 3.8-compatible syntax and the existing Qt facade; adapter enumeration
loads the appropriate QtNetwork module for PySide2 or PySide6. Both PyInstaller
specifications include QR modules, required Pillow plugins and QtNetwork. The mobile
HTML lives under the already bundled `app/resources` tree.

Windows 7 SP1 compatibility remains governed by the controlled legacy environment
and build specification. Passing Python 3.8/PySide2 tests on this host does not
constitute testing on physical Windows 7 hardware. BLE/Copernicus limitations are
unchanged.

## Verification and evidence

Automated coverage lives in `tests/test_vjr_photos.py` and
`tests/test_vjr_photo_ui.py`: endpoints, invalid/expired/used/cancelled links, limits,
orientation, restart, replacement/deletion/history retention, late-report isolation,
main-thread delivery, QR/card states, bounded concurrency, repeated shutdown and all
four Excel photo combinations. The immutable source workbook hash and unrelated
archive parts are checked.

`tools/verify_vjr_photo_acceptance.py` generates test-only landscape/portrait fixtures,
card screenshots and `docs/evidence/VJR_excel_photo_acceptance.xlsx` using isolated
data under `build`. Pictured QR codes are expired evidence, not live upload links.
See `docs/vjr-mobile-photo-upload-acceptance.md` for exact run results and outstanding
physical-device checks. Do not claim a real camera or phone upload based on the
automated HTTP tests.
