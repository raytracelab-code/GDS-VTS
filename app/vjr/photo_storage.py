"""Immutable, report-owned photo attachments. References are relative IDs only."""
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import threading
import uuid
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

SLOTS = ('departure_back_deck_photo','arrival_back_deck_photo')
TITLES = dict(zip(SLOTS,('Departure Back Deck Photo','Arrival Back Deck Photo (After Lifts)')))
MAX_UPLOAD = 15*1024*1024
MAX_PIXELS = 120_000_000
REFERENCE = re.compile(r'[a-f0-9]{32}/photos/[a-f0-9]{32}')
REPORT_ID = re.compile(r'[a-f0-9]{32}')


class PhotoError(ValueError):
    pass


def validate_photo_state(data):
    report_id = data.get('photo_report_id','')
    photos = data.get('photos',{})
    if report_id and (not isinstance(report_id,str) or not REPORT_ID.fullmatch(report_id)):
        raise PhotoError('Invalid photo report identity')
    if not isinstance(photos,dict) or any(slot not in SLOTS for slot in photos):
        raise PhotoError('Invalid VJR photo slots')
    for reference in photos.values():
        if not isinstance(reference,str) or not REFERENCE.fullmatch(reference) or not reference.startswith(report_id+'/'):
            raise PhotoError('Invalid report-safe photo reference')


def references(store):
    reports = [store.report]+list(store.undo_stack)+list(store.redo_stack)
    return {ref for report in reports for ref in report.get('photos',{}).values()}


class PhotoStorage:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.pending = set()
        self.decode_lock = threading.Lock()

    def directory(self, reference):
        if not isinstance(reference,str) or not REFERENCE.fullmatch(reference):
            raise PhotoError('Invalid photo attachment reference')
        target = (self.root/reference).resolve()
        try:
            relative = target.relative_to(self.root.resolve())
            if relative.as_posix()!=reference:
                raise ValueError('Noncanonical attachment directory')
        except ValueError:
            raise PhotoError('Photo attachment is outside the report folder')
        return target

    def image_path(self, reference):
        path = self.directory(reference)/'photo.jpg'
        if not path.is_file():
            raise PhotoError('Stored photo is unavailable. Replace it via QR or delete its reference.')
        return path

    def create(self, report_id, payload, filename, content_type):
        if not REPORT_ID.fullmatch(str(report_id)):
            raise PhotoError('Invalid photo report identity')
        if len(payload)>MAX_UPLOAD:
            raise PhotoError('Photo exceeds maximum allowed size.')
        extension = str(filename).rsplit('.',1)[-1].lower()
        if extension not in ('jpg','jpeg','png') or content_type not in ('image/jpeg','image/png','application/octet-stream'):
            raise PhotoError('Choose a JPEG or PNG photo.')
        with self.decode_lock, warnings.catch_warnings():
            warnings.simplefilter('ignore',Image.DecompressionBombWarning)
            try:
                with Image.open(BytesIO(payload)) as check:
                    image_format = check.format
                    width,height = check.size
                    if image_format not in ('JPEG','PNG'):
                        raise PhotoError('Choose a JPEG or PNG photo.')
                    if width*height>MAX_PIXELS:
                        raise PhotoError('Photo dimensions exceed the safe image-processing limit (120 megapixels).')
                    if (image_format=='PNG') != (extension=='png'):
                        raise PhotoError('Photo filename does not match its image content.')
                    if content_type!='application/octet-stream' and content_type!=('image/png' if image_format=='PNG' else 'image/jpeg'):
                        raise PhotoError('Photo content does not match its declared image type.')
                    check.verify()
                with Image.open(BytesIO(payload)) as source:
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    oriented.thumbnail((2400,2400),Image.Resampling.LANCZOS)
                    rgba = oriented.convert('RGBA')
                    display = Image.new('RGB',rgba.size,'white')
                    display.paste(rgba,mask=rgba.getchannel('A'))
                    output = BytesIO(); display.save(output,'JPEG',quality=92,optimize=True)
                    size = display.size
            except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError) as error:
                raise PhotoError('The selected file is not a valid, supported image.') from error
        attachment_id = uuid.uuid4().hex
        reference = report_id+'/photos/'+attachment_id
        target = self.directory(reference)
        temporary = target.parent/('.upload-'+attachment_id)
        with self.lock:
            temporary.mkdir(parents=True,exist_ok=False)
            try:
                files = {'original.'+('png' if image_format=='PNG' else 'jpg'):payload,'photo.jpg':output.getvalue(),
                    'info.json':json.dumps(dict(width=size[0],height=size[1],uploaded_at=datetime.now(timezone.utc).isoformat())).encode('utf-8')}
                for name,data in files.items():
                    with (temporary/name).open('wb') as stream:
                        stream.write(data); stream.flush(); os.fsync(stream.fileno())
                os.replace(str(temporary),str(target))
                self.pending.add(reference)
            finally:
                if temporary.exists():
                    shutil.rmtree(str(temporary))
        return reference

    def release(self, reference):
        with self.lock:
            self.pending.discard(reference)

    def discard(self, reference):
        with self.lock:
            self.pending.discard(reference)
            target = self.directory(reference)
            if target.is_dir():
                shutil.rmtree(str(target))

    def collect(self, store):
        # History retains old versions so replacing/deleting stays undoable.
        with self.lock:
            if store.load_error or getattr(store, 'recovered', False):
                # An unreadable or recovered report may not list every attachment the
                # damaged original referenced; never delete photos in that session.
                return
            keep = references(store)|self.pending
            reports = [store.report]+list(store.undo_stack)+list(store.redo_stack)
            identities = {report.get('photo_report_id') for report in reports}
            if not self.root.exists():
                return
            for report in self.root.iterdir():
                if report.name not in identities or not REPORT_ID.fullmatch(report.name) or not (report/'photos').is_dir():
                    continue
                for candidate in (report/'photos').iterdir():
                    reference = report.name+'/photos/'+candidate.name
                    if not REPORT_ID.fullmatch(candidate.name) or reference in keep:
                        continue
                    try:
                        checked = self.directory(reference)
                        if checked.is_dir() and not candidate.is_symlink():
                            shutil.rmtree(str(checked))
                    except (OSError,PhotoError):
                        pass  # A later cleanup can retry; never compromise a committed report.
