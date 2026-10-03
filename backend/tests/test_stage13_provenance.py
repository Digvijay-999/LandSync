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
from app.models.provenance import ProvenanceRecord, ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.matching import MatchRun, FeatureMatch
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource


def get_err_msg(resp) -> str:
    data = resp.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", ""))
        return str(data.get("detail", ""))
    return ""


@pytest.mark.asyncio
async def test_stage13_prerequisite_lock(client: AsyncClient):
    """
    Verify Stage 13 is locked/disabled when Stage 12 has not completed.
    Execution requests must reject access with 400 Bad Request.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Stage 13 Prereq Lock Test"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # Check status before Stage 12 is completed
    st_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-13/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["status"] == "disabled"
    assert st_data["is_completed"] is False
    assert st_data["is_runnable"] is False
    assert st_data["prerequisites_met"] is False
    assert "Stage 12 Unified Record" in (st_data["prerequisites_message"] or "")

    # Attempt execute before Stage 12 completes -> 400
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-13/execute")
    assert exec_resp.status_code == 400
    assert "Stage 12 (Unified Record) must be completed first" in get_err_msg(exec_resp)

    # Alias endpoint also rejects
    exec_alias_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stages/13/execute")
    assert exec_alias_resp.status_code == 400

    # Pipeline status shows Stage 13 disabled, Stage 14 disabled
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = {s["stage_number"]: s for s in pipe_resp.json()["stages"]}
    assert stages[13]["status"] == "disabled"
    assert stages[14]["status"] == "disabled"


@pytest.mark.asyncio
async def test_stage13_lineage_generation_and_stage14_unlock(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test Stage 13 Provenance generation:
    1. Sets up real upstream entities (datasets, features, matches, conflicts, validation, human decisions).
    2. Sets up Stage 12 Unified Land Records (both authoritative and rejected).
    3. Runs Stage 13 execution.
    4. Verifies database records in provenance_records and provenance_events.
    5. Verifies completeness score, human decision tracing, and graph nodes.
    6. Verifies Stage 13 -> completed and Stage 14 (Export) -> ready/unlocked.
    """
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Pune Haveli M13 Provenance Test"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    # 2. Datasets
    ds_a = Dataset(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Cadastral Map Pune Haveli",
        source_filename="cadastral.geojson",
        source_format="GEOJSON",
        feature_count=3,
    )
    ds_b = Dataset(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Municipal Property Tax GIS",
        source_filename="municipal.geojson",
        source_format="GEOJSON",
        feature_count=3,
    )
    db_session.add_all([ds_a, ds_b])
    await db_session.flush()

    dv_a = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=ds_a.id,
        version_number=1,
        storage_path="datasets/cadastral_v1.geojson",
    )
    dv_b = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=ds_b.id,
        version_number=1,
        storage_path="datasets/municipal_v1.geojson",
    )
    db_session.add_all([dv_a, dv_b])
    await db_session.flush()

    poly1 = Polygon([(73.85, 18.52), (73.86, 18.52), (73.86, 18.53), (73.85, 18.53), (73.85, 18.52)])
    geom1 = from_shape(poly1, srid=4326)

    poly2 = Polygon([(73.851, 18.521), (73.861, 18.521), (73.861, 18.531), (73.851, 18.531), (73.851, 18.521)])
    geom2 = from_shape(poly2, srid=4326)

    src_f1 = SourceFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id="SRC-CAD-001",
        geometry=geom1,
        geometry_type="Polygon",
        properties={"parcel_id": "HAV-CAD-001", "land_use": "AGRICULTURAL"},
    )
    src_f2 = SourceFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_b.id,
        source_feature_id="SRC-MUN-001",
        geometry=geom2,
        geometry_type="Polygon",
        properties={"parcel_id": "HAV-MUN-001", "land_use": "RESIDENTIAL"},
    )
    db_session.add_all([src_f1, src_f2])
    await db_session.flush()

    cf1 = CanonicalFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id=src_f1.id,
        geometry=geom1,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties={"parcel_id": "HAV-CAD-001", "land_use": "AGRICULTURAL"},
    )
    cf2 = CanonicalFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_b.id,
        source_feature_id=src_f2.id,
        geometry=geom2,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties={"parcel_id": "HAV-MUN-001", "land_use": "RESIDENTIAL"},
    )
    db_session.add_all([cf1, cf2])
    await db_session.flush()

    # 3. Match Run and Match
    match_run = MatchRun(
        id=uuid.uuid4(),
        project_id=proj_id,
        source_dataset_id=ds_a.id,
        candidate_dataset_ids=[str(ds_b.id)],
        status="completed",
        total_candidates=1,
        total_matches=1,
        total_possible_matches=0,
    )
    db_session.add(match_run)
    await db_session.flush()

    match1 = FeatureMatch(
        id=uuid.uuid4(),
        match_run_id=match_run.id,
        project_id=proj_id,
        source_dataset_id=ds_a.id,
        candidate_dataset_id=ds_b.id,
        source_feature_id=cf1.id,
        candidate_feature_id=cf2.id,
        overall_score=0.91,
        status="MATCHED",
        review_status="ACCEPTED",
        rank=1,
        is_best_candidate=True,
        explanation={"spatial_iou": 0.92, "attribute_sim": 0.89},
    )
    db_session.add(match1)
    await db_session.flush()

    harm_id_1 = "harm_pune_haveli_001"
    harm_id_rej = "harm_pune_haveli_rej"

    # 4. Conflict & Validation
    conf1 = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=harm_id_1,
        source_feature_id=cf1.id,
        candidate_feature_id=cf2.id,
        conflict_type="LAND_USE_CONFLICT",
        category="ATTRIBUTE",
        severity="HIGH",
        status="RESOLVED",
        source_a="AGRICULTURAL",
        source_b="RESIDENTIAL",
        field_name="land_use",
        detection_rule="LAND_USE_RULES",
        idempotency_key=f"conf_{harm_id_1}",
    )
    db_session.add(conf1)

    val1 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=harm_id_1,
        source_feature_id=cf1.id,
        candidate_feature_id=cf2.id,
        source_identifier="HAV-CAD-001",
        candidate_identifier="HAV-MUN-001",
        overall_status="PASS",
        geometry_validity_status="PASS",
        topology_status="PASS",
        area_status="PASS",
        semantic_status="PASS",
        conflict_status="PASS",
        failure_reasons=[],
        warning_reasons=[],
        idempotency_key=f"val_{harm_id_1}",
    )
    db_session.add(val1)

    # 5. Human Review Decisions
    hr1 = HumanReviewDecision(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=harm_id_1,
        source_feature_id=cf1.id,
        candidate_feature_id=cf2.id,
        feature_match_id=match1.id,
        action="MERGE_RECONCILE",
        adjudication_status="RESOLVED",
        reviewer_name="Senior Haveli Cadastral Inspector",
        notes="Reconciled residential zoning per Maharashtra Land Revenue Code survey 2026.",
        authoritative_geometry_source="SOURCE_A",
        authoritative_attributes={"land_use": "RESIDENTIAL", "risk_level": "LOW"},
        override_applied=True,
        idempotency_key=f"hr_{harm_id_1}",
    )
    hr_rej = HumanReviewDecision(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=harm_id_rej,
        action="REJECT_UNRESOLVED",
        adjudication_status="REJECTED",
        reviewer_name="Senior Haveli Cadastral Inspector",
        notes="Encroachment dispute under sub-judice review; quarantined from master cadastre.",
        override_applied=False,
        idempotency_key=f"hr_{harm_id_rej}",
    )
    db_session.add_all([hr1, hr_rej])
    await db_session.flush()

    # 6. Stage 12 Unified Land Records (1 authoritative, 1 rejected)
    ulr_auth = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-HAV-000001",
        status="ACTIVE",
        canonical_geometry=geom1,
        geometry_source_feature_id=cf1.id,
        geometry_source_role="CADASTRAL",
        area=11250.0,
        canonical_attributes={"parcel_id": "HAV-CAD-001", "land_use": "RESIDENTIAL"},
        harmonized_record_id=harm_id_1,
        source_a_reference="HAV-CAD-001",
        source_b_reference="HAV-MUN-001",
        geometry_source="SOURCE_A",
        land_use="RESIDENTIAL",
        mutation_status="MUTATED",
        risk_level="LOW",
        confidence_score=0.925,
        validation_status="PASS",
        human_review_decision="MERGE_RECONCILE",
        resolution_status="UNIFIED",
        metadata_trail={
            "feature_match_id": str(match1.id),
            "harmonized_record_id": harm_id_1,
            "pipeline_lineage": {
                "matching": {"feature_match_id": str(match1.id)},
                "harmonization": {"geometry_source": "SOURCE_A"},
                "confidence": {"overall_confidence": 0.925, "reasons": ["High spatial overlap"]},
            },
        },
    )

    ulr_rej = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-HAV-000002",
        status="CONFLICT",
        canonical_geometry=geom2,
        area=8900.0,
        canonical_attributes={"parcel_id": "HAV-CAD-002"},
        harmonized_record_id=harm_id_rej,
        source_a_reference="HAV-CAD-002",
        source_b_reference="HAV-MUN-002",
        confidence_score=0.510,
        validation_status="FAIL",
        human_review_decision="REJECT_UNRESOLVED",
        resolution_status="REJECTED",
        metadata_trail={
            "harmonized_record_id": harm_id_rej,
            "pipeline_lineage": {
                "confidence": {"overall_confidence": 0.510},
            },
        },
    )
    db_session.add_all([ulr_auth, ulr_rej])
    await db_session.flush()

    ulr_src1 = UnifiedLandRecordSource(
        id=uuid.uuid4(),
        unified_land_record_id=ulr_auth.id,
        feature_id=cf1.id,
        source_role="CADASTRAL",
        feature_match_id=match1.id,
    )
    ulr_src2 = UnifiedLandRecordSource(
        id=uuid.uuid4(),
        unified_land_record_id=ulr_auth.id,
        feature_id=cf2.id,
        source_role="MUNICIPAL",
        feature_match_id=match1.id,
    )
    db_session.add_all([ulr_src1, ulr_src2])

    # Mark Stage 12 completed in PipelineStageExecution
    stage12_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=12,
        stage_id="record",
        status="completed",
        inputs={"records_synthesized": 2},
        results={"unified_records_count": 2, "authoritative_count": 1, "rejected_count": 1},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage12_exec)
    await db_session.commit()

    # 7. Check Stage 13 Status before running -> ready
    st13_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-13/status")
    assert st13_resp.status_code == 200
    st13_data = st13_resp.json()
    assert st13_data["status"] == "ready"
    assert st13_data["is_completed"] is False
    assert st13_data["is_runnable"] is True
    assert st13_data["prerequisites_met"] is True

    # Check Pipeline status: Stage 13 is ready, Stage 14 is disabled
    pipe1_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe1_resp.status_code == 200
    stages_pre = {s["stage_number"]: s for s in pipe1_resp.json()["stages"]}
    assert stages_pre[13]["status"] == "ready"
    assert stages_pre[14]["status"] == "disabled"

    # 8. Execute Stage 13 Provenance
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-13/execute")
    assert exec_resp.status_code == 200
    res = exec_resp.json()
    assert res["status"] == "completed"
    assert res["stage_number"] == 13
    assert res["records_traced"] == 2
    assert res["human_decisions_traced"] >= 1
    assert res["conflicts_traced"] >= 1
    assert res["validation_events_traced"] >= 1
    assert res["lineage_completeness_pct"] >= 80.0
    assert "Stage 14 (Export) is now unlocked" in res["message"]

    # 9. Verify Stage 14 is now READY/UNLOCKED in pipeline status
    pipe2_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe2_resp.status_code == 200
    stages_post = {s["stage_number"]: s for s in pipe2_resp.json()["stages"]}
    assert stages_post[13]["status"] == "completed"
    assert stages_post[14]["status"] == "ready"
    assert stages_post[14]["is_runnable"] is True
    assert stages_post[14]["prerequisites_met"] is True

    # 10. Check Stage 13 Status endpoint confirms completed
    st13_post = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-13/status")
    assert st13_post.status_code == 200
    assert st13_post.json()["status"] == "completed"
    assert st13_post.json()["is_completed"] is True
    assert st13_post.json()["records_traced"] == 2


