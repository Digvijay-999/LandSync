import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.matching import FeatureMatch, MatchRun, MatchReview


def get_err_msg(resp) -> str:
    data = resp.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", ""))
        return str(data.get("detail", ""))
    return ""


@pytest.mark.asyncio
async def test_stage11_prerequisite_lock(client: AsyncClient):
    """
    Verify Stage 11 is locked / disabled when Stage 10 has not completed.
    API requests must reject access with clear 400 Bad Request error.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Lock Test Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # Check review summary before Stage 10
    sum_resp = await client.get(f"/api/v1/projects/{proj_id}/review-summary")
    assert sum_resp.status_code == 400
    assert "Stage 10 Confidence Scoring must be completed" in get_err_msg(sum_resp)

    # Check review queue before Stage 10
    queue_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue")
    assert queue_resp.status_code == 400

    # Pipeline status shows Stage 11 is disabled
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = {s["stage_number"]: s for s in pipe_resp.json()["stages"]}
    assert stages[11]["status"] == "disabled"
    assert stages[11]["is_runnable"] is False
    assert stages[12]["status"] == "disabled"


@pytest.mark.asyncio
async def test_stage11_human_review_workflow_and_adjudication(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Complete end-to-end test of Stage 11 Human Review:
    1. Queue retrieval and sorting (unresolved & critical first)
    2. Filtering by severity, bucket, validation status, adjudication status
    3. Mandatory note validation on Reject, Merge, and Critical overrides
    4. ACCEPT_SOURCE_A action with conflict resolution and provenance
    5. ACCEPT_SOURCE_B action
    6. MERGE_RECONCILE action with authoritative attribute persistence
    7. REJECT_UNRESOLVED action
    8. Deterministic stage completion rule enforcement (blocks premature unlock)
    9. Downstream Stage 12 unlocking when all mandatory items are resolved
    10. Re-adjudication idempotency
    """
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Pune Haveli Review Project"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])

    now = datetime.now(timezone.utc)
    sf1, cf1 = uuid.uuid4(), uuid.uuid4()
    sf2, cf2 = uuid.uuid4(), uuid.uuid4()
    sf3, cf3 = uuid.uuid4(), uuid.uuid4()

    rec1_id = f"{sf1}_{cf1}"
    rec2_id = f"{sf2}_{cf2}"
    rec3_id = f"{sf3}_{cf3}"

    # Setup mock Stage 10 execution
    mock_stage10_records = [
        {
            "id": rec1_id,
            "harmonized_record_id": rec1_id,
            "project_id": str(proj_id),
            "source_identifier": "CAD-101",
            "candidate_identifier": "MUN-101",
            "source_feature_id": str(sf1),
            "candidate_feature_id": str(cf1),
            "overall_confidence": 0.65,
            "confidence_bucket": "LOW",
            "bucket_label": "LOW / MANDATORY REVIEW",
            "review_status": "FLAGGED",
            "spatial_score": 0.70,
            "geometry_score": 0.70,
            "attribute_score": 0.50,
            "temporal_score": 0.80,
            "weights": {"spatial": 0.3, "geometry": 0.3, "attribute": 0.3, "temporal": 0.1},
            "contributions": {"spatial": 0.21, "geometry": 0.21, "attribute": 0.15, "temporal": 0.08},
            "is_ambiguous": False,
            "has_critical_conflicts": True,
            "critical_conflict_count": 1,
            "validation_status": "FAIL",
            "explanation": "Score capped at 0.78 due to critical conflict",
            "reasons": ["Unresolved critical conflict"],
        },
        {
            "id": rec2_id,
            "harmonized_record_id": rec2_id,
            "project_id": str(proj_id),
            "source_identifier": "CAD-102",
            "candidate_identifier": "MUN-102",
            "source_feature_id": str(sf2),
            "candidate_feature_id": str(cf2),
            "overall_confidence": 0.76,
            "confidence_bucket": "MEDIUM",
            "bucket_label": "MEDIUM / PENDING REVIEW",
            "review_status": "PENDING",
            "spatial_score": 0.80,
            "geometry_score": 0.80,
            "attribute_score": 0.70,
            "temporal_score": 0.80,
            "weights": {"spatial": 0.3, "geometry": 0.3, "attribute": 0.3, "temporal": 0.1},
            "contributions": {"spatial": 0.24, "geometry": 0.24, "attribute": 0.21, "temporal": 0.08},
            "is_ambiguous": False,
            "has_critical_conflicts": False,
            "critical_conflict_count": 0,
            "validation_status": "WARNING",
            "explanation": "Medium confidence",
            "reasons": ["Area discrepancy warning"],
        },
        {
            "id": rec3_id,
            "harmonized_record_id": rec3_id,
            "project_id": str(proj_id),
            "source_identifier": "CAD-103",
            "candidate_identifier": "MUN-103",
            "source_feature_id": str(sf3),
            "candidate_feature_id": str(cf3),
            "overall_confidence": 0.58,
            "confidence_bucket": "LOW",
            "bucket_label": "LOW / MANDATORY REVIEW",
            "review_status": "FLAGGED",
            "spatial_score": 0.60,
            "geometry_score": 0.60,
            "attribute_score": 0.50,
            "temporal_score": 0.80,
            "weights": {"spatial": 0.3, "geometry": 0.3, "attribute": 0.3, "temporal": 0.1},
            "contributions": {"spatial": 0.18, "geometry": 0.18, "attribute": 0.15, "temporal": 0.08},
            "is_ambiguous": False,
            "has_critical_conflicts": False,
            "critical_conflict_count": 0,
            "validation_status": "PASS",
            "explanation": "Low confidence",
            "reasons": ["Boundary mismatch"],
        },
    ]

    stage10 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=10,
        stage_id="confidence",
        status="completed",
        inputs={},
        results={
            "records_scored": 3,
            "high_count": 0,
            "medium_count": 1,
            "low_count": 2,
            "review_required_count": 3,
            "average_confidence": 0.6633,
            "records_preview": mock_stage10_records,
        },
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage10)

    # Setup mock Stage 08 GeospatialConflict on Record 1
    conf1 = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=rec1_id,
        conflict_type="AREA_DISCREPANCY",
        category="GEOMETRY",
        severity="CRITICAL",
        severity_reason="Area divergence 28.5%",
        detection_rule="Rule_AreaTolerance",
        status="OPEN",
        source_a="Cadastral",
        source_b="Municipal",
        field_name="area",
        value_a="1000.0",
        value_b="1285.0",
        explanation="Area exceeds tolerance",
        idempotency_key=f"{proj_id}_{rec1_id}_area",
    )
    # High conflict on Record 2
    conf2 = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=rec2_id,
        conflict_type="LAND_USE_CONFLICT",
        category="SEMANTIC",
        severity="HIGH",
        severity_reason="Land use mismatch",
        detection_rule="Rule_LandUse",
        status="OPEN",
        source_a="Cadastral",
        source_b="Municipal",
        field_name="land_use",
        value_a="Agricultural",
        value_b="Commercial",
        explanation="Land use classification mismatch",
        idempotency_key=f"{proj_id}_{rec2_id}_lu",
    )
    db_session.add(conf1)
    db_session.add(conf2)

    # Setup mock Stage 09 ValidationResult
    val1 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=rec1_id,
        source_identifier="CAD-101",
        candidate_identifier="MUN-101",
        overall_status="FAIL",
        failure_reasons=["Severe area divergence > 15%"],
        warning_reasons=[],
        idempotency_key=f"{proj_id}_{rec1_id}_val",
    )
    val2 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=rec2_id,
        source_identifier="CAD-102",
        candidate_identifier="MUN-102",
        overall_status="WARNING",
        failure_reasons=[],
        warning_reasons=["Minor area divergence"],
        idempotency_key=f"{proj_id}_{rec2_id}_val",
    )
    db_session.add(val1)
    db_session.add(val2)
    await db_session.commit()

    # 2. Pipeline status check: Stage 11 should be 'ready', Stage 12 'disabled'
    p_status = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert p_status.status_code == 200
    st_map = {s["stage_number"]: s for s in p_status.json()["stages"]}
    assert st_map[10]["status"] == "completed"
    assert st_map[11]["status"] == "ready"
    assert st_map[11]["is_runnable"] is True
    assert st_map[12]["status"] == "disabled"
    assert st_map[12]["is_runnable"] is False

    # 3. Retrieve Review Summary
    summary_resp = await client.get(f"/api/v1/projects/{proj_id}/review-summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_review_items"] == 3
    assert summary["unresolved_count"] == 3
    assert summary["resolved_count"] == 0
    assert summary["critical_count"] == 1
    assert summary["high_conflict_count"] == 1
    assert summary["stage_status"] == "ready"
    assert summary["is_completed"] is False

    # 4. Retrieve Review Queue with sorting & filters
    queue_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue")
    assert queue_resp.status_code == 200
    q_data = queue_resp.json()
    assert q_data["total"] == 3
    # Record 1 (CRITICAL) must be first
    assert q_data["items"][0]["harmonized_record_id"] == rec1_id
    assert q_data["items"][0]["has_critical_conflicts"] is True
    assert q_data["items"][0]["adjudication_status"] == "UNRESOLVED"

    # Filter by severity CRITICAL
    crit_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue?severity=CRITICAL")
    assert crit_resp.status_code == 200
    assert crit_resp.json()["total"] == 1
    assert crit_resp.json()["items"][0]["harmonized_record_id"] == rec1_id

    # Filter by validation status FAIL
    fail_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue?validation_status=FAIL")
    assert fail_resp.status_code == 200
    assert fail_resp.json()["total"] == 1

    # Search filter
    search_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue?search=CAD-102")
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1

    # 5. Detail inspection endpoint
    detail_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue/{rec1_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["harmonized_record_id"] == rec1_id
    assert len(detail["conflicts"]) == 1
    assert detail["validation_status"] == "FAIL"

    # 6. Test Mandatory Note Validation
    # Reject without note should fail (422)
    bad_reject = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec3_id}/adjudicate",
        json={"action": "REJECT_UNRESOLVED", "notes": ""},
    )
    assert bad_reject.status_code == 422
    assert "mandatory" in get_err_msg(bad_reject).lower()

    # Overriding critical conflict on Record 1 without note should fail (422)
    bad_override = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec1_id}/adjudicate",
        json={"action": "ACCEPT_SOURCE_A", "notes": "  "},
    )
    assert bad_override.status_code == 422
    assert "mandatory" in get_err_msg(bad_override).lower()

    # Merge without authoritative_geometry_source should fail (422)
    bad_merge = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec2_id}/adjudicate",
        json={"action": "MERGE_RECONCILE", "notes": "Merge notes", "authoritative_geometry_source": None},
    )
    assert bad_merge.status_code == 422
    assert "authoritative_geometry_source" in get_err_msg(bad_merge)

    # Attempting to finalize Stage 11 when unresolved items remain should fail (400)
    premature_finalize = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-11/execute")
    assert premature_finalize.status_code == 400
    assert "still require mandatory human adjudication" in get_err_msg(premature_finalize)

    # 7. Adjudicate Record 1: ACCEPT_SOURCE_A (with override note)
    adj1 = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec1_id}/adjudicate",
        json={
            "action": "ACCEPT_SOURCE_A",
            "reviewer_name": "Senior Cadastral Officer",
            "notes": "Verified against 2026 ground DGPS traverse; Cadastral boundary is authentic.",
        },
    )
    assert adj1.status_code == 200
    res1 = adj1.json()
    assert res1["success"] is True
    assert res1["status"] == "RESOLVED"
    assert res1["decision"]["override_applied"] is True
    assert res1["stage_status"] == "running"  # 1/3 resolved -> stage is running

    # Verify conflict status on Record 1 updated to RESOLVED
    conf1_db = (
        await db_session.execute(
            select(GeospatialConflict).where(GeospatialConflict.harmonized_record_id == rec1_id)
        )
    ).scalar_one()
    assert conf1_db.status == "RESOLVED"

    # Verify ProvenanceEvent for override
    prov1 = (
        await db_session.execute(
            select(ProvenanceEvent).where(
                ProvenanceEvent.project_id == proj_id,
                ProvenanceEvent.event_type == "HUMAN_REVIEW_OVERRIDE",
            )
        )
    ).scalar_one_or_none()
    assert prov1 is not None

    # 8. Adjudicate Record 2: MERGE_RECONCILE
    adj2 = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec2_id}/adjudicate",
        json={
            "action": "MERGE_RECONCILE",
            "reviewer_name": "Municipal Surveyor",
            "notes": "Adopting Cadastral geometry with Municipal updated commercial zoning.",
            "authoritative_geometry_source": "SOURCE_A",
            "authoritative_attributes": {
                "land_use": "Commercial",
                "mutation_status": "APPROVED",
                "risk_level": "LOW",
            },
        },
    )
    assert adj2.status_code == 200
    res2 = adj2.json()
    assert res2["action"] == "MERGE_RECONCILE"
    assert res2["decision"]["authoritative_geometry_source"] == "SOURCE_A"
    assert res2["decision"]["authoritative_attributes"]["land_use"] == "Commercial"

    # 9. Adjudicate Record 3: REJECT_UNRESOLVED
    adj3 = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec3_id}/adjudicate",
        json={
            "action": "REJECT_UNRESOLVED",
            "reviewer_name": "Lead GIS Adjudicator",
            "notes": "Candidate municipal feature is an entirely different parcel; rejected from matching.",
        },
    )
    assert adj3.status_code == 200
    res3 = adj3.json()
    assert res3["action"] == "REJECT_UNRESOLVED"
    assert res3["status"] == "REJECTED"
    assert res3["is_stage_completed"] is True
    assert res3["stage_status"] == "completed"

    # 10. Check Stage 11 Completion & Stage 12 Downstream Unlocking
    summary_final = await client.get(f"/api/v1/projects/{proj_id}/review-summary")
    assert summary_final.status_code == 200
    sum_data = summary_final.json()
    assert sum_data["unresolved_count"] == 0
    assert sum_data["resolved_count"] == 3
    assert sum_data["is_completed"] is True
    assert sum_data["stage_status"] == "completed"
    assert sum_data["accept_source_a_count"] == 1
    assert sum_data["merged_count"] == 1
    assert sum_data["rejected_count"] == 1

    # Pipeline status check: Stage 11 completed, Stage 12 unlocked!
    p_status_after = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert p_status_after.status_code == 200
    st_map_after = {s["stage_number"]: s for s in p_status_after.json()["stages"]}
    assert st_map_after[11]["status"] == "completed"
    assert st_map_after[12]["status"] == "ready"
    assert st_map_after[12]["is_runnable"] is True

    # 11. Test Idempotency: re-submitting decision on Record 2 updates in place
    adj2_rerun = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/{rec2_id}/adjudicate",
        json={
            "action": "ACCEPT_SOURCE_B",
            "reviewer_name": "Municipal Surveyor",
            "notes": "Updated decision to adopt municipal survey directly.",
        },
    )
    assert adj2_rerun.status_code == 200
    assert adj2_rerun.json()["action"] == "ACCEPT_SOURCE_B"

    # Verify only 1 decision record per harmonized record in database
    dec_count = (
        await db_session.execute(
            select(HumanReviewDecision).where(
                HumanReviewDecision.project_id == proj_id,
                HumanReviewDecision.harmonized_record_id == rec2_id,
            )
        )
    ).scalars().all()
    assert len(dec_count) == 1


