"""Seven native reference sections; all editors bind to the same report store."""
import json
from app.vdr.model import is_fuel
from app.qt.QtCore import QDate, Qt
from app.qt.QtGui import QIcon, QPixmap
from app.qt.QtWidgets import (QAbstractItemView, QComboBox, QCompleter, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLineEdit, QSizePolicy, QTableWidget, QVBoxLayout, QWidget)
from .widgets import ASSETS, DraftProfile, FlowLayout, box, button, label
from .date_picker import VdrDatePicker

CATALOG = json.loads((ASSETS/'catalogs.json').read_text(encoding='utf-8'))
EQUIPMENT = ['PORT ME', 'PORT ME OUTLET FLOWMETER', 'CENTER ME (P)', 'CENTER ME (P) OUTLET FLOWMETER',
    'CENTER ME (STBD)', 'CENTER ME (STBD) OUTLET FLOWMETER', 'STBD ME', 'STBD ME OUTLET FLOWMETER'] + [
    f'{name} {i}' for name, count in [('BOW THRUSTER', 3), ('STERN THRUSTER', 2), ('SHAFT GENERATOR', 2), ('GENERATOR', 6)]
    for i in range(1, count+1)] + ['EMERGENCY GENERATOR']
BULK = ['FUEL (ltrs)', 'FRESH WATER (ltrs)', 'LUB. OIL (ltrs)', 'GEAR OIL (ltrs)', 'DISPERSANT (ltrs)',
    'DRILL WATER (ltrs)', 'CEMENT (Slag) (mt)', 'CEMENT (mt)', 'BARITE (mt)', 'SARAPAR (bbls)', 'BENTONITE (mt)',
    'New OBM (bbls)', 'Used OBM (bbls)', 'VERSAPRO 9.3PPG (bbls)', 'OBM 7,5 PPG (bbls)', 'OBM 7,8 PPG (bbls)',
    'SBM (bbls)', 'FOAM', 'BASE OIL (bbls)', 'NABM (bbls)', 'PREMIX (bbls)']


