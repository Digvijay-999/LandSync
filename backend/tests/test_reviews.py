import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_human_review_workflow_and_preservation(client: AsyncClient):
    """
    Test Milestone 4 human review capabilities:
    - Accept, reject, and flag actions
    - Persist comments
    - Audit trail preservation
    - Machine score, status, and rank immutability
    - Invalid decision rejection
    - Nonexistent match handling
    """
    # 1. Create a project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Review Test Project"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload source and candidate datasets
    geojson_a = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]],
                },
                "properties": {"parcel_id": "CP-REV-01", "name": "Parcel Alpha"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.87, 18.54], [73.88, 18.54], [73.88, 18.55], [73.87, 18.55], [73.87, 18.54]]],
                },
                "properties": {"parcel_id": "CP-REV-02", "name": "Parcel Beta"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.89, 18.56], [73.90, 18.56], [73.90, 18.57], [73.89, 18.57], [73.89, 18.56]]],
                },
                "properties": {"parcel_id": "CP-REV-03", "name": "Parcel Gamma"},
            },
        ],
    }

    geojson_b = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.8505, 18.5205], [73.8595, 18.5205], [73.8595, 18.5295], [73.8505, 18.5295], [73.8505, 18.5205]]],
                },
                "properties": {"structure_id": "DR-REV-01", "name": "Parcel Alpha Bld"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.871, 18.541], [73.879, 18.541], [73.879, 18.549], [73.871, 18.549], [73.871, 18.541]]],
                },
                "properties": {"structure_id": "DR-REV-02", "name": "Parcel Beta Bld"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.891, 18.561], [73.899, 18.561], [73.899, 18.569], [73.891, 18.569], [73.891, 18.561]]],
                },
                "properties": {"structure_id": "DR-REV-03", "name": "Parcel Gamma Bld"},
            },
        ],
    }

    import json
    cad_resp = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(geojson_a).encode("utf-8"), "application/geo+json")},
    )
    drone_resp = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("drone.geojson", json.dumps(geojson_b).encode("utf-8"), "application/geo+json")},
    )
    assert cad_resp.status_code == 201
    assert drone_resp.status_code == 201
    ds_cad = cad_resp.json()
    ds_drone = drone_resp.json()

    # 3. Execute matching run
    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/matching-runs",
        json={
            "source_dataset_id": ds_cad["id"],
            "candidate_dataset_ids": [ds_drone["id"]],
        },
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # 4. Fetch matches
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) >= 3

    m1 = matches[0]
    m2 = matches[1]
    m3 = matches[2]

    # Check initial review status is PENDING
    assert m1["review_status"] == "PENDING"
    assert m2["review_status"] == "PENDING"
    assert m3["review_status"] == "PENDING"

    # Store initial machine results for immutability verification
    m1_orig_score = m1["overall_score"]
    m1_orig_status = m1["status"]
    m1_orig_rank = m1["rank"]
    m1_orig_role = m1["candidate_role"]

    # 5. Review action: ACCEPT match 1
    accept_resp = await client.post(
        f"/api/v1/matches/{m1['id']}/review",
        json={
            "decision": "ACCEPTED",
            "comment": "Cadastral and drone boundaries confirm identical real-world entity.",
        },
    )
    assert accept_resp.status_code == 201
    accept_data = accept_resp.json()
    assert accept_data["decision"] == "ACCEPTED"
    assert accept_data["comment"] == "Cadastral and drone boundaries confirm identical real-world entity."
    assert "created_at" in accept_data

    # 6. Verify machine results remain untouched after ACCEPT
    detail_resp1 = await client.get(f"/api/v1/matches/{m1['id']}")
    assert detail_resp1.status_code == 200
    detail1 = detail_resp1.json()
    assert detail1["review_status"] == "ACCEPTED"
    assert detail1["overall_score"] == m1_orig_score, "Machine score must NOT be modified by review"
    assert detail1["status"] == m1_orig_status, "Machine status must NOT be modified by review"
    assert detail1["rank"] == m1_orig_rank, "Machine rank must NOT be modified by review"
    assert detail1["candidate_role"] == m1_orig_role, "Machine role must NOT be modified by review"
    assert len(detail1["reviews"]) == 1
    assert detail1["reviews"][0]["decision"] == "ACCEPTED"

    # 7. Review action: REJECT match 2 via /feature-matches alias
    reject_resp = await client.post(
        f"/api/v1/feature-matches/{m2['id']}/review",
        json={
            "decision": "REJECTED",
            "comment": "Structure boundary belongs to adjacent lot.",
        },
    )
    assert reject_resp.status_code == 201
    assert reject_resp.json()["decision"] == "REJECTED"

    detail_resp2 = await client.get(f"/api/v1/feature-matches/{m2['id']}")
    assert detail_resp2.status_code == 200
    assert detail_resp2.json()["review_status"] == "REJECTED"

    # 8. Review action: FLAG match 3
    flag_resp = await client.post(
        f"/api/v1/matches/{m3['id']}/review",
        json={
            "decision": "FLAGGED",
            "comment": "Potential property boundary dispute; requires field verification.",
        },
    )
    assert flag_resp.status_code == 201
    assert flag_resp.json()["decision"] == "FLAGGED"

    detail_resp3 = await client.get(f"/api/v1/matches/{m3['id']}")
    assert detail_resp3.status_code == 200
    assert detail_resp3.json()["review_status"] == "FLAGGED"

    # 9. Re-review: Update match 3 from FLAGGED to ACCEPTED with new note (Audit history)
    rereview_resp = await client.post(
        f"/api/v1/matches/{m3['id']}/review",
        json={
            "decision": "ACCEPTED",
            "comment": "Field verification completed. Surveyor confirmed agreement.",
        },
    )
    assert rereview_resp.status_code == 201
    detail_resp3_updated = await client.get(f"/api/v1/matches/{m3['id']}")
    detail3_up = detail_resp3_updated.json()
    assert detail3_up["review_status"] == "ACCEPTED"
    assert len(detail3_up["reviews"]) == 2
    # Verify chronological order (newest first)
    assert detail3_up["reviews"][0]["decision"] == "ACCEPTED"
    assert detail3_up["reviews"][1]["decision"] == "FLAGGED"

    # 10. Check Review Statistics API
    stats_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-statistics")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["run_id"] == run_id
    assert stats["accepted"] == 2
    assert stats["rejected"] == 1
    assert stats["flagged"] == 0  # Was re-reviewed to ACCEPTED
    assert stats["reviewed"] == 3

    # 11. Check Review Queue API
    queue_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue")
    assert queue_resp.status_code == 200
    queue = queue_resp.json()
    assert queue["total"] >= 3
    assert queue["reviewed_count"] == 3

    # Filter review queue by category=reviewed
    queue_reviewed_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue?category=reviewed")
    assert queue_reviewed_resp.status_code == 200
    queue_reviewed = queue_reviewed_resp.json()
    assert queue_reviewed["total"] == 3
    for itm in queue_reviewed["items"]:
        assert itm["review_status"] in ["ACCEPTED", "REJECTED"]

    # Filter review queue by decision=REJECTED
    queue_rejected_resp = await client.get(f"/api/v1/matching-runs/{run_id}/review-queue?decision=REJECTED")
    assert queue_rejected_resp.status_code == 200
    queue_rejected = queue_rejected_resp.json()
    assert queue_rejected["total"] == 1
    assert queue_rejected["items"][0]["id"] == m2["id"]

    # 12. Validation: Invalid decision rejection (422)
    invalid_resp = await client.post(
        f"/api/v1/matches/{m1['id']}/review",
        json={"decision": "APPROVED", "comment": "Invalid word"},
    )
    assert invalid_resp.status_code == 422

    # 13. Validation: Nonexistent match (404)
    fake_id = uuid.uuid4()
    notfound_resp = await client.post(
        f"/api/v1/matches/{fake_id}/review",
        json={"decision": "ACCEPTED"},
    )
    assert notfound_resp.status_code == 404


