from openpyxl import load_workbook
wb=load_workbook(r'C:\Users\rayha\GDS-VTS\app\resources\templates\vjr_template.xlsx')
for n,d in wb.defined_names.items(): print(n, d.attr_text)
ws=wb['Departure Report Guide'] if 'Departure Report Guide' in wb.sheetnames else None