class Sections:
    def _section(self, title, hint='', metric=None):
        section = QFrame(); section.setObjectName('reportSection')
        section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(section); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(14)
        header, hl = box(True, gap=10)
        hl.addWidget(label(f'{len(self.sections)+1:02d}  {title.upper()}', 'sectionHeading'))
        if hint:
            text = label(hint, 'sectionHint'); text.setWordWrap(True); hl.addWidget(text, 1)
        else:
            hl.addStretch()
        if metric:
            hl.addWidget(metric)
        layout.addWidget(header); self.sections.append(section); self.panel_layout.addWidget(section)
        return layout

    def _editor(self, path, numeric=False, choices=None, strict=False, date_field=False):
        value = self._get(path)
        if date_field:
            w = VdrDatePicker(value, report_date=lambda: self.store.current,
                              today=lambda: QDate.fromString(self.store.today, 'yyyy-MM-dd'), maximum=self.store.today)
            w.setFixedHeight(36)
            w.valueChanged.connect(lambda value, p=path: self.edit(p, value))
        elif choices is not None:
            w = QComboBox(); w.setEditable(not strict); w.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            w.addItem(''); w.addItems(choices)
            if value and w.findText(value) < 0:
                w.addItem(value)
            w.setCurrentText(value)
            if not strict:
                w.completer().setFilterMode(Qt.MatchFlag.MatchContains)
                w.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
                w.editTextChanged.connect(lambda text, p=path: self.edit(p, text))
            else:
                w.currentTextChanged.connect(lambda text, p=path: self.edit(p, text))
        else:
            w = QLineEdit(value); w.setProperty('data', numeric)
            w.textEdited.connect(lambda text, p=path: self.edit(p, text))
            if path[0] == 'acts' and path[-1] == 'to':
                w.setMaxLength(4); w.setPlaceholderText('hhmm')
                w.editingFinished.connect(lambda p=path, e=w: self._finish_time(p, e))
        w.setAccessibleName('.'.join(map(str, path))); w.setProperty('vdrPath', path); w.installEventFilter(self)
        self.editors[tuple(path)] = w
        return w

    def _field(self, title, path, numeric=False, choices=None):
        wrapper, layout = box(gap=4); layout.addWidget(label(title.upper(), 'fieldLabel'))
        w = self._editor(path, numeric=numeric, choices=choices); w.setMinimumHeight(36); layout.addWidget(w)
        return wrapper

    def _block(self, title):
        frame = QFrame(); frame.setObjectName('formBlock'); layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 14); layout.setSpacing(10)
        layout.addWidget(label(title.upper(), 'blockTitle'))
        return frame, layout

    def _report_hse(self):
        layout = self._section('Report & HSE'); self.meta_top, top = box(True, gap=20); left, ll = box(gap=12)
        datebox, dl = box(gap=4); dl.addWidget(label('DATE *', 'fieldLabel'))
        earliest = min([QDate.fromString(self.store.today, 'yyyy-MM-dd').addDays(-364).toString('yyyy-MM-dd'), *self.store.reports])
        self.report_date = VdrDatePicker(self.store.current, report_date=lambda: self.store.current,
            today=lambda: QDate.fromString(self.store.today, 'yyyy-MM-dd'), minimum=earliest,
            maximum=self.store.today, clearable=False)
        self.report_date.setFixedHeight(36)
        self.report_date.setAccessibleName('Report date')
        self.report_date.valueChanged.connect(self.select_date)
        ll.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        dl.addWidget(self.report_date); ll.addWidget(datebox)
        ll.addWidget(self._field('Captain on duty *', ('meta', 'captain')))
        ll.addWidget(self._field('Location @ 2400H *', ('meta', 'loc24'), choices=CATALOG['locations'])); top.addWidget(left, 10)
        draft, dr = self._block('Draft profile'); self.trim_label = label('', 'sectionHint')
        draft_header = dr.takeAt(0).widget(); dh, dhl = box(True, gap=10)
        dhl.addWidget(draft_header); dhl.addStretch(); dhl.addWidget(self.trim_label); dr.addWidget(dh)
        self.draft_profile = DraftProfile(lambda: self.report); dr.addWidget(self.draft_profile)
        fields, fl = box(True, gap=10)
        fl.addWidget(self._field('Draft FWD (m) *', ('meta', 'fwd'), True))
        fl.addWidget(self._field('Draft AFT (m) *', ('meta', 'aft'), True))
        dr.addWidget(fields); top.addWidget(draft, 14); layout.addWidget(self.meta_top)
        self.hse_bottom, bottom = box(True, gap=20); hse, hl = self._block('HSE performance')
        self.perfect_days = label('', 'sectionHint')
        hse_title = hl.takeAt(0).widget(); hh, hhl = box(True, gap=10)
        hhl.addWidget(hse_title); hhl.addStretch(); hhl.addWidget(self.perfect_days); hl.addWidget(hh)
        hl.addWidget(self._field('HSE incident last 24 hours', ('hse', 'inc24')))
        gw = QWidget(); grid = QGridLayout(gw); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(10)
        for i, (key, title) in enumerate([('lti', 'Last LTI (empty = none)'), ('inj', 'Last recordable injury'),
                                         ('incd', 'Last recordable incident'), ('containment_loss', 'Last containment loss')]):
            wrapper, wl = box(gap=4); wl.addWidget(label(title.upper(), 'fieldLabel'))
            wl.addWidget(self._editor(('hse', key), date_field=True)); grid.addWidget(wrapper, i//2, i%2)
        hl.addWidget(gw); bottom.addWidget(hse)
        endurance, el = self._block('Endurance status — remaining days / date'); ew = QWidget(); eg = QGridLayout(ew)
        eg.setContentsMargins(0, 0, 0, 0); eg.setSpacing(10)
        for i, (key, title) in enumerate([('fuel', 'Fuel'), ('water', 'Drinking water'), ('prov', 'Provision'), ('nextProv', 'Next prov supply')]):
            eg.addWidget(self._field(title, ('end', key), key != 'nextProv'), i//2, i%2)
        el.addWidget(ew); el.addStretch(); bottom.addWidget(endurance); layout.addWidget(self.hse_bottom)

    def _weather(self):
        layout = self._section('Weather condition', 'tap to set — no typing needed'); self.weather_buttons = {}
        for i, row in enumerate(self.report['wx']):
            frame = QFrame(); frame.setObjectName('formBlock'); slot = QHBoxLayout(frame)
            slot.setContentsMargins(0, 0, 0, 0); slot.setSpacing(0)
            time, tl = box(margins=(6, 8, 6, 8), gap=7); time.setFixedWidth(76)
            tl.addStretch(); tl.addWidget(label(row['t'], 'computed'))
            if i:
                tl.addWidget(button('= PREV', lambda checked=False, n=i: self.copy_weather(n)))
            tl.addStretch(); slot.addWidget(time); content, cl = box(margins=(14, 10, 14, 10), gap=12)
            selectors = QWidget(); flow = FlowLayout(selectors, spacing=20)
            for field, values in [('sky', ['CLEAR', 'PARTLY CLOUDY', 'CLOUDY', 'OVERCAST', 'RAINING', 'THUNDERSTORM']),
                                  ('sea', ['CALM', 'SLIGHT', 'MODERATE', 'ROUGH', 'VERY ROUGH']), ('vis', ['10', '5', '2', '0.5'])]:
                group, gl = box(gap=6); gl.addWidget(label({'sky':'SKY', 'sea':'SEA STATE', 'vis':'VISIBILITY'}[field], 'fieldLabel'))
                buttons, bl = box(True)
                for value in values:
                    text = {'10':'10+ NM', '5':'5 NM', '2':'2 NM', '0.5':'<1 NM'}.get(value, value.title())
                    icon = {'CLEAR':'☀', 'PARTLY CLOUDY':'◔', 'CLOUDY':'☁', 'OVERCAST':'☁', 'RAINING':'☂', 'THUNDERSTORM':'ϟ'}.get(value, '≈' if field == 'sea' else '◉')
                    item = button(icon+'\n'+text, lambda checked=False, n=i, f=field, v=value: self.toggle_weather(n, f, v), check=True)
                    item.setToolTip(text); item.setAccessibleName(f'Weather {row["t"]} {field} {value}')
                    item.setStyleSheet('font-size:10px;padding:6px;'); self.weather_buttons[(i, field, value)] = item; bl.addWidget(item)
                gl.addWidget(buttons); flow.addWidget(group)
            cl.addWidget(selectors)
            readings, rl = box(True, margins=(14, 9, 14, 11), gap=28)
            readings.setObjectName('weatherReadings')
            for key, title in [('wind','Wind (kn)'), ('swell','Swell (m)')]:
                field = self._field(title, ('wx', i, key), True); field.setFixedWidth(64); rl.addWidget(field)
            temp, tpl = box(gap=4); temp.setFixedWidth(116)
            tpl.addWidget(label('TEMP (°C)', 'fieldLabel')); tc, tcl = box(True, gap=2)
            dec = button('−', lambda checked=False, n=i: self.change_temp(n, -1)); dec.setFixedSize(30,32); tcl.addWidget(dec)
            reading = self._editor(('wx', i, 'temp'), True); reading.setFixedSize(52,32); tcl.addWidget(reading)
            inc = button('+', lambda checked=False, n=i: self.change_temp(n, 1)); inc.setFixedSize(30,32); tcl.addWidget(inc)
            tpl.addWidget(tc); rl.addWidget(temp); rl.addStretch()
            cl.addWidget(readings); slot.addWidget(content, 1); layout.addWidget(frame)

    def _table(self, group, headers, widths, count):
        t = QTableWidget(count, len(headers)); t.setObjectName(group)
        headers = [v.replace(' @', '\n@').replace('Flowmeter ', 'Flowmeter\n') for v in headers]
        t.setHorizontalHeaderLabels([v.upper() for v in headers]); t.verticalHeader().hide()
        t.setProperty('baseWidths', widths)
        t.setProperty('flexColumns', {'acts':[3], 'eq':[0], 'bulk':[6], 'crew':[1,8], 'ctr':[1]}[group])
        t.installEventFilter(self)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed); t.horizontalHeader().setMinimumSectionSize(26)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col, width in enumerate(widths): t.setColumnWidth(col, width)
        t.horizontalHeader().setFixedHeight(44); t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        t.setFocusPolicy(Qt.FocusPolicy.NoFocus); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row in range(count): t.setRowHeight(row, 38)
        t.setFixedHeight(46+count*38+14); t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        t.setAccessibleName(group+' report table'); self.tables[group] = t
        return t

    def _cell(self, table, row, col, path, numeric=False, choices=None, strict=False, date_field=False):
        w = self._editor(path, numeric, choices, strict, date_field); table.setCellWidget(row, col, w)
        return w

    def _computed(self, table, row, col, key, value=''):
        w = label(value, 'computed'); table.setCellWidget(row, col, w); self.computed[key] = w
        return w

    def _remove_cell(self, table, row, col, group, index):
        w = button('×', lambda: self.remove_row(group, index)); w.setToolTip('Delete row'); w.setAccessibleName(f'Remove {group} row {index+1}')
        table.setCellWidget(row, col, w)

    def _activities(self):
        self.coverage_label = label('', 'sectionHint')
        layout = self._section('Activity log', 'consecutive, no gaps — next FROM is automatic', self.coverage_label)
        layout.addWidget(label('A. DAILY OPERATION ACTIVITY LOG', 'blockTitle'))
        t = self._table('acts', ['From', 'To', 'Dur', 'Activity', 'Movement category', 'DP', 'Lifts', 'POB', 'Location', ''], [60, 60, 64, 240, 225, 52, 56, 60, 185, 30], len(self.report['acts']))
        for i, row in enumerate(self.report['acts']):
            self._computed(t, i, 0, ('from', i)); self._cell(t, i, 1, ('acts', i, 'to'), True); self._computed(t, i, 2, ('duration', i))
            for col, key in [(3, 'act'), (4, 'cat'), (5, 'dp'), (6, 'lifts'), (7, 'pob'), (8, 'loc')]:
                choices = CATALOG['movement'] if key == 'cat' else ['N', 'Y'] if key == 'dp' else CATALOG['locations'] if key == 'loc' else None
                self._cell(t, i, col, ('acts', i, key), key in ('lifts', 'pob'), choices, key in ('cat', 'dp'))
            self._remove_cell(t, i, 9, 'acts', i)
        layout.addWidget(t); actions, al = box(True, gap=10)
        self.add_activity = button('+ Add row', lambda: self.add_row('acts')); al.addWidget(self.add_activity)
        al.addWidget(label('A row is added automatically when you enter TO on the last line. Max 50.', 'sectionHint'), 1); layout.addWidget(actions)
        layout.addWidget(label('B. DAILY DURATION AT LOCATION', 'blockTitle'))
        layout.addWidget(label('AUTO-CALCULATED FROM ACTIVITY LOG', 'sectionHint'))
        self.location_durations = QTableWidget(0, 4)
        self.location_durations.setObjectName('locationDurations')
        self.location_durations.setAccessibleName('Auto-calculated daily duration at location')
        self.location_durations.setHorizontalHeaderLabels(['FROM', 'TO', 'DURATION', 'LOCATION'])
        self.location_durations.verticalHeader().hide()
        self.location_durations.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.location_durations.horizontalHeader().setFixedHeight(44)
        self.location_durations.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.location_durations.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.location_durations.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.location_durations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.location_durations)
        self.location_duration_empty = label('No valid activity intervals with a location yet.', 'sectionHint')
        layout.addWidget(self.location_duration_empty)

    def _equipment(self):
        self.consumption_label = label('', 'metric'); layout = self._section('Running hours & consumption', 'leave empty only if not applicable', self.consumption_label)
        t = self._table('eq', ['Equipment', 'Total run hrs', 'Daily run hrs', 'Flowmeter @0000H', 'Flowmeter @2400H', 'Consumed (ltrs)', ''], [190, 120, 120, 150, 150, 130, 30], len(self.report['eq']))
        for i, row in enumerate(self.report['eq']):
            self._computed(t, i, 0, ('eqname', i), row['name'])
            for col, key in enumerate(('total', 'daily', 'fm0', 'fm24'), 1): self._cell(t, i, col, ('eq', i, key), True)
            self._computed(t, i, 5, ('cons', i)); self._remove_cell(t, i, 6, 'eq', i)
        layout.addWidget(t); actions, al = box(True, gap=10); al.addWidget(self._add_combo('eq', EQUIPMENT, '+ Add equipment…'))
        al.addWidget(label('Flowmeter @0000H must be less than @2400H.', 'sectionHint'), 1); layout.addWidget(actions)

    def _add_combo(self, group, options, title):
        combo = QComboBox(); combo.addItem(title, ''); existing = {r['name'] for r in self.report[group]}
        for value in options:
            if value not in existing: combo.addItem(value, value)
        combo.activated.connect(lambda i: self.add_row(group, combo.itemData(i)) if i else None); combo.setAccessibleName(title)
        return combo

    def _bulk(self):
        layout = self._section('Bulk inventory (ROB)', 'closing computed = opening + received − consumed − transferred')
        count = len(self.report['bulk'])+sum(bool(r['det']) for r in self.report['bulk'])
        t = self._table('bulk', ['Item', 'Opening @0000H', 'Received', 'Consumed', 'Transferred', 'Closing @2400H', 'Remarks', '', ''], [200, 104, 104, 104, 110, 110, 150, 76, 30], count)
        display, extra = 0, 0
        for i, row in enumerate(self.report['bulk']):
            self._computed(t, display, 0, ('bulkname', i), row['name'])
            for col, key in ((1, 'open'), (2, 'rcvQty'), (3, 'cons'), (6, 'remarks')):
                if key == 'cons' and is_fuel(row['name']): self._computed(t, display, col, ('fuel', i))
                else: self._cell(t, display, col, ('bulk', i, key), key != 'remarks')
            self._computed(t, display, 4, ('transfer', i)); self._computed(t, display, 5, ('closing', i))
            t.setCellWidget(display, 7, button('HIDE' if row['det'] else 'DETAILS', lambda checked=False, n=i: self.toggle_details(n)))
            self._remove_cell(t, display, 8, 'bulk', i); display += 1
            if row['det']:
                height = 160+len(row['tr'])*46; t.setSpan(display, 0, 1, 9); t.setCellWidget(display, 0, self._bulk_detail(i)); t.setRowHeight(display, height)
                extra += height-38; display += 1
        t.setFixedHeight(t.height()+extra); layout.addWidget(t); actions, al = box(True)
        al.addWidget(self._add_combo('bulk', BULK, '+ Add item…')); al.addStretch(); layout.addWidget(actions)

    def _bulk_detail(self, index):
        wrapper, layout = box(margins=(14, 12, 14, 12), gap=6); layout.addWidget(label('RECEIVED (BUNKERED)', 'fieldLabel')); received, rl = box(True, gap=8)
        for key, title in [('rcvFrom', 'From'), ('rcvB', 'Meter before'), ('rcvA', 'Meter after'), ('rcvTicket', 'Ticket no.')]:
            e = self._editor(('bulk', index, key), key in ('rcvB', 'rcvA')); e.setPlaceholderText(title); rl.addWidget(e)
        layout.addWidget(received); layout.addWidget(label('TRANSFERRED TO THIRD PARTY (IN ORDER OF TRANSFER)', 'fieldLabel'))
        for j, row in enumerate(self.report['bulk'][index]['tr']):
            transfer, tl = box(True, gap=8)
            for key, title in [('to', 'To'), ('qty', 'Quantity'), ('mb', 'Meter before'), ('ma', 'Meter after'), ('tk', 'Ticket no.')]:
                e = self._editor(('bulk', index, 'tr', j, key), key in ('qty', 'mb', 'ma')); e.setPlaceholderText(title); tl.addWidget(e)
            tl.addWidget(button('×', lambda checked=False, b=index, n=j: self.remove_transfer(b, n))); layout.addWidget(transfer)
        add = button('+ Add transfer', lambda: self.add_transfer(index)); add.setEnabled(len(self.report['bulk'][index]['tr']) < 6)
        layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignLeft)
        return wrapper

    def _nationality(self, table, row, col, group, index):
        combo = QComboBox(); combo.setEditable(True); combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); combo.addItem('', '')
        sprite = QPixmap(str(ASSETS/'flags.png')); offsets = json.loads((ASSETS/'flag_offsets.json').read_text())
        for country in dict.fromkeys(CATALOG['countries']):
            if country == '--': combo.insertSeparator(combo.count()); continue
            code = CATALOG['countryCodes'].get(country, '')
            icon = QIcon(sprite.copy(0, -int(offsets[code]), 16, 16)) if code in offsets and not sprite.isNull() else QIcon()
            combo.addItem(icon, country, code)
        value = self.report[group][index]['nat']; pos = combo.findData(value)
        if pos < 0: pos = combo.findText(value)
        if pos < 0 and value: combo.addItem(value, value); pos = combo.count()-1
        combo.setCurrentIndex(max(pos, 0)); combo.lineEdit().setCursorPosition(0)
        combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.activated.connect(lambda i: self.edit((group, index, 'nat'), combo.itemData(i) or ''))
        def commit():
            i = combo.findText(combo.currentText(), Qt.MatchFlag.MatchFixedString)
            if i >= 0: self.edit((group, index, 'nat'), combo.itemData(i) or '')
            else: combo.setCurrentIndex(max(0, combo.findData(self.report[group][index]['nat'])))
        combo.lineEdit().editingFinished.connect(commit)
        path = (group, index, 'nat'); combo.setAccessibleName('.'.join(map(str, path))); combo.setProperty('vdrPath', path); combo.installEventFilter(self)
        self.editors[path] = combo; table.setCellWidget(row, col, combo)

    def _crew(self):
        self.crew_pob = label('', 'metric'); layout = self._section('Core crew · Tour of duty', 'max 90 working days', self.crew_pob)
        t = self._table('crew', ['#', 'Name', 'Rank', 'Age', 'Nationality', 'IC / Passport no.', 'Sign-on', 'Days', 'Comments', ''], [36, 200, 150, 56, 130, 160, 140, 70, 120, 30], len(self.report['crew']))
        for i, row in enumerate(self.report['crew']):
            self._computed(t, i, 0, ('crewno', i), str(i+1))
            for col, key in [(1, 'name'), (2, 'rank'), (3, 'age'), (5, 'ic'), (6, 'signon'), (8, 'comments')]:
                w = self._cell(t, i, col, ('crew', i, key), key == 'age', sorted(set(CATALOG['ranks']+self.store.custom_ranks)) if key == 'rank' else None, date_field=key == 'signon')
                if key == 'rank': w.lineEdit().editingFinished.connect(lambda n=i: self._custom_rank(n))
            self._nationality(t, i, 4, 'crew', i); self._computed(t, i, 7, ('days', i)); self._remove_cell(t, i, 9, 'crew', i)
        layout.addWidget(t); layout.addWidget(button('+ Add crew member', lambda: self.add_row('crew')), alignment=Qt.AlignmentFlag.AlignLeft)

    def _contractors(self):
        layout = self._section('Contractors list', 'not required for short intra-field journeys')
        t = self._table('ctr', ['#', 'Name', 'Vendor', 'Age', 'Nationality', 'IC / Passport no.', ''], [36, 200, 170, 56, 140, 180, 30], len(self.report['ctr']))
        for i, row in enumerate(self.report['ctr']):
            self._computed(t, i, 0, ('ctrno', i), str(i+1))
            for col, key in [(1, 'name'), (2, 'vendor'), (3, 'age'), (5, 'ic')]: self._cell(t, i, col, ('ctr', i, key), key == 'age')
            self._nationality(t, i, 4, 'ctr', i); self._remove_cell(t, i, 6, 'ctr', i)
        layout.addWidget(t); layout.addWidget(button('+ Add contractor', lambda: self.add_row('ctr')), alignment=Qt.AlignmentFlag.AlignLeft)
