"""GDS-AUDIT-009: long PDF table rows continue across pages with the header repeated."""
import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.vdr.model import blank_row
from app.vdr.pdf import export_pdf, import_pdf
from test_vdr import fixture_report

EVIDENCE = Path(__file__).resolve().parents[1]/'docs/evidence/remaining-p1-fixes/pdf'


def words(tag, count):
    """Distinct, checkable words: TAG-0001 TAG-0002 …"""
    return ' '.join(f'{tag}-{i:04d}' for i in range(1, count+1))


def finalized(**changes):
    r = fixture_report(); r.update(finalized=True, finalizedAt='2026-11-18T12:00:00Z')
    for key, value in changes.items():
        r[key] = value
    return r


def pages_text(path):
    return [page.extract_text() for page in PdfReader(str(path)).pages]


def save(report, name, tmp_path):
    path = tmp_path/name; export_pdf(report, path)
    EVIDENCE.mkdir(parents=True, exist_ok=True); (EVIDENCE/name).write_bytes(path.read_bytes())
    return path


def test_one_normal_row(tmp_path):
    pages = pages_text(save(finalized(), '01_normal_row.pdf', tmp_path))
    assert len(pages) >= 1 and 'Alongside berth' in ''.join(pages)


def test_row_wraps_within_page(tmp_path):
    r = finalized(); r['acts'][0]['act'] = words('WRAP', 60)  # ~600 chars: wraps, fits one page
    text = ''.join(pages_text(save(r, '02_row_wraps_within_page.pdf', tmp_path)))
    assert all(f'WRAP-{i:04d}' in text for i in range(1, 61))


def test_single_row_longer_than_a_page_continues_on_next_page(tmp_path):
    r = finalized(); r['acts'][0]['act'] = words('LONG', 900)  # one cell far taller than an A4 page
    pages = pages_text(save(r, '03_single_row_crosses_pages.pdf', tmp_path))
    holding = [i for i, text in enumerate(pages) if 'LONG-' in text]
    assert len(holding) >= 2, 'the row must continue onto a following page'
    text = ''.join(pages)
    assert all(f'LONG-{i:04d}' in text for i in (1, 450, 900))  # nothing lost at the break
    assert all(text.count(f'LONG-{i:04d}') == 1 for i in (1, 451, 900))  # nothing duplicated
    for i in holding:  # header repeats on every page that carries the table
        assert 'Activity' in pages[i] and 'Movement category' in pages[i]


def test_multiple_long_rows_and_final_page_integrity(tmp_path):
    r = finalized()
    times = ['0300', '0600', '0900', '1200', '1500', '1800', '2100', '2400']
    r['acts'] = [dict(blank_row('acts'), to=t, act=words(f'ROW{n}', 100), cat=r['acts'][0]['cat'], loc='LABUAN', dp='N')
                 for n, t in enumerate(times)]
    r['crew'][0]['comments'] = words('CREW', 100)
    r['bulk'][0]['remarks'] = words('BULK', 100)
    path = save(r, '04_multiple_long_rows.pdf', tmp_path)
    pages = pages_text(path); text = ''.join(pages)
    for n in range(len(times)):
        assert f'ROW{n}-0001' in text and f'ROW{n}-0100' in text
    assert 'CREW-0100' in text and 'BULK-0100' in text
    assert 'Contractors' in pages[-1] and 'Page' in pages[-1]  # last section and footer on the final page
    assert import_pdf(path) == r  # embedded data round trip intact


def test_header_repeats_for_long_crew_table(tmp_path):
    r = finalized()
    r['crew'] = [dict(blank_row('crew'), name=f'Crew {i}', rank='AB', nat='my', age='30', ic=f'IC{i}', signon='2026-11-01',
                      comments=words(f'C{i:02d}', 40)) for i in range(60)]
    pages = pages_text(save(r, '05_crew_header_repeat.pdf', tmp_path))
    carrying = [p for p in pages if re.search(r'Crew \d+', p)]
    assert len(carrying) >= 2 and all('IC / Passport' in p and 'Comments' in p for p in carrying)
