import uuid
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Polygon, Point, box

from app.models.matching import MatchRun, FeatureMatch
from app.services.matching.config import MatchingConfig
from app.services.matching.signals import MatchingSignals, haversine_distance_meters
from app.services.matching.scoring import ScoringEngine


# ---------------------------------------------------------------------------
# 1. Signal Unit Tests
# ---------------------------------------------------------------------------

def test_haversine_distance_calculation():
    # Pune location (~73.8567, 18.5204) to shifted location (~73.8577, 18.5204)
    # 0.001 deg longitude at 18.5 deg latitude is ~105 meters
    dist = haversine_distance_meters(73.8567, 18.5204, 73.8577, 18.5204)
    assert 95.0 < dist < 115.0


def test_spatial_overlap_signal():
    p1 = box(73.850, 18.520, 73.852, 18.522)
    # Identical
    assert MatchingSignals.spatial_overlap(p1, p1) == 1.0

    # 50% shifted overlap
    p2 = box(73.851, 18.520, 73.853, 18.522)
    overlap = MatchingSignals.spatial_overlap(p1, p2)
    assert overlap is not None
    assert 0.30 < overlap < 0.40  # Intersection area 1, Union area 3 -> 0.333

    # Disjoint
    p3 = box(73.860, 18.530, 73.862, 18.532)
    assert MatchingSignals.spatial_overlap(p1, p3) == 0.0

    # Non-polygonal (Point) returns None (not applicable)
    pt = Point(73.851, 18.521)
    assert MatchingSignals.spatial_overlap(pt, p1) is None


def test_centroid_distance_signal():
    p1 = Point(73.856744, 18.520430)
    # Same point
    assert MatchingSignals.centroid_distance(p1, p1, max_distance_meters=50.0) == 1.0

    # Distant point (> 1 km away)
    p2 = Point(73.870000, 18.530000)
    assert MatchingSignals.centroid_distance(p1, p2, max_distance_meters=50.0) == 0.0


def test_area_similarity_signal():
    p1 = box(0, 0, 10, 10)  # area = 100
    p2 = box(0, 0, 10, 10)  # area = 100
    p3 = box(0, 0, 10, 5)   # area = 50

    assert MatchingSignals.area_similarity(p1, p2) == 1.0
    assert MatchingSignals.area_similarity(p1, p3) == 0.5

    # Point returns None
    assert MatchingSignals.area_similarity(Point(0, 0), p1) is None


def test_geometry_similarity_signal():
    poly = box(73.850, 18.520, 73.860, 18.530)
    pt_inside = Point(73.855, 18.525)
    pt_outside = Point(73.870, 18.540)

    # Point inside polygon gets containment score 1.0
    assert MatchingSignals.geometry_similarity(pt_inside, poly) == 1.0
    # Point outside polygon gets distance-penalized score
    assert MatchingSignals.geometry_similarity(pt_outside, poly) < 0.5


def test_attribute_similarity_exact_and_semantic():
    props_a = {
        "parcel_id": "CP-1001",
        "owner_name": "Ramesh Sharma",
        "area_sqm": 500.0,
        "land_use": "Residential",
    }
    props_b = {
        "property_id": "CP-1001",           # Semantic identifier match
        "facility_name": "Ramesh Sharma",   # Semantic name match
        "footprint_area_sqm": 490.0,        # Numeric relative match (~98%)
        "type": "Residential",              # Semantic type match
    }

    score, details = MatchingSignals.attribute_similarity(props_a, props_b)
    assert score > 0.90
    assert len(details["matched_fields"]) >= 3


def test_attribute_similarity_mismatch():
    props_a = {"parcel_id": "CP-1001", "owner": "Alice"}
    props_b = {"parcel_id": "CP-9999", "owner": "Zachary"}

    score, _ = MatchingSignals.attribute_similarity(props_a, props_b)
    assert score < 0.10


# ---------------------------------------------------------------------------
# 2. Scoring Engine & Classification Tests
# ---------------------------------------------------------------------------

