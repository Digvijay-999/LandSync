import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineStageExecution
from app.models.conflict import GeospatialConflict


@pytest.mark.asyncio
async def test_stage08_nonexistent_project(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/projects/{fake_id}/pipeline/stage-08/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_stage08_missing_stage07_prerequisite(client: AsyncClient):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 08 Prereq Test Project"},
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-08/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "Stage 07 Attribute/Geometry Harmonization must be completed" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stage08_empty_stage07_input(client: AsyncClient, db_session: AsyncSession):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 08 Empty Prereq Project"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])

    now = datetime.now(timezone.utc)
    stage7 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=7,
        stage_id="harmonization",
        status="completed",
        inputs={},
        results={"records_preview": []},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage7)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-08/execute",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage_number"] == 8
    assert data["records_scanned"] == 0
    assert data["conflicts_detected"] == 0
    assert data["status"] == "completed"

    # Verify pipeline status reflects Stage 08 completed and unlocks Stage 09
    status_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert status_resp.status_code == 200
    pipeline_data = status_resp.json()
    stage8 = next(s for s in pipeline_data["stages"] if s["stage_number"] == 8)
    assert stage8["status"] == "completed"

    stage9 = next(s for s in pipeline_data["stages"] if s["stage_number"] == 9)
    assert stage9["status"] == "ready"
    assert stage9["prerequisites_met"] is True


