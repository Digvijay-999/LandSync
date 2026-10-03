import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pipeline import PipelineStageExecution
from app.models.matching import FeatureMatch
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.provenance import ProvenanceEvent
from app.services.confidence.service import ConfidenceScoringService


# ---------------------------------------------------------------------------
# Unit Tests for Confidence Formula & Constraint Logic
# ---------------------------------------------------------------------------

def test_confidence_weighted_formula_calculation():
    """Verify multi-component confidence formula with default weights (0.30, 0.30, 0.30, 0.10)."""
    weights = {"spatial": 0.30, "geometry": 0.30, "attribute": 0.30, "temporal": 0.10}
    scores = {"spatial": 0.95, "geometry": 0.90, "attribute": 0.90, "temporal": 0.80}

    # Expected: (0.30 * 0.95) + (0.30 * 0.90) + (0.30 * 0.90) + (0.10 * 0.80)
    # = 0.285 + 0.27 + 0.27 + 0.08 = 0.905
    overall, contribs = ConfidenceScoringService.calculate_overall_confidence(
        spatial_score=scores["spatial"],
        geometry_score=scores["geometry"],
        attribute_score=scores["attribute"],
        temporal_score=scores["temporal"],
        weights=weights,
    )
    assert round(overall, 4) == 0.905
    assert round(contribs["spatial"], 4) == 0.285
    assert round(contribs["geometry"], 4) == 0.27
    assert round(contribs["attribute"], 4) == 0.27
    assert round(contribs["temporal"], 4) == 0.08


def test_confidence_weight_normalization():
    """Verify that unnormalized weights (e.g. 1.0, 1.0, 1.0, 1.0) normalize correctly to 0.25 each."""
    unnorm_weights = {"spatial": 2.0, "geometry": 2.0, "attribute": 2.0, "temporal": 2.0}
    norm_weights = ConfidenceScoringService.normalize_weights(unnorm_weights)

    assert norm_weights["spatial"] == 0.25
    assert norm_weights["geometry"] == 0.25
    assert norm_weights["attribute"] == 0.25
    assert norm_weights["temporal"] == 0.25

    overall, contribs = ConfidenceScoringService.calculate_overall_confidence(
        spatial_score=1.0,
        geometry_score=0.8,
        attribute_score=0.8,
        temporal_score=0.6,
        weights=norm_weights,
    )
    # (0.25*1.0) + (0.25*0.8) + (0.25*0.8) + (0.25*0.6) = 0.25 + 0.20 + 0.20 + 0.15 = 0.80
    assert round(overall, 4) == 0.80


def test_confidence_bucket_boundaries():
    """Verify bucket classification: >=0.90 -> HIGH, 0.70-0.89 -> MEDIUM, <0.70 -> LOW."""
    # High
    b_high, s_high = ConfidenceScoringService.assign_bucket(0.92, is_ambiguous=False)
    assert b_high == "HIGH"
    assert s_high in ["ACCEPTED", "AUTO_CONFIRMED"]

    # Edge High
    b_edge_high, s_edge_high = ConfidenceScoringService.assign_bucket(0.90, is_ambiguous=False)
    assert b_edge_high == "HIGH"
    assert s_edge_high in ["ACCEPTED", "AUTO_CONFIRMED"]

    # Medium
    b_med, s_med = ConfidenceScoringService.assign_bucket(0.85, is_ambiguous=False)
    assert b_med == "MEDIUM"
    assert s_med == "PENDING"

    # Edge Medium
    b_edge_med, s_edge_med = ConfidenceScoringService.assign_bucket(0.70, is_ambiguous=False)
    assert b_edge_med == "MEDIUM"
    assert s_edge_med == "PENDING"

    # Low
    b_low, s_low = ConfidenceScoringService.assign_bucket(0.69, is_ambiguous=False)
    assert b_low == "LOW"
    assert s_low in ["FLAGGED", "REQUIRES_REVIEW"]


def test_ambiguity_override():
    """Verify that ambiguous matches ALWAYS force AMBIGUOUS bucket and mandatory review."""
    # Even with a near-perfect score of 0.99, ambiguity forces review
    bucket, status = ConfidenceScoringService.assign_bucket(0.99, is_ambiguous=True)
    assert bucket == "AMBIGUOUS"
    assert status in ["FLAGGED", "REQUIRES_REVIEW"]


