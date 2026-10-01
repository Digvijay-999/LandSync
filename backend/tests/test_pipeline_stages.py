import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pipeline_status_not_found(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/projects/{fake_id}/pipeline/status")
    assert resp.status_code == 404
    assert f"Project with ID '{fake_id}' not found" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_pipeline_status_empty_project(client: AsyncClient):
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Pipeline Test Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Fetch pipeline status
    status_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["project_id"] == proj_id
    assert data["dataset_count"] == 0
    assert len(data["stages"]) == 14

    # Stage 01: Ingestion
    stage1 = data["stages"][0]
    assert stage1["stage_number"] == 1
    assert stage1["stage_id"] == "ingestion"
    assert stage1["status"] == "ready"
    assert stage1["is_runnable"] is True

    # Stage 05: Candidate Gen
    stage5 = data["stages"][4]
    assert stage5["stage_number"] == 5
    assert stage5["stage_id"] == "candidate"
    assert stage5["status"] == "disabled"
    assert stage5["prerequisites_met"] is False
    assert "Requires at least 2 spatial datasets" in stage5["prerequisites_message"]

    # Stage 06: Feature Matching
    stage6 = data["stages"][5]
    assert stage6["stage_number"] == 6
    assert stage6["status"] == "disabled"
    assert stage6["prerequisites_met"] is False


@pytest.mark.asyncio
async def test_candidate_generation_requires_two_datasets(client: AsyncClient):
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Single Dataset Project"})
    proj_id = proj_resp.json()["id"]

    # 2. Upload only 1 dataset
    csv_content = "id,latitude,longitude,name\n1,18.52,73.85,Parcel 1\n"
    ds_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("parcels.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert ds_resp.status_code == 201

    # 3. Attempt to run candidate generation with only 1 dataset
    cand_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/candidate-generation/run",
        json={"distance_meters": 50.0},
    )
    assert cand_resp.status_code == 400
    assert "requires at least 2 spatial datasets" in cand_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_feature_matching_requires_two_datasets(client: AsyncClient):
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Matching Test Project"})
    proj_id = proj_resp.json()["id"]

    # 2. Attempt to run matching without datasets
    match_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/feature-matching/run",
        json={"distance_meters": 50.0},
    )
    assert match_resp.status_code == 400
    assert "requires at least 2 spatial datasets" in match_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_harmonization_requires_matching_prerequisite(client: AsyncClient):
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Harmonization Test Project"})
    proj_id = proj_resp.json()["id"]

    # 2. Attempt to run harmonization without matching
    harm_resp = await client.post(
        f"/api/v1/projects/{proj_id}/pipeline/harmonization/run",
        json={"area_tolerance_pct": 5.0},
    )
    assert harm_resp.status_code == 400
    assert "Harmonization requires at least 2 spatial datasets" in harm_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stage_08_locked_before_stage_07(client: AsyncClient):
    # 1. Create project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Locking Dependency Project"})
    proj_id = proj_resp.json()["id"]

    # 2. Check pipeline status
    status_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert status_resp.status_code == 200
    stages = status_resp.json()["stages"]

    stage7 = next(s for s in stages if s["stage_number"] == 7)
    assert stage7["name"] == "Attribute/Geometry Harmonization"
    assert stage7["status"] == "disabled"
    assert stage7["prerequisites_met"] is False

    stage8 = next(s for s in stages if s["stage_number"] == 8)
    assert stage8["name"] == "Conflict Detection"
    assert stage8["status"] == "disabled"
    assert stage8["prerequisites_met"] is False
    assert "Requires Stage 07" in stage8["prerequisites_message"]