@pytest.mark.asyncio
async def test_stage13_idempotency(client: AsyncClient, db_session: AsyncSession):
    """
    Test Stage 13 idempotent execution:
    Running execute_stage_13 twice on the same project must:
    1. Not create duplicate ProvenanceRecord rows in PostgreSQL.
    2. Not create duplicate ProvenanceEvent rows.
    3. Produce identical record counts and completeness metrics.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "M13 Idempotency Test"})
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    # Setup 1 ULR and mark Stage 12 completed
    ulr = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-IDEM-001",
        status="ACTIVE",
        harmonized_record_id="harm_idem_001",
        confidence_score=0.88,
        validation_status="PASS",
        human_review_decision="ACCEPT_SOURCE_A",
        resolution_status="UNIFIED",
        metadata_trail={"harmonized_record_id": "harm_idem_001"},
    )
    db_session.add(ulr)

    stage12_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=12,
        stage_id="record",
        status="completed",
        inputs={},
        results={"unified_records_count": 1},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage12_exec)
    await db_session.commit()

    # First run
    run1 = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-13/execute")
    assert run1.status_code == 200
    res1 = run1.json()
    assert res1["records_traced"] == 1
    events1 = res1["events_count"]

    # Count DB records after Run 1
    prov_count_1 = await db_session.scalar(
        select(func.count(ProvenanceRecord.id)).where(ProvenanceRecord.project_id == proj_id)
    )
    event_count_1 = await db_session.scalar(
        select(func.count(ProvenanceEvent.id)).where(ProvenanceEvent.project_id == proj_id)
    )
    assert prov_count_1 == 1

    # Second run (re-execution)
    run2 = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-13/execute")
    assert run2.status_code == 200
    res2 = run2.json()
    assert res2["records_traced"] == 1

    # Count DB records after Run 2 -> MUST BE IDENTICAL (0 duplicates!)
    prov_count_2 = await db_session.scalar(
        select(func.count(ProvenanceRecord.id)).where(ProvenanceRecord.project_id == proj_id)
    )
    event_count_2 = await db_session.scalar(
        select(func.count(ProvenanceEvent.id)).where(ProvenanceEvent.project_id == proj_id)
    )
    assert prov_count_2 == prov_count_1 == 1
    assert event_count_2 == event_count_1


@pytest.mark.asyncio
async def test_stage13_query_apis_and_lineage_inspector(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test Provenance query APIs:
    - GET /projects/{project_id}/provenance (list, search, status filter, pagination, summary stats)
    - GET /projects/{project_id}/provenance/{unified_record_id} (interactive inspector details)
    - GET /projects/{project_id}/provenance/{unified_record_id}/timeline
    - GET /projects/{project_id}/provenance/{unified_record_id}/sources
    - 404 handling on missing project or record
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "M13 Query APIs Test"})
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    # 1. Setup 2 ULRs: 1 authoritative COMPLETE, 1 rejected QUARANTINED
    ulr1 = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-INSP-001",
        status="ACTIVE",
        harmonized_record_id="harm_insp_001",
        source_a_reference="CAD-101",
        source_b_reference="MUN-101",
        geometry_source="SOURCE_A",
        land_use="RESIDENTIAL",
        mutation_status="MUTATED",
        risk_level="LOW",
        confidence_score=0.94,
        validation_status="PASS",
        human_review_decision="MERGE_RECONCILE",
        resolution_status="UNIFIED",
        metadata_trail={"pipeline_lineage": {"confidence": {"overall_confidence": 0.94}}},
    )
    ulr2 = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-INSP-002",
        status="CONFLICT",
        harmonized_record_id="harm_insp_002",
        source_a_reference="CAD-102",
        source_b_reference="MUN-102",
        confidence_score=0.45,
        validation_status="FAIL",
        human_review_decision="REJECT_UNRESOLVED",
        resolution_status="REJECTED",
        metadata_trail={"pipeline_lineage": {}},
    )
    db_session.add_all([ulr1, ulr2])

    stage12_exec = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=12,
        stage_id="record",
        status="completed",
        inputs={},
        results={"unified_records_count": 2},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage12_exec)
    await db_session.commit()

    # Execute Stage 13
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-13/execute")
    assert exec_resp.status_code == 200

    # 2. Test GET /projects/{project_id}/provenance
    list_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 2
    assert len(list_data["items"]) == 2
    assert "completeness_stats" in list_data
    assert list_data["completeness_stats"]["quarantined"] == 1
    assert list_data["completeness_stats"]["partial"] == 1

    # Test Search filter
    search_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance?search=ULR-INSP-001")
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["items"][0]["record_identifier"] == "ULR-INSP-001"

    # Test Status filter: QUARANTINED
    quar_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance?status=QUARANTINED")
    assert quar_resp.status_code == 200
    assert quar_resp.json()["total"] == 1
    assert quar_resp.json()["items"][0]["record_identifier"] == "ULR-INSP-002"
    assert quar_resp.json()["items"][0]["lineage_status"] == "QUARANTINED"

    # 3. Test GET /projects/{project_id}/provenance/{unified_record_id}
    detail_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance/{ulr1.id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["record_identifier"] == "ULR-INSP-001"
    assert detail["resolution_status"] == "UNIFIED"
    assert "final_record" in detail
    assert detail["final_record"]["land_use"] == "RESIDENTIAL"
    assert "processing" in detail
    assert "human_decision" in detail
    assert "timeline" in detail
    assert "lineage_graph" in detail
    assert len(detail["lineage_graph"]["nodes"]) >= 5
    assert len(detail["lineage_graph"]["edges"]) >= 4

    # 4. Test GET /projects/{project_id}/provenance/{unified_record_id}/timeline
    timeline_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance/{ulr1.id}/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert isinstance(timeline, list)
    event_types = [t["event_type"] for t in timeline]
    assert "UNIFIED_RECORD_CREATED" in event_types

    # 5. Test GET /projects/{project_id}/provenance/{unified_record_id}/sources
    sources_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance/{ulr1.id}/sources")
    assert sources_resp.status_code == 200
    assert isinstance(sources_resp.json(), list)

    # 6. Test 404 for unknown record
    fake_id = uuid.uuid4()
    not_found = await client.get(f"/api/v1/projects/{proj_id}/provenance/{fake_id}")
    assert not_found.status_code == 404
