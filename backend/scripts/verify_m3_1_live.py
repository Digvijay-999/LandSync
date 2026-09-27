import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import async_session_maker
from app.models.matching import MatchRun, FeatureMatch
from sqlalchemy import select, func


async def run_m3_1_live_verification():
    print("=" * 75)
    print("LANDSYNC AI — MILESTONE 3.1 LIVE END-TO-END VERIFICATION")
    print("MATCH RESULT QUALITY + BEST-CANDIDATE RANKING ENGINE")
    print("=" * 75)

    demo_dir = backend_dir.parent / "demo-data" / "synthetic"
    cadastral_file = demo_dir / "cadastral_parcels_synth.geojson"
    drone_file = demo_dir / "drone_structures_synth.geojson"
    municipal_file = demo_dir / "municipal_records_synth.csv"

    assert cadastral_file.exists(), f"Missing {cadastral_file}"
    assert drone_file.exists(), f"Missing {drone_file}"
    assert municipal_file.exists(), f"Missing {municipal_file}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Create Project
        print("\n[1] Creating Project...")
        proj_resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "M3.1 Ranking Verification Project",
                "description": "Validation for best-candidate ranking, ambiguity detection, and quality metrics",
                "target_crs": "EPSG:4326",
            },
        )
        assert proj_resp.status_code == 201, f"Project creation failed: {proj_resp.text}"
        project = proj_resp.json()
        project_id = project["id"]
        print(f"    Project: {project['name']} (ID: {project_id})")

        # Step 2: Upload Datasets
        print("\n[2] Ingesting Synthetic Datasets...")
        with open(cadastral_file, "rb") as f:
            cad_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("cadastral_parcels_synth.geojson", f, "application/geo+json")},
            )
        assert cad_resp.status_code == 201
        cad_ds = cad_resp.json()
        print(f"    Cadastral: {cad_ds['feature_count']} parcels ingested")

        with open(drone_file, "rb") as f:
            drone_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("drone_structures_synth.geojson", f, "application/geo+json")},
            )
        assert drone_resp.status_code == 201
        drone_ds = drone_resp.json()
        print(f"    Drone Structures: {drone_ds['feature_count']} structures ingested")

        with open(municipal_file, "rb") as f:
            muni_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("municipal_records_synth.csv", f, "text/csv")},
            )
        assert muni_resp.status_code == 201
        muni_ds = muni_resp.json()
        print(f"    Municipal Records: {muni_ds['feature_count']} points ingested")

        # Step 3: Run Matching with Milestone 3.1 Ranking Configuration
        print("\n[3] Triggering Matching Run with Candidate Ranking & Tie Tolerance...")
        run_input = {
            "source_dataset_id": cad_ds["id"],
            "candidate_dataset_ids": [drone_ds["id"], muni_ds["id"]],
            "configuration": {
                "candidate_search_distance_meters": 60.0,
                "matched_threshold": 0.80,
                "possible_threshold": 0.60,
                "conflict_threshold": 0.40,
                "best_candidate_tie_tolerance": 0.015,
                "spatial_weight": 0.35,
                "area_weight": 0.20,
                "centroid_weight": 0.20,
                "geometry_weight": 0.15,
                "attribute_weight": 0.10,
                "scoring_version": "v1.1",
            },
        }

        run_resp = await client.post(f"/api/v1/projects/{project_id}/matching-runs", json=run_input)
        assert run_resp.status_code == 201, f"Matching run failed: {run_resp.text}"
        run = run_resp.json()
        run_id = run["id"]

        print(f"    Match Run ID: {run_id}")
        print(f"    Status: {run['status']}")
        print(f"    Total Processed: {run['total_features_processed']}")
        print(f"    Total Candidates: {run['total_candidates']}")

        # Step 4: Verify Quality Metrics
        print("\n[4] Verifying Run-Level Quality Metrics...")
        qm = run.get("quality_metrics")
        assert qm is not None, "MatchRun.quality_metrics must not be None"
        print(f"    Quality Metrics:")
        print(f"      • Total Source Features:        {qm['total_source_features']}")
        print(f"      • With Candidates:              {qm['features_with_candidates']}")
        print(f"      • Without Candidates (Rural):   {qm['features_with_no_candidates']}")
        print(f"      • Single Candidate:             {qm['features_with_one_candidate']}")
        print(f"      • Multiple Candidates:          {qm['features_with_multiple_candidates']}")
        print(f"      • Unambiguous Best:             {qm['features_with_unambiguous_best']}")
        print(f"      • Ambiguous Best (Tied):        {qm['features_with_ambiguous_best']}")
        print(f"      • Conflict:                     {qm['features_with_conflict']}")

        assert qm["total_source_features"] == 80, f"Expected 80 source features, got {qm['total_source_features']}"
        assert qm["features_with_no_candidates"] > 0, "Expected at least 1 feature with no candidates"
        assert qm["features_with_multiple_candidates"] > 0, "Expected multiple candidates features"
        assert qm["features_with_unambiguous_best"] > 0, "Expected unambiguous best features"
        assert qm["features_with_ambiguous_best"] > 0, "Expected ambiguous best features from twin structures"
        assert qm["features_with_conflict"] > 0, "Expected conflict features"

        # Step 5: Test candidate_role & is_best_only Filters
        print("\n[5] Verifying API Filters (candidate_role & is_best_only)...")
        # Filter BEST
        best_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?candidate_role=BEST&limit=100")
        assert best_resp.status_code == 200
        best_data = best_resp.json()
        best_items = best_data["items"]
        print(f"    Filter candidate_role=BEST returned {best_data['total']} total items (page: {len(best_items)})")
        assert best_data["total"] == qm["features_with_unambiguous_best"]
        for b in best_items:
            assert b["candidate_role"] == "BEST"
            assert b["is_best_candidate"] is True
            assert b["rank"] == 1

        # Filter is_best_only=true
        best_only_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?is_best_only=true&limit=100")
        assert best_only_resp.status_code == 200
        best_only_data = best_only_resp.json()
        best_only_items = best_only_data["items"]
        print(f"    Filter is_best_only=true returned {best_only_data['total']} total items")
        assert best_only_data["total"] == best_data["total"]
        for bo in best_only_items:
            assert bo["is_best_candidate"] is True

        # Filter AMBIGUOUS
        amb_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?candidate_role=AMBIGUOUS")
        assert amb_resp.status_code == 200
        amb_items = amb_resp.json()["items"]
        print(f"    Filter candidate_role=AMBIGUOUS returned {len(amb_items)} items")
        assert len(amb_items) > 0, "Expected ambiguous items"
        for a in amb_items:
            assert a["candidate_role"] == "AMBIGUOUS"
            assert a["is_best_candidate"] is False
            print(f"      Ambiguous Match: Source {a['source_identifier']} vs Cand {a['candidate_identifier']} | Rank: {a['rank']} | Score: {a['overall_score']:.4f} | Gap: {a['score_gap']}")

        # Filter SECONDARY
        sec_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?candidate_role=SECONDARY")
        assert sec_resp.status_code == 200
        sec_items = sec_resp.json()["items"]
        print(f"    Filter candidate_role=SECONDARY returned {len(sec_items)} items")
        for s in sec_items:
            assert s["candidate_role"] == "SECONDARY"
            assert s["is_best_candidate"] is False
            assert s["rank"] > 1

        # Step 6: Verify Source-Feature Specific Endpoints
        print("\n[6] Verifying Source Feature Candidates & Summary Endpoints...")
        sample_amb = amb_items[0]
        src_feat_id = sample_amb["source_feature_id"]

        cands_resp = await client.get(f"/api/v1/matching-runs/{run_id}/source-features/{src_feat_id}/candidates")
        assert cands_resp.status_code == 200
        src_cands = cands_resp.json()
        print(f"    Source Feature {sample_amb['source_identifier']} has {len(src_cands)} candidates returned from endpoint:")
        for c in src_cands:
            print(f"      - Rank {c['rank']}: Cand={c['candidate_identifier']} ({c['candidate_dataset_name']}) | Score={c['overall_score']:.4f} | Role={c['candidate_role']} | Gap={c['score_gap']}")

        # Summary endpoint
        summary_resp = await client.get(f"/api/v1/matching-runs/{run_id}/source-features/{src_feat_id}/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        print(f"    Summary Endpoint:")
        print(f"      • Source Identifier: {summary['source_identifier']}")
        print(f"      • Candidate Count:   {summary['candidate_count']}")
        print(f"      • Best Candidate ID: {summary['best_candidate_id']}")
        print(f"      • Candidate Role:    {summary['candidate_role']}")
        print(f"      • Score Gap:         {summary['score_gap']}")
        assert summary["candidate_role"] == "AMBIGUOUS"
        assert summary["best_candidate_id"] is None, "Ambiguous match must have best_candidate_id = None"

        # Step 7: Verify Detailed Match Endpoint fields
        print("\n[7] Verifying Detailed Match Response Fields...")
        detail_resp = await client.get(f"/api/v1/matches/{sample_amb['id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "rank" in detail
        assert "is_best_candidate" in detail
        assert "candidate_role" in detail
        assert "score_gap" in detail
        assert "candidate_count" in detail
        print(f"    MatchDetailResponse contains all M3.1 ranking fields: rank={detail['rank']}, role={detail['candidate_role']}, is_best={detail['is_best_candidate']}, score_gap={detail['score_gap']}, candidate_count={detail['candidate_count']}")

        # Step 8: Direct DB Validation
        print("\n[8] Direct PostgreSQL Database Verification...")
        async with async_session_maker() as db:
            db_run = await db.scalar(select(MatchRun).where(MatchRun.id == run_id))
            assert db_run is not None
            assert db_run.quality_metrics is not None
            print(f"    MatchRun.quality_metrics persisted in PostgreSQL: {db_run.quality_metrics}")

            db_matches = (await db.scalars(select(FeatureMatch).where(FeatureMatch.match_run_id == run_id))).all()
            print(f"    Direct DB check: {len(db_matches)} FeatureMatch records found.")

            # Validate ranking constraints across all records in DB
            for m in db_matches:
                if m.is_best_candidate:
                    assert m.candidate_role == "BEST"
                    assert m.rank == 1
                if m.candidate_role == "AMBIGUOUS":
                    assert m.is_best_candidate is False
                if m.candidate_role == "CONFLICT":
                    assert m.is_best_candidate is False

    print("\n" + "=" * 75)
    print("ALL MILESTONE 3.1 LIVE VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_m3_1_live_verification())