@pytest.mark.asyncio
async def test_stage08_conflict_detection_and_rules(client: AsyncClient, db_session: AsyncSession):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 08 Detection Test Project"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])

    sf_id1 = uuid.uuid4()
    cf_id1 = uuid.uuid4()
    sf_id2 = uuid.uuid4()
    cf_id2 = uuid.uuid4()

    mock_records_preview = [
        # Record 1: Critical Area Diff (1000 vs 1250 -> 20.0%), Critical Land Use (Agr vs Ind), Disputed Mutation, Critical Risk
        {
            "id": f"{sf_id1}_{cf_id1}",
            "source_identifier": "CAD-001",
            "candidate_identifier": "MUN-001",
            "source_survey_number": "SRV-101",
            "candidate_survey_number": "SRV-101-ALT",
            "authoritative_geometry_source": "Dataset A (CADASTRAL)",
            "geometry_status": "BOUNDARY_VARIANCE_RECONCILED",
            "source_area": 1000.0,
            "candidate_area": 1250.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 20.0,
            "source_land_use": "Agricultural Farming",
            "candidate_land_use": "Industrial MIDC Factory",
            "harmonized_land_use": "Agricultural Farming",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Disputed in Court",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low Risk",
            "candidate_risk_level": "Critical Flood Hazard",
            "harmonized_risk_level": "Critical Flood Hazard",
            "conflict_count": 5,
            "has_conflicts": True,
        },
        # Record 2: High Area Diff (1000 vs 1080 -> 7.4%), Commercial vs Residential (High), Approved vs Pending (High)
        {
            "id": f"{sf_id2}_{cf_id2}",
            "source_identifier": "CAD-002",
            "candidate_identifier": "MUN-002",
            "source_survey_number": "SRV-202",
            "candidate_survey_number": "SRV-202",
            "authoritative_geometry_source": "Dataset A (CADASTRAL)",
            "geometry_status": "CONGRUENT",
            "source_area": 1000.0,
            "candidate_area": 1080.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 7.4,
            "source_land_use": "Residential Housing",
            "candidate_land_use": "Commercial Retail Shops",
            "harmonized_land_use": "Commercial Retail Shops",
            "source_mutation_status": "Sanctioned Approved",
            "candidate_mutation_status": "Pending Verification",
            "harmonized_mutation_status": "Sanctioned Approved",
            "source_risk_level": "Medium Risk",
            "candidate_risk_level": "Medium Risk",
            "harmonized_risk_level": "Medium Risk",
            "conflict_count": 3,
            "has_conflicts": True,
        },
    ]

    now = datetime.now(timezone.utc)
    stage7 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=7,
        stage_id="harmonization",
        status="completed",
        inputs={},
        results={"records_preview": mock_records_preview},
        started_at=now,
        completed_at=now,
    )
    db_session.add(stage7)
    await db_session.commit()

    # 1. Execute Stage 08
    resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-08/execute",
        json={
            "area_low_threshold_pct": 2.0,
            "area_medium_threshold_pct": 5.0,
            "area_high_threshold_pct": 15.0,
            "include_geometry_metrics": False,
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()

    assert res_data["stage_number"] == 8
    assert res_data["records_scanned"] == 2
    assert res_data["conflicts_detected"] >= 7
    assert res_data["conflicts_created"] >= 7
    assert res_data["conflicts_updated"] == 0
    assert res_data["critical_count"] >= 3
    assert res_data["high_count"] >= 2

    # Check distinct conflict types generated
    types_detected = res_data["counts_by_type"]
    assert "AREA_DISCREPANCY" in types_detected
    assert "LAND_USE_CONFLICT" in types_detected
    assert "MUTATION_CONFLICT" in types_detected
    assert "RISK_CONFLICT" in types_detected
    assert "ATTRIBUTE_MISMATCH" in types_detected

    # 2. Idempotency test: Re-execute without changes
    resp_reexec = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-08/execute",
        json={},
    )
    assert resp_reexec.status_code == 200
    reexec_data = resp_reexec.json()
    assert reexec_data["conflicts_detected"] == res_data["conflicts_detected"]
    assert reexec_data["conflicts_created"] == 0
    assert reexec_data["conflicts_updated"] == res_data["conflicts_detected"]

    # 3. List conflicts with pagination & filters
    list_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts")
    assert list_resp.status_code == 200
    conflicts_data = list_resp.json()
    assert conflicts_data["total"] == res_data["conflicts_detected"]
    assert len(conflicts_data["items"]) == res_data["conflicts_detected"]

    # Filter by severity: CRITICAL
    crit_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts?severity=CRITICAL")
    assert crit_resp.status_code == 200
    crit_items = crit_resp.json()["items"]
    assert len(crit_items) == res_data["critical_count"]
    for c in crit_items:
        assert c["severity"] == "CRITICAL"

    # Filter by conflict_type: AREA_DISCREPANCY
    area_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts?conflict_type=AREA_DISCREPANCY")
    assert area_resp.status_code == 200
    area_items = area_resp.json()["items"]
    assert len(area_items) == 2
    for c in area_items:
        assert c["conflict_type"] == "AREA_DISCREPANCY"
        assert c["category"] == "GEOMETRY"

    # Filter by search keyword: SRV-101
    search_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts?search=SRV-101")
    assert search_resp.status_code == 200
    search_items = search_resp.json()["items"]
    assert len(search_items) >= 1

    # 4. Detail & Status updates
    target_conflict = conflicts_data["items"][0]
    conflict_id = target_conflict["id"]

    detail_resp = await client.get(f"/api/v1/conflicts/{conflict_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == conflict_id
    assert detail["detection_rule"] is not None
    assert detail["severity_reason"] is not None
    assert detail["status"] == "OPEN"

    # Status update: ACKNOWLEDGED
    patch_resp = await client.patch(
        f"/api/v1/conflicts/{conflict_id}",
        json={"status": "ACKNOWLEDGED", "notes": "Surveyor has verified variance in field inspection."},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["status"] == "ACKNOWLEDGED"
    assert len(updated["evidence"].get("status_history", [])) == 1
    assert updated["evidence"]["status_history"][0]["notes"] == "Surveyor has verified variance in field inspection."

    # Status update: RESOLVED
    patch_resp2 = await client.patch(
        f"/api/v1/conflicts/{conflict_id}",
        json={"status": "RESOLVED", "notes": "Resolved via field survey ground truth."},
    )
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["status"] == "RESOLVED"

    # Status update: DISMISSED
    patch_resp3 = await client.patch(
        f"/api/v1/conflicts/{conflict_id}",
        json={"status": "DISMISSED", "notes": "Dismissed as within statutory allowance."},
    )
    assert patch_resp3.status_code == 200
    assert patch_resp3.json()["status"] == "DISMISSED"

    # Invalid status update: returns 400
    patch_invalid = await client.patch(
        f"/api/v1/conflicts/{conflict_id}",
        json={"status": "INVALID_STATUS"},
    )
    assert patch_invalid.status_code == 400
