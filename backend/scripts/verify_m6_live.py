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
from app.models.provenance import ProvenanceEvent
from app.models.unified import UnifiedLandRecord


async def main():
    print("=" * 70)
    print("LANDSYNC AI — MILESTONE 6: LIVE PROVENANCE & EXPORT VERIFICATION")
    print("=" * 70)

    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Verify Database Schema for ProvenanceEvent
    print("\n[STEP 1] Verifying Database Schema for Provenance & Audit Events...")
    async with session_factory() as session:
        result = await session.execute(
            select(func.count(ProvenanceEvent.id))
        )
        existing_events = result.scalar() or 0
        print(f"  ✓ provenance_events table verified in PostgreSQL (existing events: {existing_events})")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 2. Setup Project & Upload Datasets
        print("\n[STEP 2] Setting Up Project & Uploading Datasets...")
        proj_resp = await client.post("/api/v1/projects", json={"name": "M6 Live Verification Project"})
        assert proj_resp.status_code == 201
        proj_id = proj_resp.json()["id"]
        print(f"  ✓ Created project: {proj_id}")

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
                        "parcel_id": "CP-LIVE-101",
                        "name": "Live Cadastral 101",
                        "land_use": "Residential",
                        "area": 850.0,
                        "address": "101 Metro Way",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.87, 18.54], [73.88, 18.54], [73.88, 18.55], [73.87, 18.55], [73.87, 18.54]]],
                    },
                    "properties": {
                        "parcel_id": "CP-LIVE-102",
                        "name": "Live Cadastral 102",
                        "land_use": "Commercial",
                        "area": 1200.0,
                        "address": "102 Central Plaza",
                    },
                },
            ],
        }

        drone_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.851, 18.521], [73.859, 18.521], [73.859, 18.529], [73.851, 18.529], [73.851, 18.521]]],
                    },
                    "properties": {
                        "structure_id": "DR-LIVE-201",
                        "name": "Live Drone 201",
                        "land_use": "Residential",
                        "area": 840.0,
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.871, 18.541], [73.879, 18.541], [73.879, 18.549], [73.871, 18.549], [73.871, 18.541]]],
                    },
                    "properties": {
                        "structure_id": "DR-LIVE-202",
                        "name": "Live Drone 202",
                        "land_use": "Industrial",
                        "area": 600.0,
                    },
                },
            ],
        }

        cad_resp = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson).encode("utf-8"), "application/geo+json")},
        )
        assert cad_resp.status_code == 201
        cad_ds_id = cad_resp.json()["id"]

        drone_resp = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("drone.geojson", json.dumps(drone_geojson).encode("utf-8"), "application/geo+json")},
        )
        assert drone_resp.status_code == 201
        drone_ds_id = drone_resp.json()["id"]
        print(f"  ✓ Uploaded datasets (Cadastral: {cad_ds_id[:8]}..., Drone: {drone_ds_id[:8]}...)")

        # 3. Matching & Reviews
        print("\n[STEP 3] Running Spatial Matching and Recording Human Reviews...")
        match_run_resp = await client.post(
            f"/api/v1/projects/{proj_id}/matching-runs",
            json={"source_dataset_id": cad_ds_id, "candidate_dataset_ids": [drone_ds_id]},
        )
        assert match_run_resp.status_code == 201
        run_id = match_run_resp.json()["id"]

        matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
        assert matches_resp.status_code == 200
        matches = matches_resp.json()["items"]
        assert len(matches) >= 2

        for i, m in enumerate(matches[:2]):
            rev = await client.post(
                f"/api/v1/matches/{m['id']}/review",
                json={"decision": "ACCEPTED", "comment": f"Live verification approval for candidate {i+1}"},
            )
            assert rev.status_code == 201
        print(f"  ✓ Accepted {len(matches[:2])} matching candidate relationships with audit commentary")

        # 4. Build Unified Land Records
        print("\n[STEP 4] Synthesizing Unified Land Records...")
        build_resp = await client.post(f"/api/v1/projects/{proj_id}/unified-records/build")
        assert build_resp.status_code == 200
        print(f"  ✓ Built {build_resp.json()['records_created']} unified records")

        list_resp = await client.get(f"/api/v1/projects/{proj_id}/unified-records")
        assert list_resp.status_code == 200
        records = list_resp.json()["items"]
        assert len(records) == 2
        rec1 = records[0]

        # 5. Provenance Chain Verification
        print("\n[STEP 5] Verifying Full Provenance Chain (/unified-records/{record_id}/provenance)...")
        prov_resp = await client.get(f"/api/v1/unified-records/{rec1['id']}/provenance")
        assert prov_resp.status_code == 200
        prov = prov_resp.json()

        print(f"  ✓ Record Identifier: {prov['record_id']}")
        print(f"  ✓ Status: {prov['status']}")
        print(f"  ✓ Contributing Sources: {len(prov['sources'])}")
        for s in prov["sources"]:
            print(f"      - [{s['role']}] {s['dataset_name']} v{s['dataset_version']} -> {s['feature_identifier']} ({s['geometry_type']})")

        print(f"  ✓ Match Relationships: {len(prov['relationships'])}")
        for rel in prov["relationships"]:
            print(f"      - Match {rel['match_id'][:8]}... Score: {rel['machine_score']:.2f}, Rank: #{rel['candidate_rank']}, Decision: {rel['human_decision']}")

        print(f"  ✓ Review History Decisions: {len(prov['review_history'])}")
        for rh in prov["review_history"]:
            print(f"      - Decision: {rh['decision']}, Comment: '{rh['comment']}'")

        print(f"  ✓ Chronological Evidence Timeline: {len(prov['timeline'])} steps")
        for step in prov["timeline"]:
            print(f"      [{step['event_type']}] {step['title']} ({step['timestamp'][:19]})")

        # 6. Project Provenance Summary
        print("\n[STEP 6] Verifying Project Provenance Summary (/projects/{project_id}/provenance)...")
        summary_resp = await client.get(f"/api/v1/projects/{proj_id}/provenance")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        print(f"  ✓ Project: {summary['project_name']}")
        print(f"  ✓ Unified Records: {summary['total_unified_records']}")
        print(f"  ✓ Total Sources: {summary['total_sources']}")
        print(f"  ✓ Accepted Matches: {summary['total_accepted_matches']}")

        # 7. GeoJSON Project Export
        print("\n[STEP 7] Verifying Project GeoJSON Export (/projects/{project_id}/exports/unified-records.geojson)...")
        geojson_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/unified-records.geojson")
        assert geojson_resp.status_code == 200
        geojson_data = json.loads(geojson_resp.text)
        assert geojson_data["type"] == "FeatureCollection"
        assert geojson_data["metadata"]["record_count"] == 2
        print(f"  ✓ Successfully exported valid GeoJSON FeatureCollection with {len(geojson_data['features'])} features")
        print(f"  ✓ Metadata CRS: {geojson_data['metadata']['crs']}, Timestamp: {geojson_data['metadata']['export_timestamp']}")

        # 8. CSV Project Export
        print("\n[STEP 8] Verifying Project CSV Export (/projects/{project_id}/exports/unified-records.csv)...")
        csv_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/unified-records.csv")
        assert csv_resp.status_code == 200
        csv_rows = list(csv.reader(io.StringIO(csv_resp.text)))
        print(f"  ✓ Successfully exported CSV with {len(csv_rows)} rows (1 header + {len(csv_rows)-1} records)")
        print(f"  ✓ Columns: {', '.join(csv_rows[0][:6])}...")

        # 9. Single Record Exports
        print("\n[STEP 9] Verifying Single Record GeoJSON & CSV Exports...")
        s_geo = await client.get(f"/api/v1/unified-records/{rec1['id']}/export.geojson")
        assert s_geo.status_code == 200
        s_geo_data = json.loads(s_geo.text)
        assert s_geo_data["type"] == "Feature"
        print(f"  ✓ Single GeoJSON Feature exported for {s_geo_data['id']}")

        s_csv = await client.get(f"/api/v1/unified-records/{rec1['id']}/export.csv")
        assert s_csv.status_code == 200
        s_csv_rows = list(csv.reader(io.StringIO(s_csv.text)))
        assert len(s_csv_rows) == 2
        print(f"  ✓ Single CSV row exported for {s_csv_rows[1][0]}")

        # 10. Audit Events Registered
        print("\n[STEP 10] Verifying Audit Trails (EXPORT_CREATED events)...")
        audit_check = await client.get(f"/api/v1/projects/{proj_id}/provenance")
        assert audit_check.status_code == 200
        export_events = [e for e in audit_check.json()["latest_events"] if e["event_type"] == "EXPORT_CREATED"]
        assert len(export_events) >= 1
        print(f"  ✓ Verified {len(export_events)} EXPORT_CREATED audit events recorded in database")

        # 11. Security & Project Isolation
        print("\n[STEP 11] Verifying Security & Project Isolation...")
        iso_proj = await client.post("/api/v1/projects", json={"name": "M6 Isolated Project"})
        iso_id = iso_proj.json()["id"]

        iso_geo = await client.get(f"/api/v1/projects/{iso_id}/exports/unified-records.geojson")
        assert iso_geo.status_code == 200
        assert json.loads(iso_geo.text)["metadata"]["record_count"] == 0

        iso_csv = await client.get(f"/api/v1/projects/{iso_id}/exports/unified-records.csv")
        assert iso_csv.status_code == 200
        assert len(list(csv.reader(io.StringIO(iso_csv.text)))) == 1
        print("  ✓ Isolated project exports return 0 records cleanly")

    print("\n" + "=" * 70)
    print("ALL MILESTONE 6 LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