@pytest.mark.asyncio
async def test_seed_demo_reviews_endpoint(client: AsyncClient):
    """
    Test seed-demo-reviews endpoint sets deterministic demo review decisions.
    """
    # Create project & run matching with demo synthetic datasets
    from pathlib import Path
    demo_dir = Path(__file__).resolve().parent.parent.parent / "demo-data" / "synthetic"
    if not demo_dir.exists():
        demo_dir = Path("/app/demo-data/synthetic")
    if not demo_dir.exists():
        demo_dir = Path(__file__).resolve().parent.parent / "demo-data" / "synthetic"

    cadastral_file = demo_dir / "cadastral_parcels_synth.geojson"
    drone_file = demo_dir / "drone_structures_synth.geojson"

    if not cadastral_file.exists() or not drone_file.exists():
        pytest.skip("Demo data files not mounted in container test environment")

    proj_resp = await client.post("/api/v1/projects", json={"name": "Seed Demo Review Project"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    with open(cadastral_file, "rb") as f:
        cad_resp = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("cadastral.geojson", f, "application/geo+json")},
        )
    with open(drone_file, "rb") as f:
        drone_resp = await client.post(
            f"/api/v1/projects/{proj_id}/datasets",
            files={"file": ("drone.geojson", f, "application/geo+json")},
        )
    assert cad_resp.status_code == 201
    assert drone_resp.status_code == 201

    run_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={
            "source_dataset_id": cad_resp.json()["id"],
            "candidate_dataset_ids": [drone_resp.json()["id"]],
        },
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Seed demo reviews
    seed_resp = await client.post(f"/api/v1/matching-runs/{run_id}/seed-demo-reviews")
    assert seed_resp.status_code == 200
    stats = seed_resp.json()
    assert stats["accepted"] >= 1
    assert stats["rejected"] >= 1
    assert stats["flagged"] >= 1
    assert stats["reviewed"] == stats["accepted"] + stats["rejected"] + stats["flagged"]
    assert stats["pending_review"] > 0

