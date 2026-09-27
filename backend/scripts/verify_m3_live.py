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


async def run_live_verification():
    print("=" * 70)
    print("LANDSYNC AI — MILESTONE 3 LIVE END-TO-END VERIFICATION")
    print("=" * 70)

    demo_dir = backend_dir.parent / "demo-data" / "synthetic"
    cadastral_file = demo_dir / "cadastral_parcels_synth.geojson"
    drone_file = demo_dir / "drone_structures_synth.geojson"
    municipal_file = demo_dir / "municipal_records_synth.csv"

    assert cadastral_file.exists(), f"Missing {cadastral_file}"
    assert drone_file.exists(), f"Missing {drone_file}"
    assert municipal_file.exists(), f"Missing {municipal_file}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Create Live Project
        print("\n[1] Creating Project...")
        proj_resp = await client.post(
            "/api/v1/projects",
            json={
                "name": "M3 Production Verification Project",
                "description": "Validation workspace for PostGIS candidate generation and multi-signal matching",
                "target_crs": "EPSG:4326",
            },
        )
        assert proj_resp.status_code == 201, f"Project creation failed: {proj_resp.text}"
        project = proj_resp.json()
        project_id = project["id"]
        print(f"    Created project: {project['name']} (ID: {project_id}, CRS: {project['target_crs']})")

        # Step 2: Upload Synthetic Datasets
        print("\n[2] Ingesting Synthetic Datasets...")
        with open(cadastral_file, "rb") as f:
            cad_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("cadastral_parcels_synth.geojson", f, "application/geo+json")},
            )
        assert cad_resp.status_code == 201, f"Cadastral upload failed: {cad_resp.text}"
        cad_ds = cad_resp.json()
        print(f"    Ingested Cadastral: {cad_ds['feature_count']} features ({cad_ds['source_format']}, {cad_ds.get('detected_crs')})")

        with open(drone_file, "rb") as f:
            drone_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("drone_structures_synth.geojson", f, "application/geo+json")},
            )
        assert drone_resp.status_code == 201, f"Drone upload failed: {drone_resp.text}"
        drone_ds = drone_resp.json()
        print(f"    Ingested Drone: {drone_ds['feature_count']} features ({drone_ds['source_format']}, {drone_ds.get('detected_crs')})")

        with open(municipal_file, "rb") as f:
            muni_resp = await client.post(
                f"/api/v1/projects/{project_id}/datasets",
                files={"file": ("municipal_records_synth.csv", f, "text/csv")},
            )
        assert muni_resp.status_code == 201, f"Municipal upload failed: {muni_resp.text}"
        muni_ds = muni_resp.json()
        print(f"    Ingested Municipal: {muni_ds['feature_count']} features ({muni_ds['source_format']}, {muni_ds.get('detected_crs')})")

        # Step 3: Trigger Matching Run (Cadastral -> Drone + Municipal)
        print("\n[3] Triggering Multi-Dataset Matching Run (Cadastral -> Drone + Municipal)...")
        run_input = {
            "source_dataset_id": cad_ds["id"],
            "candidate_dataset_ids": [drone_ds["id"], muni_ds["id"]],
            "configuration": {
                "candidate_search_distance_meters": 60.0,
                "matched_threshold": 0.80,
                "possible_threshold": 0.60,
                "conflict_threshold": 0.40,
                "spatial_weight": 0.35,
                "area_weight": 0.20,
                "centroid_weight": 0.20,
                "geometry_weight": 0.15,
                "attribute_weight": 0.10,
            },
        }

        run_resp = await client.post(f"/api/v1/projects/{project_id}/matching-runs", json=run_input)
        assert run_resp.status_code == 201, f"Matching run failed: {run_resp.text}"
        run = run_resp.json()
        run_id = run["id"]

        print(f"    Match Run ID: {run_id}")
        print(f"    Status: {run['status']}")
        print(f"    Features Processed:   {run['total_features_processed']}")
        print(f"    Candidates Evaluated: {run['total_candidates']}")
        print(f"    Matched (>=80%):      {run['total_matches']}")
        print(f"    Possible (60-79%):    {run['total_possible_matches']}")
        print(f"    Conflicts:            {run['total_conflicts']}")
        print(f"    Unmatched:            {run['total_unmatched']}")

        # Verify all classification categories exist
        assert run["total_matches"] > 0, "Expected > 0 matched"
        assert run["total_possible_matches"] > 0, "Expected > 0 possible matches"
        assert run["total_conflicts"] > 0, "Expected > 0 conflicts"
        assert run["total_unmatched"] > 0, "Expected > 0 unmatched"

        # Step 4: Verify Matches API & Filtering
        print("\n[4] Verifying Match Querying & Filtering API...")
        all_matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?limit=200")
        assert all_matches_resp.status_code == 200
        all_matches = all_matches_resp.json()["items"]
        print(f"    Retrieved {len(all_matches)} total match records")

        # Check matched filter
        matched_filter_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?status=matched")
        assert matched_filter_resp.status_code == 200
        matched_count = matched_filter_resp.json()["total"]
        assert matched_count == run["total_matches"], f"Filter count {matched_count} != {run['total_matches']}"
        print(f"    Filter 'status=matched' returned exactly {matched_count} records")

        # Check conflict filter
        conflict_filter_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?status=conflict")
        assert conflict_filter_resp.status_code == 200
        conflict_items = conflict_filter_resp.json()["items"]
        print(f"    Filter 'status=conflict' returned {len(conflict_items)} records")
        for c in conflict_items[:2]:
            print(f"      Conflict: {c['source_identifier']} vs {c['candidate_identifier']} | Score: {c['overall_score']:.2f}")
            print(f"      Reasons: {c['explanation']['reasons']}")

        # Check unmatched filter
        unmatched_filter_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?status=unmatched")
        assert unmatched_filter_resp.status_code == 200
        unmatched_items = unmatched_filter_resp.json()["items"]
        print(f"    Filter 'status=unmatched' returned {len(unmatched_items)} records")
        for u in unmatched_items[:2]:
            print(f"      Unmatched: {u['source_identifier']} ({u['source_dataset_name']}) -> {u['explanation']['reasons']}")

        # Step 5: Verify Detailed Match Explanation & Geometry Payload
        print("\n[5] Verifying Match Detail Endpoint & Polygon Geometries...")
        sample_matched = next(m for m in all_matches if m["status"] == "matched" and m["candidate_feature_id"])
        detail_resp = await client.get(f"/api/v1/matches/{sample_matched['id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        print(f"    Match Detail ID: {detail['id']}")
        print(f"    Source Feat: {detail['source_feature']['dataset_name']} ({detail['source_feature']['geometry_type']})")
        print(f"    Candidate Feat: {detail['candidate_feature']['dataset_name']} ({detail['candidate_feature']['geometry_type']})")
        print(f"    Overall Score: {detail['overall_score']:.4f}")
        print(f"    Components: {detail['explanation']['component_scores']}")
        print(f"    Reasons: {detail['explanation']['reasons']}")
        if detail["intersection_geometry"]:
            print(f"    Intersection Geometry Type: {detail['intersection_geometry']['type']}")

        # Step 6: Verify Persistence in PostGIS DB directly
        print("\n[6] Verifying Direct Database Persistence in PostgreSQL/PostGIS...")
        async with async_session_maker() as db:
            run_query = await db.execute(select(MatchRun).where(MatchRun.id == run_id))
            db_run = run_query.scalar_one_or_none()
            assert db_run is not None, "MatchRun missing in database"
            assert db_run.status == "completed"

            count_query = await db.execute(
                select(func.count(FeatureMatch.id)).where(FeatureMatch.match_run_id == run_id)
            )
            total_matches_in_db = count_query.scalar()
            print(f"    Direct DB check: MatchRun {db_run.id} found with {total_matches_in_db} FeatureMatch records.")
            assert total_matches_in_db == all_matches_resp.json()["total"]

        # Step 7: Verify Directional Matching & Historical Run Preservation
        print("\n[7] Verifying Directional Matching (Drone -> Cadastral) & Historical Preservation...")
        reverse_run_resp = await client.post(
            f"/api/v1/projects/{project_id}/matching-runs",
            json={
                "source_dataset_id": drone_ds["id"],
                "candidate_dataset_ids": [cad_ds["id"]],
                "configuration": {"candidate_search_distance_meters": 50.0},
            },
        )
        assert reverse_run_resp.status_code == 201
        rev_run = reverse_run_resp.json()
        print(f"    Reverse Run ID: {rev_run['id']} (Features: {rev_run['total_features_processed']}, Matched: {rev_run['total_matches']})")

        # Verify both runs coexist
        list_runs_resp = await client.get(f"/api/v1/projects/{project_id}/matching-runs")
        assert list_runs_resp.status_code == 200
        runs_list = list_runs_resp.json()["items"]
        assert len(runs_list) == 2, f"Expected 2 historical runs, found {len(runs_list)}"
        print(f"    Verified: Project preserves all {len(runs_list)} historical match runs independently.")

        # Verify reverse run has Drone as source and Cadastral as candidate
        rev_matches_resp = await client.get(f"/api/v1/matching-runs/{rev_run['id']}/matches?limit=5")
        assert rev_matches_resp.status_code == 200
        sample_rev_match = rev_matches_resp.json()["items"][0]
        assert sample_rev_match["source_dataset_name"] == drone_ds["name"]
        print(f"    Verified directional identity: Source={sample_rev_match['source_dataset_name']} ({sample_rev_match['source_identifier']})")

    print("\n" + "=" * 70)
    print("ALL M3 LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_live_verification())
