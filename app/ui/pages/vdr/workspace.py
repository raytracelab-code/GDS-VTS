"""VDR workspace controller. One Python store backs every section and export."""
from app.core.compat import remove_suffix
from app.qt import exec_qt
from datetime import date, timedelta
from pathlib import Path
from app.qt.QtCore import QDate, QEvent, QEasingCurve, QPropertyAnimation, QSettings, QStandardPaths, Qt, QTimer
from app.qt.QtGui import QColor, QFont, QKeySequence, QShortcut
from app.qt.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFrame, QLayout, QPushButton, QTableWidget,
    QHBoxLayout, QLineEdit, QMessageBox, QScrollArea, QTableWidgetItem, QVBoxLayout, QWidget)
from app.core.vessel_identity import load_identity
from app.vdr.model import (SECTIONS, blank_row, calculate, carry_forward_status, derive_location_durations, field_limit, fmt, hhmm,
    hse_perfect_days, number, report_number, reset_carry_forward, tour_days, validate)
from app.ui.theme import COLORS, FONT_BODY, FONT_DATA
from app.vdr.store import ReportStore
from .sections import CATALOG, Sections
from .date_picker import VdrDatePicker
from .style import STYLE, CALCULATION_ERROR_STYLE, VALIDATION_STYLE
from .widgets import box, button, label, load_fonts


