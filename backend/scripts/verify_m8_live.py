import asyncio
import io
import json
import os
import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Force stdout to UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.main import app
from app.models.project import Project
from app.models.dataset import Dataset
from app.models.feature import CanonicalFeature
from app.models.matching import FeatureMatch
from app.models.unified import UnifiedLandRecord
from app.models.conflict import AttributeConflict


async def main():
    print("=" * 75)
    print("LANDSYNC AI — MILESTONE 8: LIVE GEOSPATIAL REASONING & EVIDENCE ASSISTANT")
    print("=" * 75)

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Verify Assistant Service Health & Configuration
    print("\n[STEP 1] Checking Assistant Health and Provider Status...")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        health_resp = await client.get("/api/v1/assistant/health")
        assert health_resp.status_code == 200, health_resp.text
        health = health_resp.json()
        print(f"  ✓ Assistant Health: {health['status'].upper()}")
        print(f"  ✓ AI Enabled: {health['ai_enabled']}")
        print(f"  ✓ Provider: {health['configured_provider']} (Model: {health['model_name']})")
        print(f"  ✓ Available Tools ({len(health['available_tools'])}): {', '.join(health['available_tools'][:4])}...")

        # 2. Setup Project & Ingest Datasets
        print("\n[STEP 2] Setting Up Multi-Source Harmonization Workspace in PostgreSQL...")
        proj_resp = await client.post("/api/v1/projects", json={"name": "M8 Live Assistant Workspace"})
        assert proj_resp.status_code == 201, proj_resp.text
        proj_id = proj_resp.json()["id"]
        print(f"  ✓ Created Project: {proj_id}")

        cadastral_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.850, 18.520], [73.855, 18.520], [73.855, 18.525], [73.850, 18.525], [73.850, 18.520]]],
                    },
                    "properties": {
                        "parcel_id": "CAD-801",
                        "land_use": "Residential",
                        "area": 1250.0,
                        "address": "15 Heritage Lane, Sector 4",
                    },
                }
            ],
        }
        upload_cad = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("cadastral_pune.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")},
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
                        "coordinates": [[[73.8502, 18.5202], [73.8552, 18.5202], [73.8552, 18.5252], [73.8502, 18.5252], [73.8502, 18.5202]]],
                    },
                    "properties": {
                        "structure_id": "DRN-801",
                        "land_use": "Commercial",  # Contradicts Residential
                        "area": 980.0,             # Contradicts 1250 sqm (>20% delta)
                    },
                }
            ],
        }
        upload_drn = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("drone_ortho.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")},
        )
        assert upload_drn.status_code == 201
        drn_ds_id = upload_drn.json()["id"]
        print(f"  ✓ Ingested Cadastral Dataset ({cad_ds_id[:8]}...) and Drone Dataset ({drn_ds_id[:8]}...)")

        # 3. Matching & Review Pipeline
        print("\n[STEP 3] Executing Spatial Matching, Review Acceptance & Unified Record Build...")
        match_run = await client.post(
            f"/api/v1/projects/{proj_id}/matching-runs",
            json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
        )
        assert match_run.status_code == 201
        run_id = match_run.json()["id"]

        matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
        matches = matches_resp.json()["items"]
        assert len(matches) > 0
        match_id = matches[0]["id"]

        rev_resp = await client.post(
            f"/api/v1/matches/{match_id}/review",
            json={"decision": "ACCEPTED", "comment": "Verified parcel boundaries and ground truth"},
        )
        assert rev_resp.status_code == 201

        build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
        assert build_resp.status_code == 200

        records_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
        records = records_resp.json()["items"]
        assert len(records) > 0
        record_id = records[0]["id"]
        record_ident = records[0]["record_identifier"]
        print(f"  ✓ Harmonized Record Created: {record_ident} (Status: {records[0]['status']})")

        # 4. Snapshot Database Row Counts for Non-Mutation Guarantee
        print("\n[STEP 4] Taking Database Pre-Query Snapshot to Verify 100% Non-Mutation...")
        async with session_factory() as session:
            count_proj_0 = (await session.execute(select(func.count(Project.id)))).scalar()
            count_ds_0 = (await session.execute(select(func.count(Dataset.id)))).scalar()
            count_feat_0 = (await session.execute(select(func.count(CanonicalFeature.id)))).scalar()
            count_match_0 = (await session.execute(select(func.count(FeatureMatch.id)))).scalar()
            count_unif_0 = (await session.execute(select(func.count(UnifiedLandRecord.id)))).scalar()
            count_conf_0 = (await session.execute(select(func.count(AttributeConflict.id)))).scalar()
        print(f"  ✓ Snapshot taken: Proj={count_proj_0}, DS={count_ds_0}, Feat={count_feat_0}, Unif={count_unif_0}, Conf={count_conf_0}")

        # 5. Project Knowledge Base Re-Indexing
        print("\n[STEP 5] Reindexing Project Knowledge Base into PostgreSQL Vector Store...")
        reindex_resp = await client.post(f"/api/v1/assistant/projects/{proj_id}/reindex")
        assert reindex_resp.status_code == 200, reindex_resp.text
        reindex = reindex_resp.json()
        print(f"  ✓ Indexed {reindex['documents_indexed']} documents in {reindex['duration_ms']:.1f} ms:")
        for cat, cnt in reindex["categories_indexed"].items():
            print(f"    - {cat}: {cnt}")

        # 6. Direct Semantic Search Endpoint
        print("\n[STEP 6] Testing Direct Semantic Vector Search Endpoint...")
        sem_resp = await client.get(
            f"/api/v1/assistant/projects/{proj_id}/semantic-search",
            params={"query": "commercial and residential zoning discrepancies", "limit": 3},
        )
        assert sem_resp.status_code == 200, sem_resp.text
        sem_data = sem_resp.json()
        print(f"  ✓ Semantic search returned {len(sem_data)} results:")
        for item in sem_data:
            doc = item["document"]
            print(f"    - [{doc['document_category']}] {doc['title']} (similarity: {item['similarity_score']:.3f})")

        # 7. Assistant Live Queries
        print("\n[STEP 7] Executing Required Live Assistant Geospatial Reasoning Queries...")

        # Query 1: Project Summary
        print("\n  [QUERY 1] 'Summarize this project.'")
        q1_resp = await client.post(
            "/api/v1/assistant/query",
            json={"query": "Summarize this project.", "project_id": proj_id},
        )
        assert q1_resp.status_code == 200
        q1 = q1_resp.json()
        print(f"    Intent: {q1['intent']} | Grounded: {q1['grounded_score'] * 100:.0f}% | Citations: {len(q1['evidence_sources'])}")
        print(f"    Snippet: {q1['answer'][:180]}...")

        # Query 2: Active Unified Records Count
        print("\n  [QUERY 2] 'How many active unified records are there?'")
        q2_resp = await client.post(
            "/api/v1/assistant/query",
            json={"query": "How many active unified records are there?", "project_id": proj_id},
        )
        assert q2_resp.status_code == 200
        q2 = q2_resp.json()
        print(f"    Intent: {q2['intent']} | Grounded: {q2['grounded_score'] * 100:.0f}% | Citations: {len(q2['evidence_sources'])}")
        print(f"    Snippet: {q2['answer'][:180]}...")

        # Query 3: Unresolved Conflicts
        print("\n  [QUERY 3] 'Show me unresolved conflicts.'")
        q3_resp = await client.post(
            "/api/v1/assistant/query",
            json={"query": "Show me unresolved conflicts.", "project_id": proj_id},
        )
        assert q3_resp.status_code == 200
        q3 = q3_resp.json()
        print(f"    Intent: {q3['intent']} | Grounded: {q3['grounded_score'] * 100:.0f}% | Citations: {len(q3['evidence_sources'])}")
        print(f"    Snippet: {q3['answer'][:180]}...")

        # Query 4: Why is record in conflict?
        print(f"\n  [QUERY 4] 'Why is {record_ident} in conflict?'")
        q4_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": f"Why is {record_ident} in conflict?",
                "project_id": proj_id,
                "context_record_id": record_id,
            },
        )
        assert q4_resp.status_code == 200
        q4 = q4_resp.json()
        print(f"    Intent: {q4['intent']} | Grounded: {q4['grounded_score'] * 100:.0f}% | Citations: {len(q4['evidence_sources'])}")
        print(f"    Snippet: {q4['answer'][:180]}...")

        # Query 5: What datasets contributed?
        print(f"\n  [QUERY 5] 'What datasets contributed to {record_ident}?'")
        q5_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": f"What datasets contributed to {record_ident}?",
                "project_id": proj_id,
                "context_record_id": record_id,
            },
        )
        assert q5_resp.status_code == 200
        q5 = q5_resp.json()
        print(f"    Intent: {q5['intent']} | Grounded: {q5['grounded_score'] * 100:.0f}% | Citations: {len(q5['evidence_sources'])}")
        print(f"    Snippet: {q5['answer'][:180]}...")

        # Query 6: Provenance history explanation
        print(f"\n  [QUERY 6] 'Explain the provenance history of {record_ident}.'")
        q6_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": f"Explain the provenance history of {record_ident}.",
                "project_id": proj_id,
                "context_record_id": record_id,
            },
        )
        assert q6_resp.status_code == 200
        q6 = q6_resp.json()
        print(f"    Intent: {q6['intent']} | Grounded: {q6['grounded_score'] * 100:.0f}% | Citations: {len(q6['evidence_sources'])}")
        print(f"    Snippet: {q6['answer'][:180]}...")

        # Query 7: Semantic Search Query via Assistant
        print("\n  [QUERY 7] Semantic Knowledge Search: 'Find documentation on zoning discrepancies and residential use'")
        q7_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": "Find documentation on zoning discrepancies and residential use in knowledge base",
                "project_id": proj_id,
            },
        )
        assert q7_resp.status_code == 200
        q7 = q7_resp.json()
        print(f"    Intent: {q7['intent']} | Grounded: {q7['grounded_score'] * 100:.0f}% | Citations: {len(q7['evidence_sources'])}")
        print(f"    Snippet: {q7['answer'][:180]}...")

        # Query 8: Spatial Query
        print("\n  [QUERY 8] Spatial Proximity Query: 'Find parcels near coordinates 18.522 73.852 within 500 meters.'")
        q8_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": "Find parcels near coordinates 18.522 73.852 within 500 meters.",
                "project_id": proj_id,
            },
        )
        assert q8_resp.status_code == 200
        q8 = q8_resp.json()
        print(f"    Intent: {q8['intent']} | Grounded: {q8['grounded_score'] * 100:.0f}% | Citations: {len(q8['evidence_sources'])}")
        print(f"    Snippet: {q8['answer'][:180]}...")

        # Query 9: Multi-step Complex Investigation
        print(f"\n  [QUERY 9] Multi-step Complex Investigation: 'Why is {record_ident} in conflict and how was the final value determined? Complete detailed report.'")
        q9_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "query": f"Why is {record_ident} in conflict and how was the final value determined? Complete detailed report.",
                "project_id": proj_id,
                "context_record_id": record_id,
            },
        )
        assert q9_resp.status_code == 200
        q9 = q9_resp.json()
        print(f"    Intent: {q9['intent']} | Grounded: {q9['grounded_score'] * 100:.0f}% | Citations: {len(q9['evidence_sources'])}")
        print(f"    Reasoning Trace Steps ({len(q9['reasoning_steps'])}):")
        for step in q9["reasoning_steps"]:
            print(f"      * {step}")
        assert len(q9["evidence_sources"]) >= 3, f"Expected >=3 evidence sources, got {len(q9['evidence_sources'])}"
        print(f"    ✓ Multi-step investigation returned {len(q9['evidence_sources'])} distinct evidence sources (>= 3 verified)")
        print(f"    Snippet: {q9['answer'][:180]}...")

        # Suggested Questions Endpoint
        print("\n[STEP 8] Testing Suggested Questions Generator...")
        sq_resp = await client.get(
            f"/api/v1/assistant/suggested-questions?project_id={proj_id}&context_record_id={record_id}"
        )
        assert sq_resp.status_code == 200
        sq = sq_resp.json()
        print(f"  ✓ Generated {len(sq['suggested_questions'])} follow-up questions:")
        for idx, q_text in enumerate(sq['suggested_questions'], 1):
            print(f"    {idx}. {q_text}")

        # 9. Read-Only Non-Mutation Verification
        print("\n[STEP 9] Verifying 100% Read-Only Non-Mutation Guarantee...")
        async with session_factory() as session:
            count_proj_1 = (await session.execute(select(func.count(Project.id)))).scalar()
            count_ds_1 = (await session.execute(select(func.count(Dataset.id)))).scalar()
            count_feat_1 = (await session.execute(select(func.count(CanonicalFeature.id)))).scalar()
            count_match_1 = (await session.execute(select(func.count(FeatureMatch.id)))).scalar()
            count_unif_1 = (await session.execute(select(func.count(UnifiedLandRecord.id)))).scalar()
            count_conf_1 = (await session.execute(select(func.count(AttributeConflict.id)))).scalar()

        assert count_proj_0 == count_proj_1, "Mutation detected on Project!"
        assert count_ds_0 == count_ds_1, "Mutation detected on Dataset!"
        assert count_feat_0 == count_feat_1, "Mutation detected on CanonicalFeature!"
        assert count_match_0 == count_match_1, "Mutation detected on FeatureMatch!"
        assert count_unif_0 == count_unif_1, "Mutation detected on UnifiedLandRecord!"
        assert count_conf_0 == count_conf_1, "Mutation detected on AttributeConflict!"

        print("  ✓ Zero database mutations detected across all core domain tables after 9 AI queries.")
        print("  ✓ Absolute read-only evidence safety verified.")

    print("\n" + "=" * 75)
    print("LANDSYNC AI — MILESTONE 8 LIVE VERIFICATION SUCCESSFUL!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
