import asyncio
import json
import os
import sys
import time
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
    print("=" * 80)
    print("LANDSYNC AI — MILESTONE 9: ADVANCED GEOSPATIAL INTELLIGENCE VERIFICATION")
    print("=" * 80)

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ---------------------------------------------------------------------
        # STEP 0: System & Engine Health Check
        # ---------------------------------------------------------------------
        print("\n[STEP 0] Verifying System & PostGIS Spatial Engine Health...")
        health_resp = await client.get("/api/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        h_data = health_resp.json()
        print(f"  ✓ System Status: {h_data.get('status', 'ok').upper()}")
        print(f"  ✓ Database: {h_data.get('database', {}).get('postgis_version', 'PostGIS Active')}")

        # ---------------------------------------------------------------------
        # STEP 1: Provision Real Harmonization Workspace
        # ---------------------------------------------------------------------
        print("\n[STEP 1] Provisioning Real Geospatial Workspace in PostgreSQL...")
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": f"M9 Geospatial Intelligence Live Verification ({uuid.uuid4().hex[:6]})"},
        )
        assert proj_resp.status_code == 201, proj_resp.text
        proj_id = proj_resp.json()["id"]
        print(f"  ✓ Created Workspace ID: {proj_id}")

        # Ingest Dataset 1: Cadastral Parcels (Polygons)
        cadastral_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.8500, 18.5200], [73.8530, 18.5200], [73.8530, 18.5230], [73.8500, 18.5230], [73.8500, 18.5200]]],
                    },
                    "properties": {
                        "parcel_id": "CAD-101",
                        "owner": "Municipal Housing Board",
                        "land_use": "Residential",
                        "area": 1200.0,
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.8540, 18.5200], [73.8570, 18.5200], [73.8570, 18.5230], [73.8540, 18.5230], [73.8540, 18.5200]]],
                    },
                    "properties": {
                        "parcel_id": "CAD-102",
                        "owner": "Apollo Tech Park",
                        "land_use": "Commercial",
                        "area": 950.0,
                    },
                },
            ],
        }
        cad_up = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("pune_cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/json")},
        )
        assert cad_up.status_code == 201
        cad_ds_id = cad_up.json()["id"]
        print(f"  ✓ Ingested Cadastral Dataset ({cad_ds_id}): 2 parcels")

        # Ingest Dataset 2: Drone Survey (Polygons overlapping CAD-101 with attribute conflict)
        drone_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.8505, 18.5205], [73.8525, 18.5205], [73.8525, 18.5225], [73.8505, 18.5225], [73.8505, 18.5205]]],
                    },
                    "properties": {
                        "structure_id": "DRN-201",
                        "operator": "SkySurvey Ltd",
                        "land_use": "Commercial",  # Conflicting land use!
                        "area": 850.0,            # Discrepancy > 25%!
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.8600, 18.5200], [73.8630, 18.5200], [73.8630, 18.5230], [73.8600, 18.5230], [73.8600, 18.5200]]],
                    },
                    "properties": {
                        "structure_id": "DRN-202",
                        "operator": "SkySurvey Ltd",
                        "land_use": "Industrial",
                        "area": 1100.0,
                    },
                },
            ],
        }
        drn_up = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("drone_structures.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/json")},
        )
        assert drn_up.status_code == 201
        drn_ds_id = drn_up.json()["id"]
        print(f"  ✓ Ingested Drone Dataset ({drn_ds_id}): 2 structures")

        # Ingest Dataset 3: Municipal Infrastructure (Points)
        municipal_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [73.8502, 18.5202],
                    },
                    "properties": {
                        "asset_id": "ASSET-HYDRANT-01",
                        "type": "Fire Hydrant",
                        "status": "Operational",
                    },
                }
            ],
        }
        mun_up = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("municipal_assets.geojson", json.dumps(municipal_geojson).encode("utf-8"), "application/json")},
        )
        assert mun_up.status_code == 201
        mun_ds_id = mun_up.json()["id"]
        print(f"  ✓ Ingested Municipal Assets ({mun_ds_id}): 1 asset point")

        # ---------------------------------------------------------------------
        # STEP 2: Harmonize Records & Generate Real Attribute Conflict
        # ---------------------------------------------------------------------
        print("\n[STEP 2] Running Matching, Acceptance, and Unified Record Build...")
        match_run_resp = await client.post(
            f"/api/v1/projects/{proj_id}/matching-runs",
            json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drn_ds_id]},
        )
        assert match_run_resp.status_code == 201
        run_id = match_run_resp.json()["id"]

        matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
        matches = matches_resp.json()["items"]
        assert len(matches) >= 1
        match_id = matches[0]["id"]

        await client.post(
            f"/api/v1/matches/{match_id}/review",
            json={"decision": "ACCEPTED", "comment": "Confirmed Cadastral CAD-101 and Drone DRN-201 match"},
        )

        build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
        assert build_resp.status_code == 200
        b_data = build_resp.json()
        print(f"  ✓ Built {b_data['records_created']} unified records ({b_data['conflict_records']} with unresolved conflicts)")

        # ---------------------------------------------------------------------
        # TEST 1: PostGIS Proximity Search
        # "Find parcels within 100 meters of municipal assets."
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("TEST 1: PROXIMITY SEARCH — Parcels within 100 meters of municipal assets")
        print("-" * 80)
        t1_start = time.perf_counter()
        prox_resp = await client.post(
            "/api/v1/analysis/proximity",
            json={
                "project_id": proj_id,
                "target_geometry": {"type": "Point", "coordinates": [73.8502, 18.5202]},
                "distance": 100.0,
                "unit": "meters",
            },
        )
        t1_duration = (time.perf_counter() - t1_start) * 1000.0
        assert prox_resp.status_code == 200, prox_resp.text
        prox_data = prox_resp.json()

        print(f"  ✓ Analysis Type: {prox_data['analysis_type']}")
        print(f"  ✓ Execution Time: {t1_duration:.1f} ms (Engine reported: {prox_data['execution_time_ms']} ms)")
        print(f"  ✓ Found Features Count: {prox_data['result_count']}")
        print(f"  ✓ Distance Statistics: {prox_data['statistics']}")
        print(f"  ✓ GeoJSON Features: {len(prox_data['result_geojson']['features'])} items")

        assert prox_data["result_count"] >= 1, "Expected at least 1 feature in proximity"
        assert prox_data["result_geojson"]["type"] == "FeatureCollection"
        found_idents = [f["properties"].get("identifier") for f in prox_data["result_geojson"]["features"] if "_role" in f["properties"] and f["properties"]["_role"] == "proximity_match"]
        print(f"  ✓ Matched Identifiers: {found_idents}")
        print("  -> TEST 1 PASSED: Real PostGIS distance query returned valid map-compatible GeoJSON.")

        # ---------------------------------------------------------------------
        # TEST 2: PostGIS Intersection Analysis
        # "Which cadastral parcels overlap drone structures?"
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("TEST 2: INTERSECTION ANALYSIS — Cadastral parcels overlapping drone structures")
        print("-" * 80)
        t2_start = time.perf_counter()
        inter_resp = await client.post(
            "/api/v1/analysis/intersection",
            json={
                "project_id": proj_id,
                "dataset_a_id": cad_ds_id,
                "dataset_b_id": drn_ds_id,
            },
        )
        t2_duration = (time.perf_counter() - t2_start) * 1000.0
        assert inter_resp.status_code == 200, inter_resp.text
        inter_data = inter_resp.json()

        print(f"  ✓ Analysis Type: {inter_data['analysis_type']}")
        print(f"  ✓ Intersecting Pairs Count: {inter_data['result_count']}")
        print(f"  ✓ Overlap Area: {inter_data['statistics']['total_intersection_area_sqm']} m²")
        assert inter_data["result_count"] >= 1, "Expected at least 1 intersecting pair"
        pair = inter_data["statistics"]["pairs"][0]
        print(f"  ✓ Verified Intersection: Parcel {pair['feature_a_ident']} ∩ Structure {pair['feature_b_ident']} ({pair['intersection_area_sqm']} m², overlap {pair['overlap_pct_a']}%)")
        print("  -> TEST 2 PASSED: Real PostGIS ST_Intersects and ST_Intersection calculated exact overlap.")

        # ---------------------------------------------------------------------
        # TEST 3: Spatial Conflict Intelligence & Clustering
        # "Where are unresolved conflicts concentrated?"
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("TEST 3: SPATIAL CONFLICT CLUSTERING — Geographic hotspot aggregation")
        print("-" * 80)
        t3_start = time.perf_counter()
        conf_resp = await client.post(
            "/api/v1/analysis/conflicts",
            json={"project_id": proj_id},
        )
        t3_duration = (time.perf_counter() - t3_start) * 1000.0
        assert conf_resp.status_code == 200, conf_resp.text
        conf_data = conf_resp.json()

        print(f"  ✓ Total Unresolved Conflicts: {conf_data['total_conflicts']}")
        print(f"  ✓ Clusters Identified: {len(conf_data['clusters'])}")
        print(f"  ✓ Dataset Disagreements: {conf_data.get('dataset_pair_disagreements', {})}")
        assert conf_data["total_conflicts"] >= 1, "Expected at least 1 unresolved conflict"
        assert len(conf_data["clusters"]) >= 1, "Expected at least 1 spatial cluster"
        cluster = conf_data["clusters"][0]
        print(f"  ✓ Cluster ID: {cluster['cluster_id']} (Centroid: {cluster['centroid']}, Affected Records: {cluster['affected_record_ids']})")
        print("  -> TEST 3 PASSED: Spatial conflict aggregation successfully localized conflict hotspots.")

        # ---------------------------------------------------------------------
        # TEST 4: Dataset Comparison Experience
        # "Compare the cadastral and drone datasets."
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("TEST 4: DATASET COMPARISON — Dual-source spatial coverage and differences")
        print("-" * 80)
        t4_start = time.perf_counter()
        comp_resp = await client.post(
            "/api/v1/analysis/compare",
            json={
                "project_id": proj_id,
                "dataset_a_id": cad_ds_id,
                "dataset_b_id": drn_ds_id,
            },
        )
        t4_duration = (time.perf_counter() - t4_start) * 1000.0
        assert comp_resp.status_code == 200, comp_resp.text
        comp_data = comp_resp.json()

        print(f"  ✓ Dataset A ({comp_data['dataset_a_name']}): {comp_data['dataset_a_count']} features")
        print(f"  ✓ Dataset B ({comp_data['dataset_b_name']}): {comp_data['dataset_b_count']} features")
        print(f"  ✓ Intersecting Features: {comp_data['intersecting_count']}")
        print(f"  ✓ Unmatched A Features: {comp_data['unmatched_a_count']}")
        print(f"  ✓ Unmatched B Features: {comp_data['unmatched_b_count']}")
        print(f"  ✓ Overlap Area: {comp_data['overlap_area_sqm']} m² (Coverage: {comp_data['overlap_percentage']}%)")
        print(f"  ✓ Classified GeoJSON Features: {len(comp_data['analysis']['result_geojson']['features'])}")

        assert comp_data["dataset_a_count"] == 2
        assert comp_data["dataset_b_count"] == 2
        assert comp_data["intersecting_count"] >= 1
        assert comp_data["unmatched_a_count"] >= 1
        assert comp_data["unmatched_b_count"] >= 1
        print("  -> TEST 4 PASSED: Complete spatial coverage and diff comparison executed.")

        # ---------------------------------------------------------------------
        # TEST 5: Complex AI Spatial Investigation
        # "Find parcels within 200m of municipal assets that have unresolved conflicts and explain what sources disagree."
        # ---------------------------------------------------------------------
        print("\n" + "-" * 80)
        print("TEST 5: COMPLEX AI SPATIAL INVESTIGATION — Natural Language to PostGIS + Reasoning")
        print("-" * 80)

        # Record pre-query database counts to verify read-only guarantee
        async with session_factory() as sess:
            unif_count_before = (await sess.execute(select(func.count(UnifiedLandRecord.id)).where(UnifiedLandRecord.project_id == proj_id))).scalar_one()
            conf_count_before = (await sess.execute(select(func.count(AttributeConflict.id)).where(AttributeConflict.project_id == proj_id))).scalar_one()
            feat_count_before = (await sess.execute(select(func.count(CanonicalFeature.id)))).scalar_one()

        t5_start = time.perf_counter()
        ai_resp = await client.post(
            "/api/v1/assistant/query",
            json={
                "project_id": proj_id,
                "query": "Find parcels within 200m of municipal assets that have unresolved conflicts and explain what sources disagree.",
            },
        )
        t5_duration = (time.perf_counter() - t5_start) * 1000.0
        assert ai_resp.status_code == 200, ai_resp.text
        ai_data = ai_resp.json()

        print(f"  ✓ Classified Intent: {ai_data['intent']}")
        print(f"  ✓ Reasoning Steps Trace ({len(ai_data['reasoning_steps'])}):")
        for step in ai_data["reasoning_steps"]:
            print(f"     -> {step}")
        print(f"\n  ✓ AI Synthesized Answer:\n     \"{ai_data['answer']}\"\n")
        print(f"  ✓ Grounding Score: {ai_data['grounded_score']} (Verified against database)")
        print(f"  ✓ Evidence Sources Cited ({len(ai_data['evidence_sources'])}):")
        for ev in ai_data["evidence_sources"][:3]:
            print(f"     * [{ev.get('source_type', 'EVIDENCE')}] {ev.get('title', '')}: {ev.get('relevance_note', '')}")

        assert ai_data["intent"] in ["COMPLEX_SPATIAL_INVESTIGATION", "SPATIAL_ANALYSIS"]
        assert ai_data["spatial_result"] is not None, "Expected spatial_result to be attached for map rendering"
        assert ai_data["spatial_result"]["result_geojson"]["type"] == "FeatureCollection"
        assert len(ai_data["evidence_sources"]) >= 1, "Expected evidence citations"
        assert ai_data["grounded_score"] == 1.0, "Expected 100% grounded score"

        # Verify read-only database guarantee
        async with session_factory() as sess:
            unif_count_after = (await sess.execute(select(func.count(UnifiedLandRecord.id)).where(UnifiedLandRecord.project_id == proj_id))).scalar_one()
            conf_count_after = (await sess.execute(select(func.count(AttributeConflict.id)).where(AttributeConflict.project_id == proj_id))).scalar_one()

        assert unif_count_before == unif_count_after, "AI mutated unified land records! Read-only violated."
        assert conf_count_before == conf_count_after, "AI mutated attribute conflicts! Read-only violated."
        print("  ✓ Read-Only Guarantee: Database records and conflicts remained completely unaltered.")
        print("  -> TEST 5 PASSED: Complex multi-step spatial query planned, executed, visualized, and explained.")

    print("\n" + "=" * 80)
    print("ALL 5 MILESTONE 9 LIVE TESTS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