@pytest.mark.asyncio
async def test_stage11_invalid_decision_and_nonexistent_record(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test error handling:
    - Nonexistent record returns 404
    - Invalid action value returns 422
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Edge Cases Project"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    # Mock Stage 10 completed
    stage10 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=10,
        stage_id="confidence",
        status="completed",
        inputs={},
        results={
            "records_scored": 1,
            "records_preview": [
                {
                    "id": "rec_001",
                    "harmonized_record_id": "rec_001",
                    "source_identifier": "CAD-01",
                    "candidate_identifier": "MUN-01",
                    "overall_confidence": 0.65,
                    "confidence_bucket": "LOW",
                    "bucket_label": "LOW / MANDATORY REVIEW",
                    "review_status": "FLAGGED",
                    "has_critical_conflicts": False,
                    "validation_status": "PASS",
                }
            ],
        },
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage10)
    await db_session.commit()

    # Query nonexistent record detail -> 404
    missing_resp = await client.get(f"/api/v1/projects/{proj_id}/review-queue/nonexistent_record_xyz")
    assert missing_resp.status_code == 404

    # Submit invalid action -> 422
    bad_action_resp = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/rec_001/adjudicate",
        json={"action": "INVALID_ACTION_NAME", "notes": "Some notes"},
    )
    assert bad_action_resp.status_code == 422

    # Submit to nonexistent record -> 404
    missing_adj_resp = await client.post(
        f"/api/v1/projects/{proj_id}/review-queue/nonexistent_record_xyz/adjudicate",
        json={"action": "ACCEPT_SOURCE_A", "notes": "Some notes"},
    )
    assert missing_adj_resp.status_code == 404

