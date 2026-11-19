"""Single PDF interchange pipeline, including reference jsPDF metadata support."""
import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import re
import zlib
from xml.sax.saxutils import escape

from .model import calculate, fmt, hhmm, hse_perfect_days, normalize, number, report_number, tour_days

ASSETS = Path(__file__).resolve().parents[1] / 'resources/vdr'
MAX_PDF = 32 * 1024 * 1024
MAX_RECORD = 4 * 1024 * 1024


def decode_record(payload):
    try:
        compressed = base64.b64decode(re.sub(rb'\s', b'', payload), validate=True)
        decoder = zlib.decompressobj()
        data = decoder.decompress(compressed, MAX_RECORD + 1)
        if len(data) > MAX_RECORD or not decoder.eof:
            raise ValueError('Embedded report data exceeds limit or is incomplete')
        return normalize(json.loads(data.decode('utf-8')))
    except (zlib.error, UnicodeError, TypeError) as error:
        raise ValueError('Invalid embedded report data') from error


def import_pdf(path):
    from pypdf import PdfReader
    path = Path(path)
    if path.stat().st_size > MAX_PDF:
        raise ValueError('PDF exceeds 32 MB limit')
    raw = path.read_bytes()
    if not raw.startswith(b'%PDF-'):
        raise ValueError('Please select a PDF report')
    # Original reference files place an uncompressed XML packet in the PDF.
    match = re.search(rb'<jspdf:metadata>([A-Za-z0-9+/=\s]*?)</jspdf:metadata>', raw)
    if match:
        return decode_record(match[1])
    try:
        reader = PdfReader(BytesIO(raw))
        packet = reader.trailer['/Root'].get('/Metadata')
        if packet:
            match = re.search(rb'<jspdf:metadata>([A-Za-z0-9+/=\s]*?)</jspdf:metadata>', packet.get_object().get_data())
            if match:
                return decode_record(match[1])
    except Exception as error:
        raise ValueError('Could not read embedded report data') from error
    raise ValueError('No report data found in that PDF')


