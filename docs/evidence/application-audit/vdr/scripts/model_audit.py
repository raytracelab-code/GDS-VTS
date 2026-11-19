import sys, json, tempfile, os
from pathlib import Path
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS')
sys.path.insert(0, r'C:\Users\rayha\GDS-VTS\tests')
from copy import deepcopy
from test_vdr import fixture_report
from app.vdr.model import *
from app.vdr.store import ReportStore

def show(t, v): print(f'[{t}]', v)

# --- activity log edge cases
def acts(*rows):
    r = fixture_report(); r['acts'] = []
    for to, loc in rows:
        a = blank_row('acts'); a.update(to=to, act='x', cat='Standby steaming offshore', loc=loc, dp='N'); r['acts'].append(a)
    return r
r = acts(('0600','A'), ('0600','A'), ('2400','A'))
show('zero-duration row', [(e['msg']) for e in validate(r)])
r = acts(('0600','A'), ('0500','B'), ('2400','A'))
show('backwards time', [(e['msg']) for e in validate(r)], )
show('backwards loc durations', derive_location_durations(r['acts']))
r = acts(('1200','A'), ('', 'B'), ('2400','A'))
show('missing TO mid-row', [(e['msg']) for e in validate(r)])
show('missing TO intervals', calculate(r)['actD'])
r = acts(('0000','A'), ('2400','A'))
show('first row 0000', [(e['msg']) for e in validate(r)])
r = acts(('2400','A'),)
show('full day ok', validate(r), )
for t in ('24:00','2359','930','0960','12','1200 ','１２００'):
    show(f'minutes({t!r})', minutes(t))
# location A -> B -> A
r = acts(('0600','A'), ('1200','B'), ('2400','A'))
show('loc dur A-B-A', derive_location_durations(r['acts']))
show('summary A-B-A', activity_summary(r)['locations'])
r = acts(('0600','LABUAN'), ('1200','labuan '), ('2400','Labuan'))
show('case variants', derive_location_durations(r['acts']), )
show('case summary', activity_summary(r)['locations'])

# --- running hours
r = fixture_report(); r['eq'][0].update(fm0='500', fm24='100')
show('negative cons', (calculate(r)['eqCons'], calculate(r)['totalCons'], [e['msg'] for e in validate(r)]))
r = fixture_report(); r['eq'][0].update(daily='30')
show('daily 30h', [e['msg'] for e in validate(r)])
r = fixture_report(); r['eq'][0].update(daily='12', total='5')
show('total<daily', [e['msg'] for e in validate(r)])
r = fixture_report(); r['eq'][0].update(fm0='100', fm24='')
show('fm24 missing', (calculate(r)['eqCons'], [e['msg'] for e in validate(r)]))

# --- bulk
r = fixture_report(); r['bulk'][1].update(open='100', cons='500')
show('neg closing FW', (calculate(r)['bulkClose'][1], [e['msg'] for e in validate(r)]))
r = fixture_report(); r['bulk'][1].update(open='', rcvQty='500', cons='10')
show('no opening but received', (calculate(r)['bulkClose'][1], validate(r)))
r = fixture_report(); r['bulk'][1].update(open='12345678901234567', rcvQty='0.1')
c = calculate(r)['bulkClose'][1]; show('huge open closing', (c, fmt(c)))
nxt = rollover(r, '2026-11-19'); show('huge rollover opening str', nxt['bulk'][1]['open'])
r = fixture_report(); r['bulk'][1].update(open='1e3', rcvQty='inf', cons='nan')
show('1e3/inf/nan', (calculate(r)['bulkClose'][1], [e['msg'] for e in validate(r)]))
r = fixture_report(); r['bulk'][1].update(open='1,000.5')
show('comma thousands', calculate(r)['bulkClose'][1])
r = fixture_report(); r['bulk'][1].update(open='1.000,5')
show('EU decimal 1.000,5', (calculate(r)['bulkClose'][1], [e['msg'] for e in validate(r)]))
r = fixture_report(); r['bulk'][0].update(rcvQty='1000', rcvB='100', rcvA='300')
show('rcv meter mismatch (1000 vs 200)', [e['msg'] for e in validate(r)])
r = fixture_report(); r['bulk'][0]['tr'] = [dict(to='X', qty='100', mb='500', ma='100', tk='')]
show('transfer meter reversed', [e['msg'] for e in validate(r)])
r = fixture_report(); r['bulk'][1]['tr'] = [dict(to='', qty='50', mb='', ma='', tk='')]
show('transfer qty w/o recipient', [e['msg'] for e in validate(r)])
r = fixture_report(); r['eq'] = [blank_row('eq', 'PORT ME')]; r['bulk'][0].update(open='5000', rcvQty='')
show('no flowmeter -> fuel cons', (calculate(r)['totalCons'], calculate(r)['bulkClose'][0]))
r = fixture_report(); r['bulk'][0]['name'] = 'fuel (ltrs)'
show('lowercase fuel is_fuel', calculate(r)['bulkClose'][0])

