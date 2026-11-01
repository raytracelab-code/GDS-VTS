"""Create a clearly synthetic Phase 2 package; it is never auto-activated."""
import json
import zipfile
from pathlib import Path

OUT=Path(__file__).resolve().parent/'sample_spatial'/'test_jampuk.gdsspatial'
manifest={"schema_version":1,"package_id":"TEST-JAMPUK-001","name":"TEST Jampuk Operational Spatial Package","revision":"2026.11.01","created_at":"2026-11-01T08:00:00Z","coordinate_reference_system":"EPSG:4326"}
def feature(identifier,name,geometry):return {"type":"Feature","id":identifier,"properties":{"name":name,"source":"SYNTHETIC TEST DATA"},"geometry":geometry}
def fc(*features):return {"type":"FeatureCollection","features":list(features)}
data={
'site_boundaries.geojson':fc(feature('SITE-001','TEST SITE BOUNDARY',{'type':'Polygon','coordinates':[[[91.70,22.10],[91.82,22.10],[91.82,22.22],[91.70,22.10]]]})),
'pipelines.geojson':fc(feature('PIPE-001','TEST PIPELINE A',{'type':'LineString','coordinates':[[91.71,22.12],[91.80,22.20]]}),feature('PIPE-002','TEST PIPELINE B',{'type':'LineString','coordinates':[[91.72,22.19],[91.81,22.13]]})),
'anchor_patterns.geojson':fc(feature('ANCHOR-001','TEST ANCHOR POSITION',{'type':'Point','coordinates':[91.75,22.16]}),feature('ANCHOR-002','TEST ANCHOR SPREAD',{'type':'LineString','coordinates':[[91.74,22.15],[91.77,22.17]]})),
'survey_areas.geojson':fc(feature('SURVEY-001','TEST SURVEY AREA',{'type':'Polygon','coordinates':[[[91.73,22.13],[91.76,22.13],[91.76,22.15],[91.73,22.13]]]})),
'operational_zones.geojson':fc(feature('ZONE-001','TEST OPERATIONAL ZONE',{'type':'Polygon','coordinates':[[[91.77,22.17],[91.80,22.17],[91.80,22.20],[91.77,22.17]]]})),}
OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as archive:
 archive.writestr('manifest.json',json.dumps(manifest))
 for name,value in data.items():archive.writestr(name,json.dumps(value))
print(OUT)
