"""VDR presentation using the existing native GDS Deep Current theme."""
from string import Template
from app.ui.theme import COLORS, FONT_BODY, FONT_DISPLAY, FONT_DATA


def themed(qss):
    """Share palette/font constants without changing the application's theme."""
    return Template(qss).substitute(COLORS, body=FONT_BODY, display=FONT_DISPLAY, data=FONT_DATA)


STYLE = themed("""
QWidget#vdrPage {background:$workspace;color:$text;}
#vdrPage QWidget {font-family:'$body';font-size:13px;color:$text;background:transparent;}
#vdrPage QFrame#topbar {background:$surface;border-bottom:1px solid $border;}
#vdrPage QLabel#pageTitle {font-family:'$display';font-size:18px;font-weight:600;color:$navy;}
#vdrPage QLabel#subtitle {font-size:10px;letter-spacing:.7px;color:$muted;}
#vdrPage QLabel#chromeText {color:$muted;font-size:11px;}
#vdrPage QLabel#hireValue {color:$dark;font-family:'$data';font-size:13px;font-weight:600;}
#vdrPage QLabel#badge {color:$navy;background:$workspace;border:1px solid $border;border-radius:8px;padding:3px 8px;font-size:11px;font-weight:600;}
#vdrPage QLabel#badge[finalized="true"] {color:#087D70;background:#E6F8F4;border-color:$seafoam;}
#vdrPage QFrame#sidebar {background:$surface;border:1px solid $border;border-radius:14px;}
#vdrPage #sidebar QLabel {color:$muted;font-size:11px;}
#vdrPage #sidebar QLabel#reportDate {color:$dark;font-family:'$data';font-size:14px;font-weight:600;}
#vdrPage QPushButton {min-height:0;border-radius:8px;border:1px solid $border;background:$surface;color:$navy;padding:6px 10px;font-size:13px;font-weight:600;}
#vdrPage QPushButton:hover {background:$workspace;border-color:$light;}
#vdrPage QPushButton:pressed {background:$border;color:$dark;}
#vdrPage QPushButton:checked {background:$navy;color:$surface;border-color:$navy;}
#vdrPage QPushButton:focus {border:1px solid $accent;}
#vdrPage QPushButton:disabled {color:$muted;background:$workspace;border-color:$border;}
#vdrPage #topbar QPushButton {padding:7px 12px;}
#vdrPage #topbar QPushButton#iconButton {font-size:18px;padding:3px 10px;}
#vdrPage #topbar QPushButton#download, #vdrPage #topbar QPushButton#finalize {background:$navy;color:$surface;border-color:$navy;}
#vdrPage #topbar QPushButton#download:hover, #vdrPage #topbar QPushButton#finalize:hover {background:$light;border-color:$light;}
#vdrPage #topbar QPushButton#download:disabled, #vdrPage #topbar QPushButton#finalize:disabled {background:$workspace;color:$muted;border-color:$border;}
#vdrPage #topbar QPushButton#finalize:disabled {background:#E6F8F4;color:#087D70;border-color:$seafoam;}
#vdrPage #sidebar QPushButton {font-size:11px;padding:6px 8px;}
#vdrPage #sidebar QPushButton:checked {background:$navy;color:$surface;border-color:$navy;}
#vdrPage #sidebar QPushButton#sectionNav {border:1px solid transparent;text-align:left;padding:8px 10px;font-size:13px;font-weight:600;}
#vdrPage #sidebar QPushButton#sectionNav:hover {background:$workspace;border-color:$border;}
#vdrPage #sidebar QPushButton#sectionNav:checked {background:$navy;color:$surface;border-color:$navy;}
#vdrPage QFrame#reportPanel {background:$surface;border:1px solid $border;border-radius:14px;}
#vdrPage QFrame#reportSection {border:0;border-bottom:1px solid $border;}
#vdrPage QLabel#sectionHeading {font-family:'$display';font-weight:600;font-size:14px;letter-spacing:.3px;color:$navy;}
#vdrPage QLabel#sectionHint {font-size:11px;color:$muted;}
#vdrPage QLabel#fieldLabel {font-size:10px;color:$muted;letter-spacing:.5px;}
#vdrPage QFrame#formBlock {background:$surface;border:1px solid $border;border-radius:10px;}
#vdrPage QLabel#blockTitle {font-family:'$display';font-weight:600;font-size:12px;color:$dark;}
#vdrPage QLineEdit, #vdrPage QComboBox {min-height:0;background:$surface;border:1px solid $border;border-radius:6px;color:$text;padding:7px 8px;font-size:13px;selection-background-color:$navy;selection-color:$surface;}
#vdrPage QLineEdit:hover, #vdrPage QComboBox:hover {border-color:$light;}
#vdrPage QLineEdit:focus, #vdrPage QComboBox:focus {border:1px solid $navy;}
#vdrPage QLineEdit:read-only {background:$workspace;color:$navy;}
#vdrPage QLineEdit#vdrDateInput {background:$surface;color:$text;}
#vdrPage QLineEdit#vdrDateInput[dateLocked="true"] {background:$workspace;color:$muted;}
#vdrPage QComboBox::drop-down {border:0;width:18px;}
#vdrPage QComboBox QAbstractItemView {font-family:'$body';font-size:13px;color:$text;background:$surface;border:1px solid $border;selection-background-color:$navy;selection-color:$surface;}
#vdrPage QTableWidget {border:1px solid $border;border-radius:8px;background:$surface;gridline-color:$border;}
#vdrPage QHeaderView::section {background:$workspace;border:0;border-right:1px solid $border;border-bottom:1px solid $border;padding:7px 8px;color:$navy;font-family:'$display';font-size:10px;font-weight:600;}
#vdrPage QTableWidget QLineEdit, #vdrPage QTableWidget QComboBox {border:0;border-left:1px solid $border;border-radius:0;padding:7px 8px;font-size:13px;}
#vdrPage QTableWidget QLineEdit:focus, #vdrPage QTableWidget QComboBox:focus {background:$workspace;border:1px solid $navy;}
#vdrPage QTableWidget QPushButton {padding:0;border:0;color:$navy;background:transparent;border-radius:4px;}
#vdrPage QTableWidget QPushButton:hover {background:$workspace;color:$danger;}
#vdrPage QTableWidget QLineEdit#vdrDateInput {font-family:'$data';font-size:12px;}
#vdrPage QLabel#computed {background:$workspace;color:$navy;padding:7px 8px;font-family:'$data';font-size:13px;}
#vdrPage QLabel#metric {font-family:'$data';font-size:16px;font-weight:600;color:$navy;}
#vdrPage QLineEdit[data="true"] {font-family:'$data';}
#vdrPage #weatherReadings {background:$workspace;border:1px solid $border;border-radius:8px;}
#vdrPage QScrollArea {border:0;background:transparent;}
#vdrPage QScrollBar:horizontal {height:12px;background:$workspace;margin:0;}
#vdrPage QScrollBar:vertical {width:10px;background:$workspace;margin:0;}
#vdrPage QScrollBar::handle {background:$border;min-width:24px;min-height:24px;border-radius:4px;}
#vdrPage QScrollBar::handle:hover {background:$muted;}
#vdrPage QLineEdit[plausibility="warning"] {border:1px solid #D9A441;background:#FFFBF0;}
#vdrPage QLineEdit[data="true"] {qproperty-alignment:'AlignRight|AlignVCenter';}
#vdrPage QLineEdit#vdrDateInput {qproperty-alignment:'AlignLeft|AlignVCenter';}
#vdrPage QFrame#storageBanner {background:#FFF7E6;border-bottom:1px solid #F0C36D;}
#vdrPage QFrame#storageBanner[level="error"], #vdrPage QFrame#storageBanner[level="save"] {background:#FDECEC;border-bottom:1px solid $danger;}
#vdrPage QLabel#bannerText {color:$dark;font-size:12px;font-weight:600;}
#vdrPage QFrame#carryNotice {background:$workspace;border:1px solid $border;border-radius:8px;}
#vdrPage QLabel#carryText {color:$muted;font-size:11px;padding:6px 8px;}
#vdrPage QLabel#carryText[attention="true"] {color:$dark;font-weight:600;}
""")

CALCULATION_ERROR_STYLE = themed('color:$text;background:$workspace;border-left:2px solid $danger;font-weight:600;')

VALIDATION_STYLE = themed("""
QWidget {font-family:'$body';font-size:13px;background:transparent;color:$text;}
QDialog {background:$workspace;}
QLabel {color:$text;}
QLabel#validationTitle {font-family:'$display';font-size:16px;font-weight:600;color:$navy;}
QScrollArea {background:$surface;border:1px solid $border;border-radius:10px;}
QPushButton {background:$surface;color:$navy;border:1px solid $border;border-radius:8px;padding:6px 12px;}
QPushButton:hover {background:$workspace;border-color:$navy;}
QPushButton:focus {border-color:$accent;}
""")
