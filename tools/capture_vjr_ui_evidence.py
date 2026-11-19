"""Capture real Qt widgets with isolated test fixtures; never touch user reports."""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from app.qt.QtCore import QPoint
from app.qt.QtGui import QFont, QImage, QPainter
from app.qt.QtWidgets import QApplication, QFrame
from app.ui.pages.vjr_workspace import VjrPage
from app.ui.pages.vdr.workspace import VdrPage
from app.vjr.store import VjrStore
from app.vdr.store import ReportStore
from vjr_fixture import full_report
from test_vdr import fixture_report


def main():
    app = QApplication.instance() or QApplication([])
    QFont.insertSubstitutions('Cascadia Mono',['Consolas','JetBrains Mono','Courier New'])
    QFont.insertSubstitutions('Segoe UI Semibold',['Segoe UI','Arial'])
    destination = ROOT/'docs/evidence/vjr-ui-redesign'
    destination.mkdir(parents=True,exist_ok=True)
    captures = []
    def settle():
        for _ in range(6):
            app.processEvents()
    with tempfile.TemporaryDirectory(prefix='gds-vjr-ui-') as directory:
        store = VjrStore(Path(directory)/'vjr.json'); store.report = full_report()
        page = VjrPage(store,lambda:{})
        page.resize(1600,900); page.show(); settle()
        def capture(name,index=None,size=None,card=None,horizontal=False):
            if size:
                page.resize(*size)
            if index is not None:
                page.tabs.setCurrentIndex(index)
            settle()
            scroll = page.tabs.currentWidget()
            scroll.verticalScrollBar().setValue(0)
            if card:
                widget = next(w for w in scroll.findChildren(QFrame) if w.property('cardTitle')==card)
                scroll.verticalScrollBar().setValue(widget.mapTo(scroll.widget(),QPoint(0,0)).y())
            if horizontal:
                table = page.tables[('progress',)][0]
                table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
            settle()
            path = destination/(name+'.png')
            if not page.grab().save(str(path)):
                raise OSError('Could not capture '+str(path))
            captures.append(dict(file=path.name,width=page.width(),height=page.height(),section=page.tabs.tabText(page.tabs.currentIndex())))
        capture('01_overview_header',0)
        capture('02_general_information',0,(1366,768))
        capture('03_core_crew',1,(1600,900))
        capture('04_contractors',2)
        capture('05_waypoint_plan',3)
        capture('06_departure_report',4)
        capture('07_departure_deck_space',4,card='Deck Space')
        capture('08_departure_inventory',4,card='Inventory')
        capture('09_arrival_report',5)
        capture('09b_arrival_departure_reference',5,card='Departure Reference · Linked')
        capture('10_voyage_progress',6,(1920,1080))
        capture('10b_voyage_weather_and_remarks',6,horizontal=True)
        capture('11_departure_photo_reserved',4,(1600,900),card='Back Deck Photo')
        capture('12_arrival_photo_reserved',5,card='Back Deck Photo (After Lifts)')
        for name,size in [('13_responsive_1920',(1920,1080)),('14_responsive_1600',(1600,900)),('15_responsive_1366',(1366,768))]:
            capture(name,4,size)
        capture('16_vjr_comparison',4,(1600,900))
        vjr_image = page.grab().toImage()
        vdr_store = ReportStore(Path(directory)/'vdr.json',today='2026-11-19')
        vdr_store.reports[vdr_store.current] = fixture_report('2026-11-19')
        vdr = VdrPage(vdr_store); vdr.resize(1600,900); vdr.show(); settle()
        vdr_image = vdr.grab().toImage(); vdr_image.save(str(destination/'17_vdr_reference.png'))
        comparison = QImage(3200,900,QImage.Format.Format_ARGB32)
        comparison.fill(0xffffffff); painter = QPainter(comparison)
        painter.drawImage(0,0,vdr_image); painter.drawImage(1600,0,vjr_image); painter.end()
        comparison.save(str(destination/'18_vdr_vjr_side_by_side.png'))
        page.tabs.setCurrentIndex(0); settle()
        page.editors[('meta','capacity')].setText('-1')
        page.set_field(('meta','capacity'),'-1'); settle()
        page.grab().save(str(destination/'19_inline_validation.png'))
        store.report = full_report(); page.rebuild(); page.tabs.setCurrentIndex(1); settle()
        for group,capacity in [('crew',200),('contractors',200),('waypoints',30),('progress',100)]:
            source = store.report[group][0]
            store.report[group] = [dict(source) for _ in range(capacity)]
        page.rebuild(); settle()
        identities = {key:id(value[0]) for key,value in page.tables.items()}
        before = time.perf_counter()
        page.set_field(('crew',0,'remarks'),'Performance check')
        elapsed = time.perf_counter()-before
        assert identities=={key:id(value[0]) for key,value in page.tables.items()}
        page.grab().save(str(destination/'20_full_capacity_crew.png'))
        manifest = dict(captures=captures,full_capacity_edit_seconds=round(elapsed,4),
                        widgets_reused_on_edit=True,fixture='tests/vjr_fixture.py',user_store_modified=False)
        (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        vdr.save_timer.stop(); vdr.close(); page.close(); settle()
    print(destination)


if __name__=='__main__':
    main()
