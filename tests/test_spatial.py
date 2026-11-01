import json
import zipfile
import pytest
from app.nav.spatial.exceptions import SpatialPackageError
from app.nav.spatial.models import SpatialCategory
from app.nav.spatial.package_loader import read_package
from app.nav.spatial.repository import SpatialRepository
from app.nav.spatial.state_service import SpatialStateService
from app.nav.spatial.validator import normalize_collection,validate_manifest
from app.nav.spatial.interaction import choose_feature, feature_bounds, feature_identity, feature_info, SpatialSelection

MANIFEST={"schema_version":1,"package_id":"TEST-JAMPUK","name":"TEST Spatial Package","revision":"2026.11.01","created_at":"2026-11-01T08:00:00Z","coordinate_reference_system":"EPSG:4326"}
def collection(geometry={"type":"Polygon","coordinates":[[[91.7,22.1],[91.8,22.1],[91.8,22.2],[91.7,22.1]]]}): return {"type":"FeatureCollection","features":[{"type":"Feature","id":"one","properties":{"name":"TEST"},"geometry":geometry}]}
def package(path,manifest=MANIFEST,files=None):
 files=files or {"site_boundaries.geojson":collection()}
 with zipfile.ZipFile(path,"w") as z:
  z.writestr("manifest.json",json.dumps(manifest))
  for name,value in files.items():z.writestr(name,json.dumps(value))
def test_manifest_rules():
 assert validate_manifest(MANIFEST)["package_id"]=="TEST-JAMPUK"
 with pytest.raises(SpatialPackageError):validate_manifest({})
 with pytest.raises(SpatialPackageError):validate_manifest(dict(MANIFEST,schema_version=2))
 with pytest.raises(SpatialPackageError):validate_manifest(dict(MANIFEST,coordinate_reference_system="EPSG:3857"))
def test_geojson_rules():
 assert normalize_collection(collection(),SpatialCategory.SITE_BOUNDARY,"P")["features"][0]["properties"]["category"]=="site-boundary"
 with pytest.raises(SpatialPackageError):normalize_collection({"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"LineString","coordinates":[[0,0],[1,1]]}}]},SpatialCategory.SITE_BOUNDARY,"P")
 with pytest.raises(SpatialPackageError):normalize_collection(collection({"type":"Point","coordinates":[200,0]}),SpatialCategory.ANCHOR_PATTERN,"P")
def test_package_security_and_state(tmp_path):
 bad=tmp_path/"bad.gdsspatial"
 with zipfile.ZipFile(bad,"w") as z:z.writestr("../evil", "x")
 with pytest.raises(SpatialPackageError):read_package(bad)
 good=tmp_path/"good.gdsspatial";package(good)
 service=SpatialStateService(SpatialRepository(tmp_path/"store"));state=service.import_package(good)
 assert state.feature_counts["total"]==1 and set(state.bridge_payload())=={"siteBoundary","pipelines","anchorPatterns","surveyAreas","operationalZones","metadata","featureCounts"}
 restored=SpatialStateService(SpatialRepository(tmp_path/"store"));assert restored.state.metadata["revision"]=="2026.11.01"
def test_failed_import_does_not_replace_active(tmp_path):
 good=tmp_path/"good.gdsspatial";package(good);service=SpatialStateService(SpatialRepository(tmp_path/"store"));service.import_package(good)
 broken=tmp_path/"broken.gdsspatial";package(broken,dict(MANIFEST,revision="bad",coordinate_reference_system="BAD"))
 with pytest.raises(SpatialPackageError):service.import_package(broken)
 assert service.state.metadata["revision"]=="2026.11.01"

def test_package_change_clears_selection(tmp_path):
 first=tmp_path/"first.gdsspatial"; package(first); service=SpatialStateService(SpatialRepository(tmp_path/"store")); service.import_package(first)
 service.selection.select(service.state.collections,"site-boundary","TEST-JAMPUK-site-boundary-1")
 second=tmp_path/"second.gdsspatial"; package(second,dict(MANIFEST,revision="2026.11.02")); service.import_package(second)
 assert service.selection.feature is None

def feature(category, feature_id, geometry={"type":"Point","coordinates":[-71,42]}, **props):
 return {"type":"Feature","properties":{"category":category,"feature_id":feature_id,"name":"Name",**props},"geometry":geometry}

def test_selection_priority_and_identity_are_deterministic():
 assert feature_identity(feature("pipeline","PIPE-001"))=={"category":"pipeline","feature_id":"PIPE-001"}
 assert choose_feature([feature("site-boundary","S"),feature("pipeline","P"),feature("operational-zone","O")])["properties"]["category"]=="operational-zone"
 assert choose_feature([feature("pipeline","P"),feature("anchor-pattern","A"),feature("survey-area","V")])["properties"]["category"]=="anchor-pattern"

def test_safe_feature_info_and_selection_clear():
 selected=feature("pipeline","PIPE-001",status="ACTIVE",source_properties={"unsafe":"never displayed"})
 assert feature_info(selected)=={"name":"Name","category":"pipeline","feature_id":"PIPE-001","status":"ACTIVE"}
 state=SpatialSelection(); assert state.select({"pipeline":{"features":[selected]}},"pipeline","PIPE-001")["feature_id"]=="PIPE-001"
 assert state.clear()=={} and state.feature is None

@pytest.mark.parametrize(("geometry","expected"),[
 ({"type":"Point","coordinates":[-72,41]},(-72,41,-72,41)),
 ({"type":"MultiPoint","coordinates":[[-72,41],[-70,43]]},(-72,41,-70,43)),
 ({"type":"LineString","coordinates":[[-72,41],[-70,43]]},(-72,41,-70,43)),
 ({"type":"MultiLineString","coordinates":[[[-72,41],[-70,43]],[[-71,40],[-69,42]]]},(-72,40,-69,43)),
 ({"type":"Polygon","coordinates":[[[-72,41],[-70,41],[-70,43],[-72,41]]]},(-72,41,-70,43)),
 ({"type":"MultiPolygon","coordinates":[[[[-72,41],[-70,41],[-70,43],[-72,41]]],[[[-69,40],[-68,40],[-68,42],[-69,40]]]]},(-72,40,-68,43)),
])
def test_feature_bounds(geometry,expected):
 assert feature_bounds(feature("pipeline","X",geometry))==expected