def test_weight_renormalization_point_vs_point():
    config = MatchingConfig()
    # For point vs point: spatial overlap and area are None
    overall, status, exp = ScoringEngine.evaluate_match(
        spatial_score=None,
        centroid_score=0.95,
        area_score=None,
        geometry_score=0.95,
        attribute_score=0.90,
        attribute_details={"matched_fields": []},
        config=config,
        geom_type_a="Point",
        geom_type_b="Point",
    )

    # Weights for centroid (0.2), geometry (0.15), attribute (0.10) sum to 0.45
    # Overall score should be ~0.94, classified as 'matched'
    assert overall > 0.90
    assert status == "matched"
    assert "reasons" in exp
    assert exp["component_scores"]["spatial_overlap"] is None


def test_conflict_classification_logic():
    config = MatchingConfig()
    # Strong spatial overlap (0.95), but severe attribute conflict (0.0)
    overall, status, exp = ScoringEngine.evaluate_match(
        spatial_score=0.95,
        centroid_score=0.95,
        area_score=0.90,
        geometry_score=0.95,
        attribute_score=0.05,
        attribute_details={"matched_fields": [{"field_a": "owner", "field_b": "owner", "similarity": 0.0}]},
        config=config,
    )

    assert status == "conflict"
    assert any("conflict" in r.lower() for r in exp["reasons"])


def test_unmatched_classification_low_score():
    config = MatchingConfig()
    overall, status, _ = ScoringEngine.evaluate_match(
        spatial_score=0.0,
        centroid_score=0.1,
        area_score=0.1,
        geometry_score=0.05,
        attribute_score=0.1,
        attribute_details={"matched_fields": []},
        config=config,
    )
    assert overall < 0.40
    assert status == "unmatched"


