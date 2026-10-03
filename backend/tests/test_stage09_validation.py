import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineStageExecution
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult


@pytest.mark.asyncio
async def test_stage09_nonexistent_project(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/projects/{fake_id}/pipeline/stage-09/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_stage09_missing_stage07_prerequisite(client: AsyncClient):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 09 Prereq Test Project"},
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "Stage 07 Attribute/Geometry Harmonization must be completed" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stage09_empty_stage07_input(client: AsyncClient, db_session: AsyncSession):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 09 Empty Prereq Project"},
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
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={},
    )
    assert resp.status_code == 400
    assert "No harmonized records found" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stage09_validation_rules_and_execution(client: AsyncClient, db_session: AsyncSession):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 09 Full Validation Project"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])

    sf_id1 = uuid.uuid4()
    cf_id1 = uuid.uuid4()
    sf_id2 = uuid.uuid4()
    cf_id2 = uuid.uuid4()
    sf_id3 = uuid.uuid4()
    cf_id3 = uuid.uuid4()

    mock_records_preview = [
        # Record 1: PASS Record - Area discrepancy 1.5% <= 5%, valid semantics, no conflicts
        {
            "id": f"{sf_id1}_{cf_id1}",
            "source_identifier": "CAD-101",
            "candidate_identifier": "MUN-101",
            "source_survey_number": "SRV-101",
            "candidate_survey_number": "SRV-101",
            "authoritative_geometry_source": "Cadastral Layer (CADASTRAL)",
            "geometry_status": "CONGRUENT",
            "source_area": 1000.0,
            "candidate_area": 1015.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 1.5,
            "source_land_use": "Residential Housing",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low Risk",
            "candidate_risk_level": "Low Risk",
            "harmonized_risk_level": "Low Risk",
            "conflict_count": 0,
            "has_conflicts": False,
        },
        # Record 2: WARNING Record - Area discrepancy 8.5% (5-15%), Pending mutation, high conflict
        {
            "id": f"{sf_id2}_{cf_id2}",
            "source_identifier": "CAD-102",
            "candidate_identifier": "MUN-102",
            "source_survey_number": "SRV-102",
            "candidate_survey_number": "SRV-102",
            "authoritative_geometry_source": "Cadastral Layer (CADASTRAL)",
            "geometry_status": "BOUNDARY_VARIANCE_RECONCILED",
            "source_area": 1000.0,
            "candidate_area": 1085.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 8.5,
            "source_land_use": "Commercial Retail",
            "candidate_land_use": "Commercial",
            "harmonized_land_use": "Commercial",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Pending Verification",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Medium Risk",
            "candidate_risk_level": "Medium Risk",
            "harmonized_risk_level": "Medium Risk",
            "conflict_count": 1,
            "has_conflicts": True,
        },
        # Record 3: FAIL Record - Area discrepancy 25.0% (> 15%), Incompatible Land Use (Agricultural vs Industrial), Disputed Mutation, Critical Conflict
        {
            "id": f"{sf_id3}_{cf_id3}",
            "source_identifier": "CAD-103",
            "candidate_identifier": "MUN-103",
            "source_survey_number": "SRV-103",
            "candidate_survey_number": "SRV-103-DISP",
            "authoritative_geometry_source": "Cadastral Layer (CADASTRAL)",
            "geometry_status": "BOUNDARY_VARIANCE_RECONCILED",
            "source_area": 1000.0,
            "candidate_area": 1250.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 25.0,
            "source_land_use": "Agricultural Farming",
            "candidate_land_use": "Industrial MIDC Factory",
            "harmonized_land_use": "Agricultural Farming",
            "source_mutation_status": "Disputed Court Stay",
            "candidate_mutation_status": "Pending",
            "harmonized_mutation_status": "Disputed Court Stay",
            "source_risk_level": "Low",
            "candidate_risk_level": "Critical Hazard",
            "harmonized_risk_level": "Critical Hazard",
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

    # Add Stage 08 GeospatialConflict for Record 3
    conf_crit = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf_id3}_{cf_id3}",
        conflict_type="AREA_DISCREPANCY",
        category="GEOMETRY",
        severity="CRITICAL",
        severity_reason="Severe area divergence of 25.0%",
        detection_rule="RULE_AREA_DISCREPANCY",
        status="OPEN",
        source_a="Cadastral",
        source_b="Municipal",
        field_name="area",
        value_a="1000.0 m²",
        value_b="1250.0 m²",
        explanation="Area discrepancy 25.0% exceeds allowable threshold",
        idempotency_key=f"{proj_id}:{sf_id3}_{cf_id3}:AREA_DISCREPANCY",
    )
    # Add High conflict for Record 2
    conf_high = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf_id2}_{cf_id2}",
        conflict_type="MUTATION_CONFLICT",
        category="REGISTRY",
        severity="HIGH",
        severity_reason="Registry mutation status discrepancy",
        detection_rule="RULE_MUTATION_CONFLICT",
        status="OPEN",
        source_a="Cadastral",
        source_b="Municipal",
        field_name="mutation_status",
        value_a="Approved",
        value_b="Pending Verification",
        explanation="Registry mutation mismatch between sources",
        idempotency_key=f"{proj_id}:{sf_id2}_{cf_id2}:MUTATION_CONFLICT",
    )
    db_session.add(conf_crit)
    db_session.add(conf_high)
    await db_session.commit()

    # 1. Execute Stage 09 Validation
    exec_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={
            "area_tolerance_pct": 5.0,
            "area_warning_threshold_pct": 15.0,
            "check_topology": True,
            "check_semantics": True,
            "consume_conflicts": True,
        },
    )
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()
    assert res_data["stage_id"] == "validation"
    assert res_data["stage_number"] == 9
    assert res_data["records_validated"] == 3
    assert res_data["pass_count"] == 1
    assert res_data["warning_count"] == 1
    assert res_data["fail_count"] == 1
    assert res_data["area_failures_count"] >= 1
    assert res_data["conflict_failures_count"] >= 1
    assert res_data["results_created"] == 3
    assert res_data["results_updated"] == 0

    # 2. Idempotency test: Re-executing updates existing records
    exec_resp2 = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={},
    )
    assert exec_resp2.status_code == 200
    res_data2 = exec_resp2.json()
    assert res_data2["records_validated"] == 3
    assert res_data2["results_created"] == 0
    assert res_data2["results_updated"] == 3

    # 3. Retrieve Summary
    summary_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_validated"] == 3
    assert summary["pass_count"] == 1
    assert summary["warning_count"] == 1
    assert summary["fail_count"] == 1
    assert summary["counts_by_status"]["PASS"] == 1
    assert summary["counts_by_status"]["WARNING"] == 1
    assert summary["counts_by_status"]["FAIL"] == 1

    # 4. List Results with Pagination & Filtering
    list_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-results")
    assert list_resp.status_code == 200
    results_list = list_resp.json()
    assert results_list["total"] == 3
    assert len(results_list["items"]) == 3
    # FAIL should be first due to order_rank
    assert results_list["items"][0]["overall_status"] == "FAIL"

    # Filter by status: FAIL
    fail_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-results?status=FAIL")
    assert fail_resp.status_code == 200
    fail_items = fail_resp.json()["items"]
    assert len(fail_items) == 1
    assert fail_items[0]["overall_status"] == "FAIL"
    assert len(fail_items[0]["failure_reasons"]) > 0

    # Filter by category: AREA
    area_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-results?category=AREA")
    assert area_resp.status_code == 200
    assert len(area_resp.json()["items"]) >= 2  # Warning (8.5%) and Fail (25%)

    # Filter by search
    search_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-results?search=CAD-101")
    assert search_resp.status_code == 200
    assert len(search_resp.json()["items"]) == 1
    assert search_resp.json()["items"][0]["source_identifier"] == "CAD-101"
    assert search_resp.json()["items"][0]["overall_status"] == "PASS"

    # 5. Detail inspection endpoint
    target_result = fail_items[0]
    detail_resp = await client.get(f"/api/v1/validation-results/{target_result['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == target_result["id"]
    assert detail["overall_status"] == "FAIL"
    assert "area_metrics" in detail
    assert "geometry_metrics" in detail
    assert "topology_metrics" in detail
    assert "semantic_metrics" in detail
    assert "conflict_metrics" in detail

    # 6. Pipeline status check: Stage 09 should be completed, and Stage 10 available
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = pipe_resp.json()["stages"]
    st9 = next(s for s in stages if s["stage_number"] == 9)
    assert st9["status"] == "completed"
    assert st9["results_summary"] is not None

    st10 = next(s for s in stages if s["stage_number"] == 10)
    assert st10["status"] == "ready"
    assert st10["is_runnable"] is True


@pytest.mark.asyncio
async def test_stage09_geometry_and_semantic_edge_cases(client: AsyncClient, db_session: AsyncSession):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 09 Edge Cases Project"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])

    sf_id_null = uuid.uuid4()
    cf_id_null = uuid.uuid4()
    sf_id_no_id = uuid.uuid4()
    cf_id_no_id = uuid.uuid4()
    sf_id_resolved = uuid.uuid4()
    cf_id_resolved = uuid.uuid4()

    mock_records_preview = [
        # Case A: Missing survey number and Unknown identifier -> Semantic FAIL
        {
            "id": f"{sf_id_no_id}_{cf_id_no_id}",
            "source_identifier": "Unknown",
            "candidate_identifier": "Unknown",
            "source_survey_number": None,
            "candidate_survey_number": None,
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "CONGRUENT",
            "source_area": 500.0,
            "candidate_area": 500.0,
            "harmonized_area": 500.0,
            "area_discrepancy_pct": 0.0,
            "source_land_use": "Residential",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 0,
            "has_conflicts": False,
        },
        # Case B: Resolved conflict -> Should PASS conflict check!
        {
            "id": f"{sf_id_resolved}_{cf_id_resolved}",
            "source_identifier": "CAD-RES-1",
            "candidate_identifier": "MUN-RES-1",
            "source_survey_number": "SRV-999",
            "candidate_survey_number": "SRV-999",
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "CONGRUENT",
            "source_area": 800.0,
            "candidate_area": 805.0,
            "harmonized_area": 800.0,
            "area_discrepancy_pct": 0.6,
            "source_land_use": "Commercial",
            "candidate_land_use": "Commercial",
            "harmonized_land_use": "Commercial",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 1,
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

    # Add RESOLVED conflict for Case B
    conf_resolved = GeospatialConflict(
        id=uuid.uuid4(),
        project_id=proj_id,
        harmonized_record_id=f"{sf_id_resolved}_{cf_id_resolved}",
        conflict_type="LAND_USE_CONFLICT",
        category="SEMANTIC",
        severity="HIGH",
        severity_reason="Historical conflict now resolved",
        detection_rule="RULE_SEMANTIC_LAND_USE_DISAGREEMENT",
        status="RESOLVED",
        source_a="Cadastral",
        source_b="Municipal",
        field_name="land_use",
        value_a="Commercial",
        value_b="Commercial",
        explanation="Resolved during field adjudication",
        idempotency_key=f"{proj_id}:{sf_id_resolved}_{cf_id_resolved}:LAND_USE_CONFLICT",
    )
    db_session.add(conf_resolved)
    await db_session.commit()

    exec_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={},
    )
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()
    assert res_data["records_validated"] == 2
    # Case A failed semantics -> FAIL
    # Case B resolved conflict & valid -> PASS
    assert res_data["pass_count"] == 1
    assert res_data["fail_count"] == 1
    assert res_data["semantic_failures_count"] >= 1


@pytest.mark.asyncio
async def test_stage09_geometry_topology_failure_cases(client: AsyncClient, db_session: AsyncSession):
    """Explicitly verify invalid geometry, empty geometry, null geometry, and topology self-intersection."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Stage 09 Geometry & Topology Failures"},
    )
    proj_id = uuid.UUID(proj_resp.json()["id"])

    mock_records_preview = [
        # Record 1: Invalid geometry
        {
            "id": "rec_invalid_geom",
            "source_identifier": "CAD-INV",
            "candidate_identifier": "MUN-INV",
            "source_survey_number": "SRV-INV",
            "candidate_survey_number": "SRV-INV",
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "INVALID",
            "source_area": 1000.0,
            "candidate_area": 1000.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 0.0,
            "source_land_use": "Residential",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 0,
            "has_conflicts": False,
        },
        # Record 2: Empty geometry
        {
            "id": "rec_empty_geom",
            "source_identifier": "CAD-EMP",
            "candidate_identifier": "MUN-EMP",
            "source_survey_number": "SRV-EMP",
            "candidate_survey_number": "SRV-EMP",
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "EMPTY",
            "source_area": 1000.0,
            "candidate_area": 1000.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 0.0,
            "source_land_use": "Residential",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 0,
            "has_conflicts": False,
        },
        # Record 3: Null geometry
        {
            "id": "rec_null_geom",
            "source_identifier": "CAD-NUL",
            "candidate_identifier": "MUN-NUL",
            "source_survey_number": "SRV-NUL",
            "candidate_survey_number": "SRV-NUL",
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "NULL",
            "source_area": 1000.0,
            "candidate_area": 1000.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 0.0,
            "source_land_use": "Residential",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 0,
            "has_conflicts": False,
        },
        # Record 4: Topology failure (self-intersecting)
        {
            "id": "rec_self_intersect",
            "source_identifier": "CAD-TOPO",
            "candidate_identifier": "MUN-TOPO",
            "source_survey_number": "SRV-TOPO",
            "candidate_survey_number": "SRV-TOPO",
            "authoritative_geometry_source": "Cadastral Layer",
            "geometry_status": "SELF_INTERSECTING",
            "source_area": 1000.0,
            "candidate_area": 1000.0,
            "harmonized_area": 1000.0,
            "area_discrepancy_pct": 0.0,
            "source_land_use": "Residential",
            "candidate_land_use": "Residential",
            "harmonized_land_use": "Residential",
            "source_mutation_status": "Approved",
            "candidate_mutation_status": "Approved",
            "harmonized_mutation_status": "Approved",
            "source_risk_level": "Low",
            "candidate_risk_level": "Low",
            "harmonized_risk_level": "Low",
            "conflict_count": 0,
            "has_conflicts": False,
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

    exec_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/stage-09/execute",
        json={},
    )
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()
    assert res_data["records_validated"] == 4
    # All 4 records have geometry or topology defects -> FAIL
    assert res_data["fail_count"] == 4
    assert res_data["geometry_failures_count"] == 3  # INVALID, EMPTY, NULL
    assert res_data["topology_failures_count"] == 1  # SELF_INTERSECTING

    # Verify individual results via API
    list_resp = await client.get(f"/api/v1/projects/{proj_id}/validation-results")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 4

    rec_inv = next(i for i in items if i["candidate_identifier"] == "MUN-INV")
    assert rec_inv["geometry_validity_status"] == "FAIL"
    assert "INVALID" in rec_inv["failure_reasons"][0]

    rec_emp = next(i for i in items if i["candidate_identifier"] == "MUN-EMP")
    assert rec_emp["geometry_validity_status"] == "FAIL"
    assert rec_emp["geometry_metrics"]["is_empty"] is True

    rec_nul = next(i for i in items if i["candidate_identifier"] == "MUN-NUL")
    assert rec_nul["geometry_validity_status"] == "FAIL"
    assert rec_nul["geometry_metrics"]["is_null"] is True

    rec_topo = next(i for i in items if i["candidate_identifier"] == "MUN-TOPO")
    assert rec_topo["topology_status"] == "FAIL"
    assert rec_topo["topology_metrics"]["self_intersection"] is True


