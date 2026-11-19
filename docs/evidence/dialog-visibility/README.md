# Dialog visibility audit

## How dialogs now behave

Every application-created pop-up goes through `app/ui/dialogs.py`. Native Windows file dialogs are left native.

- **Fit and position (`fit_to_screen`).** Every pop-up is sized and placed so the **whole window, title bar included**, stays inside the usable area of the screen that shows the main window. The taskbar is excluded and the size is capped at 92 % of that area. It opens centred on the main window, so it follows the main window to another monitor. The title-bar height is measured from the real main window, which matters because Qt5 and Qt6 differ.
- **Run (`exec_dialog`).** Each dialog is modal to its parent, so it can never open behind the main window. No always-on-top flags are used.
- **Messages (`notify`, `confirm`).** GDS styling is applied:
  - message text wraps at 520 px, and long paths get break points inserted;
  - technical detail sits behind **Show Details…**;
  - buttons have clear names, such as "Reopen report" and "Delete photo";
  - for destructive actions, the default button and Esc are **Cancel**.
- **Issue lists (`IssuesDialog`).** Layout is a header, a scrolling list of groups, and a fixed footer with **Close**. Each group has one clearly named action, such as **Open Vessel & Client** or **Go to Activity log**.
- **Main window.** On first show it is kept on a connected screen and within its usable area.

## Checklist (all application dialogs)

**Configurations tested:**

| Source | Configurations |
|---|---|
| `capture_dialogs.py` | 1920×1080, 1600×900, 1366×768 and 1280×720 at 100 % (Qt6); 1366×768 at 125 % and 150 % (Qt6 and Qt5); 1366×768 and 1280×720 at 100 % (Qt5) |
| `app_sweep.py` | The real MainWindow at 1366×768, Qt6 and Qt5 |

| # | Dialog | Trigger | Fits | Footer visible | Changes |
|---|---|---|---|---|---|
| 1 | Finalize validation | VDR → Finalize report | ✓ | ✓ | Rebuilt: issues grouped by destination; one action per group ("Open Vessel & Client" replaces "01 REPORT & HSE · 2 / Go"); scrolling list; fixed Close |
| 2 | Imported as a draft | VDR → Import (invalid finalized PDF) | ✓ | ✓ | Same dialog as 1 |
| 3 | Previous reports | VDR sidebar | ✓ | ✓ | Fitted; GDS styling; only the list scrolls; empty state |
| 4 | Reopen finalized report | VDR → Reopen report | ✓ | ✓ | States the date, Report No., status and the next REV; Cancel is the default |
| 5 | Replace existing report | VDR → Import onto an existing day | ✓ | ✓ | "Replace report" / Cancel (Cancel is the default) |
| 6 | Import failed | VDR → Import (bad PDF) | ✓ | ✓ | Plain message; error and path under Details |
| 7 | PDF not created | VDR → Download PDF (error) | ✓ | ✓ | Path under Details; wraps |
| 8 | Excel not created (several issues) | VDR → Download Excel | ✓ | ✓ | Grouped, scrollable issue dialog instead of one long message box |
| 9 | Excel not created (single error) | VDR → Download Excel | ✓ | ✓ | Path under Details |
| 10 | VJR validation before Excel | VJR → Download Excel | ✓ | ✓ | Was a 20-line message box. Now grouped by VJR section, each with "Go to …" |
| 11 | VJR Excel not created | VJR → Download Excel (error) | ✓ | ✓ | Path under Details |
| 12 | Start a new voyage? | VJR → New voyage… | ✓ | ✓ | Bulleted consequences; "Start new voyage" / Cancel |
| 13 | Voyage history | VJR sidebar | ✓ | ✓ | Fitted; GDS styling; two-line headers (no clipping at 125–150 %); empty state |
| 14 | Make this the current journey? | Voyage history | ✓ | ✓ | Bulleted consequences; "Make current" / Cancel |
| 15 | Voyage not restored | Voyage history (error) | ✓ | ✓ | Detail under Details |
| 16 | Local network upload help | VJR photo card → "Can't connect?" | ✓ | ✓ | Wrapped, styled |
| 17 | Delete this photo? | VJR photo card → Delete | ✓ | ✓ | "Delete photo" / Cancel (Cancel is the default) |
| 18 | Offline map regions | NAV → Layers → Map regions… | ✓ | ✓ | Fitted to the screen; the region list scrolls; **Close button added** |
| 19 | Remove this map region? | Map regions → Remove | ✓ | ✓ | "Remove region" / Cancel (Cancel is the default) |
| 20 | Offline map regions error | Map regions (install error) | ✓ | ✓ | Detail under Details |
| 21 | Vessel Configuration | NAV → vessel config | ✓ | ✓ | Fitted; GDS-styled fields |
| 22 | Spatial package activated / not imported | NAV → Import spatial package | ✓ | ✓ | Wrapped; detail under Details |

**Inline UI, not a pop-up, checked in context:**
- **Renderer failure overlay** (`nav_page.py`): an inline panel over the map, never a modal and never repeated. Its width is bounded to 280–520 px.
- **Storage and recovery banners** (VDR banner, VJR notice): inline, with word wrap. Long paths now break.
- **Connection messages** (Configure cards): inline, so transient device events never open modals.
- **Vessel & Client card** (Configure): inline form.
- **Calendar popover** (`date_picker.py`): already clamped to the screen's available geometry.
- **QR photo card**: inline in the VJR page. Its minimum width (~600 px) fits the VJR content area at 1366×768; `test_photo_card_qr_fits_vjr_content_width` checks this.

**Native, unchanged:** Download PDF, Download Excel (VDR and VJR), Import VDR report, Import spatial package.

## Evidence files

- `<size>@<scale>%-<Qt>/NN_*.png` and `checklist.json` (geometry, fits screen, footer visible) for each configuration.
- `app-sweep/*.png` and `sweep_PySide6.json` / `sweep_PySide2.json`: real MainWindow results (modal, parented, active, inside the screen, offset from the main window's centre, button visibility).
- `baseline/`, `final/`: test logs.
