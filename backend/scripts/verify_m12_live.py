import asyncio
import json
from app.core.database import async_session_maker
from app.services.unified.service import UnifiedRecordService
from app.services.pipeline.service import PipelineService

PUNE_PROJECT_ID = '92534d7c-3d0f-4cbe-96af-2449f320b470'

async def main():
    async with async_session_maker() as db:
        print("Checking initial Stage 12 status...")
        initial_status = await UnifiedRecordService.get_stage12_status(db, PUNE_PROJECT_ID)
        print("Initial Status:", json.dumps(initial_status, default=str, indent=2))
        
        print("\nExecuting Stage 12 for Pune Haveli...")
        exec_res = await PipelineService.run_stage_12(db, PUNE_PROJECT_ID)
        print("Execution Result:", json.dumps(exec_res, default=str, indent=2))
        
        print("\nChecking post-execution Stage 12 status...")
        post_status = await UnifiedRecordService.get_stage12_status(db, PUNE_PROJECT_ID)
        print("Post Status:", json.dumps(post_status, default=str, indent=2))
        
        print("\nChecking overall pipeline gating...")
        pipeline_status = await PipelineService.get_pipeline_status(db, PUNE_PROJECT_ID)
        for s in pipeline_status.stages:
            if s.stage_number in [10, 11, 12, 13, 14]:
                print(f"Stage {s.stage_number:02d} ({s.name}): status={s.status}, runnable={s.is_runnable}, prereqs_met={s.prerequisites_met}, message={s.prerequisites_message}")

        print("\nInspecting sample records...")
        resp = await UnifiedRecordService.get_records(db, PUNE_PROJECT_ID, limit=10)
        print(f"Total records in ULR: {resp.total}")
        for r in resp.items[:5]:
            print(f"  Record {r.record_identifier}: resolution={r.resolution_status}, decision={r.human_review_decision}, land_use={r.land_use}, area={r.area}, geom_src={r.geometry_source}, conf={r.confidence_score}")

if __name__ == '__main__':
    asyncio.run(main())
