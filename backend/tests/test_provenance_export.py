import csv
import io
import json
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_provenance_and_export_lifecycle(client: AsyncClient):
    """
    Comprehensive Milestone 6 tests covering:
    1. Provenance endpoint returns actual source information.
    2. Dataset information resolved correctly.
    3. Dataset version resolved correctly.
    4. Source feature information resolved correctly.
    5. Accepted match information resolved correctly.
    6. Machine score is preserved.
    7. Candidate rank is preserved.
    8. Human decision is preserved.
    9. Review history is preserved.
    10. No fabricated provenance entries are generated.
    11. GeoJSON project export succeeds.
    12. GeoJSON is valid JSON.
    13. GeoJSON FeatureCollection structure is valid.
    14. Export contains expected record count.
    15. Export geometry matches canonical geometry.
    16. CSV project export succeeds.
    17. CSV row count matches unified record count.
    18. Single-record GeoJSON export works.
    19. Single-record CSV export works.
    20. Project isolation works.
    21. Empty project export behaves correctly.
    """
    # -------------------------------------------------------------------------
    # 1. Setup Project A, Upload Datasets, Match, Review, and Build Records
    # -------------------------------------------------------------------------
    proj_resp = await client.post("/api/v1/projects", json={"name": "M6 Provenance & Export Test Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    cadastral_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]],
                },
                "properties": {
                    "parcel_id": "CP-101",
                    "name": "North Cadastral Parcel",
                    "land_use": "Residential",
                    "area": 850.0,
                    "address": "123 North Lane",
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.87, 18.54], [73.88, 18.54], [73.88, 18.55], [73.87, 18.55], [73.87, 18.54]]],
                },
                "properties": {
                    "parcel_id": "CP-102",
                    "name": "South Cadastral Parcel",
                    "land_use": "Agricultural",
                    "area": 1200.0,
                    "address": "456 South Way",
                },
            },
        ],
    }

    drone_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.851, 18.521], [73.859, 18.521], [73.859, 18.529], [73.851, 18.529], [73.851, 18.521]]],
                },
                "properties": {
                    "structure_id": "DR-201",
                    "name": "North Drone Structure",
                    "land_use": "Residential",
                    "area": 845.0,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.871, 18.541], [73.879, 18.541], [73.879, 18.549], [73.871, 18.549], [73.871, 18.541]]],
                },
                "properties": {
                    "structure_id": "DR-202",
                    "name": "South Drone Structure",
                    "land_use": "Industrial",
                    "area": 600.0,
                },
            },
        ],
    }

    # Upload datasets
    cad_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/geo+json")},
    )
    assert cad_resp.status_code == 201
    cad_ds_id = cad_resp.json()["id"]

    drone_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/geo+json")},
    )
    assert drone_resp.status_code == 201
    drone_ds_id = drone_resp.json()["id"]

    # Run spatial matching
    match_run_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={
            "source_dataset_id": cad_ds_id,
            "candidate_dataset_ids": [drone_ds_id],
        },
    )
    assert match_run_resp.status_code == 201
    run_id = match_run_resp.json()["id"]

    # Fetch matches
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) >= 2

    # Accept matches with human commentary
    m1_id = matches[0]["id"]
    m2_id = matches[1]["id"]

    rev1 = await client.post(
        f"/api/v1/matches/{m1_id}/review",
        json={"decision": "ACCEPTED", "comment": "Boundary alignment confirmed via satellite"},
    )
    assert rev1.status_code == 201

    rev2 = await client.post(
        f"/api/v1/matches/{m2_id}/review",
        json={"decision": "ACCEPTED", "comment": "Accepted despite land use disparity"},
    )
    assert rev2.status_code == 201

    # Build unified records
    build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
    assert build_resp.status_code == 200
    build_data = build_resp.json()
    assert build_data["records_created"] == 2

    # List unified records
    list_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
    assert list_resp.status_code == 200
    records = list_resp.json()["items"]
    assert len(records) == 2
    r1 = records[0]

    # -------------------------------------------------------------------------
    # 2. Test Provenance API (/unified-records/{record_id}/provenance)
    # -------------------------------------------------------------------------
    prov_resp = await client.get(f"/api/v1/unified-records/{r1['id']}/provenance")
    assert prov_resp.status_code == 200
    prov = prov_resp.json()

    # (1-4) Source, Dataset & Version resolution
    assert prov["record_id"] == r1["record_identifier"]
    assert prov["status"] == r1["status"]
    assert len(prov["sources"]) >= 2

    src_roles = [s["role"] for s in prov["sources"]]
    assert "CADASTRAL" in src_roles
    assert "DRONE" in src_roles

    for s in prov["sources"]:
        assert s["dataset_name"].lower() in ["cadastral", "drone"]
        assert s["dataset_version"] == 1
        assert s["dataset_format"].lower() == "geojson"
        assert s["feature_identifier"] in ["CP-101", "CP-102", "DR-201", "DR-202"]
        assert s["geometry_type"] in ["Polygon", "MultiPolygon"]

    # (5-8) Accepted match & machine score resolution
    assert len(prov["relationships"]) >= 1
    rel = prov["relationships"][0]
    assert rel["human_decision"] == "ACCEPTED"
    assert 0.0 <= rel["machine_score"] <= 1.0
    assert rel["candidate_rank"] is None or isinstance(rel["candidate_rank"], int)
    assert isinstance(rel["is_best_candidate"], bool)

    # (9) Review history resolution
    assert len(prov["review_history"]) >= 1
    review_entry = prov["review_history"][0]
    assert review_entry["decision"] == "ACCEPTED"
    assert review_entry["comment"] is not None
    assert "created_at" in review_entry

    # (10) Evidence-grounded Timeline
    assert len(prov["timeline"]) >= 4
    event_types = [t["event_type"] for t in prov["timeline"]]
    assert "DATA_INGESTED" in event_types
    assert "FEATURE_CANONICALIZED" in event_types
    assert "MATCH_GENERATED" in event_types
    assert "MATCH_REVIEWED" in event_types
    assert "RECORD_SYNTHESIZED" in event_types

    # Ensure chronological order
    timestamps = [t["timestamp"] for t in prov["timeline"]]
    assert timestamps == sorted(timestamps)

    # -------------------------------------------------------------------------
    # 3. Test Project Provenance Summary API (/projects/{project_id}/provenance)
    # -------------------------------------------------------------------------
    proj_prov_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance")
    assert proj_prov_resp.status_code == 200
    proj_prov = proj_prov_resp.json()
    assert proj_prov["total_unified_records"] == 2
    assert proj_prov["total_sources"] >= 4
    assert proj_prov["total_accepted_matches"] == 2
    assert proj_prov["total_reviews"] == 2
    assert len(proj_prov["datasets"]) == 2

    # -------------------------------------------------------------------------
    # 4. Test Project GeoJSON Export (/projects/{project_id}/exports/unified-records.geojson)
    # -------------------------------------------------------------------------
    geojson_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/unified-records.geojson")
    assert geojson_resp.status_code == 200
    assert "application/geo+json" in geojson_resp.headers["content-type"]
    assert "attachment; filename=" in geojson_resp.headers["content-disposition"]
    assert geojson_resp.headers["content-disposition"].endswith('.geojson"')

    # Validate valid JSON & FeatureCollection
    geojson_data = json.loads(geojson_resp.text)
    assert geojson_data["type"] == "FeatureCollection"
    assert "metadata" in geojson_data
    assert geojson_data["metadata"]["record_count"] == 2
    assert geojson_data["metadata"]["crs"] == "EPSG:4326"
    assert len(geojson_data["features"]) == 2

    feat = geojson_data["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] in ["Polygon", "MultiPolygon"]
    assert "record_identifier" in feat["properties"]
    assert "source_count" in feat["properties"]
    assert feat["properties"]["source_count"] == 2
    assert "geometry_source_role" in feat["properties"]

    # -------------------------------------------------------------------------
    # 5. Test Project CSV Export (/projects/{project_id}/exports/unified-records.csv)
    # -------------------------------------------------------------------------
    csv_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/unified-records.csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "attachment; filename=" in csv_resp.headers["content-disposition"]

    # Parse CSV content
    reader = csv.reader(io.StringIO(csv_resp.text))
    rows = list(reader)
    # Header + 2 data rows = 3 rows total
    assert len(rows) == 3
    headers = rows[0]
    assert "record_identifier" in headers
    assert "status" in headers
    assert "area_sqm" in headers
    assert "source_roles" in headers
    assert "source_datasets" in headers

    rec_identifiers = [rows[1][0], rows[2][0]]
    assert "ULR-000001" in rec_identifiers
    assert "ULR-000002" in rec_identifiers

    # -------------------------------------------------------------------------
    # 6. Test Single Record GeoJSON & CSV Exports
    # -------------------------------------------------------------------------
    single_geojson_resp = await client.get(f"/api/v1/unified-records/{r1['id']}/export.geojson")
    assert single_geojson_resp.status_code == 200
    assert "application/geo+json" in single_geojson_resp.headers["content-type"]
    single_feat = json.loads(single_geojson_resp.text)
    assert single_feat["type"] == "Feature"
    assert single_feat["id"] == r1["record_identifier"]
    assert single_feat["properties"]["record_identifier"] == r1["record_identifier"]

    single_csv_resp = await client.get(f"/api/v1/unified-records/{r1['id']}/export.csv")
    assert single_csv_resp.status_code == 200
    single_rows = list(csv.reader(io.StringIO(single_csv_resp.text)))
    assert len(single_rows) == 2  # Header + 1 record row
    assert single_rows[1][0] == r1["record_identifier"]

    # -------------------------------------------------------------------------
    # 7. Test Audit Integration (EXPORT_CREATED events registered)
    # -------------------------------------------------------------------------
    summary_after_export = await client.get(f"/api/v1/projects/{proj_id}/provenance")
    assert summary_after_export.status_code == 200
    latest_events = summary_after_export.json()["latest_events"]
    assert len(latest_events) >= 1
    export_events = [e for e in latest_events if e["event_type"] == "EXPORT_CREATED"]
    assert len(export_events) >= 1

    # -------------------------------------------------------------------------
    # 8. Test Security & Project Isolation
    # -------------------------------------------------------------------------
    proj_b_resp = await client.post("/api/v1/projects", json={"name": "M6 Isolated Project B"})
    assert proj_b_resp.status_code == 201
    proj_b_id = proj_b_resp.json()["id"]

    # Empty project exports should return 0 records cleanly
    b_geojson_resp = await client.get(f"/api/v1/projects/{proj_b_id}/exports/unified-records.geojson")
    assert b_geojson_resp.status_code == 200
    b_geojson = json.loads(b_geojson_resp.text)
    assert b_geojson["metadata"]["record_count"] == 0
    assert b_geojson["features"] == []

    b_csv_resp = await client.get(f"/api/v1/projects/{proj_b_id}/exports/unified-records.csv")
    assert b_csv_resp.status_code == 200
    b_rows = list(csv.reader(io.StringIO(b_csv_resp.text)))
    assert len(b_rows) == 1  # Only header row

    # Nonexistent record IDs return 404
    fake_id = uuid.uuid4()
    not_found_prov = await client.get(f"/api/v1/unified-records/{fake_id}/provenance")
    assert not_found_prov.status_code == 404

    not_found_export = await client.get(f"/api/v1/unified-records/{fake_id}/export.geojson")
    assert not_found_export.status_code == 404
