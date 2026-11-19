"""Template-led VJR. All edits, calculations and exports use the canonical store."""
from pathlib import Path
import re
from app.qt.QtCore import Qt, QDate, QTime, QSettings, QStandardPaths, QSignalBlocker, QTimer
from app.qt.QtGui import QKeySequence, QShortcut, QColor, QFont, QPen, QPainter
from app.qt.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QDateEdit, QTimeEdit, QCheckBox, QComboBox, QFormLayout,
    QFrame, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QStyledItemDelegate,
    QFileDialog, QMessageBox, QAbstractItemView, QSizePolicy, QHeaderView, QAbstractSpinBox, QStyle)
from app.vjr.schema import META, GENERAL, DEPARTURE, ARRIVAL, TABLES, DECK, INVENTORY, CAPACITIES, COMPASS
from app.vjr.model import blank_row, with_identity, arrival_fields
from app.core.vessel_identity import load_identity
from app.ui import dialogs
from app.core.plausibility import check as plausibility_check
# VJR column -> plausibility rule (soft warnings only; hard limits stay in app/vjr/validation.py)
REQUIRED_FIELDS = {('meta','vessel'), ('departure','departure_date'), ('departure','departure_location')}
PLAUSIBILITY_KIND = {('waypoints','speed'):'planned_speed', ('progress','speed'):'actual_speed', 'visibility':'visibility_nm',
                     'wind_speed':'wind_speed_knots', 'wave_height':'wave_height_m', 'quantity':'quantity', 'course':'course'}
from app.vjr.store import VjrStore
from app.vjr.validation import validate, validate_value
from app.vjr.calculations import working_days, deck_values, deck_totals
from app.vjr.excel import VjrExcelExporter, suggested_filename, ExcelExportError
from .vjr_widgets import STYLE, FieldGrid, ReportTable
from .vdr.widgets import load_fonts
from .vdr.date_picker import VdrDatePicker
from app.ui.theme import COLORS, FONT_DATA
from .vjr_photos import PhotoController, PhotoCard
from app.vjr.photo_storage import SLOTS

MIN_DATE = QDate(1752,9,14)


def date_editor(value, parent=None):
    editor = VdrDatePicker(str(value or ''), parent=parent)
    editor.setFixedHeight(36)
    return editor


def date_value(editor):
    return editor.iso_value()


class FieldDelegate(QStyledItemDelegate):
    def __init__(self, schema, parent):
        super().__init__(parent); self.schema = schema

    def createEditor(self, parent, option, index):
        if index.column()>=len(self.schema):
            return None
        kind = self.schema[index.column()][3]
        if kind=='date':
            editor = date_editor('',parent)
            editor.valueChanged.connect(lambda _value:self.commitData.emit(editor))
            return editor
        choices = None
        if kind in ('hour','minute'):
            choices = ['%02d' % i for i in range(24 if kind=='hour' else 60)]
        elif kind in ('ns','ew','compass'):
            choices = ['N','S'] if kind=='ns' else ['E','W'] if kind=='ew' else list(COMPASS)
        if choices is not None:
            editor = QComboBox(parent); editor.addItems(['']+choices); return editor
        return super().createEditor(parent,option,index)

    def setEditorData(self, editor, index):
        value = str(index.data() or '')
        if isinstance(editor,VdrDatePicker):
            editor.set_value(value,emit=False)
        elif isinstance(editor,QComboBox):
            if self.schema[index.column()][3] in ('hour','minute') and value:
                try:
                    value = '%02d' % int(float(value))
                except ValueError:
                    pass
            editor.setCurrentText(value)
        else:
            super().setEditorData(editor,index)

    def setModelData(self, editor, model, index):
        if isinstance(editor,VdrDatePicker):
            model.setData(index,date_value(editor))
        elif isinstance(editor,QComboBox):
            model.setData(index,editor.currentText())
        else:
            super().setModelData(editor,model,index)

    def paint(self,painter,option,index):
        super().paint(painter,option,index)
        if index.data(Qt.ItemDataRole.UserRole):
            painter.save(); painter.setPen(QPen(QColor('#D97770'),1))
            painter.drawRect(option.rect.adjusted(1,1,-2,-2)); painter.restore()
        elif str(index.data(Qt.ItemDataRole.ToolTipRole) or '').startswith('▲'):
            # Suspicious (possible but unusual) value: amber outline + light tint, same pattern as the invalid outline.
            painter.save(); painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            painter.fillRect(option.rect.adjusted(1,1,-1,-1), QColor('#FFF0CC')); painter.restore()
            painter.save(); painter.setPen(QPen(QColor('#D9A441'),1))
            painter.drawRect(option.rect.adjusted(1,1,-2,-2)); painter.restore()

    def initStyleOption(self,option,index):
        super().initStyleOption(option,index)
        if index.column()<len(self.schema) and self.schema[index.column()][3]=='date':
            day = QDate.fromString(str(index.data() or ''),'yyyy-MM-dd')
            if day.isValid():
                option.text = day.toString('dd MMM yyyy')


