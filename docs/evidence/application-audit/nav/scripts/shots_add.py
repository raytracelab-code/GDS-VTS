EV=r'C:\Users\rayha\GDS-VTS\docs\evidence\application-audit\nav'
def shots():
    page.grab().save(EV+r'\nav_default_offscreen.png')
    page.toggle_layers(); app.processEvents(); page.grab().save(EV+r'\nav_layers_panel_offscreen.png'); page.toggle_layers()
    print('SHOTS saved',flush=True)
QTimer.singleShot(int(os.environ.get('PROBE_MS','12000'))-500, shots)
