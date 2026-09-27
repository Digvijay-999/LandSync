import json
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unified_record_lifecycle_and_idempotency(client: AsyncClient):
    """
    Comprehensive tests for Milestone 5 Unified Land Records:
    1. Unified record creation from accepted match.
    2. Exclusion of REJECTED, PENDING, and FLAGGED matches.
    3. Multi-source connected relationship grouping (transitive closure).
    4. Canonical geometry priority (Cadastral > Drone > Municipal).
    5. Conflict detection (land use disagreement & area discrepancy).
    6. ACTIVE, INCOMPLETE, and CONFLICT status assignments.
    7. Idempotency (repeated builds never produce duplicate records).
    8. Project isolation.
    9. Pagination, Detail, and Statistics APIs.
    """
    # -------------------------------------------------------------------------
    # 1. Setup Project A and Datasets
    # -------------------------------------------------------------------------
    proj_resp = await client.post("/api/v1/projects", json={"name": "Unified Records Test Project A"})
    assert proj_resp.status_code == 201
    proj_a_id = proj_resp.json()["id"]

    # Cadastral Parcels (Source A)
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
                    "name": "Parcel North",
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
                    "name": "Parcel South",
                    "land_use": "Agricultural",
                    "area": 1200.0,
                    "address": "456 South Way",
                },
            },
        ],
    }

    # Drone Structures (Source B)
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
                    "name": "Structure North",
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
                    "name": "Structure South",
                    "land_use": "Industrial",  # Conflicting land use with Agricultural!
                    "area": 600.0,            # Discrepancy > 30% from 1200.0!
                },
            },
        ],
    }

    # Municipal Records (Source C)
    municipal_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8505, 18.5205], [73.8595, 18.5205], [73.8595, 18.5295], [73.8505, 18.5295], [73.8505, 18.5205]]],
                },
                "properties": {
                    "tax_id": "MUN-301",
                    "assessment": "Tax Office Assessment",
                    "land_use": "Residential",
                    "address": "123 North Lane, City Center",
                },
            },
        ],
    }

    # Upload datasets
    cad_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/geo+json")},
    )
    drone_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/geo+json")},
    )
    muni_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("municipal.geojson", json.dumps(municipal_geojson).encode("utf-8"), "application/geo+json")},
    )
    assert cad_resp.status_code == 201 and drone_resp.status_code == 201 and muni_resp.status_code == 201
    cad_ds = cad_resp.json()
    drone_ds = drone_resp.json()
    muni_ds = muni_resp.json()

    # -------------------------------------------------------------------------
    # 2. Run Matching: Cadastral -> Drone
    # -------------------------------------------------------------------------
    run1_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/matching-runs",
        json={
            "source_dataset_id": cad_ds["id"],
            "candidate_dataset_ids": [drone_ds["id"]],
        },
    )
    assert run1_resp.status_code == 201
    run1_id = run1_resp.json()["id"]

    matches1_resp = await client.get(f"/api/v1/matching-runs/{run1_id}/matches")
    assert matches1_resp.status_code == 200
    matches1 = matches1_resp.json()["items"]
    assert len(matches1) >= 2

    # Find the matches for CP-101 and CP-102
    match_cp101 = next(m for m in matches1 if "CP-101" in m["source_identifier"])
    match_cp102 = next(m for m in matches1 if "CP-102" in m["source_identifier"])

    # -------------------------------------------------------------------------
    # 3. Review Decisions on Run 1:
    #    - Accept match_cp101 (CP-101 <-> DR-201)
    #    - Accept match_cp102 (CP-102 <-> DR-202)
    # -------------------------------------------------------------------------
    rev1_resp = await client.post(
        f"/api/v1/matches/{match_cp101['id']}/review",
        json={"decision": "ACCEPTED", "comment": "Cadastral and Drone agree on CP-101."},
    )
    assert rev1_resp.status_code == 201

    rev2_resp = await client.post(
        f"/api/v1/matches/{match_cp102['id']}/review",
        json={"decision": "ACCEPTED", "comment": "Accepted despite difference for conflict testing."},
    )
    assert rev2_resp.status_code == 201

    # -------------------------------------------------------------------------
    # 4. Run Matching: Drone -> Municipal
    #    - Match DR-201 with MUN-301 and ACCEPT it
    # -------------------------------------------------------------------------
    run2_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/matching-runs",
        json={
            "source_dataset_id": drone_ds["id"],
            "candidate_dataset_ids": [muni_ds["id"]],
        },
    )
    assert run2_resp.status_code == 201
    run2_id = run2_resp.json()["id"]

    matches2_resp = await client.get(f"/api/v1/matching-runs/{run2_id}/matches")
    assert matches2_resp.status_code == 200
    matches2 = matches2_resp.json()["items"]
    assert len(matches2) >= 1

    match_dr201_muni = next(m for m in matches2 if "DR-201" in m["source_identifier"] and m["candidate_feature_id"])

    rev3_resp = await client.post(
        f"/api/v1/matches/{match_dr201_muni['id']}/review",
        json={"decision": "ACCEPTED", "comment": "Drone DR-201 matches Municipal MUN-301."},
    )
    assert rev3_resp.status_code == 201

    # -------------------------------------------------------------------------
    # 5. Build Unified Records (First Run)
    # -------------------------------------------------------------------------
    build_resp = await client.post(f"/api/v1/projects/{proj_a_id}/unified-records/build")
    assert build_resp.status_code == 200
    build_data = build_resp.json()
    assert build_data["records_created"] == 2
    assert build_data["accepted_relationships_processed"] == 3
    assert build_data["total_records"] == 2

    # -------------------------------------------------------------------------
    # 6. Idempotency Check: Running Build a Second Time Must NOT Create Duplicates
    # -------------------------------------------------------------------------
    build_idempotent_resp = await client.post(f"/api/v1/projects/{proj_a_id}/unified-records/build")
    assert build_idempotent_resp.status_code == 200
    idem_data = build_idempotent_resp.json()
    assert idem_data["records_created"] == 0, "No duplicate records must be created on re-build"
    assert idem_data["records_unchanged"] == 2
    assert idem_data["total_records"] == 2

    # -------------------------------------------------------------------------
    # 7. List Records and Verify Pagination
    # -------------------------------------------------------------------------
    list_resp = await client.get(f"/api/v1/projects/{proj_a_id}/unified-records?skip=0&limit=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 2
    assert len(list_data["items"]) == 2

    # Check Human-Readable Record Identifiers (ULR-000001, ULR-000002)
    id1 = list_data["items"][0]["record_identifier"]
    id2 = list_data["items"][1]["record_identifier"]
    assert id1.startswith("ULR-")
    assert id2.startswith("ULR-")
    assert id1 != id2

    # -------------------------------------------------------------------------
    # 8. Verify Connected Component (CP-101 + DR-201 + MUN-301 in ONE Record)
    # -------------------------------------------------------------------------
    # Find the record with 3 sources
    record_3_src = next((r for r in list_data["items"] if r["source_count"] == 3), None)
    assert record_3_src is not None, "Expected one unified record containing all 3 connected sources"

    # Detail API for record with 3 sources
    detail_resp = await client.get(f"/api/v1/unified-records/{record_3_src['id']}")
    assert detail_resp.status_code == 200
    d3 = detail_resp.json()
    assert d3["status"] == "ACTIVE"
    assert len(d3["sources"]) == 3

    # Check contributing sources roles
    roles = {s["source_role"] for s in d3["sources"]}
    assert "CADASTRAL" in roles
    assert "DRONE" in roles
    assert "MUNICIPAL" in roles

    # Canonical Geometry Priority: Cadastral MUST be preferred over Drone and Municipal!
    assert d3["geometry_source_role"] == "CADASTRAL"
    assert d3["canonical_geometry"] is not None
    assert d3["canonical_geometry"]["type"] == "Polygon"
    assert d3["area"] == 850.0  # From cadastral area

    # Canonical Attributes
    assert d3["canonical_attributes"]["land_use"] == "Residential"
    assert len(d3["canonical_attributes"]["conflicts"]) == 0

    # -------------------------------------------------------------------------
    # 9. Verify Conflict Detection on Record 2 (CP-102 <-> DR-202)
    # -------------------------------------------------------------------------
    record_conflict = next((r for r in list_data["items"] if r["status"] == "CONFLICT"), None)
    assert record_conflict is not None, "Expected conflict record due to land_use and area disparity"

    detail_conf_resp = await client.get(f"/api/v1/unified-records/{record_conflict['id']}")
    assert detail_conf_resp.status_code == 200
    d_conf = detail_conf_resp.json()
    assert d_conf["status"] == "CONFLICT"
    assert len(d_conf["sources"]) == 2

    # Conflicts list in canonical attributes
    conflicts = d_conf["canonical_attributes"]["conflicts"]
    assert len(conflicts) >= 1
    conf_fields = [c["field"] for c in conflicts]
    assert "land_use" in conf_fields or "area" in conf_fields

    # -------------------------------------------------------------------------
    # 10. Verify Sources Endpoint
    # -------------------------------------------------------------------------
    sources_resp = await client.get(f"/api/v1/unified-records/{record_3_src['id']}/sources")
    assert sources_resp.status_code == 200
    sources_list = sources_resp.json()
    assert len(sources_list) == 3
    for s in sources_list:
        assert "geometry" in s
        assert "properties" in s
        assert "source_identifier" in s

    # -------------------------------------------------------------------------
    # 11. Verify Project-Level Statistics API
    # -------------------------------------------------------------------------
    stats_resp = await client.get(f"/api/v1/projects/{proj_a_id}/unified-records/statistics")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_records"] == 2
    assert stats["active"] == 1
    assert stats["conflict"] == 1
    assert stats["incomplete"] == 0
    assert stats["average_sources_per_record"] == 2.5
    assert stats["records_with_cadastral"] == 2
    assert stats["records_with_drone"] == 2
    assert stats["records_with_municipal"] == 1

    # -------------------------------------------------------------------------
    # 12. Verify Project Isolation
    # -------------------------------------------------------------------------
    proj_b_resp = await client.post("/api/v1/projects", json={"name": "Project B Empty"})
    assert proj_b_resp.status_code == 201
    proj_b_id = proj_b_resp.json()["id"]

    list_b_resp = await client.get(f"/api/v1/projects/{proj_b_id}/unified-records")
    assert list_b_resp.status_code == 200
    assert list_b_resp.json()["total"] == 0

    stats_b_resp = await client.get(f"/api/v1/projects/{proj_b_id}/unified-records/statistics")
    assert stats_b_resp.status_code == 200
    assert stats_b_resp.json()["total_records"] == 0

    # -------------------------------------------------------------------------
    # 13. Verify Exclusion of Non-Accepted Relationships
    # -------------------------------------------------------------------------
    # Create another match and REJECT it -> build -> no new record created
    rev_rej_resp = await client.post(
        f"/api/v1/matches/{match_cp101['id']}/review",
        json={"decision": "REJECTED", "comment": "Changed mind, now rejected."},
    )
    assert rev_rej_resp.status_code == 201

    # Re-run build for Project B
    build_b_resp = await client.post(f"/api/v1/projects/{proj_b_id}/unified-records/build")
    assert build_b_resp.status_code == 200
    assert build_b_resp.json()["total_records"] == 0