def export_pdf(report, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    report = normalize(deepcopy(report))
    if not report['finalized']:
        raise ValueError('Finalize the report before exporting')
    for name, filename in [('VdrBody', 'inter'), ('VdrTitle', 'manrope'), ('VdrData', 'jetbrains-mono')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(ASSETS/f'{filename}.ttf')))
    body = ParagraphStyle('body', fontName='VdrBody', fontSize=7, leading=9, textColor=colors.HexColor('#17263A'))
    head = ParagraphStyle('head', parent=body, fontName='VdrTitle', fontSize=10, leading=14, spaceBefore=10, spaceAfter=5)
    width = A4[0] - 64
    flow = []
    calc = calculate(report)
    def paragraph(value):
        return Paragraph(escape(str(value if value not in ('', None) else '—')), body)
    def table(headers, rows, widths=None):
        values = ([headers] if headers else []) + rows
        if not rows:
            values.append(['No entries'] + ['']*(len(headers)-1))
        result = Table([[paragraph(v) for v in row] for row in values],
                       colWidths=[width*v/sum(widths) for v in widths] if widths else None,
                       repeatRows=1 if headers else 0, hAlign='LEFT',
                       # GDS-AUDIT-009: a row taller than the remaining page continues on the next
                       # page (cell text split between lines) and the header row repeats.
                       splitInRow=1)
        styles = [('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#D6D6D6')),
                  ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5),
                  ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]
        if headers:
            styles.append(('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7EDF4')))
        result.setStyle(TableStyle(styles))
        flow.append(result)
    def section(title):
        flow.append(Paragraph(escape(title), head))
    m, h, e = report['meta'], report['hse'], report['end']
    identity = report.get('identity', {})
    report_no, perfect = report_number(report, identity), hse_perfect_days(report, identity)
    section('1 · Report & HSE')
    table([], [['Vessel', identity.get('vessel', ''), 'Client', identity.get('client', '')],
               ['Date of hire', identity.get('hireDate', ''), 'Report No.', '' if report_no is None else str(report_no)],
               ['HSE perfect days', '' if perfect is None else str(perfect), 'Report date', m['date']],
               ['Captain on duty', m['captain'], 'Location @ 2400H', m['loc24']],
               ['Draft FWD (m)', m['fwd'], 'Draft AFT (m)', m['aft']],
               ['Fuel endurance (days)', e['fuel'], 'Drinking water endurance (days)', e['water']],
               ['Provision (days)', e['prov'], 'Next provision', e['nextProv']],
               ['HSE incident 24h', h['inc24'] or 'Nil', 'Last LTI', h['lti'] or 'None'],
               ['Last recordable injury', h['inj'] or 'None', 'Last recordable incident', h['incd'] or 'None'],
               ['Last containment loss', h['containment_loss'] or 'None', '', '']], [1, 1, 1, 1])
    section('2 · Weather condition')
    table(['Time', 'Wind (kn)', 'Swell (m)', 'Sea state', 'Sky', 'Vis (NM)', 'Temp °C'],
          [[r[k] for k in ('t', 'wind', 'swell', 'sea', 'sky', 'vis', 'temp')] for r in report['wx']], [1, 1, 1, 1.3, 1.6, 1, 1])
    section('3 · Daily operation activity log')
    table(['From', 'To', 'Activity', 'Movement category', 'DP', 'Lifts', 'POB', 'Location'],
          [[hhmm(calc['actD'][i]['fromM'])] + [r[k] for k in ('to', 'act', 'cat', 'dp', 'lifts', 'pob', 'loc')]
           for i, r in enumerate(report['acts']) if any(r.values())], [0.7, 0.7, 3, 2.5, .5, .6, .6, 1.6])
    section('4 · Running hours & consumption')
    table(['Equipment', 'Total hrs', 'Daily hrs', 'FM @0000H', 'FM @2400H', 'Consumed (L)'],
          [[r[k] for k in ('name', 'total', 'daily', 'fm0', 'fm24')] + [fmt(calc['eqCons'][i])]
           for i, r in enumerate(report['eq'])] + [['Total daily', '', '', '', '', fmt(calc['totalCons'])]], [2, 1, 1, 1.4, 1.4, 1.4])
    section('5 · Bulk inventory (ROB)')
    table(['Item', 'Opening', 'Received', 'Consumed', 'Transferred', 'Closing @2400H'],
          [[r['name'], r['open'], r['rcvQty'], fmt(calc['totalCons']) if r['name'].startswith('FUEL') else r['cons'],
            fmt(sum(number(t['qty']) or 0 for t in r['tr'])), fmt(calc['bulkClose'][i])]
           for i, r in enumerate(report['bulk'])], [2, 1, 1, 1, 1, 1.4])
    for r in report['bulk']:
        if any(r[k] for k in ('rcvFrom', 'rcvB', 'rcvA', 'rcvTicket')) or r['tr'] or r['remarks']:
            flow.append(Paragraph(escape(r['name'] + ' · transaction detail'), head))
            table(['Direction / party', 'Quantity', 'Meter before', 'Meter after', 'Ticket'],
                  [['Received: '+r['rcvFrom'], r['rcvQty'], r['rcvB'], r['rcvA'], r['rcvTicket']]] +
                  [['To: '+t['to'], t['qty'], t['mb'], t['ma'], t['tk']] for t in r['tr']], [2, 1, 1, 1, 1])
            if r['remarks']:
                flow.append(paragraph('Remarks: ' + r['remarks']))
    section('6 · Core crew · Tour of duty')
    catalogs = json.loads((ASSETS/'catalogs.json').read_text(encoding='utf-8'))
    countries = {v:k for k,v in catalogs['countryCodes'].items()}
    table(['#', 'Name', 'Rank', 'Nationality', 'Age', 'IC / Passport', 'Sign-on', 'Days', 'Comments'],
          [[str(i+1), r['name'], r['rank'], countries.get(r['nat'], r['nat']), r['age'], r['ic'], r['signon'],
            str(tour_days(r['signon'], m['date']) or ''), r['comments']] for i,r in enumerate(report['crew']) if r['name'].strip()],
          [.4, 1.6, 1.2, 1.1, .5, 1.3, 1.2, .5, 1.8])
    section('7 · Contractors')
    table(['#', 'Name', 'Vendor', 'Nationality', 'Age', 'IC / Passport'],
          [[str(i+1), r['name'], r['vendor'], countries.get(r['nat'], r['nat']), r['age'], r['ic']]
           for i,r in enumerate(report['ctr']) if r['name'].strip()], [.4, 2, 1.5, 1.3, .6, 1.6])
    def chrome(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#1E3A5F'))
        canvas.rect(0, A4[1]-66, A4[0], 66, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('VdrTitle', 14)
        canvas.drawString(32, A4[1]-26, 'GDS VTS · Vessel Daily Report')
        canvas.setFont('VdrBody', 8)
        canvas.drawString(32, A4[1]-44, ' · '.join(v for v in (identity.get('client'), identity.get('vessel')) if v) or 'GDS VTS')
        canvas.drawRightString(A4[0]-32, A4[1]-44, m['date'])
        canvas.setFillColor(colors.HexColor('#65758A'))
        canvas.setFont('VdrData', 6)
        canvas.drawString(32, 20, 'FINALIZED · '+report['finalizedAt'])
        canvas.drawRightString(A4[0]-32, 20, f'Page {doc.page}')
        canvas.restoreState()
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=32, rightMargin=32, topMargin=80, bottomMargin=36)
    try:
        doc.build(flow, onFirstPage=chrome, onLaterPages=chrome)
    except Exception as error:
        if type(error).__name__ != 'LayoutError':
            raise
        raise ValueError('A table cell is too long to fit on one PDF page. Shorten the longest activity, '
                         'remark or comment text, then finalize and download again.') from error
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(output.getvalue())))
    payload = base64.b64encode(zlib.compress(json.dumps(report, ensure_ascii=False).encode('utf-8')))
    packet = DecodedStreamObject()
    packet.set_data(b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:jspdf="https://gds-tracking.com/ns/vdr"><jspdf:metadata>'+payload+b'</jspdf:metadata></rdf:Description></rdf:RDF></x:xmpmeta>')
    packet.update({NameObject('/Type'):NameObject('/Metadata'), NameObject('/Subtype'):NameObject('/XML')})
    writer.root_object[NameObject('/Metadata')] = writer._add_object(packet)
    writer.add_metadata({'/Title':'GDS VTS · Vessel Daily Report · '+m['date'], '/Producer':'GDS VTS'})
    # Atomic write: a failed export never leaves a half-written PDF at the destination.
    import os, tempfile
    target = Path(path)
    fd, temp = tempfile.mkstemp(prefix='.vdr-pdf-', suffix='.pdf', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            writer.write(stream); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, str(target))
    except PermissionError as error:
        raise ValueError(f'Cannot save the PDF to {target}. Close it if it is open in a PDF viewer, or choose another folder.') from error
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
