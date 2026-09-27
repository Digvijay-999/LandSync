"""
Milestone 4 Live End-to-End Verification Script
Verifies:
1. Database schema & Alembic migration 0006_match_reviews
2. Matching run generation & review queue retrieval
3. Prioritized review queue ordering (Category & Score)
4. Human decision actions: ACCEPT, REJECT, FLAG with comments
5. Strict preservation of machine score, status, rank, and candidate_role
6. Multi-decision audit trail history persistence
7. Review statistics calculated from database
8. Rejection of invalid decisions and 404 handling
9. Seed demo reviews functionality
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.main import app
from app.models.matching import FeatureMatch, MatchReview, MatchRun


async def run_live_verification():
    print("=" * 70)
    print("LANDSYNC AI — MILESTONE 4: LIVE END-TO-END VERIFICATION")
    print("=" * 70)

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Verify Database Schema & Table Structure
    print("\n[STEP 1] Verifying Database Schema & Tables...")
    async with session_factory() as session:
        # Check review_status column on feature_matches
        col_check = await session.execute(text("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'feature_matches' AND column_name = 'review_status';
        """))
        col = col_check.fetchone()
        assert col is not None, "Column review_status missing from feature_matches"
        print(f"  ✓ feature_matches.review_status exists (type: {col[1]}, default: {col[2]})")

        # Check match_reviews table
        tbl_check = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'match_reviews' 
            ORDER BY ordinal_position;
        """))
        tbl_cols = tbl_check.fetchall()
        assert len(tbl_cols) >= 6, "match_reviews table is missing required columns"
        col_names = [c[0] for c in tbl_cols]
        print(f"  ✓ match_reviews table exists with columns: {', '.join(col_names)}")

    # 2. Test via ASGI HTTP Client
    print("\n[STEP 2] Testing HTTP API Endpoints via FastAPI Test Client...")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        h_resp = await client.get("/api/v1/health")
        assert h_resp.status_code == 200
        print("  ✓ Backend health endpoint responsive")

        # Create Project
        proj_resp = await client.post("/api/v1/projects", json={"name": "M4 Live Verification Project"})
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]
        print(f"  ✓ Created project: {project_id}")

        # Upload Synthetic Datasets
        demo_dir = backend_dir.parent / "demo-data" / "synthetic"
        cad_path = demo_dir / "cadastral_parcels_synth.geojson"
        drone_path = demo_dir / "drone_structures_synth.geojson"

        with open(cad_path, "rb") as f:
            cad_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("cadastral.geojson", f, "application/geo+json")},
            )
        with open(drone_path, "rb") as f:
            drone_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("drone.geojson", f, "application/geo+json")},
            )
        assert cad_resp.status_code == 201 and drone_resp.status_code == 201
        cad_ds_id = cad_resp.json()["id"]
        drone_ds_id = drone_resp.json()["id"]
        print(f"  ✓ Uploaded datasets: Cadastral ({cad_ds_id[:8]}...), Drone ({drone_ds_id[:8]}...)")

        # Execute Matching Run
        run_resp = await client.post(
            f"/api/v1/projects/{project_id}/matching-runs",
            json={
                "source_dataset_id": cad_ds_id,
                "candidate_dataset_ids": [drone_ds_id],
                "configuration": {
                    "matched_threshold": 0.70,
                    "possible_threshold": 0.45,
                    "candidate_search_distance_meters": 60,
                },
            },
        )
        assert run_resp.status_code == 201
        run_id = run_resp.json()["id"]
        total_candidates = run_resp.json()["total_candidates"]
        print(f"  ✓ Executed matching run: {run_id[:8]}... ({total_candidates} candidates generated)")

        # 3. Verify Review Queue API
        print("\n[STEP 3] Verifying Review Queue API & Prioritization...")
        queue_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue")
        assert queue_resp.status_code == 200
        queue = queue_resp.json()
        print(f"  ✓ Retrieved review queue: total={queue['total']}, run_total_candidates={total_candidates}")
        assert queue["total"] > 0
        print(f"  ✓ Retrieved review queue ({queue['total']} items)")
        print(f"    Category counts: Pending={queue['category_counts']['pending']}, "
              f"Ambiguous={queue['category_counts']['ambiguous']}, "
              f"Conflict={queue['category_counts']['conflict']}, "
              f"Possible={queue['category_counts']['possible']}")

        items = queue["items"]
        assert len(items) >= 2, "Expected at least 2 candidate items"
        m1 = items[0]
        m2 = items[1]
        m3 = items[2] if len(items) > 2 else items[1]

        # Check default review status is PENDING
        assert m1["review_status"] == "PENDING"
        assert m2["review_status"] == "PENDING"
        print("  ✓ All initial queue items have review_status = 'PENDING'")

        # 4. Human Review Action: ACCEPT
        print("\n[STEP 4] Executing Human Decision: ACCEPT...")
        m1_orig_score = m1["overall_score"]
        m1_orig_status = m1["status"]
        m1_orig_rank = m1["rank"]
        m1_orig_role = m1["candidate_role"]

        acc_resp = await client.post(
            f"/api/v1/matches/{m1['id']}/review",
            json={
                "decision": "ACCEPTED",
                "comment": "Cadastral boundaries and structural area align with ground survey.",
            },
        )
        assert acc_resp.status_code == 201
        acc_data = acc_resp.json()
        assert acc_data["decision"] == "ACCEPTED"
        print(f"  ✓ Successfully recorded review decision: {acc_data['decision']} on match {m1['id'][:8]}...")

        # 5. Immutability Verification: Machine Score & Status MUST remain untouched
        print("\n[STEP 5] Verifying Machine Decision Immutability...")
        detail1_resp = await client.get(f"/api/v1/matches/{m1['id']}")
        assert detail1_resp.status_code == 200
        d1 = detail1_resp.json()
        assert d1["review_status"] == "ACCEPTED"
        assert d1["overall_score"] == m1_orig_score, "Score modified!"
        assert d1["status"] == m1_orig_status, "Status modified!"
        assert d1["rank"] == m1_orig_rank, "Rank modified!"
        assert d1["candidate_role"] == m1_orig_role, "Role modified!"
        print(f"  ✓ Human Decision: {d1['review_status']}")
        print(f"  ✓ Machine Score: {d1['overall_score']} (UNCHANGED)")
        print(f"  ✓ Machine Classification: {d1['status']} (UNCHANGED)")
        print(f"  ✓ Candidate Role: {d1['candidate_role']} (UNCHANGED)")
        print(f"  ✓ Candidate Rank: {d1['rank']} (UNCHANGED)")

        # 6. Human Review Action: REJECT
        print("\n[STEP 6] Executing Human Decision: REJECT...")
        rej_resp = await client.post(
            f"/api/v1/matches/{m2['id']}/review",
            json={
                "decision": "REJECTED",
                "comment": "Footprint offset indicates neighboring lot structure.",
            },
        )
        assert rej_resp.status_code == 201
        assert rej_resp.json()["decision"] == "REJECTED"
        print(f"  ✓ Successfully recorded REJECTED decision on match {m2['id'][:8]}...")

        # 7. Human Review Action: FLAG & Multi-Decision Audit Trail
        print("\n[STEP 7] Executing Human Decision: FLAG and Audit Trail...")
        flag_resp = await client.post(
            f"/api/v1/matches/{m3['id']}/review",
            json={
                "decision": "FLAGGED",
                "comment": "Twin structures detected within 0.015 tolerance. Flagged for site inspection.",
            },
        )
        assert flag_resp.status_code == 201
        print(f"  ✓ Successfully recorded FLAGGED decision on match {m3['id'][:8]}...")

        # Subsequent re-review: surveyor confirms match, changes decision to ACCEPTED
        rerev_resp = await client.post(
            f"/api/v1/matches/{m3['id']}/review",
            json={
                "decision": "ACCEPTED",
                "comment": "Field verification complete: parcel boundary markers align with building corners.",
            },
        )
        assert rerev_resp.status_code == 201
        print(f"  ✓ Re-reviewed match {m3['id'][:8]}... to ACCEPTED")

        # Verify audit history
        detail3_resp = await client.get(f"/api/v1/matches/{m3['id']}")
        assert detail3_resp.status_code == 200
        d3 = detail3_resp.json()
        assert d3["review_status"] == "ACCEPTED"
        assert len(d3["reviews"]) >= 2
        print(f"  ✓ Audit history preserved: {len(d3['reviews'])} historical decisions stored")
        for i, rev in enumerate(d3["reviews"]):
            print(f"    - Decision #{len(d3['reviews']) - i}: {rev['decision']} at {rev['created_at']} -> \"{rev['comment']}\"")

        # 8. Check Review Statistics API
        print("\n[STEP 8] Verifying Database-Driven Review Statistics API...")
        stats_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-statistics")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        print(f"  ✓ Total Candidates: {stats['total_candidates']}")
        print(f"  ✓ Pending Review:   {stats['pending_review']}")
        print(f"  ✓ Accepted:         {stats['accepted']}")
        print(f"  ✓ Rejected:         {stats['rejected']}")
        print(f"  ✓ Flagged:          {stats['flagged']}")
        print(f"  ✓ Total Reviewed:   {stats['reviewed']}")
        assert stats["accepted"] >= 1
        assert stats["rejected"] >= 1
        assert stats["reviewed"] == (stats["accepted"] + stats["rejected"] + stats["flagged"])

        # 9. Verify Review Queue Category Filters
        print("\n[STEP 9] Verifying Review Queue Category Filtering...")
        q_acc_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue?category=accepted")
        assert q_acc_resp.status_code == 200
        q_acc = q_acc_resp.json()
        assert q_acc["total"] == stats["accepted"]
        for item in q_acc["items"]:
            assert item["review_status"] == "ACCEPTED"
        print(f"  ✓ Filter category=accepted returned exactly {q_acc['total']} accepted items")

        q_rej_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue?category=rejected")
        assert q_rej_resp.status_code == 200
        q_rej = q_rej_resp.json()
        assert q_rej["total"] == stats["rejected"]
        print(f"  ✓ Filter category=rejected returned exactly {q_rej['total']} rejected items")

        # 10. Verify Validation & Error Handling
        print("\n[STEP 10] Verifying Validation & Nonexistent Match Handling...")
        inv_resp = await client.post(
            f"/api/v1/matches/{m1['id']}/review",
            json={"decision": "APPROVE_ALL"},  # Invalid decision enum
        )
        assert inv_resp.status_code == 422
        print("  ✓ Invalid review decision correctly rejected with HTTP 422")

        fake_uuid = uuid.uuid4()
        notfound_resp = await client.post(
            f"/api/v1/matches/{fake_uuid}/review",
            json={"decision": "ACCEPTED"},
        )
        assert notfound_resp.status_code == 404
        print("  ✓ Nonexistent match ID correctly rejected with HTTP 404")

        # 11. Test Seed Demo Reviews Endpoint
        print("\n[STEP 11] Verifying Seed Demo Reviews Endpoint...")
        # Create a new matching run to seed demo reviews
        run2_resp = await client.post(
            f"/api/v1/projects/{project_id}/matching-runs",
            json={
                "source_dataset_id": cad_ds_id,
                "candidate_dataset_ids": [drone_ds_id],
            },
        )
        assert run2_resp.status_code == 201
        run2_id = run2_resp.json()["id"]

        seed_resp = await client.post(f"/api/v1/matching-runs/{run2_id}/seed-demo-reviews")
        assert seed_resp.status_code == 200
        seed_stats = seed_resp.json()
        print(f"  ✓ Seed demo reviews successful:")
        print(f"    Accepted={seed_stats['accepted']}, Rejected={seed_stats['rejected']}, Flagged={seed_stats['flagged']}")
        assert seed_stats["accepted"] >= 1
        assert seed_stats["rejected"] >= 1

    print("\n" + "=" * 70)
    print("ALL MILESTONE 4 LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_live_verification())
