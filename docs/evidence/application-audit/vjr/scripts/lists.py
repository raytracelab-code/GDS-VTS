from openpyxl import load_workbook
wb=load_workbook(r'C:\Users\rayha\GDS-VTS\app\resources\templates\vjr_template.xlsx')
ws=wb['GDS Meta']
for col,a,b in (('Z',7,11),('S',12,29),('W',7,34),('M',7,9),('I',7,9),('G',7,9)):
    print(col,[ws[f'{col}{r}'].value for r in range(a,b+1)])
print('AC',[ws[f'AC{r}'].value for r in range(7,12)])
