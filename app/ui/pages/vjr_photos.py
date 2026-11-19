"""Qt-thread photo commits and the two VJR mobile-upload cards."""
from io import BytesIO
import logging
import math
import uuid
import qrcode
from qrcode.image.pil import PilImage
from app.qt.QtCore import QObject, QTimer, Qt, Signal, Slot
from app.qt.QtGui import QPixmap
from app.qt.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
                              QMessageBox, QPushButton, QVBoxLayout)
from app.vjr.photo_network import lan_addresses
from app.vjr.photo_server import UploadService, INACTIVE
from app.vjr.photo_storage import PhotoError, PhotoStorage, SLOTS, TITLES, references

LOG = logging.getLogger(__name__)
HELP = ('Ensure the phone and PC are on the same Wi-Fi/LAN.\n\n'
        'Allow GDS VTS through Windows Firewall on Private networks if Windows requests permission. '
        'GDS VTS does not change firewall rules.\n\n'
        'Check the selected network interface and PC address, then regenerate the QR. '
        'Guest Wi-Fi or client isolation may prevent devices reaching each other.')


def qr_png(url):
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=6,border=4)
    code.add_data(url); code.make(fit=True)
    output = BytesIO(); code.make_image(image_factory=PilImage).save(output,format='PNG')
    return output.getvalue()


class PhotoController(QObject):
    delivery = Signal(object)
    changed = Signal(str)

    def __init__(self, store, parent=None, address_provider=None, service_factory=None):
        super().__init__(parent)
        self.store = store; self.storage = PhotoStorage(store.path.parent/'attachments')
        self.address_provider = address_provider or lan_addresses
        self.service = (service_factory or UploadService)(self.storage,self.delivery.emit)
        self.tokens = {}; self.identity = store.report.get('photo_report_id','')
        self.last_references = None
        self.delivery.connect(self.receive,Qt.ConnectionType.QueuedConnection)
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self.tick)
        QApplication.instance().aboutToQuit.connect(self.close)

    def generate(self, slot, address, preferred_port=0):
        if slot not in SLOTS:
            raise PhotoError('Unknown photo slot')
        if self.store.load_error:
            raise PhotoError(self.store.load_error)
        if not self.store.report.get('photo_report_id'):
            identity = uuid.uuid4().hex
            self.store.mutate(lambda report:report.update(photo_report_id=identity,photos={}))
        self.sync()
        self.service.start(address,preferred_port)
        session = self.service.create_session(self.store.report['photo_report_id'],slot)
        self.tokens[slot] = session.token
        self.timer.start(); self.changed.emit(slot)
        return session

    def cancel(self, slot):
        token = self.tokens.get(slot)
        if token:
            self.service.sessions.cancel(token)
        self.changed.emit(slot)

    def sync(self):
        identity = self.store.report.get('photo_report_id','')
        if identity!=self.identity:
            self.service.sessions.cancel_all(); self.tokens.clear(); self.identity = identity
        current = frozenset(references(self.store))
        if current!=self.last_references:
            self.storage.collect(self.store); self.last_references = current

    def tick(self):
        self.sync()
        for slot in list(self.tokens):
            self.changed.emit(slot)
        if not any(self.state(slot)[0] in ('waiting','uploading','error') for slot in self.tokens):
            self.timer.stop()

    def state(self, slot):
        token = self.tokens.get(slot)
        if not token:
            return '',None
        try:
            session = self.service.sessions.get(token)
        except PhotoError:
            self.tokens.pop(slot,None)
            return '',None
        return session.state,session

    @Slot(object)
    def receive(self, delivery):
        def commit():
            session = delivery.session
            if self.store.report.get('photo_report_id')!=session.report_id or not self.service.accepts(delivery):
                raise PhotoError(INACTIVE)
            self.store.mutate(lambda report:report.setdefault('photos',{}).__setitem__(session.slot,delivery.reference))
        delivery.apply(commit)
        if delivery.success:
            self.changed.emit(delivery.session.slot)

    def delete(self, slot):
        self.cancel(slot)
        self.store.mutate(lambda report:report.setdefault('photos',{}).pop(slot,None))
        self.sync(); self.changed.emit(slot)

    def close(self):
        self.timer.stop(); self.service.close()
        self.storage.collect(self.store)


