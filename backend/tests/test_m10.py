import csv
import io
import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conflict import AttributeConflict
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord
from app.models.dataset import Dataset, DatasetVersion
from app.schemas.spatial_analysis import SpatialAnalysisType
from app.services.assistant.semantic_resolver import DatasetSemanticResolver
from app.services.assistant.conflict_advisor import ConflictAdvisorService
from app.services.spatial_analysis.export import AnalysisExportService


@pytest.mark.asyncio
async def test_m10_comprehensive_suite(client: AsyncClient, db_session: AsyncSession):
    """
    Milestone 10 Comprehensive Productization & Intelligence Suite:
    1. Semantic dataset resolution (target & reference resolution, confidence, reasoning)
    2. Ambiguous query handling (graceful fallback without guessing)
    3. Target/reference dataset separation in proximity query (only target features returned)
    4. Proximity query PostGIS correctness (correct distances and roles)
    5. Version comparison single version graceful explanation
    6. Version comparison added/removed/changed detection (simulated 2nd version)
    7. Analysis export as standard RFC 7946 GeoJSON
    8. Analysis export as tabular CSV with flattened attributes
    9. Conflict recommendation generation (advisory proposal)
    10. Recommendation grounding in actual conflict differences and sources
    11. AI read-only behavior (zero mutations to unified records, conflicts, features)
    12. Map result payload inspection (_role tags for MapLibre styling)
    13. Empty analysis result handling
    14. Project isolation guarantee (Project A analysis does not leak to Project B)
    """

    # -------------------------------------------------------------------------
    # Setup: Project A
    # -------------------------------------------------------------------------
    proj_resp = await client.post("/api/v1/projects", json={"name": "M10 Productization Workspace"})
    assert proj_resp.status_code == 201
    proj_a_id = proj_resp.json()["id"]

    # 1. Ingest Cadastral Parcels Dataset
    cad_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8500, 18.5200], [73.8520, 18.5200], [73.8520, 18.5220], [73.8500, 18.5220], [73.8500, 18.5200]]],
                },
                "properties": {"parcel_id": "CAD-101", "land_use": "Residential", "area": 1200.0},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8530, 18.5200], [73.8550, 18.5200], [73.8550, 18.5220], [73.8530, 18.5220], [73.8530, 18.5200]]],
                },
                "properties": {"parcel_id": "CAD-102", "land_use": "Commercial", "area": 850.0},
            },
        ],
    }
    upload_cad = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("cadastral_parcels.geojson", json.dumps(cad_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_cad.status_code == 201
    cad_ds_id = upload_cad.json()["id"]

    # 2. Ingest Municipal Assets Dataset (Points)
    mun_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
                "properties": {"asset_id": "MUN-HYDRANT-1", "type": "Fire Hydrant"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [73.8900, 18.5900]},  # far away asset
                "properties": {"asset_id": "MUN-HYDRANT-FAR", "type": "Fire Hydrant"},
            }
        ],
    }
    upload_mun = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("municipal_assets.geojson", json.dumps(mun_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_mun.status_code == 201
    mun_ds_id = upload_mun.json()["id"]

    # 3. Ingest Drone Survey Dataset (Overlaps CAD-101 with attribute divergence)
    drn_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8505, 18.5205], [73.8515, 18.5205], [73.8515, 18.5215], [73.8505, 18.5215], [73.8505, 18.5205]]],
                },
                "properties": {"structure_id": "DRN-201", "land_use": "Commercial", "area": 800.0},
            }
        ],
    }
    upload_drn = await client.post(
        f"/api/v1/projects/{proj_a_id}/datasets",
        files={"file": ("drone_structures.geojson", json.dumps(drn_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_drn.status_code == 201
    drn_ds_id = upload_drn.json()["id"]

    # Setup: Project B (For Isolation Testing)
    proj_b_resp = await client.post("/api/v1/projects", json={"name": "Project B Isolation Workspace"})
    assert proj_b_resp.status_code == 201
    proj_b_id = proj_b_resp.json()["id"]

    # =========================================================================
    # PART 1: Semantic Dataset Resolution
    # =========================================================================
    plan = await DatasetSemanticResolver.resolve_spatial_query_plan(
        db_session,
        uuid.UUID(proj_a_id),
        "Find parcels within 100 meters of municipal assets"
    )
    assert plan.intent == "spatial_analysis"
    assert plan.analysis_type == "proximity"
    assert str(plan.target_dataset_id) == cad_ds_id
    assert str(plan.reference_dataset_id) == mun_ds_id
    assert plan.distance == 100.0
    assert plan.unit == "meters"
    assert plan.confidence > 0.5

    # =========================================================================
    # PART 2: Ambiguous Dataset Handling
    # =========================================================================
    ambiguous_plan = await DatasetSemanticResolver.resolve_spatial_query_plan(
        db_session,
        uuid.UUID(proj_a_id),
        "Find things near other things with distance 50m"
    )
    # Resolver should not fabricate arbitrary dataset IDs when names don't match
    assert ambiguous_plan.target_dataset_id is None
    assert ambiguous_plan.reference_dataset_id is None

    # =========================================================================
    # PART 3 & 4: Target/Reference Separation & Proximity Query Correctness
    # =========================================================================
    # Proximity query: Target = Cadastral, Reference = Municipal Assets, Distance = 100m
    prox_resp = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_a_id,
            "target_dataset_id": cad_ds_id,
            "reference_dataset_id": mun_ds_id,
            "distance": 100.0,
            "unit": "meters",
        },
    )
    assert prox_resp.status_code == 200
    prox_data = prox_resp.json()
    assert prox_data["analysis_type"] == SpatialAnalysisType.PROXIMITY
    assert prox_data["result_count"] >= 1

    # CRITICAL: result_features must strictly contain TARGET features, not reference features!
    for feat in prox_data["result_features"]:
        assert feat["dataset_id"] == cad_ds_id
        assert feat["dataset_id"] != mun_ds_id
        assert "distance_meters" in feat
        assert feat["distance_meters"] <= 100.0

    # In result_geojson: check role tags for MapLibre
    geojson = prox_data["result_geojson"]
    roles = [f["properties"].get("_role") for f in geojson["features"]]
    assert "proximity_match" in roles
    assert "proximity_reference" in roles

    # =========================================================================
    # PART 5: Version Comparison (Single Version Graceful Explanation)
    # =========================================================================
    ver_comp_resp = await client.post(
        "/api/v1/analysis/versions/compare",
        json={"project_id": proj_a_id, "dataset_id": cad_ds_id},
    )
    assert ver_comp_resp.status_code == 200
    ver_comp_data = ver_comp_resp.json()
    assert ver_comp_data["status"] == "insufficient_versions"
    assert "has 1 version" in ver_comp_data["message"]
    assert ver_comp_data["added_count"] == 0
    assert ver_comp_data["removed_count"] == 0
    assert ver_comp_data["changed_count"] == 0

    # =========================================================================
    # PART 6: Version Comparison (Added/Removed/Changed with Multi-Version)
    # =========================================================================
    # Simulate a second version for cad_ds_id by creating a new version record & canonical features
    from app.models.feature import SourceFeature
    from shapely.geometry import shape

    v2 = DatasetVersion(
        dataset_id=uuid.UUID(cad_ds_id),
        version_number=2,
        storage_path="cadastral_v2.geojson",
        file_size=1024,
    )
    db_session.add(v2)
    await db_session.flush()

    # In v2: CAD-101 is changed (modified geom & land_use), CAD-102 is unchanged, CAD-103 is added
    sf1 = SourceFeature(
        dataset_version_id=v2.id,
        source_feature_id="CAD-101",
        geometry=shape({
            "type": "Polygon",
            "coordinates": [[[73.8500, 18.5200], [73.8525, 18.5200], [73.8525, 18.5225], [73.8500, 18.5225], [73.8500, 18.5200]]],
        }),
        properties={"parcel_id": "CAD-101", "land_use": "Commercial", "area": 1400.0},
        geometry_type="Polygon",
    )
    sf2 = SourceFeature(
        dataset_version_id=v2.id,
        source_feature_id="CAD-102",
        geometry=shape(cad_geojson["features"][1]["geometry"]),
        properties={"parcel_id": "CAD-102", "land_use": "Commercial", "area": 850.0},
        geometry_type="Polygon",
    )
    sf3 = SourceFeature(
        dataset_version_id=v2.id,
        source_feature_id="CAD-103",
        geometry=shape({
            "type": "Polygon",
            "coordinates": [[[73.8600, 18.5200], [73.8620, 18.5200], [73.8620, 18.5220], [73.8600, 18.5220], [73.8600, 18.5200]]],
        }),
        properties={"parcel_id": "CAD-103", "land_use": "Residential", "area": 600.0},
        geometry_type="Polygon",
    )
    db_session.add_all([sf1, sf2, sf3])
    await db_session.flush()

    cf1 = CanonicalFeature(
        dataset_version_id=v2.id,
        source_feature_id=sf1.id,
        geometry=sf1.geometry,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties=sf1.properties,
    )
    cf2 = CanonicalFeature(
        dataset_version_id=v2.id,
        source_feature_id=sf2.id,
        geometry=sf2.geometry,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties=sf2.properties,
    )
    cf3 = CanonicalFeature(
        dataset_version_id=v2.id,
        source_feature_id=sf3.id,
        geometry=sf3.geometry,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties=sf3.properties,
    )
    db_session.add_all([cf1, cf2, cf3])
    await db_session.commit()

    ver_comp_resp2 = await client.post(
        "/api/v1/analysis/versions/compare",
        json={"project_id": proj_a_id, "dataset_id": cad_ds_id, "version_a_number": 1, "version_b_number": 2},
    )
    assert ver_comp_resp2.status_code == 200
    v2_data = ver_comp_resp2.json()
    assert v2_data["status"] == "success"
    assert v2_data["added_count"] == 1
    assert v2_data["changed_count"] == 1
    assert v2_data["unchanged_count"] == 1
    assert v2_data["removed_count"] == 0

    # =========================================================================
    # PART 7: Export as GeoJSON
    # =========================================================================
    analysis_id = prox_data["analysis_id"]
    export_geojson_resp = await client.get(f"/api/v1/analysis/{analysis_id}/export?format=geojson")
    assert export_geojson_resp.status_code == 200
    assert "application/geo+json" in export_geojson_resp.headers["content-type"]
    exported_geojson = export_geojson_resp.json()
    assert exported_geojson["type"] == "FeatureCollection"
    assert len(exported_geojson["features"]) > 0

    # =========================================================================
    # PART 8: Export as CSV
    # =========================================================================
    export_csv_resp = await client.get(f"/api/v1/analysis/{analysis_id}/export?format=csv")
    assert export_csv_resp.status_code == 200
    assert "text/csv" in export_csv_resp.headers["content-type"]
    csv_text = export_csv_resp.text
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) > 0
    assert "feature_id" in rows[0]
    assert "dataset_name" in rows[0]

    # =========================================================================
    # PART 9 & 10 & 11: Conflict Resolution Proposals & Read-Only Verification
    # =========================================================================
    # Generate match & acceptance to create a conflict
    match_run = await client.post(
        f"/api/v1/projects/{proj_a_id}/matching-runs",
        json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
    )
    assert match_run.status_code == 201
    run_id = match_run.json()["id"]

    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) >= 1
    match_id = matches[0]["id"]

    await client.post(
        f"/api/v1/matches/{match_id}/review",
        json={"decision": "ACCEPTED", "comment": "Accept CAD/DRN match to establish conflict"},
    )
    build_resp = await client.post(f"/api/v1/projects/{proj_a_id}/unified-records/build")
    assert build_resp.status_code == 200

    # Fetch conflicts
    conf_list_resp = await client.get(f"/api/v1/projects/{proj_a_id}/conflicts")
    assert conf_list_resp.status_code == 200
    conflicts = conf_list_resp.json()["items"]
    assert len(conflicts) >= 1
    target_conflict = conflicts[0]
    conflict_id = target_conflict["id"]

    # Record DB counts before proposing resolution
    stmt_unif = select(func.count()).select_from(UnifiedLandRecord)
    stmt_conf = select(func.count()).select_from(AttributeConflict)
    stmt_feat = select(func.count()).select_from(CanonicalFeature)

    res_unif_before = await db_session.execute(stmt_unif)
    count_unif_before = res_unif_before.scalar_one()

    res_conf_before = await db_session.execute(stmt_conf)
    count_conf_before = res_conf_before.scalar_one()

    res_feat_before = await db_session.execute(stmt_feat)
    count_feat_before = res_feat_before.scalar_one()

    # Generate proposal via API
    prop_resp = await client.post(f"/api/v1/conflicts/{conflict_id}/propose-resolution")
    assert prop_resp.status_code == 200
    proposal = prop_resp.json()

    assert proposal["requires_human_approval"] is True
    assert proposal["is_advisory_only"] is True
    assert proposal["fact_statement"] != ""
    assert proposal["inference_statement"] != ""
    assert proposal["recommendation_statement"] != ""
    assert proposal["reasoning"] != ""
    assert len(proposal["supporting_evidence"]) >= 1

    # Verify ZERO database mutations occurred (read-only safety)
    res_unif_after = await db_session.execute(stmt_unif)
    assert res_unif_after.scalar_one() == count_unif_before

    res_conf_after = await db_session.execute(stmt_conf)
    assert res_conf_after.scalar_one() == count_conf_before

    res_feat_after = await db_session.execute(stmt_feat)
    assert res_feat_after.scalar_one() == count_feat_before

    # Verify conflict status in DB was NOT changed automatically
    stmt_check_conf = select(AttributeConflict).where(AttributeConflict.id == uuid.UUID(conflict_id))
    conf_obj = (await db_session.execute(stmt_check_conf)).scalar_one()
    assert conf_obj.status == "UNRESOLVED"

    # =========================================================================
    # PART 12: Map Result Payload
    # =========================================================================
    assert prox_data["result_geojson"]["type"] == "FeatureCollection"
    for f in prox_data["result_geojson"]["features"]:
        assert "_role" in f["properties"]
        assert f["geometry"]["type"] in ["Polygon", "Point", "MultiPolygon", "MultiPoint", "LineString"]

    # =========================================================================
    # PART 13: Empty Analysis Result Handling
    # =========================================================================
    empty_prox = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_a_id,
            "target_geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "distance": 100.0,
            "unit": "meters",
        },
    )
    assert empty_prox.status_code == 200
    empty_data = empty_prox.json()
    assert empty_data["result_count"] == 0
    assert len(empty_data["result_features"]) == 0
    assert empty_data["result_geojson"]["type"] == "FeatureCollection"

    # =========================================================================
    # PART 14: Project Isolation Guarantee
    # =========================================================================
    # In Project B, no datasets exist; proximity query in Project B returns 0 features
    proj_b_prox = await client.post(
        "/api/v1/analysis/proximity",
        json={
            "project_id": proj_b_id,
            "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
            "distance": 1000.0,
            "unit": "meters",
        },
    )
    assert proj_b_prox.status_code == 200
    assert proj_b_prox.json()["result_count"] == 0
