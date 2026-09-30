import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.dataset import Dataset
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord
from app.models.conflict import AttributeConflict
from app.models.assistant import AssistantDocument
from app.schemas.assistant import AssistantIntent


@pytest.mark.asyncio
async def test_assistant_health_endpoint(client: AsyncClient):
    """Verifies assistant health endpoint reports provider, tools, and embedding specs."""
    resp = await client.get("/api/v1/assistant/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "available_tools" in data
    assert len(data["available_tools"]) >= 10
    assert "get_project_summary" in data["available_tools"]
    assert "search_evidence_knowledge_base" in data["available_tools"]
    assert "embedding_dimension" in data
    assert data["embedding_dimension"] == 384


@pytest.mark.asyncio
async def test_assistant_full_lifecycle_and_multistep(client: AsyncClient, db_session: AsyncSession):
    """
    Tests end-to-end assistant reasoning across:
    1. Project setup with Cadastral + Drone datasets
    2. Spatial matching, review acceptance, unified record build (with conflicts)
    3. RAG project re-indexing and semantic vector search
    4. Project overview query
    5. Conflict explanation query
    6. Specific record investigation query
    7. Spatial proximity search query
    8. Attribute keyword search query
    9. Real multi-step LangGraph investigation (db_worker -> spatial_worker -> rag_worker)
    10. Suggested questions endpoint
    11. Read-only non-mutation guarantee
    """
    # Step 1: Create project and upload 2 datasets (Cadastral & Drone)
    proj_resp = await client.post("/api/v1/projects", json={"name": "M8 Assistant Verification Workspace"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

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
                    "parcel_id": "CAD-101",
                    "land_use": "Residential",
                    "area": 1200.0,
                    "address": "42 Shivaji Nagar",
                },
            }
        ],
    }
    upload_cad = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_cad.status_code == 201
    cad_ds_id = upload_cad.json()["id"]

    drone_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8505, 18.5205], [73.8595, 18.5205], [73.8595, 18.5295], [73.8505, 18.5295], [73.8505, 18.5205]]],
                },
                "properties": {
                    "structure_id": "DRN-201",
                    "land_use": "Commercial",  # Conflicting land use
                    "area": 950.0,            # Discrepancy > 20%
                },
            }
        ],
    }
    upload_drn = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")},
    )
    assert upload_drn.status_code == 201
    drn_ds_id = upload_drn.json()["id"]

    # Step 2: Run spatial matching
    match_run = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
    )
    assert match_run.status_code == 201
    run_id = match_run.json()["id"]

    # Fetch matches
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) > 0
    match_id = matches[0]["id"]

    # Step 3: Accept match review
    review_resp = await client.post(
        f"/api/v1/matches/{match_id}/review",
        json={"decision": "ACCEPTED", "comment": "Verified spatial overlap"},
    )
    assert review_resp.status_code == 201

    # Step 4: Generate Unified Land Records (triggers conflict detection)
    gen_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
    assert gen_resp.status_code == 200
    records_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
    assert records_resp.status_code == 200
    records = records_resp.json()["items"]
    assert len(records) > 0
    record_id = records[0]["id"]
    record_identifier = records[0]["record_identifier"]

    # Step 5: Test RAG Vector Indexing
    reindex_resp = await client.post(f"/api/v1/assistant/projects/{proj_id}/reindex")
    assert reindex_resp.status_code == 200
    reindex_data = reindex_resp.json()
    assert reindex_data["documents_indexed"] >= 3
    assert "categories_indexed" in reindex_data

    # Step 6: Test Semantic Vector Search
    sem_resp = await client.get(
        f"/api/v1/assistant/projects/{proj_id}/semantic-search?query=residential%20land%20use"
    )
    assert sem_resp.status_code == 200
    sem_data = sem_resp.json()
    assert len(sem_data) > 0
    assert sem_data[0]["similarity_score"] > 0.0

    # Snapshot database counts before queries to verify non-mutation
    count_proj_before = (await db_session.execute(select(func.count(Project.id)))).scalar()
    count_ds_before = (await db_session.execute(select(func.count(Dataset.id)))).scalar()
    count_feat_before = (await db_session.execute(select(func.count(CanonicalFeature.id)))).scalar()
    count_unif_before = (await db_session.execute(select(func.count(UnifiedLandRecord.id)))).scalar()
    count_conf_before = (await db_session.execute(select(func.count(AttributeConflict.id)))).scalar()

    # TEST 1: Project Overview Query
    q1_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": "Give me an executive overview of this LandSync project and harmonization status.",
            "project_id": proj_id,
        },
    )
    assert q1_resp.status_code == 200
    q1_data = q1_resp.json()
    assert q1_data["intent"] == AssistantIntent.PROJECT_OVERVIEW
    assert "M8 Assistant Verification Workspace" in q1_data["answer"]
    assert len(q1_data["evidence_sources"]) > 0
    assert q1_data["grounded_score"] >= 0.7

    # TEST 2: Conflict Explanation Query
    q2_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": "Why is there an attribute conflict on land_use?",
            "project_id": proj_id,
            "context_record_id": record_id,
        },
    )
    assert q2_resp.status_code == 200
    q2_data = q2_resp.json()
    assert q2_data["intent"] == AssistantIntent.CONFLICT_EXPLANATION
    assert "land_use" in q2_data["answer"].lower()
    conflict_sources = [s for s in q2_data["evidence_sources"] if s["source_type"] == "ATTRIBUTE_CONFLICT"]
    assert len(conflict_sources) > 0
    assert q2_data["grounded_score"] >= 0.7

    # TEST 3: Specific Record Investigation Query
    q3_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": f"Investigate unified record {record_identifier} and its contributing source features.",
            "project_id": proj_id,
            "context_record_id": record_id,
        },
    )
    assert q3_resp.status_code == 200
    q3_data = q3_resp.json()
    assert q3_data["intent"] == AssistantIntent.RECORD_INVESTIGATION
    assert record_identifier in q3_data["answer"]

    # TEST 4: Spatial Proximity Query
    q4_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": "Find parcels near coordinates 18.525 73.855 within 500 meters.",
            "project_id": proj_id,
        },
    )
    assert q4_resp.status_code == 200
    q4_data = q4_resp.json()
    assert q4_data["intent"] == AssistantIntent.SPATIAL_PROXIMITY
    assert len(q4_data["evidence_sources"]) > 0

    # TEST 5: Attribute Search Query
    q5_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": "Search for parcels with residential or commercial land use.",
            "project_id": proj_id,
        },
    )
    assert q5_resp.status_code == 200
    q5_data = q5_resp.json()
    assert q5_data["intent"] == AssistantIntent.ATTRIBUTE_SEARCH
    assert len(q5_data["evidence_sources"]) > 0

    # TEST 6: Real Multi-Step Complex Investigation
    q6_resp = await client.post(
        "/api/v1/assistant/query",
        json={
            "query": f"Why is {record_identifier} in conflict and how was the final value determined? Complete detailed report.",
            "project_id": proj_id,
            "context_record_id": record_id,
        },
    )
    assert q6_resp.status_code == 200
    q6_data = q6_resp.json()
    assert q6_data["intent"] == AssistantIntent.COMPLEX_INVESTIGATION
    assert len(q6_data["reasoning_steps"]) >= 4
    # Multi-step investigation executed db_worker, spatial_worker, and rag_worker
    step_texts = " ".join(q6_data["reasoning_steps"])
    assert "DB Worker" in step_texts
    assert "Spatial Worker" in step_texts
    assert "RAG Worker" in step_texts
    assert q6_data["grounded_score"] >= 0.7

    # TEST 7: Suggested Questions Endpoint
    sq_resp = await client.get(
        f"/api/v1/assistant/suggested-questions?project_id={proj_id}&context_record_id={record_id}"
    )
    assert sq_resp.status_code == 200
    sq_data = sq_resp.json()
    assert len(sq_data["suggested_questions"]) >= 2
    assert any(record_identifier in q for q in sq_data["suggested_questions"])

    # TEST 8: READ-ONLY NON-MUTATION GUARANTEE
    count_proj_after = (await db_session.execute(select(func.count(Project.id)))).scalar()
    count_ds_after = (await db_session.execute(select(func.count(Dataset.id)))).scalar()
    count_feat_after = (await db_session.execute(select(func.count(CanonicalFeature.id)))).scalar()
    count_unif_after = (await db_session.execute(select(func.count(UnifiedLandRecord.id)))).scalar()
    count_conf_after = (await db_session.execute(select(func.count(AttributeConflict.id)))).scalar()

    assert count_proj_before == count_proj_after, "Assistant mutated Project table!"
    assert count_ds_before == count_ds_after, "Assistant mutated Dataset table!"
    assert count_feat_before == count_feat_after, "Assistant mutated CanonicalFeature table!"
    assert count_unif_before == count_unif_after, "Assistant mutated UnifiedLandRecord table!"
    assert count_conf_before == count_conf_after, "Assistant mutated AttributeConflict table!"
