import asyncio
import csv
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
from app.models.conflict import AttributeConflict, ConflictResolution
from app.models.provenance import ProvenanceEvent
from app.models.unified import UnifiedLandRecord


async def main():
    print("=" * 75)
    print("LANDSYNC AI — MILESTONE 7: LIVE ATTRIBUTE CONFLICT & RECONCILIATION VERIFICATION")
    print("=" * 75)

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Verify Database Schema for AttributeConflict & ConflictResolution
    print("\n[STEP 1] Verifying PostgreSQL Database Schema for M7 Tables...")
    async with session_factory() as session:
        conf_count = (await session.execute(select(func.count(AttributeConflict.id)))).scalar() or 0
        res_count = (await session.execute(select(func.count(ConflictResolution.id)))).scalar() or 0
        print(f"  ✓ attribute_conflicts table verified in PostgreSQL (existing: {conf_count})")
        print(f"  ✓ conflict_resolutions table verified in PostgreSQL (existing: {res_count})")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 2. Setup Project & Upload Multi-Source Heterogeneous Datasets
        print("\n[STEP 2] Setting Up Project & Uploading Datasets with Discrepancies...")
        proj_resp = await client.post("/api/v1/projects", json={"name": "M7 Attribute Conflict Project"})
        assert proj_resp.status_code == 201, proj_resp.text
        proj_id = proj_resp.json()["id"]
        print(f"  ✓ Created Project: {proj_id}")

        # Cadastral Parcel: Residential, 850 sqm
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
                        "parcel_id": "CAD-701",
                        "name": "Live Cadastral 701",
                        "land_use": "Residential",
                        "area": 850.0,
                        "zoning": "R-1",
                        "address": "101 Metro Way",
                    },
                },
            ],
        }

        # Drone Footprint: Commercial (mismatch!), 975 sqm (difference!), height 14.5
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
                        "structure_id": "DRN-701",
                        "name": "Live Drone 701",
                        "land_use": "Commercial",
                        "area": 975.0,
                        "height": 14.5,
                    },
                },
            ],
        }

        # Upload Cadastral
        cad_upload = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/geo+json")},
            data={"name": "Cadastral Registry 2026"},
        )
        assert cad_upload.status_code == 201, cad_upload.text
        cad_id = cad_upload.json()["id"]
        print(f"  ✓ Uploaded Cadastral Dataset: {cad_id} (Name: Cadastral Registry 2026)")

        # Upload Drone
        drone_upload = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/geo+json")},
            data={"name": "Drone Survey 2026"},
        )
        assert drone_upload.status_code == 201, drone_upload.text
        drone_id = drone_upload.json()["id"]
        print(f"  ✓ Uploaded Drone Dataset: {drone_id} (Name: Drone Survey 2026)")

        # 3. Spatial Matching & Human Review
        print("\n[STEP 3] Executing Spatial Matching & Human Review Acceptance...")
        run_resp = await client.post(
            f"/api/v1/projects/{proj_id}/matching-runs",
            json={"source_dataset_id": cad_id, "candidate_dataset_ids": [drone_id]},
        )
        assert run_resp.status_code == 201, run_resp.text
        run_id = run_resp.json()["id"]
        print(f"  ✓ Executed MatchRun: {run_id}")

        matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
        assert matches_resp.status_code == 200
        matches = matches_resp.json()["items"]
        assert len(matches) > 0, "Expected spatial match"
        match_id = matches[0]["id"]
        print(f"  ✓ Spatial Candidate Found (Score: {matches[0]['overall_score']:.4f})")

        # Human Review: Accept Match
        rev_resp = await client.post(
            f"/api/v1/matches/{match_id}/review",
            json={"decision": "ACCEPTED", "comment": "Verified parcel footprint correspondence"},
        )
        assert rev_resp.status_code in (200, 201), rev_resp.text
        print("  ✓ Review Decision: ACCEPTED")

        # 4. Build Unified Land Records & Detect Conflicts
        print("\n[STEP 4] Harmonizing Unified Records & Auto-Detecting Attribute Conflicts...")
        build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
        assert build_resp.status_code == 200, build_resp.text
        build_stats = build_resp.json()
        print(f"  ✓ Build Summary: {build_stats['total_records']} total records, {build_stats['active_records']} active, {build_stats['conflict_records']} in conflict")

        records_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
        assert records_resp.status_code == 200
        records = records_resp.json()["items"]
        assert len(records) == 1, "Expected 1 unified record"
        rec = records[0]
        rec_id = rec["id"]
        print(f"  ✓ Unified Record ID: {rec_id} (Status: {rec['status']})")
        assert rec["status"] == "CONFLICT", f"Expected CONFLICT status, got {rec['status']}"

        # 5. Query Conflict Endpoints & Inspect Multi-Source Evidence
        print("\n[STEP 5] Querying Conflict APIs & Verifying Cross-Dataset Evidence...")
        conf_resp = await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")
        assert conf_resp.status_code == 200, conf_resp.text
        conflicts = conf_resp.json()
        print(f"  ✓ Detected Conflicts Count: {len(conflicts)}")
        assert len(conflicts) >= 2, f"Expected at least 2 conflicts (land_use & area), got {len(conflicts)}"

        land_use_conf = next((c for c in conflicts if c["attribute_name"] == "land_use"), None)
        area_conf = next((c for c in conflicts if c["attribute_name"] == "area"), None)

        address_conf = next((c for c in conflicts if c["attribute_name"] == "address"), None)

        assert land_use_conf is not None, "Missing land_use conflict"
        assert area_conf is not None, "Missing area conflict"
        assert address_conf is not None, "Missing address conflict"

        print(f"  ✓ Land Use Conflict: type={land_use_conf['conflict_type']}, severity={land_use_conf['severity']}, status={land_use_conf['status']}")
        for dv in land_use_conf["detected_values"]:
            print(f"     → Source: {dv['source_role']} ({dv['dataset_name']}): value='{dv['value']}'")

        print(f"  ✓ Area Conflict: type={area_conf['conflict_type']}, severity={area_conf['severity']}, status={area_conf['status']}")
        for dv in area_conf["detected_values"]:
            print(f"     → Source: {dv['source_role']} ({dv['dataset_name']}): value={dv['value']}")

        print(f"  ✓ Address Conflict: type={address_conf['conflict_type']}, severity={address_conf['severity']}, status={address_conf['status']}")
        for dv in address_conf["detected_values"]:
            print(f"     → Source: {dv['source_role']} ({dv['dataset_name']}): value='{dv['value']}'")

        # Project Conflict Summary
        summary_resp = await client.get(f"/api/v1/projects/{proj_id}/conflicts/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        print(f"  ✓ Project Conflict Summary: total={summary['total_conflicts']}, unresolved={summary['unresolved_conflicts']}, resolved={summary['resolved_conflicts']}")
        assert summary["unresolved_conflicts"] >= 3

        # 6. Reconcile Land Use via SOURCE_SELECTION
        print("\n[STEP 6] Reconciling Land Use via SOURCE_SELECTION (Cadastral Authority)...")
        cad_feature_id = next(dv["feature_id"] for dv in land_use_conf["detected_values"] if dv["source_role"] == "CADASTRAL")
        resolve_lu_resp = await client.post(
            f"/api/v1/conflicts/{land_use_conf['id']}/resolve",
            json={
                "resolution_type": "SOURCE_SELECTION",
                "selected_source_feature_id": cad_feature_id,
                "comment": "Cadastral registry holds legal zoning & land use authority",
                "resolved_by": "Chief GIS Officer",
            },
        )
        assert resolve_lu_resp.status_code == 200, resolve_lu_resp.text
        lu_resolved = resolve_lu_resp.json()
        print(f"  ✓ Land Use Conflict Status: {lu_resolved['status']}")
        assert lu_resolved["status"] == "RESOLVED"
        assert lu_resolved["resolution"]["resolved_value"] == "Residential"
        assert lu_resolved["resolution"]["selected_source_role"] == "CADASTRAL"

        # 7. Reconcile Area via MANUAL_VALUE
        print("\n[STEP 7] Reconciling Area via MANUAL_VALUE (Ground Survey Verification)...")
        resolve_area_resp = await client.post(
            f"/api/v1/conflicts/{area_conf['id']}/resolve",
            json={
                "resolution_type": "MANUAL_VALUE",
                "manual_value": 850.0,
                "comment": "Field boundary audit confirmed Cadastral boundary dimension of 850.0 m²",
                "resolved_by": "Licensed Surveyor",
            },
        )
        assert resolve_area_resp.status_code == 200, resolve_area_resp.text
        area_resolved = resolve_area_resp.json()
        print(f"  ✓ Area Conflict Status: {area_resolved['status']}")
        assert area_resolved["status"] == "RESOLVED"
        assert area_resolved["resolution"]["resolved_value"] == 850.0

        # 8. Verify Unified Record Remains Gated in CONFLICT while Open Conflicts Exist
        print("\n[STEP 8] Verifying Record Remains Gated in CONFLICT while Open Conflicts Exist...")
        rec_detail_resp = await client.get(f"/api/v1/unified-records/{rec_id}")
        assert rec_detail_resp.status_code == 200
        rec_detail = rec_detail_resp.json()
        print(f"  ✓ Record Status: {rec_detail['status']} (Correctly gated by remaining 'address' conflict)")
        assert rec_detail["status"] == "CONFLICT", f"Expected CONFLICT, got {rec_detail['status']}"

        # 9. Verify Conflict Dismissal Workflow (Dismissing 'address' conflict)
        print("\n[STEP 9] Testing Conflict Dismissal Workflow (Tolerable Variance)...")
        dismiss_resp = await client.post(
            f"/api/v1/conflicts/{address_conf['id']}/dismiss",
            json={
                "reason": "Drone aerial datasets do not collect street postal address; Cadastral address remains canonical",
                "resolved_by": "Lead Reviewer",
            },
        )
        assert dismiss_resp.status_code == 200, dismiss_resp.text
        dismissed = dismiss_resp.json()
        assert dismissed["status"] == "DISMISSED"
        print("  ✓ Conflict 'address' successfully transitioned to DISMISSED with mandatory reason")

        # 9b. Verify Dynamic Record Status Transition to ACTIVE
        print("\n[STEP 9b] Verifying Dynamic Record Status Transition to ACTIVE...")
        rec_detail_resp2 = await client.get(f"/api/v1/unified-records/{rec_id}")
        assert rec_detail_resp2.status_code == 200
        rec_detail2 = rec_detail_resp2.json()
        print(f"  ✓ Record Status: {rec_detail2['status']} (All conflicts now resolved or dismissed)")
        assert rec_detail2["status"] == "ACTIVE", f"Expected ACTIVE, got {rec_detail2['status']}"
        assert rec_detail2["canonical_attributes"]["land_use"] == "Residential"
        assert rec_detail2["area"] == 850.0
        print("  ✓ Canonical attributes immediately updated with reconciled values")

        # 10. Verify Full Provenance Timeline with Conflict Events
        print("\n[STEP 10] Verifying Immutable Provenance Timeline & Audit Logging...")
        prov_resp = await client.get(f"/api/v1/unified-records/{rec_id}/provenance")
        assert prov_resp.status_code == 200
        prov = prov_resp.json()
        timeline_titles = [e["title"] for e in prov["timeline"]]
        print(f"  ✓ Provenance Timeline Events: {len(prov['timeline'])} events logged")
        for e in prov["timeline"]:
            print(f"     → [{e['event_type']}] {e['title']}: {e['description']}")

        assert any("Conflict" in t for t in timeline_titles), "Expected conflict events in timeline"
        assert len(prov["conflicts"]) >= 2, "Expected conflicts array in provenance"

        # 11. Verify Multi-Format Export Integration (GeoJSON & CSV)
        print("\n[STEP 11] Verifying Multi-Format Export with Conflict Metrics...")
        # Single GeoJSON
        geojson_resp = await client.get(f"/api/v1/unified-records/{rec_id}/export.geojson")
        assert geojson_resp.status_code == 200
        geojson_data = geojson_resp.json()
        props = geojson_data["properties"]
        print(f"  ✓ Single GeoJSON Export Properties:")
        print(f"     → unresolved_conflict_count: {props.get('unresolved_conflict_count')}")
        print(f"     → resolved_conflict_count: {props.get('resolved_conflict_count')}")
        print(f"     → conflict_status: {props.get('conflict_status')}")
        assert props["unresolved_conflict_count"] == 0
        assert props["resolved_conflict_count"] >= 2
        assert props["conflict_status"] == "RESOLVED"

        # Project CSV
        csv_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/unified-records.csv")
        assert csv_resp.status_code == 200
        csv_reader = csv.DictReader(io.StringIO(csv_resp.text))
        rows = list(csv_reader)
        assert len(rows) == 1
        print(f"  ✓ Project CSV Export Columns:")
        print(f"     → conflict_status: {rows[0]['conflict_status']}")
        print(f"     → resolved_conflict_count: {rows[0]['resolved_conflict_count']}")
        assert rows[0]["conflict_status"] == "RESOLVED"
        assert int(rows[0]["resolved_conflict_count"]) >= 2

        # 12. Verify Idempotent Rebuild Preserves Human Resolutions
        print("\n[STEP 12] Testing Idempotent Rebuild (Human Decisions Must Persist)...")
        rebuild_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
        assert rebuild_resp.status_code == 200
        rebuild_conf_resp = await client.get(f"/api/v1/unified-records/{rec_id}/conflicts")
        rebuild_confs = rebuild_conf_resp.json()
        resolved_count = sum(1 for c in rebuild_confs if c["status"] == "RESOLVED")
        print(f"  ✓ After Rebuild: {resolved_count}/{len(rebuild_confs)} conflicts remain in RESOLVED status")
        assert resolved_count >= 2, "Human conflict resolutions were lost during rebuild!"

    print("\n" + "=" * 75)
    print("ALL MILESTONE 7 LIVE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
