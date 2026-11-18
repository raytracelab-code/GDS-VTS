"""Dedicated historical containment-loss date and legacy state/PDF compatibility."""
from copy import deepcopy
import base64
import json
import zlib
import pytest
from pypdf import PdfReader
from app.vdr.model import new_report, normalize, rollover
from app.vdr.store import ReportStore
from app.vdr.pdf import export_pdf, import_pdf
from app.ui.pages.vdr.date_picker import VdrDatePicker
from app.ui.pages.vdr.workspace import VdrPage
from test_vdr import fixture_report


def test_new_report_defaults_and_dedicated_key():
    report = new_report('2026-11-19')
    assert report['hse']['containment_loss'] == ''
    assert {'inc24','lti','inj','incd','containment_loss'} == set(report['hse'])
    report['hse']['incd'] = '2026-10-01'
    report['hse']['containment_loss'] = '2026-11-12'
    assert normalize(report)['hse'] == report['hse']


@pytest.mark.parametrize('legacy',[True,False])
def test_saved_state_normalization_and_deserialization(tmp_path, legacy):
    report = fixture_report('2026-11-19')
    report['hse'].update(incd='2026-10-01',containment_loss='2026-11-12')
    if legacy:
        report['hse'].pop('containment_loss')
    before = deepcopy(report)
    path = tmp_path/'reports.json'
    path.write_text(json.dumps({'reports':{'2026-11-19':report}}))
    store = ReportStore(path,today='2026-11-19')
    assert not store.load_error
    expected = '' if legacy else '2026-11-12'
    assert store.report['hse']['containment_loss'] == expected
    assert store.report['hse']['incd'] == '2026-10-01'
    assert report == before
    store.save()
    assert json.loads(path.read_text())['reports'][store.current]['hse']['containment_loss'] == expected
    assert ReportStore(path,today=store.today).report == store.report


@pytest.mark.parametrize('value',['','2026-11-12'])
def test_rollover_matches_other_historical_hse_dates_and_finalization(tmp_path, value):
    report = fixture_report('2026-11-18')
    report['hse'].update(inc24='Nil',lti=value,inj=value,incd=value,containment_loss=value)
    store = ReportStore(tmp_path/'reports.json',today='2026-11-19')
    store.reports['2026-11-18'] = report
    store.reports.pop('2026-11-19')
    store.select('2026-11-19')
    assert store.report['hse'] == dict(inc24='',lti=value,inj=value,incd=value,containment_loss=value)
    assert rollover(report,'2026-11-19')['hse'] == store.report['hse']
    store.reports[store.current] = fixture_report(store.current)
    store.report['hse']['containment_loss'] = value
    assert store.finalize() == [] and store.report['finalized']


@pytest.mark.parametrize('mode',['scroll','steps'])
def test_calendar_selection_clear_autosave_history_and_finalized_lock(qtbot,tmp_path,mode):
    store = ReportStore(tmp_path/'reports.json',today='2026-11-19')
    store.reports[store.current] = fixture_report(store.current)
    store.report['hse']['incd'] = '2026-10-01'
    page = VdrPage(store); qtbot.addWidget(page); page.resize(1440,900); page.show()
    page.set_mode(mode); page.go_section(0)
    field = page.editors[('hse','containment_loss')]
    assert isinstance(field,VdrDatePicker) and field.clearable and field.iso_value() == ''
    assert page.sections[0].isAncestorOf(field) and len(page.sections) == 7
    popup = field.open_calendar(); assert popup.title.text() == 'November 2026'
    popup.select('2026-11-12')
    assert field.text() == '12 Nov 2026' and page.report['hse']['containment_loss'] == '2026-11-12'
    assert page.report['hse']['incd'] == '2026-10-01'
    popup = field.open_calendar()
    assert next(b for b in popup.day_buttons if b.property('selected')).property('isoDate') == '2026-11-12'
    popup.hide()
    qtbot.waitUntil(lambda:page.saved.text().startswith('Saved '),timeout=3000)
    assert ReportStore(store.path,today=store.today).report['hse']['containment_loss'] == '2026-11-12'
    page.undo(); assert page.report['hse']['containment_loss'] == ''
    page.redo(); assert page.report['hse']['containment_loss'] == '2026-11-12'
    field = page.editors[('hse','containment_loss')]
    field.open_calendar().clear_button.click()
    assert page.report['hse']['containment_loss'] == ''
    page.undo(); assert page.report['hse']['containment_loss'] == '2026-11-12'
    assert page.finalize()
    assert page.editors[('hse','containment_loss')].open_calendar() is None
    page.save_timer.stop()


@pytest.mark.parametrize('value',['','2026-11-12'])
def test_pdf_visible_hse_row_and_embedded_state(tmp_path,value):
    report = fixture_report(); report['hse']['containment_loss'] = value
    report['hse']['incd'] = '2026-10-01'; report['finalized'] = True
    path = tmp_path/'report.pdf'; export_pdf(report,path)
    text = '\n'.join(p.extract_text() for p in PdfReader(path).pages)
    assert 'Last containment loss' in text and 'Last recordable incident' in text
    if value:
        assert value in text
    assert import_pdf(path) == normalize(report)


def test_legacy_pdf_without_key_imports_empty(tmp_path):
    report = fixture_report(); report['hse'].pop('containment_loss')
    report['hse']['incd'] = '2026-10-01'
    # Original reference PDFs use this embedded jsPDF state packet.
    payload = base64.b64encode(zlib.compress(json.dumps(report).encode()))
    path = tmp_path/'legacy.pdf'
    path.write_bytes(b'%PDF-1.7\n<jspdf:metadata>'+payload+b'</jspdf:metadata>')
    imported = import_pdf(path)
    assert imported['hse']['containment_loss'] == ''
    assert imported['hse']['incd'] == '2026-10-01'
