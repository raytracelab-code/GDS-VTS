import threading
import pytest
from app.qt.QtWidgets import QMessageBox
from app.ui.pages.vjr_photos import PhotoController, PhotoCard, qr_png
from app.vjr.photo_network import LanAddress
from app.vjr.photo_server import UploadService
from app.vjr.photo_storage import SLOTS
from app.vjr.store import VjrStore
from test_vjr_photos import photo_bytes, request


@pytest.fixture
def photo_ui(qtbot,tmp_path):
    store=VjrStore(tmp_path/'report.json'); clock=[0.0]
    controller=PhotoController(store,address_provider=lambda:[LanAddress('127.0.0.1','Isolated test')],
        service_factory=lambda storage,deliver:UploadService(storage,deliver,lifetime=10,clock=lambda:clock[0],allow_loopback=True))
    cards=[PhotoCard(controller,slot) for slot in SLOTS]
    for card in cards:
        qtbot.addWidget(card); card.show()
    yield controller,cards,store,clock
    controller.close()


def test_generate_wait_upload_preview_restart_replace_delete(photo_ui,qtbot,monkeypatch):
    controller,cards,store,clock=photo_ui; card=cards[0]
    main_thread=threading.get_ident(); mutations=[]; mutate=store.mutate
    def record(action):
        mutations.append(threading.get_ident()); mutate(action)
    monkeypatch.setattr(store,'mutate',record)
    card.generate_button.click()
    state,session=controller.state(SLOTS[0])
    assert state=='waiting' and card.qr.isVisible() and card.qr.pixmap() is not None
    result=[]
    worker=threading.Thread(target=lambda:result.append(request(controller.service,session,photo_bytes())))
    worker.start(); qtbot.waitUntil(lambda:bool(result),timeout=8000); worker.join()
    controller.tick()
    assert result[0][0]==200 and card.preview.isVisible()
    assert 'Preview available' in card.status.text()
    reference=store.report['photos'][SLOTS[0]]
    assert VjrStore(store.path).report['photos'][SLOTS[0]]==reference
    assert all(thread==main_thread for thread in mutations)
    card.generate_button.click(); _,replacement=controller.state(SLOTS[0])
    assert replacement.token!=session.token and store.report['photos'][SLOTS[0]]==reference
    card.cancel_button.click(); assert store.report['photos'][SLOTS[0]]==reference
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.StandardButton.Yes)
    card.delete_button.click()
    assert SLOTS[0] not in store.report['photos'] and not card.preview.isVisible()
    assert 'No photo uploaded' in card.status.text()
    store.undo(); controller.sync(); card.refresh(); assert card.preview.isVisible()


def test_qr_expiration_and_slot_independence(photo_ui):
    controller,cards,store,clock=photo_ui
    cards[0].generate_button.click(); first=controller.state(SLOTS[0])[1]
    cards[1].generate_button.click(); second=controller.state(SLOTS[1])[1]
    assert first.slot!=second.slot and first.token!=second.token
    assert controller.state(SLOTS[0])[0]=='waiting'
    clock[0]=11; controller.tick()
    assert 'expired' in cards[0].status.text() and not cards[0].qr.isVisible()
    assert controller.state(SLOTS[1])[0]=='expired'
    assert qr_png('http://192.168.1.2:12345/vjr-photo/'+'A'*43).startswith(b'\x89PNG')


def test_missing_photo_preview_is_clear(photo_ui):
    controller,cards,store,_=photo_ui
    cards[0].generate_button.click(); identity=store.report['photo_report_id']
    store.report['photos'][SLOTS[0]]=identity+'/photos/'+'a'*32
    cards[0].refresh()
    assert 'unavailable' in cards[0].status.text()
