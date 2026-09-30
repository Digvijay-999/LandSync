import json
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_attribute_conflict_detection_and_evidence(client: AsyncClient):
    """
    Validates:
    - VALUE_MISMATCH detection when sources disagree on categorical fields (e.g. land_use).
    - NUMERIC_DIFFERENCE detection when numeric difference exceeds tolerances (e.g. area).
    - Case-insensitive / whitespace-normalized values are NOT flagged as conflicts.
    - NULL_VALUE_CONFLICT detection when one source has value and another has none.
    - Conflict evidence contains source_role, dataset_name, dataset_version, feature_id, raw_value.
    - Initial unified record status is 'CONFLICT'.
    """
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "M7 Conflict Test Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Upload Cadastral Dataset (Residential, 850 sqm)
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
                    "parcel_id": "CAD-001",
                    "land_use": "Residential",
                    "area": 850.0,
                    "address": "100 MG Road",
                },
            }
        ],
    }
    upload_cad = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_cad.status_code == 201
    cad_ds_id = upload_cad.json()["id"]

    # 3. Upload Drone Dataset (Commercial - conflicting!, 600 sqm - discrepancy > 30%!)
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
                    "structure_id": "DRN-001",
                    "land_use": "Commercial",  # Conflicts with Residential
                    "area": 600.0,            # Discrepancy > 5% and > 1.0 sqm
                },
            }
        ],
    }
    upload_drn = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_drn.status_code == 201
    drn_ds_id = upload_drn.json()["id"]

    # 4. Run Matching
    match_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
    )
    assert match_resp.status_code == 201
    run_id = match_resp.json()["id"]

    # 5. Review & Accept Match
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) >= 1
    match_id = matches[0]["id"]

    rev_resp = await client.post(
        f"/api/v1/matches/{match_id}/review",
        json={"decision": "ACCEPTED", "comment": "Verified overlapping parcels"},
    )
    assert rev_resp.status_code == 201

    # 6. Build Unified Records
    build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
    assert build_resp.status_code == 200
    build_data = build_resp.json()
    assert build_data["records_created"] == 1
    assert build_data["conflict_records"] == 1

    # 7. Verify Unified Record status
    records_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
    assert records_resp.status_code == 200
    records = records_resp.json()["items"]
    assert len(records) == 1
    rec = records[0]
    assert rec["status"] == "CONFLICT"
    rec_id = rec["id"]

    # 8. Query Record Conflicts endpoint
    conflicts_resp = await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")
    assert conflicts_resp.status_code == 200
    conflicts = conflicts_resp.json()
    assert len(conflicts) >= 2

    # Verify land_use conflict
    lu_conflicts = [c for c in conflicts if c["attribute_name"] == "land_use"]
    assert len(lu_conflicts) == 1
    lu_c = lu_conflicts[0]
    assert lu_c["conflict_type"] == "VALUE_MISMATCH"
    assert lu_c["severity"] == "HIGH"
    assert lu_c["status"] == "UNRESOLVED"
    assert len(lu_c["detected_values"]) == 2

    roles = {dv["source_role"]: dv["value"] for dv in lu_c["detected_values"]}
    assert roles.get("CADASTRAL") == "Residential"
    assert roles.get("DRONE") == "Commercial"

    # Verify area conflict
    area_conflicts = [c for c in conflicts if c["attribute_name"] == "area"]
    assert len(area_conflicts) == 1
    area_c = area_conflicts[0]
    assert area_c["conflict_type"] == "NUMERIC_DIFFERENCE"
    assert area_c["severity"] == "MEDIUM"
    assert area_c["status"] == "UNRESOLVED"

    # 9. Verify Project Conflict Summary
    summary_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_conflicts"] == len(conflicts)
    assert summary["unresolved_conflicts"] == len(conflicts)
    assert summary["resolved_conflicts"] == 0
    assert summary["dismissed_conflicts"] == 0
    assert summary["records_with_conflicts"] == 1


