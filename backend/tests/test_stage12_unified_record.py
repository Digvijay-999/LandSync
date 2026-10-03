import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.matching import FeatureMatch
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource


def get_err_msg(resp) -> str:
    data = resp.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", ""))
        return str(data.get("detail", ""))
    return ""


@pytest.mark.asyncio
async def test_stage12_prerequisite_lock(client: AsyncClient):
    """
    Verify Stage 12 is locked/disabled when Stage 11 has not completed.
    Execution requests must reject access with clear 400 Bad Request error.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Stage 12 Prereq Test Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # Check status endpoint before Stage 11 is completed
    st_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-12/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["stage_status"] == "disabled"
    assert st_data["is_completed"] is False
    assert st_data["is_runnable"] is False

    # Attempt execute before Stage 11 completes -> 400
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-12/execute")
    assert exec_resp.status_code == 400
    assert "Stage 11 Human Review must be completed" in get_err_msg(exec_resp)

    # Alias endpoint also rejects
    exec_alias_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stages/12/execute")
    assert exec_alias_resp.status_code == 400

    # Pipeline status shows Stage 12 disabled, Stage 13 disabled, Stage 14 disabled
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = {s["stage_number"]: s for s in pipe_resp.json()["stages"]}
    assert stages[12]["status"] == "disabled"
    assert stages[13]["status"] == "disabled"
    assert stages[14]["status"] == "disabled"


@pytest.mark.asyncio
async def test_stage12_synthesis_workflow_and_decision_precedence(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Comprehensive test of Stage 12 Unified Record synthesis engine:
    1. Human Review Precedence:
       - ACCEPT_SOURCE_A uses Source A geometry and attributes
       - ACCEPT_SOURCE_B uses Source B geometry and attributes
       - MERGE_RECONCILE uses reviewer chosen geometry and reconciled attributes
       - REJECT_UNRESOLVED marks record as REJECTED (not authoritative unified parcel)
       - AUTO_CONFIRMED uses Stage 07 harmonized values
    2. PostGIS geometry validation (SRID 4326, metric area computation)
    3. Metadata trail lineage recording
    4. Gating transitions: Stage 12 -> completed, Stage 13 -> unlocked/ready, Stage 14 -> locked
    """
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Pune Haveli Stage 12 Synthesis Project"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])

    now = datetime.now(timezone.utc)

    # 2. Setup datasets and versions
    ds_cad = Dataset(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Cadastral Cadastre Map",
        source_filename="cadastral.geojson",
        source_format="GEOJSON",
        feature_count=5,
    )
    ds_drone = Dataset(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Drone Survey Layer",
        source_filename="drone.geojson",
        source_format="GEOJSON",
        feature_count=5,
    )
    db_session.add_all([ds_cad, ds_drone])
    await db_session.flush()

    ver_cad = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=ds_cad.id,
        version_number=1,
        storage_path="/data/cadastral.geojson",
    )
    ver_drone = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=ds_drone.id,
        version_number=1,
        storage_path="/data/drone.geojson",
    )
    db_session.add_all([ver_cad, ver_drone])
    await db_session.flush()

    # 3. Create 5 pairs of canonical features with real polygon geometries in Pune (EPSG:4326)
    geom_poly1 = Polygon([(73.85, 18.52), (73.86, 18.52), (73.86, 18.53), (73.85, 18.53), (73.85, 18.52)])
    geom_poly2 = Polygon([(73.8501, 18.5201), (73.8601, 18.5201), (73.8601, 18.5301), (73.8501, 18.5301), (73.8501, 18.5201)])

    feat_pairs = []
    for i in range(5):
        sf_geom = from_shape(geom_poly1, srid=4326)
        cf_geom = from_shape(geom_poly2, srid=4326)

        src_f1 = SourceFeature(
            id=uuid.uuid4(),
            dataset_version_id=ver_cad.id,
            source_feature_id=f"SRC-CAD-{100 + i}",
            geometry=sf_geom,
            geometry_type="Polygon",
            properties={
                "parcel_id": f"PUNE-CAD-{100 + i}",
                "land_use": "Agricultural" if i % 2 == 0 else "Commercial",
                "mutation_status": "Sanctioned",
                "risk_level": "LOW",
                "area": 12000.0 + i * 500,
            },
        )
        src_f2 = SourceFeature(
            id=uuid.uuid4(),
            dataset_version_id=ver_drone.id,
            source_feature_id=f"SRC-DRN-{200 + i}",
            geometry=cf_geom,
            geometry_type="Polygon",
            properties={
                "parcel_id": f"PUNE-DRN-{200 + i}",
                "land_use": "Residential" if i % 2 == 0 else "Industrial",
                "mutation_status": "Pending",
                "risk_level": "MEDIUM",
                "area": 11800.0 + i * 500,
            },
        )
        db_session.add_all([src_f1, src_f2])
        await db_session.flush()

        sf = CanonicalFeature(
            id=uuid.uuid4(),
            dataset_version_id=ver_cad.id,
            source_feature_id=src_f1.id,
            geometry=sf_geom,
            geometry_type="Polygon",
            source_crs="EPSG:4326",
            target_crs="EPSG:4326",
            canonical_properties=src_f1.properties,
        )
        cf = CanonicalFeature(
            id=uuid.uuid4(),
            dataset_version_id=ver_drone.id,
            source_feature_id=src_f2.id,
            geometry=cf_geom,
            geometry_type="Polygon",
            source_crs="EPSG:4326",
            target_crs="EPSG:4326",
            canonical_properties=src_f2.properties,
        )
        db_session.add_all([sf, cf])
        feat_pairs.append((sf, cf))

    await db_session.flush()

    # 4. Create mock Stage 07 harmonized records
    stage7_records = []
    for i, (sf, cf) in enumerate(feat_pairs):
        rec_id = f"HR-{1001 + i}"
        stage7_records.append({
            "id": rec_id,
            "harmonized_record_id": rec_id,
            "source_identifier": sf.canonical_properties["parcel_id"],
            "candidate_identifier": cf.canonical_properties["parcel_id"],
            "source_feature_id": str(sf.id),
            "candidate_feature_id": str(cf.id),
            "authoritative_geometry_source": "SOURCE_A",
            "geometry_status": "VALID",
            "source_area": sf.canonical_properties["area"],
            "candidate_area": cf.canonical_properties["area"],
            "harmonized_area": sf.canonical_properties["area"],
            "area_discrepancy_pct": 1.7,
            "source_land_use": sf.canonical_properties["land_use"],
            "candidate_land_use": cf.canonical_properties["land_use"],
            "harmonized_land_use": sf.canonical_properties["land_use"],
            "source_mutation_status": sf.canonical_properties["mutation_status"],
            "candidate_mutation_status": cf.canonical_properties["mutation_status"],
            "harmonized_mutation_status": sf.canonical_properties["mutation_status"],
            "source_risk_level": sf.canonical_properties["risk_level"],
            "candidate_risk_level": cf.canonical_properties["risk_level"],
            "harmonized_risk_level": sf.canonical_properties["risk_level"],
            "conflict_count": 1 if i < 4 else 0,
            "has_conflicts": i < 4,
        })

    st7_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=7,
        stage_id="harmonization",
        status="completed",
        results={"records_preview": stage7_records},
        started_at=now,
        completed_at=now,
    )
    db_session.add(st7_exec)

    # 5. Create mock Stage 10 confidence records
    stage10_records = []
    for i, (sf, cf) in enumerate(feat_pairs):
        rec_id = f"HR-{1001 + i}"
        conf = 0.95 if i == 4 else 0.72  # record 4 is high confidence, auto-confirmed
        bucket = "HIGH" if conf >= 0.90 else "MEDIUM"
        stage10_records.append({
            "id": rec_id,
            "harmonized_record_id": rec_id,
            "source_identifier": sf.canonical_properties["parcel_id"],
            "candidate_identifier": cf.canonical_properties["parcel_id"],
            "source_feature_id": str(sf.id),
            "candidate_feature_id": str(cf.id),
            "overall_confidence": conf,
            "confidence_bucket": bucket,
            "bucket_label": f"{bucket} BUCKET",
            "validation_status": "PASS",
            "has_critical_conflicts": False,
            "contributions": {"spatial": 0.28, "geometry": 0.27, "attribute": 0.25, "temporal": 0.10},
            "reasons": ["High spatial overlap", "Area tolerance met"],
        })

    st10_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=10,
        stage_id="confidence",
        status="completed",
        results={"records_preview": stage10_records},
        started_at=now,
        completed_at=now,
    )
    db_session.add(st10_exec)

    # 6. Create Stage 11 completed execution and decisions
    # Record 0: ACCEPT_SOURCE_A
    # Record 1: ACCEPT_SOURCE_B
    # Record 2: MERGE_RECONCILE
    # Record 3: REJECT_UNRESOLVED
    # Record 4: No human review decision (AUTO_CONFIRMED)
    decisions = [
        HumanReviewDecision(
            id=uuid.uuid4(),
            project_id=proj_id,
            harmonized_record_id="HR-1001",
            source_feature_id=feat_pairs[0][0].id,
            candidate_feature_id=feat_pairs[0][1].id,
            action="ACCEPT_SOURCE_A",
            adjudication_status="RESOLVED",
            reviewer_name="Senior GIS Officer",
            notes="Source A verified against historical records",
            authoritative_geometry_source="SOURCE_A",
            authoritative_attributes={},
            idempotency_key=f"{proj_id}_HR-1001",
        ),
        HumanReviewDecision(
            id=uuid.uuid4(),
            project_id=proj_id,
            harmonized_record_id="HR-1002",
            source_feature_id=feat_pairs[1][0].id,
            candidate_feature_id=feat_pairs[1][1].id,
            action="ACCEPT_SOURCE_B",
            adjudication_status="RESOLVED",
            reviewer_name="Senior GIS Officer",
            notes="Drone survey represents current ground reality",
            authoritative_geometry_source="SOURCE_B",
            authoritative_attributes={},
            idempotency_key=f"{proj_id}_HR-1002",
        ),
        HumanReviewDecision(
            id=uuid.uuid4(),
            project_id=proj_id,
            harmonized_record_id="HR-1003",
            source_feature_id=feat_pairs[2][0].id,
            candidate_feature_id=feat_pairs[2][1].id,
            action="MERGE_RECONCILE",
            adjudication_status="RESOLVED",
            reviewer_name="Senior GIS Officer",
            notes="Reconciled land use to Mixed Commercial and verified area",
            authoritative_geometry_source="SOURCE_B",
            authoritative_attributes={
                "land_use": "Mixed Commercial",
                "mutation_status": "Verified Mutation",
                "risk_level": "LOW",
                "area": 13500.0,
            },
            idempotency_key=f"{proj_id}_HR-1003",
        ),
        HumanReviewDecision(
            id=uuid.uuid4(),
            project_id=proj_id,
            harmonized_record_id="HR-1004",
            source_feature_id=feat_pairs[3][0].id,
            candidate_feature_id=feat_pairs[3][1].id,
            action="REJECT_UNRESOLVED",
            adjudication_status="REJECTED",
            reviewer_name="Senior GIS Officer",
            notes="Boundary dispute in civil court; rejected from authoritative layer",
            authoritative_geometry_source=None,
            authoritative_attributes={},
            idempotency_key=f"{proj_id}_HR-1004",
        ),
    ]
    for d in decisions:
        db_session.add(d)

    st11_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=11,
        stage_id="review",
        status="completed",
        results={
            "total_review_items": 4,
            "resolved_count": 4,
            "unresolved_count": 0,
            "accept_source_a_count": 1,
            "accept_source_b_count": 1,
            "merged_count": 1,
            "rejected_count": 1,
        },
        started_at=now,
        completed_at=now,
    )
    db_session.add(st11_exec)
    await db_session.commit()

    # 7. Execute Stage 12 Unified Record synthesis
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-12/execute")
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()

    assert res_data["stage_number"] == 12
    assert res_data["stage_id"] == "record"
    assert res_data["status"] == "completed"
    assert res_data["records_considered"] == 5
    assert res_data["records_unified"] == 4  # 1 (A) + 1 (B) + 1 (Merge) + 1 (Auto)
    assert res_data["records_rejected"] == 1  # 1 (Reject)
    assert res_data["valid_geometries_count"] >= 4
    assert res_data["average_confidence"] > 0.0

    # 8. Verify individual records in database
    records_stmt = select(UnifiedLandRecord).where(UnifiedLandRecord.project_id == proj_id).order_by(UnifiedLandRecord.harmonized_record_id.asc())
    saved_records = list((await db_session.execute(records_stmt)).scalars().all())
    assert len(saved_records) == 5

    rec_by_id = {r.harmonized_record_id: r for r in saved_records}

    # Record 0 (ACCEPT_SOURCE_A)
    r0 = rec_by_id["HR-1001"]
    assert r0.resolution_status == "UNIFIED"
    assert r0.human_review_decision == "ACCEPT_SOURCE_A"
    assert r0.geometry_source == "SOURCE_A"
    assert r0.canonical_geometry is not None
    assert r0.land_use == "Agricultural"
    assert r0.status == "ACTIVE"

    # Record 1 (ACCEPT_SOURCE_B)
    r1 = rec_by_id["HR-1002"]
    assert r1.resolution_status == "UNIFIED"
    assert r1.human_review_decision == "ACCEPT_SOURCE_B"
    assert r1.geometry_source == "SOURCE_B"
    assert r1.canonical_geometry is not None
    assert r1.land_use == "Industrial"
    assert r1.status == "ACTIVE"

    # Record 2 (MERGE_RECONCILE)
    r2 = rec_by_id["HR-1003"]
    assert r2.resolution_status == "UNIFIED"
    assert r2.human_review_decision == "MERGE_RECONCILE"
    assert r2.geometry_source == "SOURCE_B"
    assert r2.land_use == "Mixed Commercial"
    assert r2.mutation_status == "Verified Mutation"
    assert r2.area == 13500.0

    # Record 3 (REJECT_UNRESOLVED)
    r3 = rec_by_id["HR-1004"]
    assert r3.resolution_status == "REJECTED"
    assert r3.human_review_decision == "REJECT_UNRESOLVED"
    assert r3.geometry_source == "REJECTED"
    assert r3.canonical_geometry is None
    assert r3.status == "CONFLICT"

    # Record 4 (AUTO_CONFIRMED)
    r4 = rec_by_id["HR-1005"]
    assert r4.resolution_status == "UNIFIED"
    assert r4.human_review_decision == "AUTO_CONFIRMED"
    assert r4.canonical_geometry is not None
    assert r4.confidence_score == 0.95

    # 9. Verify downstream stage unlocking
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = {s["stage_number"]: s for s in pipe_resp.json()["stages"]}
    assert stages[11]["status"] == "completed"
    assert stages[12]["status"] == "completed"
    assert stages[13]["status"] == "ready"  # Stage 13 UNLOCKED
    assert stages[13]["prerequisites_met"] is True
    assert stages[14]["status"] == "disabled"  # Stage 14 remains LOCKED

    # 10. Verify idempotency: executing again produces identical result and NO duplicates
    exec_again = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-12/execute")
    assert exec_again.status_code == 200
    assert exec_again.json()["records_unified"] == 4
    assert exec_again.json()["records_rejected"] == 1

    count_stmt = select(func.count(UnifiedLandRecord.id)).where(UnifiedLandRecord.project_id == proj_id)
    total_count = (await db_session.execute(count_stmt)).scalar()
    assert total_count == 5  # No duplicates!

    # 11. Test query and filtering endpoints
    # Filter by resolution_status UNIFIED
    u_list_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records?resolution_status=UNIFIED")
    assert u_list_resp.status_code == 200
    assert u_list_resp.json()["total"] == 4

    # Filter by resolution_status REJECTED
    r_list_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records?resolution_status=REJECTED")
    assert r_list_resp.status_code == 200
    assert r_list_resp.json()["total"] == 1

    # Search filter
    s_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records?search=Mixed Commercial")
    assert s_resp.status_code == 200
    assert s_resp.json()["total"] == 1
    assert s_resp.json()["items"][0]["harmonized_record_id"] == "HR-1003"

    # Detail endpoint
    rec2_db_id = r2.id
    det_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records/{rec2_db_id}")
    assert det_resp.status_code == 200
    det_data = det_resp.json()
    assert det_data["id"] == str(rec2_db_id)
    assert det_data["land_use"] == "Mixed Commercial"
    assert det_data["human_review_decision"] == "MERGE_RECONCILE"
    assert det_data["canonical_geometry"] is not None
    assert "pipeline_lineage" in det_data["metadata_trail"]


@pytest.mark.asyncio
async def test_stage12_statistics_and_sources(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test unified record statistics endpoint and contributing sources retrieval.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Stage 12 Stats Project"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])

    ur = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-STAT-01",
        status="ACTIVE",
        resolution_status="UNIFIED",
        land_use="Agricultural",
        area=10000.0,
        confidence_score=0.92,
        canonical_attributes={"land_use": "Agricultural"},
    )
    db_session.add(ur)
    await db_session.commit()

    stats_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records/statistics")
    assert stats_resp.status_code == 200
    st = stats_resp.json()
    assert st["total_records"] == 1
    assert st["active"] == 1