class PhotoCard(QFrame):
    def __init__(self, controller, slot, parent=None):
        super().__init__(parent)
        self.controller = controller; self.slot = slot; self.last_reference = None; self.last_token = None
        self.setObjectName('photoCard')
        self.setProperty('cardTitle','Back Deck Photo' if slot==SLOTS[0] else 'Back Deck Photo (After Lifts)')
        layout = QVBoxLayout(self); layout.setContentsMargins(16,14,16,16); layout.setSpacing(12)
        title = QLabel(TITLES[slot]); title.setObjectName('blockTitle'); layout.addWidget(title)
        self.status = QLabel('No photo uploaded'); self.status.setWordWrap(True); layout.addWidget(self.status)
        network_row = QHBoxLayout(); network_row.addWidget(QLabel('Network'))
        self.network = QComboBox(); self.network.setMinimumWidth(220); self.network.setMaximumWidth(400)
        network_row.addWidget(self.network,1)
        refresh = QPushButton('Refresh'); refresh.clicked.connect(self.refresh_networks); network_row.addWidget(refresh); network_row.addStretch()
        layout.addLayout(network_row)
        media = QHBoxLayout(); media.setSpacing(16)
        self.preview = QLabel(); self.preview.setFixedSize(280,210); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setObjectName('photoPreview'); media.addWidget(self.preview)
        self.qr = QLabel(); self.qr.setFixedSize(280,280); self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setObjectName('photoQr'); media.addWidget(self.qr); media.addStretch(); layout.addLayout(media)
        self.address = QLabel(); self.address.setWordWrap(True); self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.address.setObjectName('sectionHint'); layout.addWidget(self.address)
        self.expiry = QLabel(); self.expiry.setObjectName('sectionHint'); layout.addWidget(self.expiry)
        actions = QHBoxLayout()
        self.generate_button = QPushButton('Generate QR'); self.generate_button.clicked.connect(self.generate); actions.addWidget(self.generate_button)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.clicked.connect(lambda:self.controller.cancel(self.slot)); actions.addWidget(self.cancel_button)
        self.delete_button = QPushButton('Delete Photo'); self.delete_button.setObjectName('deleteRow'); self.delete_button.clicked.connect(self.delete); actions.addWidget(self.delete_button)
        actions.addStretch(); help_button = QPushButton("Can't connect?"); help_button.clicked.connect(lambda:QMessageBox.information(self,'Local network upload',HELP)); actions.addWidget(help_button)
        layout.addLayout(actions)
        controller.changed.connect(self.changed)
        self.refresh_networks(); self.refresh()

    def refresh_networks(self):
        selected = self.network.currentData(); self.network.clear()
        try:
            addresses = self.controller.address_provider()
        except (OSError,RuntimeError):
            addresses = []
        for address in addresses:
            self.network.addItem(address.label,address.address)
        index = self.network.findData(selected)
        if index>=0:
            self.network.setCurrentIndex(index)
        self.generate_button.setEnabled(bool(addresses))
        if not addresses:
            self.status.setText('No active LAN IPv4 address. Connect Wi-Fi or Ethernet, then refresh networks.')

    def generate(self):
        try:
            self.controller.generate(self.slot,self.network.currentData())
        except (OSError,ValueError) as error:
            self.status.setText(str(error))
            return
        self.refresh()

    def delete(self):
        result = QMessageBox.question(self,'Delete VJR photo','Delete this photo from the current report?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if result==QMessageBox.StandardButton.Yes:
            try:
                self.controller.delete(self.slot)
            except OSError:
                self.status.setText('Could not save the photo deletion. The current photo is unchanged.')

    def changed(self, slot):
        if slot==self.slot:
            self.refresh()

    def refresh(self):
        reference = self.controller.store.report.get('photos',{}).get(self.slot)
        missing = ''
        if reference!=self.last_reference:
            self.preview.clear(); self.last_reference = reference
            if reference:
                try:
                    image = QPixmap(str(self.controller.storage.image_path(reference)))
                    if image.isNull():
                        raise PhotoError('Stored photo preview is unavailable. Replace it via QR.')
                    self.preview.setPixmap(image.scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                except (OSError,PhotoError) as error:
                    missing = str(error)
                    self.preview.setText('Photo unavailable')
            self.preview.setToolTip(missing)
        missing = missing or self.preview.toolTip()
        state,session = self.controller.state(self.slot)
        active = state in ('waiting','uploading','error')
        self.preview.setVisible(bool(reference)); self.qr.setVisible(active)
        self.cancel_button.setVisible(active); self.delete_button.setVisible(bool(reference))
        self.address.setVisible(active); self.expiry.setVisible(active)
        self.generate_button.setText('Regenerate QR' if active else 'Replace via QR' if reference else 'Generate QR')
        self.generate_button.setEnabled(self.network.count()>0 and not self.controller.store.load_error)
        if active:
            if self.last_token!=session.token:
                image = QPixmap(); image.loadFromData(qr_png(self.controller.service.url(session)))
                self.qr.setPixmap(image.scaled(self.qr.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
                self.last_token = session.token
            remaining = max(0,math.ceil(session.expires-self.controller.service.sessions.clock()))
            message = session.message if state=='error' else 'Uploading photo…' if state=='uploading' else 'Waiting for mobile upload…'
            self.status.setText((missing+' ' if missing else '')+message)
            self.address.setText('Local upload address: '+self.controller.service.url(session)+'\nPC address: '+self.controller.service.address+'    Port: '+str(self.controller.service.port)+'    Connection: Local network')
            self.expiry.setText('Expires in %02d:%02d · Target: %s' % (remaining//60,remaining%60,TITLES[self.slot]))
        elif state=='expired':
            self.status.setText('QR expired. Generate a new QR to continue.'+(' The current photo is kept.' if reference else ''))
        elif state=='failed':
            self.status.setText('Upload attempt limit reached. Generate a new QR.'+(' The current photo is kept.' if reference else ''))
        else:
            self.status.setText(missing or 'Uploaded · Preview available' if reference else 'No photo uploaded' if self.network.count() else
                                'No active LAN IPv4 address. Connect Wi-Fi or Ethernet, then refresh networks.')
