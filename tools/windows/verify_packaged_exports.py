"""Independently reopen native packaged-app exports; never writes the template."""
import json
from hashlib import sha256
from pathlib import Path
import sys
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import load_workbook
from pypdf import PdfReader
from app.vdr.excel import SHEETS,TEMPLATE_HASH,template_path
from app.vdr.model import validate
from app.vdr.pdf import import_pdf

root=Path(__file__).resolve().parents[2]
folder=root/'docs/evidence/windows-compatibility'
xlsx,pdf=folder/'packaged-vdr.xlsx',folder/'packaged-vdr.pdf'
report=import_pdf(pdf)
assert report['finalized'] and not validate(report)
assert report['meta']['captain']=='COMPATIBILITY TEST CAPTAIN'
source=template_path();bundled=root/'dist/GDS VTS/app/resources/templates'/source.name
assert sha256(source.read_bytes()).hexdigest()==TEMPLATE_HASH
assert sha256(bundled.read_bytes()).hexdigest()==TEMPLATE_HASH
book=load_workbook(xlsx,data_only=False)
assert tuple(book.sheetnames)==SHEETS
assert book['VDR']['J12'].value==report['meta']['captain']
assert all('#REF!' not in str(cell.value) for sheet in book for row in sheet for cell in row)
# Configure is authoritative; it was empty in this isolated acceptance session.
assert book['VDR']['C12'].value is None
book.close()
with ZipFile(source) as original,ZipFile(xlsx) as exported:
    assert original.namelist()==exported.namelist()
    assert original.read('xl/worksheets/sheet2.xml')==exported.read('xl/worksheets/sheet2.xml')
    unchanged=[name for name in original.namelist() if not name.startswith('xl/worksheets/sheet')]
    assert all(original.read(name)==exported.read(name) for name in unchanged)
result={'xlsx_reopened':True,'sheets':list(SHEETS),'captain_cell':'VDR!J12',
        'vdr_guide_byte_identical':True,'nonworksheet_parts_byte_identical':len(unchanged),
        'stale_configured_vessel_cleared':True,'ref_errors':0,
        'source_and_packaged_template_sha256':TEMPLATE_HASH,'pdf_reimported':True,
        'pdf_finalized':True,'pdf_validation_errors':0,'pdf_pages':len(PdfReader(pdf).pages),
        'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()} for p in (xlsx,pdf)}}
(folder/'packaged-exports.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
