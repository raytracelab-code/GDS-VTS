"""Generate test-only photo/Excel/UI evidence without altering user report data."""
from io import BytesIO
import json
from pathlib import Path
import sys
import uuid
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from vjr_fixture import full_report
from app.vjr.store import VjrStore
from app.vjr.photo_storage import PhotoStorage, SLOTS
from app.vjr.excel import VjrExcelExporter


def test_image(title,size,color):
    image=Image.new('RGB',size,color); drawing=ImageDraw.Draw(image)
    for x in range(0,size[0],100):
        drawing.line((x,0,x,size[1]),fill='#9ac4d4',width=2)
    for y in range(0,size[1],100):
        drawing.line((0,y,size[0],y),fill='#9ac4d4',width=2)
    drawing.rectangle((25,25,size[0]-25,size[1]-25),outline='white',width=8)
    drawing.rectangle((45,45,min(size[0]-45,650),160),fill='white')
    font=ImageFont.truetype(str(ROOT/'app/resources/vdr/inter.ttf'),30)
    small=ImageFont.truetype(str(ROOT/'app/resources/vdr/inter.ttf'),20)
    drawing.text((65,65),title,fill='#18334d',font=font)
    drawing.text((65,110),'TEST ONLY - ASPECT RATIO / PLACEMENT',fill='#18334d',font=small)
    output=BytesIO(); image.save(output,'JPEG',quality=94)
    return output.getvalue()


def main():
    destination=ROOT/'docs/evidence/vjr-mobile-photo'
    destination.mkdir(parents=True,exist_ok=True)
    data_root=ROOT/'build/vjr-photo-acceptance-data'; data_root.mkdir(parents=True,exist_ok=True)
    store=VjrStore(data_root/'report.json')
    store.report=full_report(); store.report.update(photo_report_id=uuid.uuid4().hex,photos={})
    storage=PhotoStorage(data_root/'attachments')
    for slot,title,size,color,name in [
        (SLOTS[0],'DEPARTURE PHOTO',(1200,700),'#205b78','departure_test.jpg'),
        (SLOTS[1],'ARRIVAL PHOTO',(700,1100),'#28796e','arrival_test.jpg')]:
        image=test_image(title,size,color); (destination/name).write_bytes(image)
        reference=storage.create(store.report['photo_report_id'],image,name,'image/jpeg')
        store.report['photos'][slot]=reference; storage.release(reference)
    store.save()
    VjrExcelExporter(photo_root=storage.root).export(store.report,ROOT/'docs/evidence/VJR_excel_photo_acceptance.xlsx')
    from app.qt.QtWidgets import QApplication
    from app.qt.QtGui import QFont
    from app.qt.QtCore import QPoint
    from app.ui.pages.vjr_workspace import VjrPage
    from app.ui.pages.vjr_photos import qr_png
    app=QApplication.instance() or QApplication([])
    QFont.insertSubstitutions('Segoe UI Semibold',['Segoe UI','Arial'])
    page=VjrPage(store,lambda:{}); page.resize(1600,1000); page.show()
    def settle():
        for _ in range(6): app.processEvents()
    for index,slot,name in [(4,SLOTS[0],'departure_preview.png'),(5,SLOTS[1],'arrival_preview.png')]:
        page.tabs.setCurrentIndex(index); settle()
        card=page.photo_cards[slot]; scroll=page.tabs.currentWidget()
        scroll.verticalScrollBar().setValue(card.mapTo(scroll.widget(),QPoint(0,0)).y()); settle()
        page.grab().save(str(destination/name))
    # A temporary isolated LAN session demonstrates the actual QR card. Closing
    # this evidence process immediately invalidates the pictured token.
    addresses=page.photo_controller.address_provider()
    if addresses:
        page.tabs.setCurrentIndex(4); settle()
        card=page.photo_cards[SLOTS[0]]; card.generate(); settle()
        scroll=page.tabs.currentWidget(); scroll.verticalScrollBar().setValue(card.mapTo(scroll.widget(),QPoint(0,0)).y()); settle()
        page.grab().save(str(destination/'qr_waiting.png'))
        state,session=page.photo_controller.state(SLOTS[0])
        if session:
            (destination/'qr_example.png').write_bytes(qr_png(page.photo_controller.service.url(session)))
    page.close(); settle()
    print(ROOT/'docs/evidence/VJR_excel_photo_acceptance.xlsx')


if __name__=='__main__':
    main()