class VdrPage(QWidget, Sections):
    def __init__(self, store=None, identity_provider=None):
        super().__init__()
        load_fonts(); self.setObjectName('vdrPage'); self.setStyleSheet(STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.identity_provider = identity_provider or self.configured_identity
        if store is None:
            path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/'vdr/reports.json'
            store = ReportStore(path, identity=self.identity_provider())
        self.store = store
        self.step = 0
        self._carry_generation = None
        self._building = False
        self.sections, self.tables, self.editors, self.computed = [], {}, {}, {}
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True); self.save_timer.setInterval(300)
        self.save_timer.timeout.connect(self.flush_save)
        self.root = QVBoxLayout(self); self.root.setContentsMargins(0, 0, 0, 0); self.root.setSpacing(0)
        self._topbar(); self._banner()
        workspace, layout = box(True, (20, 20, 20, 20), 20); self.root.addWidget(workspace, 1)
        self._sidebar(layout)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); layout.addWidget(self.scroll, 1)
        self.scroll.verticalScrollBar().valueChanged.connect(self._scroll_changed)
        for sequence, fn in [('Ctrl+Z', self.undo), ('Ctrl+Shift+Z', self.redo), ('Ctrl+Y', self.redo)]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); shortcut.activated.connect(fn)
        self._rebuild()
        QApplication.instance().aboutToQuit.connect(self.flush_save)
        if self.store.load_error:
            self.saved.setText('NOT SAVING'); self.saved.setToolTip(self.store.load_error)
            self.show_banner(self.store.load_error, 'error')
        elif self.store.notices:
            self.show_banner('\n\n'.join(self.store.notices), 'warning')

    @staticmethod
    def configured_identity():
        """Configure → Vessel & Client is the single source (app.core.vessel_identity)."""
        return load_identity()

    def _banner(self):
        self.banner = QFrame(); self.banner.setObjectName('storageBanner'); bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(24, 10, 24, 10); bl.setSpacing(12)
        self.banner_text = label('', 'bannerText'); self.banner_text.setWordWrap(True); bl.addWidget(self.banner_text, 1)
        folder = button('Open data folder', self.open_data_folder); bl.addWidget(folder)
        self.banner_close = button('Dismiss', lambda: self.banner.hide()); bl.addWidget(self.banner_close)
        self.banner.hide(); self.root.addWidget(self.banner)

    def show_banner(self, text, level='warning'):
        self.banner.setProperty('level', level); self.banner.style().unpolish(self.banner); self.banner.style().polish(self.banner)
        self.banner_text.setText(text); self.banner_text.setToolTip(str(self.store.path)); self.banner.show()

    def open_data_folder(self):
        from app.qt.QtGui import QDesktopServices
        from app.qt.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.path.parent)))

    @property
    def report(self):
        return self.store.report

    def _topbar(self):
        self.topbar_scroll = QScrollArea(); self.topbar_scroll.setWidgetResizable(True)
        self.topbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.topbar_scroll.setFixedHeight(62)
        frame = QFrame(); frame.setObjectName('topbar')
        row = QHBoxLayout(frame); row.setContentsMargins(16, 10, 16, 10); row.setSpacing(10)
        title, titles = box(); titles.addWidget(label('Vessel Daily Report', 'pageTitle'))
        self.subtitle = label('', 'subtitle'); titles.addWidget(self.subtitle); row.addWidget(title)
        hire, hl = box(True, gap=8)
        for caption, attribute, sample in (('DATE OF HIRE', 'hire_value', '00 Mmm 0000'), ('REPORT NO.', 'report_no', '00000')):
            text = label(caption, 'chromeText'); hl.addWidget(text)
            value = label('—', 'hireValue'); value.setMinimumWidth(100 if attribute == 'hire_value' else 36)
            setattr(self, attribute, value); hl.addWidget(value)
        row.addWidget(hire)
        self.badge = label('DRAFT', 'badge'); self.badge.setFixedHeight(26); row.addWidget(self.badge); row.addStretch()
        self.saved = label('', 'chromeText'); row.addWidget(self.saved)
        self.undo_button = button('↶', self.undo, 'iconButton'); self.undo_button.setToolTip('Undo (Ctrl+Z)'); self.undo_button.setAccessibleName('Undo')
        self.redo_button = button('↷', self.redo, 'iconButton'); self.redo_button.setToolTip('Redo (Ctrl+Shift+Z)'); self.redo_button.setAccessibleName('Redo')
        self.download_button = button('Download PDF', self.download, 'download')
        self.excel_button = button('Download Excel', self.download_excel, 'download')
        self.import_button = button('Import', self.import_report)
        self.finalize_button = button('Finalize report', self.finalize, 'finalize')
        for w in (self.undo_button, self.redo_button, self.download_button, self.excel_button, self.import_button, self.finalize_button):
            row.addWidget(w)
        self.topbar_scroll.setWidget(frame); self.root.addWidget(self.topbar_scroll)

    def _sidebar(self, layout):
        scroll = QScrollArea(); scroll.setFixedWidth(258); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar = QFrame(); sidebar.setObjectName('sidebar'); side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12); side.setSpacing(12); side.addWidget(label('REPORT DATE'))
        side.setAlignment(Qt.AlignmentFlag.AlignTop)
        dates, dl = box(True, gap=6)
        self.previous_day = button('‹', lambda: self.navigate_date(-1)); self.previous_day.setFixedSize(28, 34); self.previous_day.setToolTip('Previous day')
        dl.addWidget(self.previous_day); day, dyl = box(gap=2)
        self.day_label = label('', 'reportDate'); self.day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day_info = label(''); self.day_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dyl.addWidget(self.day_label); dyl.addWidget(self.day_info); dl.addWidget(day, 1)
        self.next_day = button('›', lambda: self.navigate_date(1)); self.next_day.setFixedSize(28, 34); self.next_day.setToolTip('Next day')
        dl.addWidget(self.next_day); side.addWidget(dates)
        toggle, tl = box(True)
        self.scroll_button = button('SCROLL', lambda: self.set_mode('scroll'), check=True)
        self.steps_button = button('STEPS', lambda: self.set_mode('steps'), check=True)
        tl.addWidget(self.scroll_button); tl.addWidget(self.steps_button); side.addWidget(toggle)
        self.nav_buttons = []; nav, nl = box(gap=2)
        for i, name in enumerate(SECTIONS):
            item = button(f'{i+1:02d}   {name}'.replace('&', '&&'), lambda checked=False, s=i: self.go_section(s), 'sectionNav', True)
            self.nav_buttons.append(item); nl.addWidget(item)
        side.addWidget(nav); side.addWidget(label('KEYBOARD'))
        keyboard = label('TAB — next field\nENTER — cell below\n↑↓ — move in column\n←→ — at text edge, move\nType in lists: “lab” → LABUAN')
        keyboard.setWordWrap(True); side.addWidget(keyboard)
        legend = label('White cell — manual entry\nShaded cell — computed\nDark highlight — needs attention')
        legend.setWordWrap(True); side.addWidget(legend)
        sidebar.setFixedHeight(645)
        scroll.setWidget(sidebar); layout.addWidget(scroll); self.sidebar = sidebar

    def _rebuild(self):
        old_scroll = self.scroll.verticalScrollBar().value()
        self._building = True
        self.tables, self.editors, self.computed, self.sections = {}, {}, {}, []
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        wrapper, wl = box(); self.panel = QFrame(); self.panel.setObjectName('reportPanel')
        self.panel_layout = QVBoxLayout(self.panel); self.panel_layout.setContentsMargins(0, 0, 0, 0); self.panel_layout.setSpacing(0)
        self.panel_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        wl.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        wl.addWidget(self.panel); wl.addStretch(); self.scroll.setWidget(wrapper)
        for build in (self._report_hse, self._weather, self._activities, self._equipment, self._bulk, self._crew, self._contractors):
            build()
        self.step_footer, fl = box(True, (24, 16, 24, 16))
        self.prev_step = button('← Previous', lambda: self.go_section(self.step-1))
        self.next_step = button('Next section →', lambda: self.go_section(self.step+1))
        self.prev_step.setProperty('editAction', False); self.next_step.setProperty('editAction', False)
        fl.addWidget(self.prev_step); fl.addStretch(); fl.addWidget(self.next_step); self.panel_layout.addWidget(self.step_footer)
        self._building = False; self._apply_mode(); self.refresh_values()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(old_scroll))

    def _get(self, path):
        value = self.report
        for key in path:
            value = value[key]
        return value

    def edit(self, path, value):
        if self._building or value == self._get(path):
            return
        if self.report['finalized']:
            return  # finalized reports are read-only; use Reopen report
        if isinstance(value, str) and len(value) > field_limit(path[-1]):
            # Refuse instead of silently truncating: the previous value stays saved.
            self.show_banner(f'This text is too long ({len(value)} characters; maximum {field_limit(path[-1])}). '
                             'It has NOT been saved — shorten it and it will save automatically.', 'error')
            return
        if self.banner.property('level') == 'error' and 'too long' in self.banner_text.text():
            self.banner.hide()
        def update(report):
            target = report
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
        self.store.mutate(update); self._changed()

    def _changed(self):
        self.saved.setText('Saving…'); self.save_timer.start(); self.refresh_values()

    def refresh_values(self):
        if self._building:
            return
        calc, errors = calculate(self.report), validate(self.report)
        # Configure is the single identity source for screen, PDF and Excel alike.
        identity = self.identity_provider()
        self.subtitle.setText(' — '.join(v for v in (identity.get('client'), identity.get('vessel')) if v).upper() or 'VESSEL NOT SET — ENTER IN CONFIGURE')
        hire_date = QDate.fromString(identity.get('hireDate', ''), 'yyyy-MM-dd')
        self.hire_value.setText(hire_date.toString('dd MMM yyyy') if hire_date.isValid() else 'NOT SET')
        number_value = report_number(self.report, identity)
        self.report_no.setText(str(number_value) if number_value is not None and number_value >= 1 else '—')
        self.report_no.setToolTip('Report No. = days since Date of Hire + 1 (Date of Hire is day 1). Set Date of Hire in Configure.')
        self.badge.setText('FINALIZED' if self.report['finalized'] else f'DRAFT · {len(errors)} ISSUES' if errors else 'READY TO FINALIZE')
        if self.badge.property('finalized') != self.report['finalized']:
            self.badge.setProperty('finalized', self.report['finalized'])
            self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge)
        self.undo_button.setEnabled(bool(self.store.undo_stack)); self.redo_button.setEnabled(bool(self.store.redo_stack))
        self.download_button.setEnabled(self.report['finalized'])
        self.download_button.setToolTip('Download PDF' if self.report['finalized'] else 'Finalize the report before exporting')
        self.excel_button.setEnabled(self.report['finalized'])
        self.excel_button.setToolTip('Download Excel' if self.report['finalized'] else 'Finalize the report before exporting')
        self.finalize_button.setText('Reopen report' if self.report['finalized'] else 'Finalize report'); self.finalize_button.setEnabled(True)
        self.finalize_button.setToolTip('Return this finalized report to draft so it can be edited' if self.report['finalized'] else 'Check the report and lock it for export')
        self._apply_read_only()
        self._refresh_carry_notice()
        delta = (date.fromisoformat(self.store.today)-date.fromisoformat(self.store.current)).days
        self.day_label.setText(QDate.fromString(self.store.current, 'yyyy-MM-dd').toString('dd MMM yyyy'))
        self.day_info.setText('Today' if delta == 0 else 'Yesterday' if delta == 1 else f'{delta} days ago')
        self.previous_day.setEnabled(delta < 364); self.next_day.setEnabled(delta > 0)
        self.coverage_label.setText('COVERED '+hhmm(calc['coverage'], True)+' / 24:00')
        self.consumption_label.setText(fmt(calc['totalCons'])+' ltrs')
        self.add_activity.setEnabled(calc['coverage'] < 1440 and len(self.report['acts']) < 50)
        self._refresh_location_durations()
        self.crew_pob.setText('CREW POB  '+str(sum(bool(r['name'].strip()) for r in self.report['crew'])))
        for i, row in enumerate(calc['actD']):
            self.computed[('from', i)].setText(hhmm(row['fromM']))
            self.computed[('duration', i)].setText(hhmm(row['min'], True) if row['ok'] else 'INVALID' if self.report['acts'][i]['to'] else '—')
        for i, value in enumerate(calc['eqCons']):
            w = self.computed[('cons', i)]; w.setText(fmt(value)); w.setStyleSheet(CALCULATION_ERROR_STYLE if value is not None and value < 0 else '')
        for i, row in enumerate(self.report['bulk']):
            if ('fuel', i) in self.computed:
                self.computed[('fuel', i)].setText(fmt(calc['totalCons']))
            self.computed[('transfer', i)].setText(fmt(sum(number(t['qty']) or 0 for t in row['tr'])))
            value = calc['bulkClose'][i]; w = self.computed[('closing', i)]; w.setText(fmt(value))
            w.setStyleSheet(CALCULATION_ERROR_STYLE if value is not None and value < 0 else '')
        for i, row in enumerate(self.report['crew']):
            days = tour_days(row['signon'], self.store.current); w = self.computed[('days', i)]
            w.setText(str(days) if days is not None else '—'); w.setStyleSheet(CALCULATION_ERROR_STYLE if days is not None and (days > 90 or days < 1) else '')
        for (i, key, value), w in self.weather_buttons.items():
            w.setChecked(self.report['wx'][i][key] == value)
        fwd, aft = number(self.report['meta']['fwd']), number(self.report['meta']['aft'])
        trim = 'ENTER FWD & AFT DRAFTS' if fwd is None or aft is None else 'EVEN KEEL' if abs(fwd-aft) < .05 else f'TRIM {fmt(abs(fwd-aft))} m BY '+('STERN' if aft > fwd else 'HEAD')
        self.trim_label.setText(f'FWD {fmt(fwd)} m · AFT {fmt(aft)} m · {trim}'); self.draft_profile.update()
        days = hse_perfect_days(self.report, identity)
        self.perfect_days.setText('PERFECT DAYS  '+str(days if days is not None else '—'))
        for i, item in enumerate(self.nav_buttons):
            count = sum(e['s'] == i for e in errors)
            item.setText(f'{i+1:02d}   {SECTIONS[i]}'.replace('&', '&&')+(f'   {count}' if count else ''))

    def _refresh_location_durations(self):
        rows = derive_location_durations(self.report['acts'])
        table = self.location_durations
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            table.setRowHeight(i, 38)
            for j, key in enumerate(('from', 'to', 'duration', 'location')):
                item = QTableWidgetItem(row[key])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setBackground(QColor(COLORS['workspace']))
                item.setForeground(QColor(COLORS['navy']))
                font = QFont(FONT_BODY if key == 'location' else FONT_DATA)
                font.setPixelSize(13); item.setFont(font)
                table.setItem(i, j, item)
        table.setFixedHeight(46 + len(rows)*38 + 14)
        self.location_duration_empty.setVisible(not rows)

    def _finish_time(self, path, widget):
        if self._building or tuple(path) not in self.editors or self.editors[tuple(path)] is not widget:
            return
        text = widget.text().strip()
        if text.isdigit() and len(text) < 3:
            text = text.zfill(2)+'00'
        elif text.isdigit() and len(text) == 3:
            text = text.zfill(4)
        self.edit(path, text); widget.setText(text); calc = calculate(self.report)
        if calc['coverage'] == 1440:
            index = next(i for i,r in enumerate(calc['actD']) if r['ok'] and r['toM'] == 1440)
            later = self.report['acts'][index+1:]
            if later and not any(any(v.strip() for v in row.values()) for row in later):
                # Only empty trailing rows are removed; logged activities are never deleted by a time edit.
                self.store.mutate(lambda r: r.update(acts=r['acts'][:index+1])); self._rebuild(); self._changed()
            elif later:
                self.show_banner(f'Row {index+1} now ends the day at 2400. The {len(later)} row(s) after it were kept and are '
                                 'marked invalid — delete them (×) if they are no longer needed, or change this TO time.', 'warning')
        elif path[1] == len(self.report['acts'])-1 and calc['actD'][-1]['ok'] and len(self.report['acts']) < 50:
            self.add_row('acts')

    def add_row(self, group, name=''):
        if group == 'acts' and (calculate(self.report)['coverage'] >= 1440 or len(self.report['acts']) >= 50):
            return
        self.store.mutate(lambda r: r[group].append(blank_row(group, name))); self._rebuild(); self._changed()

    def remove_row(self, group, index):
        def remove(report):
            if len(report[group]) > 1:
                report[group].pop(index)
            elif group == 'acts':
                report[group][0] = blank_row(group)
        self.store.mutate(remove); self._rebuild(); self._changed()

    def toggle_details(self, index):
        self.store.mutate(lambda r: r['bulk'][index].update(det=not r['bulk'][index]['det'])); self._rebuild(); self._changed()

    def transfer_capacity(self, index):
        from app.vdr.validation import TRANSFER_CAPACITY_FUEL, TRANSFER_CAPACITY_OTHER
        from app.vdr.model import is_fuel
        return TRANSFER_CAPACITY_FUEL if is_fuel(self.report['bulk'][index]['name']) else TRANSFER_CAPACITY_OTHER

    def add_transfer(self, index):
        # The Excel template holds 2 fuel transfers and 1 for every other item.
        if len(self.report['bulk'][index]['tr']) >= self.transfer_capacity(index):
            return
        self.store.mutate(lambda r: (r['bulk'][index]['tr'].append(blank_row('tr')), r['bulk'][index].update(det=True)))
        self._rebuild(); self._changed()

    def remove_transfer(self, bulk, index):
        self.store.mutate(lambda r: r['bulk'][bulk]['tr'].pop(index)); self._rebuild(); self._changed()

    def _custom_rank(self, index):
        if self._building or index >= len(self.report['crew']):
            return
        value = self.report['crew'][index]['rank'].strip()
        if value and value.lower() not in [s.lower() for s in CATALOG['ranks']+self.store.custom_ranks]:
            self.store.custom_ranks.append(value); self.save_timer.start()

    def toggle_weather(self, index, field, value):
        self.edit(('wx', index, field), '' if self.report['wx'][index][field] == value else value)
        for (i, key, choice), w in self.weather_buttons.items():
            w.setChecked(self.report['wx'][i][key] == choice)

    def copy_weather(self, index):
        self.store.mutate(lambda r: r['wx'][index].update({k:v for k,v in r['wx'][index-1].items() if k != 't'}))
        self._rebuild(); self._changed()

    def change_temp(self, index, delta):
        current = number(self.report['wx'][index]['temp'])
        self.edit(('wx', index, 'temp'), remove_suffix(str((30 if current is None else current)+delta), '.0'))
        self.editors[('wx', index, 'temp')].setText(self.report['wx'][index]['temp'])

    def set_mode(self, mode):
        self.store.layout = mode; self._apply_mode(); self.save_timer.start()

    def _apply_mode(self):
        steps = self.store.layout == 'steps'
        for i, section in enumerate(self.sections):
            section.setVisible(not steps or self.step == i)
        self.scroll_button.setChecked(not steps); self.steps_button.setChecked(steps); self.step_footer.setVisible(steps)
        self.prev_step.setEnabled(self.step > 0); self.next_step.setEnabled(self.step < 6); self._mark_nav(self.step if steps else 0)
        QTimer.singleShot(0, self._fit_all_tables)

    def _mark_nav(self, selected):
        for i, item in enumerate(self.nav_buttons):
            item.setChecked(i == selected)

    def go_section(self, index):
        self.step = min(6, max(0, index))
        if self.store.layout == 'steps':
            self._apply_mode(); self.scroll.verticalScrollBar().setValue(0)
        else:
            bar = self.scroll.verticalScrollBar()
            target = self.sections[self.step].mapTo(self.scroll.widget(), self.sections[self.step].rect().topLeft()).y()
            self.animation = QPropertyAnimation(bar, b'value', self); self.animation.setDuration(220)
            self.animation.setStartValue(bar.value()); self.animation.setEndValue(target)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic); self.animation.start(); self._mark_nav(self.step)

    def _scroll_changed(self, value):
        if self.store.layout != 'scroll' or self._building or not self.sections:
            return
        selected = 0
        for i, section in enumerate(self.sections):
            if section.y() <= value+10:
                selected = i
        if value == self.scroll.verticalScrollBar().maximum():
            selected = 6
        self._mark_nav(selected)

    def navigate_date(self, delta):
        self.select_date((date.fromisoformat(self.store.current)+timedelta(days=delta)).isoformat())

    def select_date(self, day):
        if self._building or day == self.store.current:
            return
        try:
            self.store.select(day)
        except ValueError:
            return
        self.step = 0; self._rebuild(); self.scroll.verticalScrollBar().setValue(0); self.save_timer.start()

    def undo(self):
        if self.store.undo():
            self._rebuild(); self._changed()

    def redo(self):
        if self.store.redo():
            self._rebuild(); self._changed()

    def flush_save(self):
        self.save_timer.stop()
        try:
            self.store.save()
            from datetime import datetime
            self.saved.setText('Saved '+datetime.now().strftime('%H:%M:%S')); self.saved.setToolTip(str(self.store.path))
            if self.banner.property('level') == 'save':
                self.banner.hide()
            return True
        except OSError as error:
            # Clear, persistent message (not just grey status text): what happened, is data safe, what next.
            self.saved.setText('NOT SAVED'); self.saved.setToolTip(str(error))
            self.show_banner(str(error) if str(error).startswith(('Not saved', 'Could not load')) else
                             f'Not saved: {error}. Your previously saved data is safe. Saving retries on your next change.', 'save')
            return False

    def finalize(self):
        if self.report['finalized']:
            return self.reopen()
        errors = self.store.finalize(identity=self.identity_provider())
        if errors:
            self.show_errors(errors)
            return False
        self._changed()
        return self.flush_save()

    def reopen(self):
        """Finalized reports are read-only; returning to draft is explicit and confirmed."""
        answer = QMessageBox.question(self, 'Reopen report?',
            f'Reopen the finalized report for {self.store.current}?\n\nIt returns to DRAFT so it can be edited. '
            'Exported files already sent are not changed. Finalize it again before exporting.')
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.store.reopen(); self._rebuild(); self._changed()
        return True

    def show_errors(self, errors, title=None):
        title = title or f'Cannot finalize — {len(errors)} issue(s) to fix'
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(600, 520)
        dialog.setStyleSheet(VALIDATION_STYLE)
        layout = QVBoxLayout(dialog); layout.addWidget(label(title, 'validationTitle'))
        hint = label('Each item says what to fix. Press Go to jump to that section; the report stays a draft until every item is fixed.')
        hint.setWordWrap(True); layout.addWidget(hint)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); contents, cl = box(gap=8)
        for section in sorted({e['s'] for e in errors}):
            group = [e for e in errors if e['s'] == section]
            heading, hl = box(True, gap=12); hl.addWidget(label(f"{group[0]['sec'].upper()} · {len(group)}", 'blockTitle'), 1)
            def go(checked=False, section=section):
                dialog.accept(); self.go_section(section)
            hl.addWidget(button('Go', go)); cl.addWidget(heading)
            for error in group:
                text = label('• ' + error['msg']); text.setWordWrap(True); cl.addWidget(text)
        cl.addStretch(); scroll.setWidget(contents); layout.addWidget(scroll); layout.addWidget(button('Close', dialog.reject)); exec_qt(dialog)

    def _export_report(self):
        """The report as exported: identity always comes from Configure (single source)."""
        report = dict(self.report); report['identity'] = dict(self.identity_provider())
        return report

    def download(self):
        if not self.report['finalized']:
            return
        identity = self.identity_provider()
        from app.vdr.excel import suggested_filename
        name = suggested_filename(identity.get('vessel', ''), self.store.current)[:-5] + '.pdf'
        path, _ = QFileDialog.getSaveFileName(self, 'Download PDF', name, 'PDF reports (*.pdf)')
        if path:
            try:
                from app.vdr.pdf import export_pdf
                export_pdf(self._export_report(), path); self.saved.setText('PDF downloaded')
            except Exception as error:
                QMessageBox.warning(self, 'PDF not created',
                    f'The PDF could not be created. Your report data is safe and unchanged.\n\n{error}\n\n'
                    'If the file is open in a PDF viewer, close it and try again, or choose another folder.')

    def import_report(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import VDR report', '', 'PDF reports (*.pdf)')
        if not path:
            return
        try:
            from app.vdr.pdf import import_pdf
            report = import_pdf(path); day = report['meta']['date']
            if day in self.store.reports and not self.store.is_untouched(day) and QMessageBox.question(self, 'Replace report?', f'Replace the existing report for {day}? Undo remains available.') != QMessageBox.StandardButton.Yes:
                return
            issues = self.store.import_report(report, identity=self.identity_provider()); self.step = 0; self._rebuild()
            if self.flush_save():
                self.saved.setText('Imported report for '+day)
            if issues:
                self.show_errors(issues, f'Imported as DRAFT — {len(issues)} issue(s) must be fixed before it can be finalized')
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Import failed', f'The PDF could not be imported. No report was changed.\n\n{error}\n\n'
                                'Choose a PDF that was downloaded from GDS VTS (Download PDF).')

    def download_excel(self):
        if not self.report['finalized']:
            return
        from app.vdr.excel import VdrExcelExporter, suggested_filename
        # Configure is authoritative for vessel/hire identity. Empty settings must
        # clear the template, rather than fall back to its sample or imported data.
        identity = self.identity_provider()
        filename = suggested_filename(identity.get('vessel',''), self.store.current)
        path, _ = QFileDialog.getSaveFileName(self, 'Download Excel', filename, 'Excel reports (*.xlsx)')
        if not path:
            return
        if not Path(path).suffix:
            path += '.xlsx'
        try:
            VdrExcelExporter().export(self.report, path, identity=identity)
            self.saved.setText('Excel report downloaded')
        except Exception as error:
            QMessageBox.warning(self, 'Excel export failed', f'The Excel file was not created. Your report data is safe and unchanged.\n\n{error}')

    def _apply_read_only(self):
        """A finalized report is locked; only Reopen report makes it editable again."""
        locked = self.report['finalized']
        for editor in self.editors.values():
            if isinstance(editor, VdrDatePicker):
                editor.setReadOnly(locked)
            elif isinstance(editor, QLineEdit):
                editor.setReadOnly(locked)
            elif isinstance(editor, QComboBox):
                editor.setEnabled(not locked)
        if hasattr(self, 'panel'):
            for widget in self.panel.findChildren(QPushButton):
                if widget.property('editAction') is not False:
                    widget.setEnabled(not locked)
            for widget in self.panel.findChildren(QComboBox):
                if widget.property('vdrPath') is None:
                    widget.setEnabled(not locked)
        if locked:
            self.add_activity.setEnabled(False)

    def _refresh_carry_notice(self):
        if not hasattr(self, 'carry_notices'):
            return
        source = self.store.source_day(self.store.current)
        previous = self.store.reports.get(source) if source else None
        linked, differing = carry_forward_status(self.report, previous)
        when = QDate.fromString(source, 'yyyy-MM-dd').toString('dd MMM yyyy') if source else ''
        for notice, reset in self.carry_notices:
            if previous is None:
                notice.setText('No earlier report — enter opening values manually.')
                reset.hide(); continue
            gap = (date.fromisoformat(self.store.current) - date.fromisoformat(source)).days
            text = f'Openings carried from the {when} closing' + (f' ({gap} days earlier; days in between have no report)' if gap > 1 else '') + '.'
            if differing:
                items = '; '.join(f'{name}: {fmt(number(current))} (closing was {fmt(number(expected))})' for name, current, expected in differing[:4])
                text += f' {len(differing)} value(s) were changed by hand and differ: {items}' + (' …' if len(differing) > 4 else '') + '.'
            notice.setText(text); notice.setProperty('attention', bool(differing))
            notice.style().unpolish(notice); notice.style().polish(notice)
            reset.setVisible(bool(differing) and not self.report['finalized']); reset.setText(f'Use {when} closing values')

    def reset_openings(self):
        source = self.store.source_day(self.store.current)
        if not source:
            return
        previous = self.store.reports[source]
        self.store.mutate(lambda r: reset_carry_forward(r, previous, source)); self._rebuild(); self._changed()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and isinstance(watched, QTableWidget):
            # Fit synchronously from the new size (the viewport is not resized yet at this point),
            # then once more after layout settles, so widths never lag behind the window.
            self._fit_columns(watched, event.size().width() - 2*watched.frameWidth())
            QTimer.singleShot(0, lambda t=watched: self._fit_columns(t))
        elif event.type() == QEvent.Type.Show and isinstance(watched, QTableWidget):
            QTimer.singleShot(0, lambda t=watched: self._fit_columns(t))
        if event.type() == QEvent.Type.KeyPress:
            path, key = watched.property('vdrPath'), event.key()
            if path and len(path) >= 3 and isinstance(path[1], int) and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Up, Qt.Key.Key_Down):
                if isinstance(watched, QComboBox) and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    return super().eventFilter(watched, event)
                target = self.editors.get((path[0], path[1]+(-1 if key == Qt.Key.Key_Up else 1), *path[2:]))
                if target:
                    target.setFocus()
                    if isinstance(target, QLineEdit):
                        target.selectAll()
                    return True
            if path and len(path) == 3 and isinstance(watched, QLineEdit) and key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and not watched.hasSelectedText():
                if watched.cursorPosition() == (0 if key == Qt.Key.Key_Left else len(watched.text())):
                    row = [w for p,w in self.editors.items() if len(p) == 3 and p[:2] == tuple(path[:2])]
                    if watched in row:
                        i = row.index(watched)+(-1 if key == Qt.Key.Key_Left else 1)
                        if 0 <= i < len(row):
                            row[i].setFocus(); return True
        return super().eventFilter(watched, event)

    @staticmethod
    def column_widths(available, base, minimum, flex):
        """Responsive widths: fill spare width via the flex (text) columns; when the
        viewport is narrower than the base widths, shrink columns proportionally down
        to their readable minimums. Horizontal scrolling remains only below sum(minimum)."""
        total = sum(base)
        if available >= total:
            extra = available - total; widths = list(base)
            for i, col in enumerate(flex):
                widths[col] += extra // len(flex) + (extra % len(flex) if i == 0 else 0)
            return widths
        minimum = minimum or base
        if available <= sum(minimum):
            return list(minimum)
        need, slack = total - available, sum(b - m for b, m in zip(base, minimum))
        widths = [b - (b - m) * need // slack for b, m in zip(base, minimum)]
        widths[flex[0]] += available - sum(widths)  # absorb rounding so columns exactly fill
        return widths

    def _fit_columns(self, table, available=None):
        from app.qt import isValid
        if not isValid(table) or (available is None and not table.isVisible()):
            return
        widths = table.property('baseWidths')
        flex = table.property('flexColumns')
        if not widths or not flex:
            return
        available = table.viewport().width() if available is None else available
        for col, width in enumerate(self.column_widths(available, list(widths), table.property('minWidths'), list(flex))):
            if table.columnWidth(col) != width:
                table.setColumnWidth(col, width)

    def _fit_all_tables(self):
        for table in list(self.tables.values()):
            self._fit_columns(table)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'meta_top'):
            direction = QHBoxLayout.Direction.TopToBottom if self.width() < 1160 else QHBoxLayout.Direction.LeftToRight
            self.meta_top.layout().setDirection(direction); self.hse_bottom.layout().setDirection(direction)

    def showEvent(self, event):
        super().showEvent(event)
        # Identity is read from Configure on every refresh (never copied from NAV or elsewhere).
        if not self._building and hasattr(self, 'badge'):
            self.refresh_values(); QTimer.singleShot(0, self._fit_all_tables)
