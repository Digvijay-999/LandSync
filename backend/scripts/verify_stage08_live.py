import asyncio
import uuid
import httpx
from datetime import datetime

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        # 1. Fetch projects
        projects_resp = await client.get("/api/v1/projects")
        print("Projects response status:", projects_resp.status_code)
        projects = projects_resp.json().get("items", [])
        if not projects:
            print("No projects found!")
            return
        
        target_project = projects[0]
        project_id = target_project["id"]
        print(f"Target Project: {target_project['name']} ({project_id})")

        # 2. Check Pipeline Status
        status_resp = await client.get(f"/api/v1/projects/{project_id}/pipeline/status")
        print("Pipeline status response:", status_resp.status_code)
        stages = status_resp.json().get("stages", [])
        for s in stages[:9]:
            print(f"Stage {s['stage_number']:02d} ({s['stage_id']}): status={s['status']}, is_runnable={s['is_runnable']}, prereq_met={s['prerequisites_met']}")

        # 3. Ensure Stage 07 is executed
        print("\n--- Executing Stage 07 (Harmonization) ---")
        stage7_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/harmonization/run",
            json={"area_tolerance_pct": 5.0}
        )
        print("Stage 07 Status Code:", stage7_resp.status_code)
        s7_data = stage7_resp.json()
        print(f"Stage 07 Output: {s7_data.get('matched_pairs_processed')} pairs processed, {s7_data.get('harmonized_records_count')} harmonized, {s7_data.get('conflicts_forwarded_count')} forwarded conflicts")

        # 4. Execute Stage 08 (Conflict Detection)
        print("\n--- Executing Stage 08 (Conflict Detection) ---")
        stage8_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/stage-08/execute",
            json={
                "area_low_threshold_pct": 2.0,
                "area_medium_threshold_pct": 5.0,
                "area_high_threshold_pct": 15.0,
                "include_geometry_metrics": True
            }
        )
        print("Stage 08 Status Code:", stage8_resp.status_code)
        s8_data = stage8_resp.json()
        print(f"Stage 08 Execution Result:")
        print(f"  Records Scanned: {s8_data.get('records_scanned')}")
        print(f"  Total Conflicts Detected: {s8_data.get('conflicts_detected')}")
        print(f"  CRITICAL: {s8_data.get('critical_count')}")
        print(f"  HIGH: {s8_data.get('high_count')}")
        print(f"  MEDIUM: {s8_data.get('medium_count')}")
        print(f"  LOW: {s8_data.get('low_count')}")
        print(f"  Conflicts Created: {s8_data.get('conflicts_created')}")
        print(f"  Conflicts Updated: {s8_data.get('conflicts_updated')}")
        print(f"  Execution Time: {s8_data.get('execution_time_ms')} ms")
        print(f"  Counts by Type: {s8_data.get('counts_by_type')}")

        # 5. Test Idempotency: Re-execute Stage 08
        print("\n--- Testing Stage 08 Idempotency (Second Execution) ---")
        s8_reexec = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/stage-08/execute",
            json={
                "area_low_threshold_pct": 2.0,
                "area_medium_threshold_pct": 5.0,
                "area_high_threshold_pct": 15.0,
                "include_geometry_metrics": True
            }
        )
        s8_re_data = s8_reexec.json()
        print(f"  Second Run Conflicts Detected: {s8_re_data.get('conflicts_detected')}")
        print(f"  Second Run Conflicts Created: {s8_re_data.get('conflicts_created')} (Expected: 0)")
        print(f"  Second Run Conflicts Updated: {s8_re_data.get('conflicts_updated')} (Expected: {s8_data.get('conflicts_detected')})")

        # 6. Test Listing Conflicts via API
        print("\n--- Listing Conflicts with Filters ---")
        list_resp = await client.get(f"/api/v1/projects/{project_id}/conflicts?limit=5")
        conflicts_list = list_resp.json()
        print(f"  Total in DB: {conflicts_list.get('total')}")
        print(f"  Counts by Severity: {conflicts_list.get('counts_by_severity')}")
        print(f"  Counts by Type: {conflicts_list.get('counts_by_type')}")
        print(f"  Counts by Status: {conflicts_list.get('counts_by_status')}")

        # Sample conflict details
        items = conflicts_list.get("items", [])
        if items:
            sample = items[0]
            print(f"\nSample Conflict Detail (ID: {sample['id']}):")
            print(f"  Type: {sample['conflict_type']}")
            print(f"  Field: {sample['field_name']}")
            print(f"  Severity: {sample['severity']}")
            print(f"  Status: {sample['status']}")
            print(f"  Rule: {sample['detection_rule']}")
            print(f"  Reason: {sample['severity_reason']}")
            print(f"  Source A ({sample['source_a']}): {sample['value_a']} (norm: {sample['normalized_value_a']})")
            print(f"  Source B ({sample['source_b']}): {sample['value_b']} (norm: {sample['normalized_value_b']})")
            print(f"  Discrepancy: {sample['discrepancy_value']} ({sample['discrepancy_percentage']}%)")
            print(f"  Spatial Evidence: {sample.get('geometry_metadata')}")

            # 7. Test PATCH status update
            print("\n--- Testing PATCH /conflicts/{conflict_id} ---")
            patch_resp = await client.patch(
                f"/api/v1/conflicts/{sample['id']}",
                json={"status": "ACKNOWLEDGED", "notes": "Field survey team verified variance."}
            )
            print(f"  PATCH Status Code: {patch_resp.status_code}")
            patched = patch_resp.json()
            print(f"  Updated Status: {patched.get('status')}")
            print(f"  Status History: {patched.get('evidence', {}).get('status_history')}")

        # 8. Check Pipeline Status again to verify Stage 08 completed and Stage 09 unlocked
        print("\n--- Verifying Pipeline State Progression ---")
        post_status_resp = await client.get(f"/api/v1/projects/{project_id}/pipeline/status")
        post_stages = post_status_resp.json().get("stages", [])
        s8_post = next(s for s in post_stages if s["stage_number"] == 8)
        s9_post = next(s for s in post_stages if s["stage_number"] == 9)
        print(f"  Stage 08 Status: {s8_post['status']} (is_runnable={s8_post['is_runnable']})")
        print(f"  Stage 09 Status: {s9_post['status']} (prerequisites_met={s9_post['prerequisites_met']})")

if __name__ == "__main__":
    asyncio.run(main())
