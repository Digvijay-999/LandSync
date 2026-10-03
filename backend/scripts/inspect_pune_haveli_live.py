import asyncio
import uuid
from sqlalchemy import text
from app.core.database import async_session_maker

PROJECT_ID = uuid.UUID("92534d7c-3d0f-4cbe-96af-2449f320b470")

async def inspect():
    async with async_session_maker() as session:
        # Datasets & source features
        datasets = (await session.execute(
            text("SELECT id, name, feature_count FROM datasets WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).fetchall()
        
        source_count = (await session.execute(
            text("""
                SELECT count(*) FROM source_features sf
                JOIN dataset_versions dv ON sf.dataset_version_id = dv.id
                JOIN datasets d ON dv.dataset_id = d.id
                WHERE d.project_id = :p
            """),
            {"p": PROJECT_ID}
        )).scalar()

        canon_count = (await session.execute(
            text("""
                SELECT count(*) FROM canonical_features cf
                JOIN dataset_versions dv ON cf.dataset_version_id = dv.id
                JOIN datasets d ON dv.dataset_id = d.id
                WHERE d.project_id = :p
            """),
            {"p": PROJECT_ID}
        )).scalar()
        
        # Matches / candidates
        match_runs = (await session.execute(
            text("SELECT count(*) FROM match_runs WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        match_count = (await session.execute(
            text("SELECT count(*) FROM feature_matches WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()

        match_review_count = (await session.execute(
            text("SELECT count(*) FROM match_reviews mr JOIN feature_matches fm ON mr.feature_match_id = fm.id WHERE fm.project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        # Conflicts
        geo_conflicts = (await session.execute(
            text("SELECT count(*) FROM geospatial_conflicts WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        geo_by_status = (await session.execute(
            text("SELECT status, count(*) FROM geospatial_conflicts WHERE project_id = :p GROUP BY status"),
            {"p": PROJECT_ID}
        )).fetchall()

        attr_conflicts = (await session.execute(
            text("SELECT count(*) FROM attribute_conflicts WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        # Validation
        validation_count = (await session.execute(
            text("SELECT count(*) FROM validation_results WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()

        val_by_status = (await session.execute(
            text("SELECT overall_status, count(*) FROM validation_results WHERE project_id = :p GROUP BY overall_status"),
            {"p": PROJECT_ID}
        )).fetchall()
        
        # Human reviews (adjudication)
        review_count = (await session.execute(
            text("SELECT count(*) FROM human_review_decisions WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        review_by_decision = (await session.execute(
            text("SELECT action, count(*) FROM human_review_decisions WHERE project_id = :p GROUP BY action"),
            {"p": PROJECT_ID}
        )).fetchall()
        
        # Unified land records
        ulr_total = (await session.execute(
            text("SELECT count(*) FROM unified_land_records WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        ulr_auth = (await session.execute(
            text("SELECT count(*) FROM unified_land_records WHERE project_id = :p AND status = 'ACTIVE'"),
            {"p": PROJECT_ID}
        )).scalar()
        
        ulr_quarantine = (await session.execute(
            text("SELECT count(*) FROM unified_land_records WHERE project_id = :p AND status = 'QUARANTINED'"),
            {"p": PROJECT_ID}
        )).scalar()
        
        ulr_by_status = (await session.execute(
            text("SELECT status, count(*) FROM unified_land_records WHERE project_id = :p GROUP BY status"),
            {"p": PROJECT_ID}
        )).fetchall()
        prov_count = (await session.execute(
            text("SELECT count(*) FROM provenance_records WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()

        prov_events = (await session.execute(
            text("SELECT count(*) FROM provenance_events WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        # Exports
        export_count = (await session.execute(
            text("SELECT count(*) FROM export_jobs WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).scalar()
        
        exports_data = (await session.execute(
            text("SELECT id, format, status, record_count, file_size_bytes, sha256_checksum FROM export_jobs WHERE project_id = :p"),
            {"p": PROJECT_ID}
        )).fetchall()

        # Pipeline stages
        stages = (await session.execute(
            text("SELECT stage_number, stage_id, status FROM pipeline_stage_executions WHERE project_id = :p ORDER BY stage_number"),
            {"p": PROJECT_ID}
        )).fetchall()

        print("=== LIVE PUNE HAVELI INSPECTION REPORT ===")
        print(f"Project ID: {PROJECT_ID}")
        print("Datasets:")
        for d in datasets:
            print(f"  - {d[1]}: {d[2]} features (ID: {d[0]})")
        print(f"Total Raw Source Features: {source_count}")
        print(f"Total Canonical Features: {canon_count}")
        print(f"Match Runs: {match_runs}, Feature Matches: {match_count}, Match Reviews: {match_review_count}")
        print(f"Geospatial Conflicts: {geo_conflicts} ({dict(geo_by_status)})")
        print(f"Attribute Conflicts: {attr_conflicts}")
        print(f"Validation Results: {validation_count} ({dict(val_by_status)})")
        print(f"Human Review Decisions: {review_count} ({dict(review_by_decision)})")
        print(f"Unified Land Records: {ulr_total} ({dict(ulr_by_status)}) (Authoritative/Active: {ulr_auth}, Quarantined: {ulr_quarantine})")
        print(f"Provenance Records: {prov_count} (Provenance Events: {prov_events})")
        print(f"Export Jobs: {export_count}")
        for e in exports_data:
            print(f"  - Format: {e[1]}, Status: {e[2]}, Records: {e[3]}, Size: {e[4]} bytes, SHA256: {e[5][:16]}...")
        print(f"\nPipeline Stages ({len(stages)}/14):")
        for s in stages:
            print(f"  Stage {s[0]:02d} ({s[1]}): {s[2]}")

if __name__ == "__main__":
    asyncio.run(inspect())