# ---------------------------------------------------------------------------
# Integration & API Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage10_nonexistent_project(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/projects/{fake_id}/pipeline/stage-10/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_stage10_missing_prerequisite(client: AsyncClient):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 10 Prereq Test Project"},
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-10/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "Stage 09 Validation" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stage10_execution_scoring_constraints_and_persistence(
    client: AsyncClient, db_session: AsyncSession
):
    """Test full Stage 10 execution against Stage 07, 08, and 09 records."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 10 Live Confidence Project"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    # 1. Setup mock Stage 07 execution with 4 records:
    # Record 1: Clear High candidate (95% spatial, 92% geom, 94% attr, 80% temp)
    # Record 2: Ambiguous candidate (92% scores, but is_ambiguous = True)
    # Record 3: High scores but has unresolved CRITICAL conflict from Stage 08
    # Record 4: Low score candidate (60% spatial, 55% geom, 50% attr, 40% temp)
    sf1, cf1 = uuid.uuid4(), uuid.uuid4()
    sf2, cf2 = uuid.uuid4(), uuid.uuid4()
    sf3, cf3 = uuid.uuid4(), uuid.uuid4()
    sf4, cf4 = uuid.uuid4(), uuid.uuid4()

    stage07_records = [
        {
            "id": f"{sf1}_{cf1}",
            "source_feature_id": str(sf1),
            "candidate_feature_id": str(cf1),
            "source_identifier": "CAD-001",
            "candidate_identifier": "REV-001",
            "source_survey_number": "SRV-101",
            "candidate_survey_number": "SRV-101",
            "spatial_score": 0.95,
            "geometry_score": 0.92,
            "attribute_score": 0.94,
            "temporal_score": 0.80,
            "is_ambiguous": False,
        },
        {
            "id": f"{sf2}_{cf2}",
            "source_feature_id": str(sf2),
            "candidate_feature_id": str(cf2),
            "source_identifier": "CAD-002",
            "candidate_identifier": "REV-002",
            "source_survey_number": "SRV-102",
            "candidate_survey_number": "SRV-102",
            "spatial_score": 0.92,
            "geometry_score": 0.90,
            "attribute_score": 0.91,
            "temporal_score": 0.85,
            "is_ambiguous": True,  # Ambiguous!
        },
        {
            "id": f"{sf3}_{cf3}",
            "source_feature_id": str(sf3),
            "candidate_feature_id": str(cf3),
            "source_identifier": "CAD-003",
            "candidate_identifier": "REV-003",
            "source_survey_number": "SRV-103",
            "candidate_survey_number": "SRV-103",
            "spatial_score": 0.96,
            "geometry_score": 0.94,
            "attribute_score": 0.95,
            "temporal_score": 0.90,
            "is_ambiguous": False,
        },
        {
            "id": f"{sf4}_{cf4}",
            "source_feature_id": str(sf4),
            "candidate_feature_id": str(cf4),
            "source_identifier": "CAD-004",
            "candidate_identifier": "REV-004",
            "source_survey_number": "SRV-104",
            "candidate_survey_number": "SRV-104_DIFF",
            "spatial_score": 0.60,
            "geometry_score": 0.55,
            "attribute_score": 0.50,
            "temporal_score": 0.40,
            "is_ambiguous": False,
        },
    ]

    stage07 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=7,
        stage_id="harmonization",
        status="completed",
        inputs={},
        results={"records_preview": stage07_records},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage07)

    # 2. Setup mock Stage 08 Critical Conflict on Record 3
    crit_conflict = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf3}_{cf3}",
        conflict_type="OWNER_MISMATCH_DISPUTE",
        category="ATTRIBUTE",
        severity="CRITICAL",
        source_a="Cadastral",
        source_b="Revenue",
        field_name="owner_name",
        status="UNRESOLVED",
        detection_rule="Rule_OwnerMismatch",
        explanation="Conflicting ownership deed found between Cadastral and Revenue records",
        idempotency_key=f"{proj_id}_{sf3}_{cf3}_owner",
    )
    db_session.add(crit_conflict)

    # 3. Setup mock Stage 09 Validation Results
    val1 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf1}_{cf1}",
        source_identifier="CAD-001",
        candidate_identifier="REV-001",
        overall_status="PASS",
        idempotency_key=f"{proj_id}_{sf1}_{cf1}_1",
    )
    val2 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf2}_{cf2}",
        source_identifier="CAD-002",
        candidate_identifier="REV-002",
        overall_status="PASS",
        idempotency_key=f"{proj_id}_{sf2}_{cf2}_1",
    )
    val3 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf3}_{cf3}",
        source_identifier="CAD-003",
        candidate_identifier="REV-003",
        overall_status="WARNING",
        idempotency_key=f"{proj_id}_{sf3}_{cf3}_1",
    )
    val4 = ValidationResult(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf4}_{cf4}",
        source_identifier="CAD-004",
        candidate_identifier="REV-004",
        overall_status="FAIL",
        idempotency_key=f"{proj_id}_{sf4}_{cf4}_1",
    )
    db_session.add_all([val1, val2, val3, val4])

    stage09 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=9,
        stage_id="validation",
        status="completed",
        inputs={},
        results={"records_validated": 4, "pass_count": 2, "warning_count": 1, "fail_count": 1},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage09)
    await db_session.commit()

    # Check pipeline status before Stage 10: Stage 10 should be ready, Stage 11 should be disabled
    status_resp_before = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert status_resp_before.status_code == 200
    s_stages = {s["stage_number"]: s for s in status_resp_before.json()["stages"]}
    assert s_stages[10]["status"] == "ready"
    assert s_stages[10]["is_runnable"] is True
    assert s_stages[11]["status"] == "disabled"
    assert s_stages[11]["is_runnable"] is False

    # 4. Execute Stage 10 Confidence Scoring
    exec_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-10/execute",
        json={
            "spatial_weight": 0.30,
            "geometry_weight": 0.30,
            "attribute_weight": 0.30,
            "temporal_weight": 0.10,
            "enforce_validation_constraints": True,
            "enforce_conflict_constraints": True,
        },
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()

    assert data["stage_number"] == 10
    assert data["stage_id"] == "confidence"
    assert data["status"] == "completed"
    assert data["records_scored"] == 4

    # Record 1: HIGH / AUTO_CONFIRMED
    assert data["high_count"] == 1
    assert data["auto_confirmed_count"] == 1

    # Record 2: AMBIGUOUS (override)
    assert data["ambiguous_count"] == 1

    # Record 3: Capped at <= 0.78 due to critical conflict -> FLAGGED / Review Req.
    # Record 4: LOW (< 0.70)
    assert data["low_count"] >= 1
    assert data["review_required_count"] >= 3

    # 5. Verify Database Persistence of PipelineStageExecution
    stage10_exec = (
        await db_session.execute(
            select(PipelineStageExecution).where(
                PipelineStageExecution.project_id == proj_id,
                PipelineStageExecution.stage_number == 10,
            )
        )
    ).scalar_one_or_none()
    assert stage10_exec is not None
    assert stage10_exec.status == "completed"
    assert stage10_exec.results["records_scored"] == 4

    # 6. Verify Provenance Audit Event Creation
    prov_event = (
        await db_session.execute(
            select(ProvenanceEvent).where(
                ProvenanceEvent.project_id == proj_id,
                ProvenanceEvent.event_type == "CONFIDENCE_SCORING_EXECUTED",
            )
        )
    ).scalar_one_or_none()
    assert prov_event is not None
    assert prov_event.source_type == "PIPELINE_STAGE_10"
    assert prov_event.event_type == "CONFIDENCE_SCORING_EXECUTED"

    # 7. Verify API Summary Endpoint
    summary_resp = await client.get(f"/api/v1/projects/{proj_id}/confidence-summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()
    assert summary_data["total_records_scored"] == 4
    assert summary_data["high_count"] == 1
    assert summary_data["ambiguous_count"] == 1
    assert summary_data["average_confidence"] > 0

    # 8. Verify API Results List & Filtering
    # Filter by bucket HIGH
    list_high = await client.get(
        f"/api/v1/projects/{proj_id}/confidence-results",
        params={"bucket": "HIGH"},
    )
    assert list_high.status_code == 200
    assert list_high.json()["total"] == 1
    assert list_high.json()["items"][0]["source_identifier"] == "CAD-001"
    assert list_high.json()["items"][0]["confidence_bucket"] == "HIGH"
    assert list_high.json()["items"][0]["review_status"] in ["ACCEPTED", "AUTO_CONFIRMED"]

    # Filter by bucket AMBIGUOUS
    list_amb = await client.get(
        f"/api/v1/projects/{proj_id}/confidence-results",
        params={"bucket": "AMBIGUOUS"},
    )
    assert list_amb.status_code == 200
    assert list_amb.json()["total"] == 1
    assert list_amb.json()["items"][0]["source_identifier"] == "CAD-002"
    assert list_amb.json()["items"][0]["is_ambiguous"] is True

    # Search filter
    search_resp = await client.get(
        f"/api/v1/projects/{proj_id}/confidence-results",
        params={"search": "CAD-003"},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1
    rec3 = search_resp.json()["items"][0]
    # Record 3 had critical conflict -> confidence capped <= 0.78 and FLAGGED
    assert rec3["critical_conflict_count"] == 1
    assert rec3["overall_confidence"] <= 0.78
    assert rec3["review_status"] == "FLAGGED"

    # 9. Verify Detail Endpoint
    rec1_id = list_high.json()["items"][0]["id"]
    detail_resp = await client.get(f"/api/v1/confidence-results/{rec1_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == rec1_id
    assert "spatial" in detail["weights"]
    assert "spatial" in detail["contributions"]
    assert len(detail["reasons"]) > 0

    # 10. Verify Downstream Stage 11 Unlocking
    status_resp_after = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert status_resp_after.status_code == 200
    stages_after = {s["stage_number"]: s for s in status_resp_after.json()["stages"]}
    assert stages_after[10]["status"] == "completed"
    assert stages_after[11]["status"] == "ready"
    assert stages_after[11]["prerequisites_met"] is True

    # 11. Verify Re-run Idempotency (does not duplicate records)
    rerun_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-10/execute",
        json={"spatial_weight": 0.40, "geometry_weight": 0.30, "attribute_weight": 0.20, "temporal_weight": 0.10},
    )
    assert rerun_resp.status_code == 200
    rerun_data = rerun_resp.json()
    assert rerun_data["records_scored"] == 4

    # Check there is still only one PipelineStageExecution for stage 10
    stage10_count = (
        await db_session.execute(
            select(PipelineStageExecution).where(
                PipelineStageExecution.project_id == proj_id,
                PipelineStageExecution.stage_number == 10,
            )
        )
    ).scalars().all()
    assert len(stage10_count) == 1
