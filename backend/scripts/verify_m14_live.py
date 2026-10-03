import requests
import json
import hashlib
import geopandas as gpd
import pandas as pd
import io

base_url = 'http://localhost:8000/api/v1/projects/92534d7c-3d0f-4cbe-96af-2449f320b470'

# 1. Test List Exports
r = requests.get(f'{base_url}/exports')
assert r.status_code == 200, f'List exports failed: {r.text}'
exports = r.json()['items']
print(f'Total exports found: {len(exports)}')
for exp in exports:
    print(f"  - Format: {exp['format']}, Records: {exp['record_count']}, Size: {exp['file_size_bytes']} bytes, Quarantined included: {exp['include_quarantined']}")

# 2. Test GeoJSON Download
geojson_job = [e for e in exports if e['format'] == 'geojson' and not e['include_quarantined']][0]
r = requests.get(f"{base_url}/exports/{geojson_job['id']}/download")
assert r.status_code == 200, 'GeoJSON download failed'
geojson_data = r.json()
sha256_actual = hashlib.sha256(r.content).hexdigest()
assert sha256_actual == geojson_job['sha256_checksum'], f"SHA256 mismatch! {sha256_actual} vs {geojson_job['sha256_checksum']}"
assert len(geojson_data['features']) == 24, f"Expected 24 features, got {len(geojson_data['features'])}"
sample_props = geojson_data['features'][0]['properties']
assert 'provenance_id' in sample_props, 'provenance_id missing in GeoJSON properties'
assert 'resolution_status' in sample_props, 'resolution_status missing in GeoJSON properties'
assert sample_props['resolution_status'] == 'UNIFIED', 'Expected UNIFIED resolution status'
print(f"GeoJSON verified! 24 features, SHA256 matched: {sha256_actual}")

# 3. Test GPKG Download and Layer Inspection
gpkg_job = [e for e in exports if e['format'] == 'gpkg'][0]
r = requests.get(f"{base_url}/exports/{gpkg_job['id']}/download")
assert r.status_code == 200, 'GPKG download failed'
sha256_gpkg = hashlib.sha256(r.content).hexdigest()
assert sha256_gpkg == gpkg_job['sha256_checksum'], 'GPKG SHA256 mismatch'
gdf = gpd.read_file(io.BytesIO(r.content), layer='unified_land_records')
assert len(gdf) == 24, f"Expected 24 rows in GPKG layer, got {len(gdf)}"
assert 'provenance_id' in gdf.columns, 'provenance_id missing in GPKG'
print(f"GPKG verified! 24 rows in layer unified_land_records, CRS={gdf.crs}, SHA256 matched: {sha256_gpkg}")

# 4. Test CSV Download and Centroids
csv_job = [e for e in exports if e['format'] == 'csv'][0]
r = requests.get(f"{base_url}/exports/{csv_job['id']}/download")
assert r.status_code == 200, 'CSV download failed'
sha256_csv = hashlib.sha256(r.content).hexdigest()
assert sha256_csv == csv_job['sha256_checksum'], 'CSV SHA256 mismatch'
df = pd.read_csv(io.StringIO(r.text))
assert len(df) == 24, f"Expected 24 rows in CSV, got {len(df)}"
assert 'centroid_latitude' in df.columns and 'centroid_longitude' in df.columns, 'Centroid cols missing'
assert df['centroid_latitude'].notnull().all(), 'Null centroid latitude detected'
assert df['centroid_longitude'].notnull().all(), 'Null centroid longitude detected'
print(f"CSV verified! 24 rows, centroids present and valid, SHA256 matched: {sha256_csv}")

# 5. Test Full Export with Quarantined
full_job = [e for e in exports if e['include_quarantined']][0]
r = requests.get(f"{base_url}/exports/{full_job['id']}/download")
assert r.status_code == 200, 'Full GeoJSON download failed'
full_geojson = r.json()
assert len(full_geojson['features']) == 30, f"Expected 30 features, got {len(full_geojson['features'])}"
rejected = [f for f in full_geojson['features'] if f['properties']['resolution_status'] == 'REJECTED']
assert len(rejected) == 6, f"Expected 6 rejected features, got {len(rejected)}"
print(f"Full Export verified! 30 features (24 UNIFIED + 6 REJECTED)")

# 6. Test Manifest endpoint
r = requests.get(f"{base_url}/exports/{geojson_job['id']}/manifest")
assert r.status_code == 200, 'Manifest endpoint failed'
manifest = r.json()
assert manifest['sha256_checksum'] == geojson_job['sha256_checksum']
assert manifest['stage12_execution_id'] is not None
assert manifest['stage13_execution_id'] is not None
print(f"Manifest verified! Linked Stage 12 ({manifest['stage12_execution_id']}) and Stage 13 ({manifest['stage13_execution_id']})")

print("ALL VERIFICATIONS PASSED SUCCESSFULLY!")
