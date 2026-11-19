"""Reproduce the requested VJR acceptance workbook and exhaustive cell map."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from vjr_fixture import full_report
from app.vjr.excel import VjrExcelExporter, TEMPLATE_HASH
from app.vjr.schema import (META, GENERAL, DEPARTURE, ARRIVAL, TABLES, DECK, CAPACITIES,
                            SHEETS, INVENTORY_NAMES)


def main():
    destination = ROOT/'docs/evidence/VJR_excel_export_acceptance.xlsx'
    destination.parent.mkdir(parents=True,exist_ok=True)
    VjrExcelExporter().export(full_report(),destination)
    lines = ['# VJR Excel cell map','',
        'Source: `Downloads/Untitled spreadsheet.xlsx`. Bundled unchanged as '+
        '`app/resources/templates/vjr_template.xlsx`.', '', 'SHA-256: `'+TEMPLATE_HASH+'`.', '',
        'Schema version 1. Dates are stored as ISO calendar dates in JSON and exported as Excel date numbers '+
        'with the original cell number formats. Times are 24-hour HH:MM, split into original hour/minute cells. '+
        'Numbers are finite, nonnegative values. Identifiers remain text.', '',
        '| Model field | UI section | Sheet | Cell/range | Type | Source / transformation |',
        '| --- | --- | --- | --- | --- | --- |']
    def entry(field,section,sheet,cell,kind,source):
        lines.append('| %s | %s | %s | %s | %s | %s |' % (field,section,sheet,cell,kind,source))
    for key,label,cell,kind in META:
        source = 'Manual; blank remains blank'
        if key in ('vessel','client'):
            source = 'QSettings GDS/VTS vessel/name or vessel/client if present; otherwise manual'
        if key=='generated':
            source = 'UTC timestamp at export'
        entry('meta.'+key,'General / '+label,SHEETS[0],cell,kind,source)
    for group,sheet in (('crew',2),('contractors',3),('waypoints',4),('progress',7)):
        end = 7+CAPACITIES[group]
        if group!='progress':
            entry(group+'[].sequence',group,SHEETS[sheet],'B8:B'+str(end),'integer','Sequential row number; unused rows cleared')
        for key,label,col,kind in TABLES[group]:
            source = 'Manual; unused rows cleared'
            if key=='working_days':
                source='Derived: (arrival report date, else departure report date) − sign-on + 1; materialized'
            entry(group+'[].'+key,group+' / '+label,SHEETS[sheet],col+'8:'+col+str(end),kind,source)
    for group,sheet in (('departure',5),('arrival',6)):
        for key,label,cell,kind in GENERAL+DEPARTURE+ARRIVAL:
            reuse = group=='arrival' and (key in [f[0] for f in GENERAL if f[0]!='report_date']+
                                          [f[0] for f in DEPARTURE]+['destination'])
            entry(group+'.'+key,group+' / '+label,SHEETS[sheet],cell,kind,
                  'Linked from Departure; read-only; materialized' if reuse else 'Manual')
        for key,cell in (('vessel','D6'),('imo','D7'),('capacity','D8')):
            entry('meta.'+key,group+' / Vessel information',SHEETS[sheet],cell,'text / number','Linked from General; materialized')
        entry('crew / contractors count',group,SHEETS[sheet],'D15/E15, F15/G15','integer / text','Derived from current lists; materialized')
        entry(group+'.deck[].sequence',group+' Deck space',SHEETS[sheet],'B32:B36','integer','Five destination rows')
        for key,label,col,kind in DECK:
            source = 'Manual; independent '+group+' values'
            if key=='total':
                source='OPS + FSO + Drilling/Projects; materialized'
            elif key=='utilization':
                source='Total / capacity; stored as fraction with original percentage format; blank for zero/missing capacity'
            entry(group+'.deck[].'+key,group+' / '+label,SHEETS[sheet],col+'32:'+col+'36',kind,source)
        entry(group+'.deck totals',group,SHEETS[sheet],'D37, H37, I37, J37','number','Sum lifts, used space, utilization and cargo; materialized')
        for i,name in enumerate(INVENTORY_NAMES,41):
            entry(group+'.inventory[normalized product='+name+']',group+' Inventory',SHEETS[sheet],
                  'D%s / I%s' % (i,i),'number / text','Quantity / remarks; normalized-name lookup; product B and unit H untouched')
        entry('current client / reader version',group,SHEETS[sheet],'D2, N3','text','Materialized titles to eliminate stale formula caches')
        entry('report / departure / arrival date annotations',group,SHEETS[sheet],'J10, J18, J24','text',
              'Materialized relative to local export date; blanks stay blank')
    lines += ['', '## Capacities and preservation','',
        '- Crew 200 (8–207); contractors 200 (8–207); waypoints 30 (8–37); voyage progress 100 (8–107). '+
        'Verified against numbering and validation ranges. Formatting extends below several tables and is not capacity.',
        '- Five departure and five arrival deck rows (32–36), total row 37. Inventory rows 41–57.',
        '- Capacity overflow and invalid data block export without touching the destination. Invalid drafts can autosave.',
        '- Fresh pristine template archive on every export; only explicitly mapped cell values change. '+
        'Every other ZIP part and unmapped worksheet cell remains byte-identical, including styles, merged cells, '+
        'dimensions, validations, sheet states, print setup, drawings and the entire Departure Report Guide.',
        '- Critical calculations and arrival reuse are snapshot values, not live Excel formulas. '+
        'Unrelated template/reference/helper formulas are preserved. Subsequent Excel edits do not refresh materialized cells; '+
        'edit in GDS VTS and export again for a consistent report.',
        '- Back Deck Photo areas L9:U27 in Departure and Arrival are intentionally reserved and untouched '+
        'pending future photo-sharing requirements. No upload, camera, drop or image insertion feature exists.',
        '- Autosave uses an atomic JSON replacement at AppLocalDataLocation/vjr/report.json; '+
        'bounded 100-step snapshot undo/redo follows the VDR pattern and autosaves history actions. '+
        'Unreadable or unsupported stores are preserved, with an actionable error.',
        '- Existing VJR was a label only and had no stored schema to migrate. Partial version-1 data gets defaults '+
        'without truncating records; unsupported future schemas are rejected.',
        '- Decimal-to-DMS is a tested VJR helper. Telemetry integration is deferred; all journey data remains manually editable. '+
        'NAV coordinates and sensor parsing are unchanged.',
        '- VJR supports one persistent working journey. No journey archive or new-journey workflow was requested.',
        '- Configure name/client settings are reused when present; IMO and deck capacity remain VJR fields because '+
        'the current application exposes no authoritative settings for them.', '',
        'Reproduce workbook and map: `.venv/Scripts/python.exe tools/verify_vjr_acceptance.py`.', '']
    (ROOT/'docs/vjr-excel-cell-map.md').write_text('\n'.join(lines),encoding='utf-8')
    print(destination)


if __name__=='__main__':
    main()