# --- non-validated numeric fields that Excel requires numeric
r = fixture_report(); r['acts'][0].update(lifts='abc', pob='five'); r['crew'][0]['age']='forty'; r['end'].update(fuel='12 days'); r['wx'][0]['vis']='good'
show('free text in numeric fields -> validate', [e['msg'] for e in validate(r)])

# --- HSE perfect days
r = fixture_report(); show('perfect days no incidents (hire 2026-01-01, date 2026-11-18)', hse_perfect_days(r))
r['hse']['lti'] = '2026-11-18'; show('perfect days LTI today', hse_perfect_days(r))
r['hse']['lti'] = '2026-11-20'; show('perfect days LTI after report date', hse_perfect_days(r))
r['hse']['lti'] = '18/11/2026'; show('perfect days non-ISO LTI', hse_perfect_days(r))
r['hse']['lti'] = ''; r['identity']['hireDate']=''; show('perfect days no hire', hse_perfect_days(r))
r['hse']['inc24'] = 'Dropped object, near miss'; show('inc24 effect', hse_perfect_days(r))
show('report number', report_number(fixture_report()))

# --- crew
r = fixture_report(); r['crew'][1].update(name='Test Crew', rank='Master', signon='2026-11-01')
show('duplicate crew', [e['msg'] for e in validate(r)])
r = fixture_report(); r['crew'][1].update(name='X', rank='AB', signon='2026-11-19')
show('signon after report', [e['msg'] for e in validate(r)])
r = fixture_report(); r['crew'][1].update(name='', rank='AB', signon='2026-11-10', ic='999')
show('crew row w/o name but data', [e['msg'] for e in validate(r)])
r = fixture_report(); r['ctr'][1].update(name='', vendor='ACME', ic='P1')
show('contractor w/o name', [e['msg'] for e in validate(r)])

# --- rollover gaps / stale
with tempfile.TemporaryDirectory() as d:
    s = ReportStore(Path(d)/'r.json', today='2026-11-18')
    s.reports['2026-11-15'] = fixture_report('2026-11-15')
    s.select('2026-11-17')
    show('gap rollover (15 -> 17): crew carried?', (s.report['crew'][0]['name'], s.report['bulk'][0]['open'], s.report['identity']))
    s.reports['2026-11-16'] = fixture_report('2026-11-16')
    s.select('2026-11-16'); s.select('2026-11-17')
    show('17 after 16 created later still blank', s.report['crew'][0]['name'])
    # stale carry
    s2 = ReportStore(Path(d)/'r2.json', today='2026-11-18')
    s2.reports['2026-11-17'] = fixture_report('2026-11-17')
    s2.select('2026-11-18'); before = s2.report['bulk'][1]['open']
    s2.select('2026-11-17'); s2.mutate(lambda r: r['bulk'][1].update(cons='1000'))
    s2.select('2026-11-18')
    show('stale carry (open after previous edit)', (before, s2.report['bulk'][1]['open'], 'expected', calculate(s2.reports['2026-11-17'])['bulkClose'][1]))
    # finalize semantics
    s3 = ReportStore(Path(d)/'r3.json', today='2026-11-18'); s3.reports['2026-11-18'] = fixture_report()
    print('finalize errors', s3.finalize(), s3.report['finalized'])
    s3.mutate(lambda r: r['meta'].update(captain='Edited'))
    show('after edit finalized?', s3.report['finalized'])
    s3.undo(); show('after undo finalized?', s3.report['finalized'])
    # undo stack depth with keystrokes
    for ch in range(150): s3.mutate(lambda r, ch=ch: r['meta'].update(captain='C'*ch))
    show('undo stack len after 150 keystrokes', len(s3.undo_stack))
    # import overwrites finalized? import invalid finalized report
    bad = fixture_report(); bad['acts'][0]['to']='1200'; bad['finalized']=True; bad['finalizedAt']='x'
    s3.import_report(bad); show('imported invalid but finalized', (s3.report['finalized'], len(validate(s3.report))))
    # future-dated browse creating stubs
    s4 = ReportStore(Path(d)/'r4.json', today='2026-11-18')
    for i in range(1, 6): s4.select(f'2026-11-{18-i:02d}')
    show('reports created by browsing', sorted(s4.reports))
    # corrupt json
    p = Path(d)/'bad.json'; p.write_text('{"reports": {"2026-11-18": ', encoding='utf-8')
    s5 = ReportStore(p, today='2026-11-18'); show('corrupt load_error', s5.load_error)
    try: s5.save()
    except OSError as e: show('save after corrupt', e)
    # one bad report poisons all
    good = fixture_report('2026-11-17'); badday = fixture_report('2026-11-18'); badday['wx'] = badday['wx'][:3]
    p2 = Path(d)/'onebad.json'; p2.write_text(json.dumps(dict(reports={'2026-11-17': good, '2026-11-18': badday})), encoding='utf-8')
    s6 = ReportStore(p2, today='2026-11-18'); show('one bad report -> all lost?', (s6.load_error, list(s6.reports)))
    # leftover temp files
    show('dir listing', os.listdir(d))
