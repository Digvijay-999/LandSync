import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.spatial_analysis import SpatialAnalysisType


@pytest.mark.asyncio
async def test_spatial_analysis_complete_suite(client: AsyncClient, db_session: AsyncSession):
    """
    Comprehensive test suite covering Milestone 9:
    1. Proximity search (within distance)
    2. Buffer analysis
    3. Intersection analysis
    4. Containment analysis
    5. Nearest features
    6. Spatial statistics
    7. Dataset comparison (A only, B only, overlap)
    8. Spatial conflict aggregation & clustering
    9. Project isolation guarantee
    10. Parameter validation & empty/zero results
    11. LangGraph AI spatial routing & result attachment
    12. Complex multi-step spatial investigation
    """
    # -------------------------------------------------------------------------
    # Setup: Project A
    # -------------------------------------------------------------------------
    proj_resp = await client.post("/api/v1/projects", json={"name": "M9 Spatial Intelligence Test Workspace"})
    assert proj_resp.status_code == 201
    proj_a_id = proj_resp.json()["id"]

    # Ingest Dataset 1: Cadastral Parcels
    cadastral_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8500, 18.5200], [73.8520, 18.5200], [73.8520, 18.5220], [73.8500, 18.5220], [73.8500, 18.5200]]],
                },
                "properties": {"parcel_id": "CAD-001", "land_use": "Residential", "area": 1200.0},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8530, 18.5200], [73.8550, 18.5200], [73.8550, 18.5220], [73.8530, 18.5220], [73.8530, 18.5200]]],
                },
                "properties": {"parcel_id": "CAD-002", "land_use": "Commercial", "area": 850.0},
            },
        ],
    }
    upload_cad = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_cad.status_code == 201
    cad_ds_id = upload_cad.json()["id"]

    # Ingest Dataset 2: Drone Survey (Overlaps CAD-001 with conflicting land_use and area)
    drone_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8505, 18.5205], [73.8515, 18.5205], [73.8515, 18.5215], [73.8505, 18.5215], [73.8505, 18.5205]]],
                },
                "properties": {"structure_id": "DRN-101", "land_use": "Commercial", "area": 800.0},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8580, 18.5200], [73.8600, 18.5200], [73.8600, 18.5220], [73.8580, 18.5220], [73.8580, 18.5200]]],
                },
                "properties": {"structure_id": "DRN-102", "land_use": "Industrial", "area": 500.0},
            },
        ],
    }
    upload_drn = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_drn.status_code == 201
    drn_ds_id = upload_drn.json()["id"]

    # Ingest Dataset 3: Municipal Assets (Points)
    municipal_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [73.8502, 18.5202],
                },
                "properties": {"asset_id": "ASSET-HYDRANT-1", "type": "Fire Hydrant"},
            }
        ],
    }
    upload_mun = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("municipal.geojson", json.dumps(municipal_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_mun.status_code == 201
    mun_ds_id = upload_mun.json()["id"]

    # -------------------------------------------------------------------------
    # Setup: Project B (For Isolation Testing)
    # -------------------------------------------------------------------------
    proj_b_resp = await client.post("/api/v1/projects", json={"name": "Project B Isolated Workspace"})
    assert proj_b_resp.status_code == 201
    proj_b_id = proj_b_resp.json()["id"]

    # -------------------------------------------------------------------------
    # 1. Proximity Search API & Execution
    # -------------------------------------------------------------------------
    prox_resp = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": 100.0,
            "unit": "meters",
        },
    )
    assert prox_resp.status_code == 200
    prox_data = prox_resp.json()
    assert prox_data["analysis_type"] == SpatialAnalysisType.PROXIMITY
    assert prox_data["result_count"] >= 1
    assert "result_geojson" in prox_data
    assert prox_data["result_geojson"]["type"] == "FeatureCollection"
    assert len(prox_data["result_geojson"]["features"]) >= 1

    # -------------------------------------------------------------------------
    # 2. Buffer Analysis API
    # -------------------------------------------------------------------------
    buf_resp = await client.post(
        "/api/v1/analysis/buffer",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": 50.0,
            "unit": "meters",
        },
    )
    assert buf_resp.status_code == 200
    buf_data = buf_resp.json()
    assert buf_data["analysis_type"] == SpatialAnalysisType.BUFFER
    assert buf_data["result_geometry"] is not None
    assert buf_data["result_geometry"]["type"] == "Polygon"

    # -------------------------------------------------------------------------
    # 3. Intersection Analysis API
    # -------------------------------------------------------------------------
    intersect_resp = await client.post(
        "/api/v1/analysis/intersection",
        json={
            "project_id": proj_a_id,
            "dataset_a_id": cad_ds_id,
            "dataset_b_id": drn_ds_id,
        },
    )
    assert intersect_resp.status_code == 200
    intersect_data = intersect_resp.json()
    assert intersect_data["analysis_type"] == SpatialAnalysisType.INTERSECTION
    # DRN-101 is located inside CAD-001, so at least 1 intersection
    assert intersect_data["statistics"]["intersecting_pairs"] >= 1
    assert len(intersect_data["result_features"]) >= 1

    # -------------------------------------------------------------------------
    # 4. Containment Analysis API
    # -------------------------------------------------------------------------
    contain_resp = await client.post(
        "/api/v1/analysis/containment",
        json={
            "project_id": proj_a_id,
            "container_geometry": {
                "type": "Polygon",
                "coordinates": [[[73.84, 18.51], [73.87, 18.51], [73.87, 18.54], [73.84, 18.54], [73.84, 18.51]]],
            },
            "containment_mode": "contains",
        },
    )
    assert contain_resp.status_code == 200
    contain_data = contain_resp.json()
    assert contain_data["statistics"]["total_contained"] >= 4

    # -------------------------------------------------------------------------
    # 5. Nearest Features API
    # -------------------------------------------------------------------------
    near_resp = await client.post(
        "/api/v1/analysis/nearest",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8501, 18.5201]},
            "limit": 2,
        },
    )
    assert near_resp.status_code == 200
    near_data = near_resp.json()
    assert near_data["result_count"] >= 1
    assert len(near_data["result_features"]) >= 1

    # -------------------------------------------------------------------------
    # 6. Spatial Statistics API
    # -------------------------------------------------------------------------
    stats_resp = await client.post(
        "/api/v1/analysis/statistics",
        json={"project_id": proj_a_id},
    )
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["statistics"]["total_features"] >= 5
    assert "extent" in stats_data["statistics"]
    assert stats_data["statistics"]["geometry_validity"]["valid_percentage"] == 100.0

    # -------------------------------------------------------------------------
    # 7. Dataset Comparison API (cadastral vs drone)
    # -------------------------------------------------------------------------
    comp_resp = await client.post(
        "/api/v1/analysis/compare",
        json={
            "project_id": proj_a_id,
            "dataset_a_id": cad_ds_id,
            "dataset_b_id": drn_ds_id,
        },
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["dataset_a_count"] == 2
    assert comp_data["dataset_b_count"] == 2
    assert comp_data["intersecting_count"] >= 1
    assert comp_data["unmatched_a_count"] >= 1
    assert comp_data["unmatched_b_count"] >= 1
    assert comp_data["analysis"]["result_geojson"]["type"] == "FeatureCollection"

    # -------------------------------------------------------------------------
    # 8. Spatial Conflict Clustering (Matching -> Acceptance -> Conflict Generation)
    # -------------------------------------------------------------------------
    match_resp = await client.post(
        f"/api/v1/projects/{proj_a_id}/matching-runs",
        json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
    )
    assert match_resp.status_code == 201
    run_id = match_resp.json()["id"]

    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) >= 1
    match_id = matches[0]["id"]

    rev_resp = await client.post(
        f"/api/v1/matches/{match_id}/review",
        json={"decision": "ACCEPTED", "comment": "Accepted overlapping parcel-structure pair"},
    )
    assert rev_resp.status_code == 201

    build_resp = await client.post(f"/api/v1/projects/{proj_a_id}/unified-records/build")
    assert build_resp.status_code == 200
    assert build_resp.json()["conflict_records"] >= 1

    conf_resp = await client.post(
        "/api/v1/analysis/conflicts",
        json={"project_id": proj_a_id},
    )
    assert conf_resp.status_code == 200
    conf_data = conf_resp.json()
    assert conf_data["total_conflicts"] >= 1
    assert "clusters" in conf_data

    # -------------------------------------------------------------------------
    # 9. Project Isolation Guarantee
    # -------------------------------------------------------------------------
    # Querying Project B must return 0 features and 0 conflicts
    iso_stats = await client.post("/api/v1/analysis/statistics", json={"project_id": proj_b_id})
    assert iso_stats.status_code == 200
    assert iso_stats.json()["statistics"]["total_features"] == 0

    iso_prox = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_b_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": 500.0,
        },
    )
    assert iso_prox.status_code == 200
    assert iso_prox.json()["result_count"] == 0

    # -------------------------------------------------------------------------
    # 10. Parameter Validation & Edge Cases
    # -------------------------------------------------------------------------
    # Negative distance validation
    bad_dist = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": -10.0,
        },
    )
    assert bad_dist.status_code == 422

    # Zero distance
    zero_dist = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": 0.0,
        },
    )
    assert zero_dist.status_code == 200
    assert zero_dist.json()["result_count"] >= 0

    # -------------------------------------------------------------------------
    # 11. AI Spatial Intent Routing & Result Attachment
    # -------------------------------------------------------------------------
    ai_spatial_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "project_id": proj_a_id,
            "query": "Which parcels are within 150m of municipal assets?",
        },
    )
    assert ai_spatial_resp.status_code == 200
    ai_data = ai_spatial_resp.json()
    assert ai_data["intent"] in ["SPATIAL_ANALYSIS", "COMPLEX_SPATIAL_INVESTIGATION"]
    assert ai_data["spatial_result"] is not None
    assert ai_data["spatial_result"]["analysis_type"] == SpatialAnalysisType.PROXIMITY
    assert ai_data["spatial_result"]["result_geojson"] is not None

    # -------------------------------------------------------------------------
    # 12. Complex Multi-Step Spatial Investigation
    # -------------------------------------------------------------------------
    ai_complex_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "project_id": proj_a_id,
            "query": "Find parcels within 200m of municipal assets that have unresolved conflicts and explain what sources caused the conflicts.",
        },
    )
    assert ai_complex_resp.status_code == 200
    ai_complex = ai_complex_resp.json()
    assert ai_complex["intent"] in ["COMPLEX_SPATIAL_INVESTIGATION", "SPATIAL_ANALYSIS"]
    assert ai_complex["spatial_result"] is not None
    assert len(ai_complex["evidence_sources"]) >= 1
