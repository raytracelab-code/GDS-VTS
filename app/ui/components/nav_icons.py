"""Small original line icons shared by the rail and floating NAV controls."""
from app.qt.QtCore import QByteArray, Qt
from app.qt.QtGui import QIcon, QPainter, QPixmap
from app.qt.QtSvg import QSvgRenderer

PATHS = {
    'Configure': '<path d="M5 7h14M5 17h14M9 4v6m6 4v6"/>',
    'VDR': '<rect x="5" y="4" width="14" height="16" rx="2"/><path d="M8 9h8m-8 4h8m-8 4h5"/>',
    'VJR': '<path d="M5 5h14v14H5zM8 9h8m-8 4h5m-5 4h8"/>',
    'Nav': '<path d="m12 3 8 18-8-5-8 5z"/>',
    'CENTER VESSEL': '<circle cx="12" cy="12" r="6"/><path d="M12 2v6m0 8v6M2 12h6m8 0h6"/>',
    'FOLLOW': '<path d="m4 11 16-7-7 16-2-7z"/>',
    'NORTH UP': '<path d="m6 19 6-15 6 15-6-4z"/>',
    'FIT TRACK': '<path d="M4 9V4h5m6 0h5v5m0 6v5h-5M9 20H4v-5m3-1 4-5 3 5 3-4"/>',
    'MARINE': '<path d="M3 7c3-4 6 4 9 0s6 4 9 0M3 12c3-4 6 4 9 0s6 4 9 0M3 17c3-4 6 4 9 0s6 4 9 0"/>',
    'SATELLITE': '<path d="m4 9 5-5 11 11-5 5zM3 16l5 5m-3-3 4-4m6-11 6 6m-5-1 4-4"/>',
    'LAYERS': '<path d="m3 8 9-5 9 5-9 5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',
    'WEATHER': '<path d="M6 16a4 4 0 1 1 0-8 6 6 0 0 1 11-1 4.5 4.5 0 0 1 1 9M9 18l-1 3m6-3-1 3m6-3-1 3"/>',
    '2D': '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 10h8m-8 4h8"/>',
    '3D': '<path d="m12 3 8 5v9l-8 5-8-5V8zm0 10 8-5m-8 5L4 8m8 5v9"/>',
    'VESSEL CONFIG': '<path d="M4 14h16l-3 6H7zM9 14V5h6v9M12 2v3M2 22h20"/>',
    'SEARCH': '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    'CLOSE': '<path d="m6 6 12 12M6 18 18 6"/>',
}


def nav_icon(name, color='#b9ccd6'):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name, PATHS["Nav"])}</g></svg>'
    pixmap = QPixmap(24, 24); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)