# ---------------------------------------------------------------------------
# 3. Integration & End-to-End API Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matching_run_lifecycle_and_apis(client: AsyncClient, db_session: AsyncSession):
    # 1. Create Project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Reconciliation Test", "target_crs": "EPSG:4326"})
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload Cadastral Parcels Dataset (Source)
    cadastral_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-1", "owner": "John Doe", "area_sqm": 500},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-2", "owner": "Jane Smith", "area_sqm": 600},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.87, 18.52], [73.88, 18.52], [73.88, 18.53], [73.87, 18.53], [73.87, 18.52]]],
                },
            },
        ],
    }
    src_resp = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson), "application/geo+json")},
    )
    assert src_resp.status_code == 201
    src_dataset_id = src_resp.json()["id"]

    # 3. Upload Municipal Assets Dataset (Candidate 1 - Point inside P-1)
    csv_content = (
        "asset_id,property_id,facility_name,latitude,longitude\n"
        "AST-1,P-1,John Doe Property,18.525,73.855\n"
    )
    cand_resp = await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("municipal.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert cand_resp.status_code == 201
    cand_dataset_id = cand_resp.json()["id"]

    # 4. Trigger Matching Run
    run_payload = {
        "source_dataset_id": src_dataset_id,
        "candidate_dataset_ids": [cand_dataset_id],
        "configuration": {
            "candidate_search_distance_meters": 100.0,
            "matched_threshold": 0.75,
            "possible_threshold": 0.55,
        },
    }
    run_resp = await client.post(f"/api/v1/projects/{project_id}/matching-runs", json=run_payload)
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    run_id = run_data["id"]

    assert run_data["status"] == "completed"
    assert run_data["total_features_processed"] == 2
    # P-1 has candidate AST-1, P-2 has no candidates within 100m -> 1 candidate, 1 unmatched
    assert run_data["total_candidates"] == 1
    assert run_data["total_unmatched"] == 1

    # 5. List Matching Runs API
    list_runs_resp = await client.get(f"/api/v1/projects/{project_id}/matching-runs")
    assert list_runs_resp.status_code == 200
    assert list_runs_resp.json()["total"] == 1

    # 6. Get Matching Run by ID
    get_run_resp = await client.get(f"/api/v1/matching-runs/{run_id}")
    assert get_run_resp.status_code == 200
    assert get_run_resp.json()["id"] == run_id

    # 7. Get Matches for Run
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches_data = matches_resp.json()
    assert matches_data["total"] == 2  # 1 candidate match + 1 unmatched record

    # Find the candidate match
    matched_items = [m for m in matches_data["items"] if m["candidate_feature_id"] is not None]
    assert len(matched_items) == 1
    match_item = matched_items[0]
    assert match_item["source_identifier"] == "P-1"
    assert match_item["candidate_identifier"] == "AST-1"
    assert match_item["overall_score"] > 0.70

    # 8. Get Single Match Detail API (with geometries)
    detail_resp = await client.get(f"/api/v1/matches/{match_item['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["source_feature"]["geometry"] is not None
    assert detail["candidate_feature"]["geometry"] is not None
    assert "explanation" in detail
    assert "reasons" in detail["explanation"]


@pytest.mark.asyncio
async def test_cross_project_matching_prevention(client: AsyncClient):
    # Create Project 1 and Dataset 1
    p1_resp = await client.post("/api/v1/projects", json={"name": "Project 1"})
    p1_id = p1_resp.json()["id"]
    csv1 = "id,latitude,longitude\n1,18.52,73.85\n"
    ds1_resp = await client.post(
        f"/api/v1/projects/{p1_id}/datasets",
        files={"file": ("d1.csv", csv1.encode("utf-8"), "text/csv")},
    )
    ds1_id = ds1_resp.json()["id"]

    # Create Project 2 and Dataset 2
    p2_resp = await client.post("/api/v1/projects", json={"name": "Project 2"})
    p2_id = p2_resp.json()["id"]
    csv2 = "id,latitude,longitude\n2,18.52,73.85\n"
    ds2_resp = await client.post(
        f"/api/v1/projects/{p2_id}/datasets",
        files={"file": ("d2.csv", csv2.encode("utf-8"), "text/csv")},
    )
    ds2_id = ds2_resp.json()["id"]

    # Attempt to compare across projects should fail
    resp = await client.post(
        f"/api/v1/projects/{p1_id}/matching-runs",
        json={"source_dataset_id": ds1_id, "candidate_dataset_ids": [ds2_id]},
    )
    assert resp.status_code == 400
    assert "does not belong to project" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_self_dataset_matching_prevention(client: AsyncClient):
    p_resp = await client.post("/api/v1/projects", json={"name": "Self Match Test"})
    p_id = p_resp.json()["id"]
    csv1 = "id,latitude,longitude\n1,18.52,73.85\n"
    ds_resp = await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files={"file": ("d1.csv", csv1.encode("utf-8"), "text/csv")},
    )
    ds_id = ds_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{p_id}/matching-runs",
        json={"source_dataset_id": ds_id, "candidate_dataset_ids": [ds_id]},
    )
    assert resp.status_code == 400
    assert "cannot be compared against itself" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_directional_matching_and_historical_preservation(client: AsyncClient):
    # Create Project
    p_resp = await client.post("/api/v1/projects", json={"name": "Directional Test"})
    p_id = p_resp.json()["id"]

    # Dataset A (Point at 18.520, 73.850)
    csv_a = "id,name,latitude,longitude\nA-1,Alpha,18.520,73.850\n"
    ds_a_resp = await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files={"file": ("dataset_a.csv", csv_a.encode("utf-8"), "text/csv")},
    )
    ds_a_id = ds_a_resp.json()["id"]

    # Dataset B (Point shifted 10m away)
    csv_b = "id,name,latitude,longitude\nB-1,Alpha,18.52008,73.850\n"
    ds_b_resp = await client.post(
        f"/api/v1/projects/{p_id}/datasets",
        files={"file": ("dataset_b.csv", csv_b.encode("utf-8"), "text/csv")},
    )
    ds_b_id = ds_b_resp.json()["id"]

    # Run 1: Direction A -> B
    run1_resp = await client.post(
        f"/api/v1/projects/{p_id}/matching-runs",
        json={"source_dataset_id": ds_a_id, "candidate_dataset_ids": [ds_b_id]},
    )
    assert run1_resp.status_code == 201
    run1_id = run1_resp.json()["id"]

    # Run 2: Direction B -> A
    run2_resp = await client.post(
        f"/api/v1/projects/{p_id}/matching-runs",
        json={"source_dataset_id": ds_b_id, "candidate_dataset_ids": [ds_a_id]},
    )
    assert run2_resp.status_code == 201
    run2_id = run2_resp.json()["id"]

    # Both runs must exist independently (historical preservation)
    runs_resp = await client.get(f"/api/v1/projects/{p_id}/matching-runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()["items"]
    assert len(runs) == 2
    assert {r["id"] for r in runs} == {run1_id, run2_id}

    # Verify Run 1 has Source A-1 and Candidate B-1
    m1_resp = await client.get(f"/api/v1/matching-runs/{run1_id}/matches")
    m1_items = m1_resp.json()["items"]
    assert len(m1_items) == 1
    assert m1_items[0]["source_identifier"] == "A-1"
    assert m1_items[0]["candidate_identifier"] == "B-1"

    # Verify Run 2 has Source B-1 and Candidate A-1 (respecting direction)
    m2_resp = await client.get(f"/api/v1/matching-runs/{run2_id}/matches")
    m2_items = m2_resp.json()["items"]
    assert len(m2_items) == 1
    assert m2_items[0]["source_identifier"] == "B-1"
    assert m2_items[0]["candidate_identifier"] == "A-1"


# ---------------------------------------------------------------------------
# 4. Milestone 3.1: Candidate Ranking & Ambiguity Tests
# ---------------------------------------------------------------------------

def test_candidate_ranker_unit_logic():
    from app.services.matching.ranker import CandidateRanker
    config = MatchingConfig(best_candidate_tie_tolerance=0.015)
    src_id = uuid.uuid4()
    run_id = uuid.uuid4()
    proj_id = uuid.uuid4()

    # Case A: Clear winner with multiple candidates
    matches_clear = [
        FeatureMatch(
            id=uuid.uuid4(), match_run_id=run_id, project_id=proj_id,
            source_feature_id=src_id, candidate_feature_id=uuid.uuid4(),
            source_dataset_id=uuid.uuid4(), overall_score=0.72, status="possible_match"
        ),
        FeatureMatch(
            id=uuid.uuid4(), match_run_id=run_id, project_id=proj_id,
            source_feature_id=src_id, candidate_feature_id=uuid.uuid4(),
            source_dataset_id=uuid.uuid4(), overall_score=0.91, status="matched"
        ),
        FeatureMatch(
            id=uuid.uuid4(), match_run_id=run_id, project_id=proj_id,
            source_feature_id=src_id, candidate_feature_id=uuid.uuid4(),
            source_dataset_id=uuid.uuid4(), overall_score=0.55, status="unmatched"
        ),
    ]

    metrics = CandidateRanker.rank_matches_for_run(matches_clear, config)
    assert metrics["total_source_features"] == 1
    assert metrics["features_with_candidates"] == 1
    assert metrics["features_with_multiple_candidates"] == 1
    assert metrics["features_with_unambiguous_best"] == 1
    assert metrics["features_with_ambiguous_best"] == 0

    # Verify rank order: 0.91 -> rank 1, 0.72 -> rank 2, 0.55 -> rank 3
    sorted_m = sorted(matches_clear, key=lambda m: m.rank)
    assert sorted_m[0].overall_score == 0.91
    assert sorted_m[0].rank == 1
    assert sorted_m[0].is_best_candidate is True
    assert sorted_m[0].candidate_role == "BEST"
    assert sorted_m[0].candidate_count == 3
    assert sorted_m[0].score_gap == 0.19  # 0.91 - 0.72

    assert sorted_m[1].overall_score == 0.72
    assert sorted_m[1].rank == 2
    assert sorted_m[1].is_best_candidate is False
    assert sorted_m[1].candidate_role == "SECONDARY"

    # Case B: Near tie (Ambiguous)
    src_id_b = uuid.uuid4()
    matches_tied = [
        FeatureMatch(
            id=uuid.uuid4(), match_run_id=run_id, project_id=proj_id,
            source_feature_id=src_id_b, candidate_feature_id=uuid.uuid4(),
            source_dataset_id=uuid.uuid4(), overall_score=0.850, status="matched"
        ),
        FeatureMatch(
            id=uuid.uuid4(), match_run_id=run_id, project_id=proj_id,
            source_feature_id=src_id_b, candidate_feature_id=uuid.uuid4(),
            source_dataset_id=uuid.uuid4(), overall_score=0.842, status="matched"
        ),
    ]
    metrics_tied = CandidateRanker.rank_matches_for_run(matches_tied, config)
    assert metrics_tied["features_with_ambiguous_best"] == 1
    assert metrics_tied["features_with_unambiguous_best"] == 0

    assert matches_tied[0].candidate_role == "AMBIGUOUS"
    assert matches_tied[0].is_best_candidate is False
    assert matches_tied[1].candidate_role == "AMBIGUOUS"
    assert matches_tied[1].is_best_candidate is False
    assert matches_tied[0].score_gap == 0.008  # 0.850 - 0.842 <= 0.015


@pytest.mark.asyncio
async def test_multi_candidate_ranking_api(client: AsyncClient):
    # Create Project
    proj_resp = await client.post("/api/v1/projects", json={"name": "Ranking Test"})
    proj_id = proj_resp.json()["id"]

    # Source Dataset: 1 Cadastral Parcel
    cadastral_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-100", "owner": "Alice"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]],
                },
            }
        ],
    }
    src_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("cadastral.geojson", json.dumps(cadastral_geojson), "application/geo+json")},
    )
    src_ds_id = src_resp.json()["id"]

    # Candidate Dataset: 3 Municipal Records near/inside P-100
    # AST-1 (centered, matching ID/owner), AST-2 (edge, matching ID), AST-3 (near tolerance edge)
    csv_content = (
        "asset_id,property_id,facility_name,latitude,longitude\n"
        "AST-1,P-100,Alice,18.525,73.855\n"
        "AST-2,P-100,Alice Subsidiary,18.528,73.858\n"
        "AST-3,P-999,Unrelated,18.5205,73.8505\n"
    )
    cand_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        files={"file": ("municipal.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    cand_ds_id = cand_resp.json()["id"]

    # Trigger Matching Run
    run_resp = await client.post(
        f"/api/v1/projects/{proj_id}/matching-runs",
        json={"source_dataset_id": src_ds_id, "candidate_dataset_ids": [cand_ds_id]},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()
    run_id = run["id"]

    # Verify quality metrics
    qm = run.get("quality_metrics", {})
    assert qm.get("total_source_features") == 1
    assert qm.get("features_with_candidates") == 1
    assert qm.get("features_with_multiple_candidates") == 1
    assert qm.get("features_with_unambiguous_best") == 1

    # Get matches
    matches_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()["items"]
    assert len(matches) == 3

    # Check rank ordering
    assert matches[0]["rank"] == 1
    assert matches[0]["candidate_identifier"] == "AST-1"
    assert matches[0]["is_best_candidate"] is True
    assert matches[0]["candidate_role"] == "BEST"
    assert matches[0]["candidate_count"] == 3
    assert matches[0]["score_gap"] is not None and matches[0]["score_gap"] > 0

    assert matches[1]["rank"] == 2
    assert matches[1]["candidate_identifier"] == "AST-2"
    assert matches[1]["is_best_candidate"] is False
    assert matches[1]["candidate_role"] == "SECONDARY"

    assert matches[2]["rank"] == 3
    assert matches[2]["is_best_candidate"] is False

    # Test filtering by role=BEST
    best_resp = await client.get(f"/api/v1/matching-runs/{run_id}/matches?candidate_role=BEST")
    assert best_resp.status_code == 200
    assert best_resp.json()["total"] == 1
    assert best_resp.json()["items"][0]["candidate_identifier"] == "AST-1"

    # Test source-level candidates endpoint
    src_feat_id = matches[0]["source_feature_id"]
    cands_resp = await client.get(f"/api/v1/matching-runs/{run_id}/source-features/{src_feat_id}/candidates")
    assert cands_resp.status_code == 200
    cands = cands_resp.json()
    assert len(cands) == 3
    assert cands[0]["rank"] == 1
    assert cands[0]["candidate_role"] == "BEST"

    # Test source-level summary endpoint
    summary_resp = await client.get(f"/api/v1/matching-runs/{run_id}/source-features/{src_feat_id}/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["candidate_count"] == 3
    assert summary["best_candidate_identifier"] == "AST-1"
    assert summary["score_gap"] is not None
    assert summary["candidate_role"] == "BEST"