class VjrPage(QWidget):
    def __init__(self, store=None, identity_provider=None):
        super().__init__(); load_fonts(); self.setObjectName('vjrPage')
        self.setStyleSheet(STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.identity_provider = identity_provider or self.configured_identity
        path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/'vjr/report.json'
        self.store = store or VjrStore(path)
        self.photo_controller = PhotoController(self.store,self)
        self.photo_controller.changed.connect(self._photo_changed)
        self._building = False
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        topbar = QFrame(); topbar.setObjectName('topbar'); top = QHBoxLayout(topbar)
        top.setContentsMargins(24,14,24,14); top.setSpacing(12)
        titles = QVBoxLayout(); titles.setSpacing(3)
        title = QLabel('VJR'); title.setObjectName('pageTitle'); titles.addWidget(title)
        subtitle = QLabel('Vessel Journey Report'); subtitle.setObjectName('subtitle'); titles.addWidget(subtitle)
        top.addLayout(titles); top.addStretch()
        self.vessel_context = QLabel(); self.vessel_context.setObjectName('vesselContext')
        self.vessel_context.setMaximumWidth(230); top.addWidget(self.vessel_context)
        self.journey_status = QLabel('Working report'); self.journey_status.setObjectName('journeyStatus')
        top.addWidget(self.journey_status)
        self.saved = QLabel('Autosave ready'); self.saved.setObjectName('chromeText'); top.addWidget(self.saved)
        self.undo_button = self.button('↶',self.undo); self.undo_button.setObjectName('iconButton')
        self.undo_button.setAccessibleName('Undo'); self.undo_button.setToolTip('Undo (Ctrl+Z)'); top.addWidget(self.undo_button)
        self.redo_button = self.button('↷',self.redo); self.redo_button.setObjectName('iconButton')
        self.redo_button.setAccessibleName('Redo'); self.redo_button.setToolTip('Redo (Ctrl+Shift+Z)'); top.addWidget(self.redo_button)
        self.new_voyage_button = self.button('New voyage…',self.new_voyage)
        self.new_voyage_button.setToolTip('Archive this journey and start a new one (crew list is kept)'); top.addWidget(self.new_voyage_button)
        self.excel_button = self.button('Download Excel',self.download_excel)
        self.excel_button.setObjectName('download'); top.addWidget(self.excel_button); root.addWidget(topbar)
        workspace = QHBoxLayout(); workspace.setContentsMargins(20,20,20,20); workspace.setSpacing(20)
        root.addLayout(workspace,1)
        sidebar_scroll = QScrollArea(); sidebar_scroll.setWidgetResizable(True); sidebar_scroll.setFixedWidth(214)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar = QFrame(); self.sidebar.setObjectName('sidebar'); side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12,16,12,16); side.setSpacing(8)
        caption = QLabel('JOURNEY WORKSPACE'); caption.setObjectName('navCaption'); side.addWidget(caption)
        self.nav_buttons = []
        names = ('Report information','Core crew','Contractors','Waypoint plan','Departure report','Arrival report','Voyage progress')
        for i,name in enumerate(names):
            button = self.button('%02d   %s' % (i+1,name),lambda _checked=False,n=i:self.tabs.setCurrentIndex(n))
            button.setObjectName('sectionNav'); button.setCheckable(True); button.setAutoExclusive(True)
            side.addWidget(button); self.nav_buttons.append(button)
        side.addSpacing(12)
        self.history_button = self.button('Voyage history…',self.show_voyage_history)
        self.history_button.setToolTip('Archived voyages, newest first'); side.addWidget(self.history_button)
        self.nav_summary = QLabel(); self.nav_summary.setObjectName('navSummary'); self.nav_summary.setWordWrap(True)
        side.addWidget(self.nav_summary); side.addStretch()
        legend = QLabel('White fields are editable.\nTinted fields are linked or calculated.')
        legend.setObjectName('navSummary'); legend.setWordWrap(True); side.addWidget(legend)
        sidebar_scroll.setWidget(self.sidebar); workspace.addWidget(sidebar_scroll)
        content = QVBoxLayout(); content.setSpacing(12); workspace.addLayout(content,1)
        self.storage_notice = QLabel(); self.storage_notice.setObjectName('storageNotice'); self.storage_notice.setWordWrap(True)
        self.storage_notice.setVisible(bool(self.store.notices or self.store.load_error))
        self.storage_notice.setText(dialogs.wrap_long_tokens(self.store.load_error or '\n\n'.join(self.store.notices))); content.addWidget(self.storage_notice)
        self.errors = QLabel(); self.errors.setObjectName('validationNotice'); self.errors.setWordWrap(True); content.addWidget(self.errors)
        self.tabs = QTabWidget(); self.tabs.setObjectName('sectionPages'); self.tabs.tabBar().hide()
        self.tabs.setStyleSheet('QTabWidget::pane {border:0;}')
        self.tabs.currentChanged.connect(self._section_changed); content.addWidget(self.tabs,1)
        for sequence,callback in (('Ctrl+Z',self.undo),('Ctrl+Shift+Z',self.redo),('Ctrl+Y',self.redo)):
            shortcut = QShortcut(QKeySequence(sequence),self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); shortcut.activated.connect(callback)
        QApplication.instance().aboutToQuit.connect(self.flush_save)
        self.rebuild()

    @staticmethod
    def configured_identity():
        """Configure → Vessel & Client is the single source; these VJR fields are always read-only."""
        identity = load_identity()
        return {key:identity[key] for key in ('vessel','imo','client','client_id','capacity')}

    @property
    def report(self):
        return with_identity(self.store.report,self.identity_provider())

    @staticmethod
    def button(text,callback):
        button = QPushButton(text); button.clicked.connect(callback); return button

    def showEvent(self,event):
        super().showEvent(event); self.refresh()

    def mutate(self,action, structural=False):
        if self._building:
            return
        try:
            self.store.mutate(action); self._set_saved('Saved')
            if self.storage_notice.isVisible() and self.storage_notice.text().startswith('Not saved'):
                self.storage_notice.hide()
            if structural:
                self.rebuild()
            else:
                self.refresh()
        except (OSError,ValueError,TypeError) as error:
            self._set_saved('NOT SAVED'); self.saved.setToolTip(str(error)); self._storage_error(error)

    def set_field(self,path,value):
        def edit(report):
            current = report
            for part in path[:-1]:
                current = current[part]
            current[path[-1]] = value
        self.mutate(edit)

    def _storage_error(self, error):
        text = str(error)
        if not text.startswith(('Not saved','Could not load')):
            text = f'Not saved: {text}. Your previously saved journey is safe; your next edit retries.'
        self.storage_notice.setText(dialogs.wrap_long_tokens(text)); self.storage_notice.show()

    def _set_saved(self, text):
        """Autosave state as a compact badge: quiet when saved, prominent only on failure (text unchanged)."""
        from app.ui.status import set_badge
        set_badge(self.saved, text, 'error' if 'NOT SAV' in text.upper() or 'FAILED' in text.upper() else
                  'success' if text.startswith('Saved') else 'neutral', with_icon=False)

    def flush_save(self):
        try:
            self.store.save()
            return True
        except OSError as error:
            self._set_saved('NOT SAVED'); self._storage_error(error)
            return False

    def undo(self):
        self.history(False)

    def redo(self):
        self.history(True)

    def history(self,redo):
        try:
            if self.store.redo() if redo else self.store.undo():
                self.rebuild(); self._set_saved('Saved · '+('Redone' if redo else 'Undone'))
        except OSError as error:
            self._set_saved('History not saved: '+str(error))

    def card(self,layout,title):
        frame = QFrame(); frame.setObjectName('formBlock'); body = QVBoxLayout(frame)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
        frame.setProperty('cardTitle',title)
        body.setContentsMargins(16,14,16,16); body.setSpacing(14)
        heading = QLabel(title.upper()); heading.setObjectName('blockTitle'); body.addWidget(heading); layout.addWidget(frame)
        return body

    def add_tab(self,title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget(); layout = QVBoxLayout(body); layout.setContentsMargins(0,0,10,0); layout.setSpacing(16)
        heading = QLabel('%02d  %s' % (self.tabs.count()+1,title)); heading.setObjectName('sectionHeading')
        layout.addWidget(heading)
        descriptions = {
            'General / Report Information':'Vessel identity and report details used throughout this journey.',
            'Core Crew':'Maintain the crew list. Working days follow the current report dates.',
            'Contractors':'Maintain contractors joining this journey.',
            'Waypoint Plan':'Plan the route using degrees, minutes and seconds.',
            'Departure Report':'Prepare departure details, destination loads and inventory.',
            'Arrival Report':'Review departure references and record the arrival state.',
            'Voyage Progress':'Update every hour throughout the journey. Position uses degrees, minutes and seconds.'}
        hint = QLabel(descriptions.get(title,'')); hint.setObjectName('sectionHint'); hint.setWordWrap(True); layout.addWidget(hint)
        scroll.setWidget(body); self.tabs.addTab(scroll,title); return layout

    def form(self,layout,title,group,schema,linked=False,register=True):
        body = self.card(layout,title); grid = FieldGrid(); body.addWidget(grid)
        data = self.report[group] if group!='arrival' else arrival_fields(self.report)
        identity = self.identity_provider()
        for key,label,_,kind in schema:
            path = (group,key); value = data.get(key,'')
            wrapper = QWidget(); field = QVBoxLayout(wrapper); field.setContentsMargins(0,0,0,0); field.setSpacing(5)
            caption = QLabel(label.upper() + (' *' if path in REQUIRED_FIELDS else '')); caption.setObjectName('fieldLabel'); field.addWidget(caption)
            if path in REQUIRED_FIELDS:
                caption.setToolTip('Required before downloading Excel')
            linked_key = linked if isinstance(linked,bool) else key in linked
            readonly = linked_key or kind=='automatic' or (group=='meta' and key in identity)
            if readonly:
                editor = QLineEdit(str(value)); editor.setReadOnly(True)
                if kind=='automatic':
                    editor.setText('Generated on download')
                else:
                    self.linked.append((path,editor))
                    editor.setToolTip('Set in Configure → Vessel & Client' if group=='meta' else 'Linked from Departure Report')
            elif kind=='date':
                editor = date_editor(value); editor.setAccessibleName(label)
                editor.valueChanged.connect(lambda value,p=path:self.set_field(p,value))
            elif kind=='time':
                container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0,0,0,0)
                row.setSpacing(10)
                editor = QTimeEdit(); editor.setDisplayFormat('HH:mm'); editor.setTime(QTime.fromString(value or '00:00','HH:mm'))
                editor.setFixedWidth(100); editor.setFixedHeight(36)
                enabled = QCheckBox('Set'); enabled.setChecked(bool(value)); enabled.setToolTip('Include this time in the report')
                editor.setEnabled(bool(value)); editor.setAccessibleName(label); row.addWidget(editor)
                row.addWidget(enabled); row.addStretch()
                def time_changed(_=None,p=path,e=editor,check=enabled):
                    e.setEnabled(check.isChecked()); self.set_field(p,e.time().toString('HH:mm') if check.isChecked() else '')
                editor.timeChanged.connect(time_changed); enabled.toggled.connect(time_changed)
                field.addWidget(container)
            else:
                editor = QLineEdit(str(value)); editor.textEdited.connect(lambda text,p=path:self.set_field(p,text))
            editor.setAccessibleName(label)
            if kind!='time' or readonly:
                editor.setFixedHeight(36); field.addWidget(editor)
            if kind not in ('text','date','time','automatic'):
                editor.setProperty('data',True)
                editor.setAlignment(Qt.AlignmentFlag.AlignRight)
            if register:
                self.editors[path]=editor
                error = QLabel(); error.setObjectName('inlineError'); error.setWordWrap(True); error.hide()
                field.addWidget(error); self.field_errors[path]=error
            grid.add_field(wrapper,wide=key.endswith('remarks'))

    def rows(self,path):
        value = self.report
        for part in path:
            value = value[part]
        return value

    def table(self,layout,title,path,schema,capacity=None):
        body = self.card(layout,title); rows = self.rows(path)
        group = path[0]
        groups = []
        if path==('waypoints',):
            groups = [(0,3,'LATITUDE'),(4,7,'LONGITUDE'),(8,9,'NAVIGATION'),(10,10,'REMARKS'),(11,11,'')]
        elif path==('progress',):
            groups = [(0,2,'DATE / TIME'),(3,6,'LATITUDE'),(7,10,'LONGITUDE'),(11,12,'NAVIGATION'),
                      (13,18,'WEATHER'),(19,19,'REMARKS'),(20,20,'')]
        if capacity is not None:
            bar = QHBoxLayout(); count = QLabel('%s / %s rows' % (len(rows),capacity)); count.setObjectName('tableHint')
            bar.addWidget(count); bar.addStretch()
            name = dict(crew='Add Crew',contractors='Add Contractor',waypoints='Add Waypoint',progress='Add Voyage Progress Row')[group]
            add = self.button(name,lambda:self.add_row(path,schema,capacity)); add.setEnabled(len(rows)<capacity)
            delete = self.button('Delete row',lambda:self.remove_row(path)); delete.setObjectName('deleteRow'); delete.setEnabled(bool(rows))
            bar.addWidget(add); bar.addWidget(delete); body.addLayout(bar)
        deck = len(path)==2 and path[1]=='deck'
        table = ReportTable(len(rows)+(1 if deck else 0),len(schema)+(1 if capacity else 0),groups)
        table.setObjectName('.'.join(path))
        labels = dict(nationality='Nationality',passport='IC / Passport',sign_on='Date Sign-on',working_days='Working\nDays',
            lat_degree='Deg',lat_minute='Min',lat_second='Sec',lat_direction='N/S',
            lon_degree='Deg',lon_minute='Min',lon_second='Sec',lon_direction='E/W',
            course='Course (°)',speed='Speed (kn)',visibility='Visibility (nm)',wind_speed='Wind (kn)',
            wind_direction='Wind Dir.',wave_height='Swell (m)',wave_direction='Swell Dir.',
            location='Destination',lifts='Expected\nLifts',ops='OPS',fso='FSO',drilling='Drilling /\nProjects',
            total='Total (m²)',utilization='Utilization %',weight='Cargo (t)')
        table.setHorizontalHeaderLabels([labels.get(key,label) for key,label,_,_ in schema]+(['Action'] if capacity else []))
        table.setItemDelegate(FieldDelegate(schema,table)); table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        widths = dict(name=180,rank=120,vendor=150,age=58,nationality=118,passport=135,sign_on=128,working_days=82,
            lat_degree=66,lat_minute=58,lat_second=74,lat_direction=48,lon_degree=66,lon_minute=58,lon_second=74,
            lon_direction=48,course=82,speed=82,remarks=220,date=124,hour=54,minute=54,sky=98,visibility=96,
            wind_speed=82,wind_direction=82,wave_height=82,wave_direction=82,location=170,lifts=84,ops=72,fso=72,
            drilling=96,total=86,utilization=92,weight=90,product=240,quantity=120,unit=72)
        for col,(key,_,_,kind) in enumerate(schema):
            table.setColumnWidth(col,widths.get(key,120))
        for index,row in enumerate(rows):
            for col,(key,_,_,kind) in enumerate(schema):
                item = QTableWidgetItem(str(row.get(key,'')))
                if kind in ('derived','fixed'):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                numeric = kind not in ('text','date','fixed','ns','ew','compass')
                item.setTextAlignment((Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
                if numeric or kind=='date':
                    font = QFont(FONT_DATA); font.setPixelSize(12); item.setFont(font)
                table.setItem(index,col,item)
            if capacity:
                delete = self.button('×',lambda _checked=False,n=index,p=path:self.delete_row_at(p,n))
                delete.setObjectName('deleteRow'); delete.setToolTip('Delete row %s' % (index+1))
                delete.setAccessibleName('Delete %s row %s' % (group,index+1)); table.setCellWidget(index,len(schema),delete)
        if capacity:
            table.setColumnWidth(len(schema),58)
        table.horizontalHeader().setStretchLastSection(not capacity)
        if deck:
            table.setVerticalHeaderLabels([str(i+1) for i in range(len(rows))]+['Σ'])
            for col in range(len(schema)):
                item = QTableWidgetItem('TOTAL' if col==0 else '')
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QColor('#E4EFEE')); table.setItem(len(rows),col,item)
        table.cellChanged.connect(lambda row,col:self.set_field(path+(row,schema[col][0]),table.item(row,col).text())
                                  if row<len(rows) and col<len(schema) else None)
        body.addWidget(table); self.tables[path]=(table,schema)
        self.table_cards[path]=body.parentWidget()
        if not rows:
            empty = QLabel('No rows yet. Use %s to begin.' % name)
            empty.setObjectName('emptyState'); empty.setAlignment(Qt.AlignmentFlag.AlignCenter); body.addWidget(empty)
        hint = QLabel('Select a cell to edit. Use Tab to move between fields.' if capacity else
                      'Tinted cells are calculated.' if deck else 'Products and units are fixed; enter quantities and remarks.')
        hint.setObjectName('tableHint'); body.addWidget(hint)
        self._size_table(path,table,len(rows))

    def delete_row_at(self,path,index):
        self.tables[path][0].setCurrentCell(index,0)
        self.remove_row(path)

    def _size_table(self,path,table,count):
        header = table.horizontalHeader().height()
        height = header+count*36+18
        if len(path)==1:
            height = min(height,max(190,min(520,self.tabs.height()-190)))
        elif path[1]=='deck':
            height += 36
        table.setFixedHeight(height)

    def _section_changed(self,index):
        for i,button in enumerate(self.nav_buttons):
            button.setChecked(i==index)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'tables'):
            for path,(table,_) in self.tables.items():
                self._size_table(path,table,len(self.rows(path)))

    def add_row(self,path,schema,capacity):
        if len(self.rows(path))>=capacity:
            return
        def add(report):
            rows = report
            for part in path:
                rows = rows[part]
            rows.append(blank_row(schema))
        self.mutate(add,True)

    def remove_row(self,path):
        index = self.tables[path][0].currentRow()
        if index<0:
            return
        def remove(report):
            rows = report
            for part in path:
                rows = rows[part]
            rows.pop(index)
        self.mutate(remove,True)

    def report_tab(self,group):
        layout = self.add_tab(group.title()+' Report')
        self.form(layout,'Vessel identity · Linked from General','meta',[f for f in META if f[0] in ('vessel','imo','capacity')],True,False)
        keys = ('captain','prepared_by','checked_by','prepared_tel','checked_tel','report_date')
        fields = [next(f for f in GENERAL if f[0]==key) for key in keys]
        linked = set(keys)-{'report_date'} if group=='arrival' else False
        self.form(layout,'General Information'+(' · Departure values linked' if group=='arrival' else ''),group,fields,linked)
        counts = QLineEdit(); counts.setReadOnly(True); counts.setFixedHeight(36)
        self.linked.append(((group,'counts'),counts)); layout.addWidget(counts)
        self.form(layout,'Departure Information' if group=='departure' else 'Departure Reference · Linked',group,DEPARTURE,group=='arrival')
        self.form(layout,'Estimated Arrival' if group=='departure' else 'Actual Arrival',group,ARRIVAL,
                  {'destination'} if group=='arrival' else False)
        self.form(layout,'Draft / Requirements'+(' · Linked' if group=='arrival' else ''),group,
                  [f for f in GENERAL if f[0] not in keys],group=='arrival')
        self.table(layout,'Deck Space',(group,'deck'),DECK)
        self.table(layout,'Inventory',(group,'inventory'),INVENTORY)
        self.photo_card(layout,group)
        layout.addStretch()

    def photo_card(self,layout,group):
        slot = SLOTS[0] if group=='departure' else SLOTS[1]
        card = PhotoCard(self.photo_controller,slot)
        self.photo_cards[slot] = card; layout.addWidget(card)

    def _photo_changed(self,slot):
        if not self._building and hasattr(self,'photo_cards'):
            self._set_saved('Saved' if self.store.report.get('photos',{}).get(slot) else self.saved.text())
            self.refresh()

    def closeEvent(self,event):
        self.photo_controller.close()
        super().closeEvent(event)

    def rebuild(self):
        selected = max(0,self.tabs.currentIndex()); self._building = True
        scrolls = [self.tabs.widget(i).verticalScrollBar().value() for i in range(self.tabs.count())]
        while self.tabs.count():
            widget = self.tabs.widget(0); self.tabs.removeTab(0); widget.deleteLater()
        self.editors, self.tables, self.linked = {}, {}, []
        self.field_errors, self.table_cards, self._rendered_rows = {}, {}, {}
        self.photo_cards = {}
        layout = self.add_tab('General / Report Information')
        self.form(layout,'Vessel identity','meta',[f for f in META if f[0] in ('vessel','imo','capacity')])
        self.form(layout,'Report details','meta',[f for f in META if f[0] in ('report_id','report_name','client')])
        self.form(layout,'Report metadata','meta',[f for f in META if f[0] in ('client_id','generated','reader_version','reader_revision')])
        layout.addStretch()
        for group,title in (('crew','Core Crew'),('contractors','Contractors'),('waypoints','Waypoint Plan')):
            layout = self.add_tab(title); self.table(layout,title,(group,),TABLES[group],CAPACITIES[group]); layout.addStretch()
        self.report_tab('departure'); self.report_tab('arrival')
        layout = self.add_tab('Voyage Progress')
        self.table(layout,'Voyage Progress',('progress',),TABLES['progress'],CAPACITIES['progress']); layout.addStretch()
        self.tabs.setCurrentIndex(selected); self._building = False; self.refresh()
        self._section_changed(selected)
        for index,value in enumerate(scrolls):
            QTimer.singleShot(0,lambda i=index,v=value:self.tabs.widget(i).verticalScrollBar().setValue(v))

    @staticmethod
    def display(value,percentage=False):
        return '' if value is None else ('%.2f%%' % (value*100)) if percentage else ('%g' % value)

    def refresh(self):
        if self._building:
            return
        report = self.report; issues = validate(report)
        self.photo_controller.sync()
        for card in self.photo_cards.values():
            card.refresh()
        readable = [issue.split(': ',1)[-1] for issue in issues]
        self.errors.setText(('Review before download: '+readable[0]+(' (+%s more)' % (len(issues)-1) if len(issues)>1 else '')) if issues else '')
        self.errors.setToolTip('\n'.join(readable)); self.errors.setVisible(bool(issues))
        self.excel_button.setEnabled(not issues and not self.store.load_error)
        self.undo_button.setEnabled(bool(self.store.undo_stack)); self.redo_button.setEnabled(bool(self.store.redo_stack))
        vessel = str(report['meta'].get('vessel',''))
        self.vessel_context.setText(self.vessel_context.fontMetrics().elidedText(vessel or 'Vessel not set',Qt.TextElideMode.ElideRight,230))
        self.vessel_context.setToolTip(vessel)
        self.journey_status.setText('Needs attention' if issues else 'Arrival recorded' if report['arrival'].get('report_date') else
                                    'Departure recorded' if report['departure'].get('report_date') else 'Working report')
        counts = {}
        for issue in issues:
            match = re.match(r'[a-z_]+', issue); counts[self.SECTION_OF.get(match.group(0) if match else '', 0)] = counts.get(self.SECTION_OF.get(match.group(0) if match else '', 0), 0) + 1
        for i, button in enumerate(self.nav_buttons):
            # Same text markers as VDR: "⚠ n" items to fix, "✓" section complete.
            button.setText('%02d   %s' % (i+1, self.SECTION_NAMES[i]) + (f'   ⚠ {counts[i]}' if counts.get(i) else '   ✓'))
            button.setToolTip(f'{counts[i]} item(s) to fix before downloading Excel' if counts.get(i) else 'No issues')
        self.nav_summary.setText('%s crew · %s contractors\n%s waypoints · %s progress rows' % (
            len(report['crew']),len(report['contractors']),len(report['waypoints']),len(report['progress'])))
        if self.store.load_error:
            self._set_saved(self.store.load_error)
        for (group,key),editor in self.linked:
            data = report[group] if group!='arrival' else arrival_fields(report)
            if key=='counts':
                value = 'Crew: %s     Contractors: %s' % (len(report['crew']),len(report['contractors']))
            elif key=='totals':
                try:
                    totals = deck_totals(data['deck'],report['meta']['capacity'])
                    value = 'Totals   Lifts: %s   Deck: %s m²   Utilization: %s   Cargo: %s tonnes' % (
                        self.display(totals['lifts']),self.display(totals['total']),self.display(totals['utilization'],True),self.display(totals['weight']))
                except (ValueError,TypeError):
                    value = 'Totals unavailable: correct deck space values'
            else:
                value = data.get(key,'')
            if editor.text()!=str(value):
                editor.setText(str(value))
        for path,(table,schema) in self.tables.items():
            blocker = QSignalBlocker(table)
            rows = report
            for part in path:
                rows = rows[part]
            for index,row in enumerate(rows):
                dependency = (report['meta'].get('capacity',''),report['departure']['report_date'],report['arrival']['report_date'])
                snapshot = (dict(row),dependency)
                cache_key = (path,index)
                if self._rendered_rows.get(cache_key)==snapshot:
                    continue
                self._rendered_rows[cache_key]=snapshot
                computed = {}
                try:
                    if path==('crew',):
                        computed['working_days'] = working_days(row.get('sign_on',''),report['departure']['report_date'],report['arrival']['report_date'])
                    elif len(path)==2 and path[1]=='deck':
                        computed = deck_values(row,report['meta']['capacity'])
                except (ValueError,TypeError):
                    computed = {key:None for key,_,_,kind in schema if kind=='derived'}
                for col,(key,_,_,kind) in enumerate(schema):
                    item = table.item(index,col)
                    if item is None:  # table older than the data (changed outside this page): rebuild instead of crashing
                        QTimer.singleShot(0,self.rebuild); return
                    if kind=='derived':
                        value = self.display(computed.get(key),key=='utilization')
                        if item.text()!=value:
                            item.setText(value)
                    try:
                        validate_value(row.get(key,''),kind)
                        item.setData(Qt.ItemDataRole.UserRole,False)
                        item.setBackground(QColor('#EEF5F5' if kind=='derived' else '#F4F7F9' if kind=='fixed' else 'transparent'))
                        item.setForeground(QColor(COLORS['navy'] if kind in ('derived','fixed') else COLORS['text']))
                        item.setToolTip('Calculated from report values' if kind=='derived' else 'Fixed template value' if kind=='fixed' else '')
                        warning = plausibility_check(PLAUSIBILITY_KIND.get((path[0],key)) or PLAUSIBILITY_KIND.get(key), row.get(key,''))
                        if warning:
                            item.setBackground(QColor('#FFF4DC')); item.setToolTip('▲ '+warning[1])
                    except (ValueError,TypeError) as error:
                        item.setBackground(QColor('#FFF0ED')); item.setToolTip(str(error)); item.setData(Qt.ItemDataRole.UserRole,True)
            if len(path)==2 and path[1]=='deck':
                try:
                    totals = deck_totals(rows,report['meta']['capacity'])
                except (ValueError,TypeError):
                    totals = {}
                for col,(key,_,_,_) in enumerate(schema):
                    item = table.item(len(rows),col)
                    value = 'TOTAL' if key=='location' else self.display(totals.get(key),key=='utilization')
                    if item.text()!=value:
                        item.setText(value)
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setTextAlignment((Qt.AlignmentFlag.AlignLeft if key=='location' else Qt.AlignmentFlag.AlignRight)|Qt.AlignmentFlag.AlignVCenter)
            del blocker
        for (group,key),editor in self.editors.items():
            issue = next((e for e in issues if e.startswith(group+'.'+key+':')), '')
            message = issue.split(' — ',1)[-1] if issue else ''
            if editor.property('invalid')!=bool(issue):
                editor.setProperty('invalid',bool(issue)); editor.style().unpolish(editor); editor.style().polish(editor)
            if issue:
                editor.setToolTip(message)
            error = self.field_errors.get((group,key))
            if error:
                error.setText(message); error.setVisible(bool(issue))

    def show_voyage_history(self):
        from .vjr_history import VoyageHistoryDialog
        from app.qt import exec_qt
        self.flush_save()
        dialog = VoyageHistoryDialog(self.store, self)
        dialogs.exec_dialog(dialog, self)
        if dialog.restored:
            self.rebuild(); self._set_saved('Voyage restored · previous journey archived as '+dialog.restored.name)
        return dialog

    def new_voyage(self):
        """GDS-AUDIT-011: archive the current journey and start a fresh one."""
        current = self.store.report['departure']
        route = ' → '.join(v for v in (current.get('departure_location'), current.get('destination')) if v) or 'the current journey'
        if not dialogs.confirm(self, 'Start a new voyage?',
                f'• {route} is archived unchanged (open it again from Voyage history).\n'
                '• The crew and contractor lists are kept for the new voyage.\n'
                '• A new, empty journey becomes the current journey.\n\n'
                'Undo (Ctrl+Z) restores the previous journey.', 'Start new voyage'):
            return False
        try:
            archived = self.store.archive()
        except OSError as error:
            self._storage_error(error); return False
        from app.vjr.model import new_report
        previous = self.store.report
        def start(report):
            fresh = new_report()
            fresh['crew'] = [dict(row) for row in previous['crew']]
            fresh['contractors'] = [dict(row) for row in previous['contractors']]
            report.clear(); report.update(fresh)
        self.mutate(start, structural=True)
        self._set_saved('New voyage started · previous archived as '+archived.name)
        return True

    def download_excel(self):
        focused = QApplication.focusWidget()
        if focused:
            focused.clearFocus()
        report = self.report; issues = validate(report)
        if issues:
            self.show_issues(issues); return
        name = suggested_filename(report['meta']['vessel'],report['departure']['departure_date'])
        destination,_ = QFileDialog.getSaveFileName(self,'Download VJR Excel',name,'Excel Workbook (*.xlsx)')
        if not destination:
            return
        if not Path(destination).suffix:
            destination += '.xlsx'
        try:
            from app.ui.status import busy
            with busy():
                VjrExcelExporter(photo_root=self.photo_controller.storage.root).export(report,destination)
            self._set_saved('Saved · Excel downloaded')
        except (ExcelExportError,OSError,ValueError) as error:
            dialogs.notify(self,'Excel file not created','The VJR Excel file was not created. Your journey data is safe and unchanged.\n\n'
                           'If the file is open in Excel, close it and try again, or choose another folder.',details=f'{error}\n\nDestination: {destination}')

    SECTION_OF = dict(meta=0, crew=1, contractors=2, waypoints=3, departure=4, arrival=5, progress=6)
    SECTION_NAMES = ('Report information','Core crew','Contractors','Waypoint plan','Departure report','Arrival report','Voyage progress')

    def show_issues(self, issues):
        """Validation issues grouped by VJR section, each with one Go action (scrollable, fixed footer)."""
        import re as _re
        grouped = {}
        for issue in issues:
            key = _re.match(r'[a-z_]+', issue); section = self.SECTION_OF.get(key.group(0) if key else '', 0)
            grouped.setdefault(section, []).append(issue.split(': ', 1)[-1])
        groups = [dict(title=self.SECTION_NAMES[s], items=grouped[s], action='Go to '+self.SECTION_NAMES[s],
                       callback=lambda s=s: self.tabs.setCurrentIndex(s)) for s in sorted(grouped)]
        dialog = dialogs.IssuesDialog(self, 'Complete these items before downloading Excel',
            f'{len(issues)} item(s) must be corrected. Your journey is saved; nothing has been exported.', groups)
        dialogs.exec_dialog(dialog, self)
        return dialog
