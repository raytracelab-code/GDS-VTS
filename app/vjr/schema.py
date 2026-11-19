"""Verified fields from Untitled spreadsheet.xlsx (not a generated workbook)."""
SHEETS = ('GDS Meta', 'Departure Report Guide', '1. Core Crew', '2. Contractor',
          '3. Waypoint Plan', '4. Departure Report', '5. Arrival Report', '6. Voyage Progress')
CAPACITIES = dict(crew=200, contractors=200, waypoints=30, progress=100)
# key, human label, Excel column/cell, type. Blank values remain blank.
META = [('report_id','Report ID','D7','text'), ('report_name','Report Name','D8','text'),
        ('client_id','Client ID','D9','text'), ('generated','Generated Timestamp','D10','automatic'),
        ('vessel','Vessel Name','D11','text'), ('imo','Vessel IMO','D12','text'),
        ('capacity','Total Deck Space (m²)','D13','number'), ('client','Client Name','D14','text'),
        ('reader_version','Reader Version','D26','text'), ('reader_revision','Reader Revision','D27','text')]
CREW = [('name','Name','C','text'), ('rank','Rank','D','text'), ('age','Age','E','age'),
        ('nationality','Country of Nationality','F','text'), ('passport','IC / Passport No.','G','text'),
        ('sign_on','Date Sign-on','H','date'), ('working_days','Working Days','I','derived'),
        ('remarks','Remarks','J','text')]
CONTRACTORS = [('name','Name','C','text'), ('vendor','Vendor','D','text'), ('age','Age','E','age'),
        ('nationality','Country of Nationality','F','text'), ('passport','IC / Passport No.','G','text'),
        ('remarks','Remarks','H','text')]
WAYPOINTS = [('lat_degree','Latitude Degree','C','lat_degree'), ('lat_minute','Latitude Minute','E','minute'),
        ('lat_second','Latitude Second','G','second'), ('lat_direction','N/S','I','ns'),
        ('lon_degree','Longitude Degree','J','lon_degree'), ('lon_minute','Longitude Minute','L','minute'),
        ('lon_second','Longitude Second','N','second'), ('lon_direction','E/W','P','ew'),
        ('course','Course (°)','Q','course'), ('speed','Planned Speed (knots)','R','number'),
        ('remarks','Remarks','S','text')]
PROGRESS = [('date','Date','B','date'), ('hour','Hour','C','hour'), ('minute','Minute','D','minute')]+[
    (key,label,col,kind) for (key,label,_,kind),col in zip(WAYPOINTS[:8],('E','G','I','K','L','N','P','R'))]+[
        ('course','Course (°)','S','course'), ('speed','Actual Speed (knots)','T','number'),
        ('sky','Sky','U','text'), ('visibility','Visibility (nm)','V','number'),
        ('wind_speed','Wind Speed (knots)','W','number'), ('wind_direction','Wind Direction','X','compass'),
        ('wave_height','Wave / Swell Height (m)','Y','number'),
        ('wave_direction','Wave / Swell Direction','Z','compass'), ('remarks','Remarks','AA','text')]
GENERAL = [('captain','Captain Name','D9','text'), ('report_date','Report Date','D10','date'),
        ('prepared_by','Report Prepared By','D11','text'), ('prepared_tel','Prepared By Tel No.','I11','text'),
        ('checked_by','Checked By','D12','text'), ('checked_tel','Checked By Tel No.','I12','text'),
        ('draft_forward','Draft Forward','E13','number'), ('draft_midship','Draft Midship','G13','number'),
        ('draft_aft','Draft AFT','I13','number'), ('fuel_requirement','Requirements: Fuel Oil','E14','number'),
        ('fw_requirement','Requirements: FW (fresh water)','G14','number'), ('dw_requirement','Requirements: DW (drill water)','I14','number')]
DEPARTURE = [('departure_date','Departure Date','D18','date'), ('departure_time','Departure Time (24-hour)','D19/F19','time'),
        ('departure_location','Departure Location','D20','text'), ('departure_remarks','Departure Remarks','D21','text')]
ARRIVAL = [('arrival_date','Arrival Date','D24','date'), ('arrival_time','Arrival Time (24-hour)','D25/F25','time'),
        ('destination','Arrival Destination','D26','text'), ('arrival_remarks','Arrival Remarks','D27','text')]
DECK = [('location','Destination Location','C','text'), ('lifts','Lifts Expected','D','count'),
        ('ops','OPS (m²)','E','number'), ('fso','FSO (m²)','F','number'),
        ('drilling','Drilling / Projects (m²)','G','number'), ('total','Total (m²)','H','derived'),
        ('utilization','Utilization (%)','I','derived'), ('weight','Cargo Weight (Tonnes)','J','number'),
        ('remarks','Remarks','K','text')]
INVENTORY_NAMES = ('FUEL','FRESH WATER','LUB. OIL','GEAR OIL','DISPERSANT','DRILL WATER',
    'CEMENT (Slag)','CEMENT','BARITE','SARAPAR','BENTONITE','New OBM','Used OBM',
    'VERSAPRO 9.3PPG','OBM 7,5 PPG','OBM 7,8 PPG','SBM')
INVENTORY = [('product','Product','B','fixed'), ('quantity','Quantity','D','number'),
             ('unit','Unit','H','fixed'), ('remarks','Remarks','I','text')]
TABLES = dict(crew=CREW, contractors=CONTRACTORS, waypoints=WAYPOINTS, progress=PROGRESS)
COMPASS = ('N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW')
