from openpyxl import load_workbook
wb=load_workbook('app/resources/templates/vjr_template.xlsx')
for name in ('4. Departure Report','5. Arrival Report'):
    ws=wb[name]
    print('==',name)
    for ref in ('D2','N3','D6','D9','D10','J10','D11','E13','G13','I13','E14','D15','D18','D19','F19','J18','D20','D24','D25','F25','J24','D26','D27','H37','I37','D41','H41','C32','H32','I32'):
        print(ref,repr(ws[ref].value))
    print([ (str(v.sqref),v.type,v.formula1) for v in ws.data_validations.dataValidation][:12])
ws=wb['6. Voyage Progress']
print('== progress', ws.max_row)
for r in (6,7,8,9,107,108):
    print(r,[ws.cell(r,c).value for c in range(1,28)])
print([(str(v.sqref),v.type,v.formula1) for v in ws.data_validations.dataValidation])
ws=wb['3. Waypoint Plan']
for r in (6,7,8):
    print(r,[ws.cell(r,c).value for c in range(1,20)])
print([(str(v.sqref),v.type,v.operator,v.formula1,v.formula2) for v in ws.data_validations.dataValidation])
ws=wb['1. Core Crew']
for r in (7,8):
    print(r,[ws.cell(r,c).value for c in range(1,11)])