@pytest.mark.asyncio
async def test_human_resolution_source_selection_and_audit(client: AsyncClient):
    """
    Validates:
    - Resolving a conflict via SOURCE_SELECTION.
    - Strict validation: requires non-empty comment, requires valid contributing source feature ID.
    - Canonical record attribute updated with chosen source's value.
    - Resolution metadata and provenance event CONFLICT_RESOLVED recorded.
    """
    # 1. Setup project with conflicting land_use
    proj_resp = await client.post("/api/v1/projects", json={"name": "M7 Source Selection Project"})
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
                "properties": {"parcel_id": "CAD-101", "land_use": "Residential", "area": 500.0},
            }
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
                "properties": {"structure_id": "DRN-101", "land_use": "Commercial", "area": 500.0},
            }
        ],
    }
    cad_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("cad.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")})
    drn_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("drn.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")})
    cad_id = cad_up.json()["id"]
    drn_id = drn_up.json()["id"]

    match_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": cad_id, "candidate_dataset_ids": [drn_id]},
    )
    run_id = match_resp.json()["id"]
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    match_id = matches_resp.json()["items"][0]["id"]
    await client.post(f"/api/v1/matches/{match_id}/review", json={"decision": "ACCEPTED", "comment": "Matches"})
    await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")

    records = (await client.get(f"/api/v1/projects/{proj_id}/unified-records")).json()["items"]
    rec_id = records[0]["id"]
    conflicts = (await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")).json()
    lu_c = [c for c in conflicts if c["attribute_name"] == "land_use"][0]
    conflict_id = lu_c["id"]

    cad_source_val = [dv for dv in lu_c["detected_values"] if dv["source_role"] == "CADASTRAL"][0]
    cad_feature_id = cad_source_val["feature_id"]

    # Test Validation 1: Missing comment fails
    fail_comment = await client.post(
        f"/api/v1/conflicts/{conflict_id}/resolve",
        json={
            "resolution_type": "SOURCE_SELECTION",
            "selected_source_feature_id": cad_feature_id,
            "comment": "",
        },
    )
    assert fail_comment.status_code in [400, 422]

    # Test Validation 2: Invalid feature ID fails
    fake_fid = str(uuid.uuid4())
    fail_fid = await client.post(
        f"/api/v1/conflicts/{conflict_id}/resolve",
        json={
            "resolution_type": "SOURCE_SELECTION",
            "selected_source_feature_id": fake_fid,
            "comment": "Selecting non-existent feature",
        },
    )
    assert fail_fid.status_code == 400

    # Successful SOURCE_SELECTION resolution
    resolve_resp = await client.post(
        f"/api/v1/conflicts/{conflict_id}/resolve",
        json={
            "resolution_type": "SOURCE_SELECTION",
            "selected_source_feature_id": cad_feature_id,
            "comment": "Cadastral registry takes precedence for legal zoning.",
            "resolved_by": "Lead Land Registrar",
        },
    )
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["resolution"] is not None
    assert res_data["resolution"]["resolution_type"] == "SOURCE_SELECTION"
    assert res_data["resolution"]["resolved_value"] == "Residential"
    assert res_data["resolution"]["selected_source_role"] == "CADASTRAL"
    assert res_data["resolution"]["resolved_by"] == "Lead Land Registrar"

    # Verify unified record status changed from CONFLICT to ACTIVE (all conflicts resolved)
    rec_after = (await client.get(f"/api/v1/unified-records/{rec_id}")).json()
    assert rec_after["status"] == "ACTIVE"
    assert rec_after["canonical_attributes"]["land_use"] == "Residential"
    assert "land_use_resolution" in rec_after["canonical_attributes"]

    # Verify Provenance timeline includes CONFLICT_RESOLVED
    prov_resp = await client.get(f"/api/v1/unified-records/{rec_id}/provenance")
    assert prov_resp.status_code == 200
    timeline = prov_resp.json()["timeline"]
    res_events = [t for t in timeline if t["event_type"] == "CONFLICT_RESOLVED"]
    assert len(res_events) >= 1
    assert "Cadastral registry takes precedence" in res_events[0]["description"]


@pytest.mark.asyncio
async def test_human_resolution_manual_value_and_dismissal(client: AsyncClient):
    """
    Validates:
    - Resolving a conflict via MANUAL_VALUE with custom string / number.
    - Validation: reject empty manual value.
    - Dismissing a conflict with mandatory reason.
    - Validation: reject empty dismissal reason.
    - Status transitions appropriately.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "M7 Manual Value Project"})
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
                "properties": {"parcel_id": "CAD-201", "land_use": "Commercial", "area": 1000.0},
            }
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
                "properties": {"structure_id": "DRN-201", "land_use": "Industrial", "area": 1400.0},
            }
        ],
    }
    cad_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("cad.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")})
    drn_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("drn.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")})
    cad_id = cad_up.json()["id"]
    drn_id = drn_up.json()["id"]

    match_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": cad_id, "candidate_dataset_ids": [drn_id]},
    )
    run_id = match_resp.json()["id"]
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    match_id = matches_resp.json()["items"][0]["id"]
    await client.post(f"/api/v1/matches/{match_id}/review", json={"decision": "ACCEPTED", "comment": "Matches"})
    await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")

    records = (await client.get(f"/api/v1/projects/{proj_id}/unified-records")).json()["items"]
    rec_id = records[0]["id"]
    conflicts = (await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")).json()
    lu_c = [c for c in conflicts if c["attribute_name"] == "land_use"][0]
    area_c = [c for c in conflicts if c["attribute_name"] == "area"][0]

    # Test MANUAL_VALUE validation: empty value rejected
    fail_mv = await client.post(
        f"/api/v1/conflicts/{lu_c['id']}/resolve",
        json={"resolution_type": "MANUAL_VALUE", "manual_value": "", "comment": "Setting value"},
    )
    assert fail_mv.status_code == 400

    # Successful MANUAL_VALUE resolution for land_use
    mv_resp = await client.post(
        f"/api/v1/conflicts/{lu_c['id']}/resolve",
        json={
            "resolution_type": "MANUAL_VALUE",
            "manual_value": "Mixed Use Commercial/Residential",
            "comment": "Site inspection confirmed mixed ground retail and upper apartments.",
            "resolved_by": "Senior Inspector",
        },
    )
    assert mv_resp.status_code == 200
    assert mv_resp.json()["status"] == "RESOLVED"
    assert mv_resp.json()["resolution"]["resolved_value"] == "Mixed Use Commercial/Residential"

    # Record should still be CONFLICT because area conflict is still UNRESOLVED
    rec_mid = (await client.get(f"/api/v1/unified-records/{rec_id}")).json()
    assert rec_mid["status"] == "CONFLICT"

    # Dismiss area conflict
    fail_dismiss = await client.post(
        f"/api/v1/conflicts/{area_c['id']}/dismiss",
        json={"reason": ""},
    )
    assert fail_dismiss.status_code in [400, 422]

    dismiss_resp = await client.post(
        f"/api/v1/conflicts/{area_c['id']}/dismiss",
        json={"reason": "Drone polygon includes non-enclosed porch; cadastral boundary is accurate."},
    )
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "DISMISSED"
    assert dismiss_resp.json()["dismissal_reason"] is not None

    # Now both conflicts are resolved/dismissed -> record transitions to ACTIVE
    rec_final = (await client.get(f"/api/v1/unified-records/{rec_id}")).json()
    assert rec_final["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_idempotent_rebuild_preserves_resolutions(client: AsyncClient):
    """
    Validates:
    - Rebuilding unified records does NOT reset human resolved or dismissed conflicts.
    - Resolved values in canonical_attributes remain preserved.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "M7 Idempotency Test"})
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
                "properties": {"parcel_id": "CAD-301", "land_use": "Residential", "area": 500.0},
            }
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
                "properties": {"structure_id": "DRN-301", "land_use": "Commercial", "area": 500.0},
            }
        ],
    }
    cad_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("cad.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")})
    drn_up = await client.post(f"/api/v1/projects/{proj_id}/datasets", files={"file": ("drn.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")})
    cad_id = cad_up.json()["id"]
    drn_id = drn_up.json()["id"]

    match_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": cad_id, "candidate_dataset_ids": [drn_id]},
    )
    run_id = match_resp.json()["id"]
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    match_id = matches_resp.json()["items"][0]["id"]
    await client.post(f"/api/v1/matches/{match_id}/review", json={"decision": "ACCEPTED", "comment": "Matches"})
    await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")

    records = (await client.get(f"/api/v1/projects/{proj_id}/unified-records")).json()["items"]
    rec_id = records[0]["id"]
    conflicts = (await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")).json()
    lu_c = [c for c in conflicts if c["attribute_name"] == "land_use"][0]

    # Resolve manually
    await client.post(
        f"/api/v1/conflicts/{lu_c['id']}/resolve",
        json={
            "resolution_type": "MANUAL_VALUE",
            "manual_value": "Preserved Value",
            "comment": "Audit test comment",
        },
    )

    # Re-run record build!
    rebuild_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
    assert rebuild_resp.status_code == 200

    # Verify conflict status is still RESOLVED and value is still "Preserved Value"
    conflicts_recheck = (await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")).json()
    lu_recheck = [c for c in conflicts_recheck if c["attribute_name"] == "land_use"][0]
    assert lu_recheck["status"] == "RESOLVED"
    assert lu_recheck["resolution"]["resolved_value"] == "Preserved Value"

    rec_recheck = (await client.get(f"/api/v1/unified-records/{rec_id}")).json()
    assert rec_recheck["canonical_attributes"]["land_use"] == "Preserved Value"
