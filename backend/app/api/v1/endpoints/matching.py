import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.schemas.matching import (
    MatchingRunCreateRequest,
    MatchingRunRead,
    MatchingRunListResponse,
    FeatureMatchListItem,
    FeatureMatchListResponse,
    SourceFeatureCandidateItem,
    SourceFeatureSummaryResponse,
    MatchDetailResponse,
    MatchReviewCreateInput,
    MatchReviewResponse,
    ReviewQueueResponse,
    ReviewStatisticsResponse,
)
from app.services.matching.config import MatchingConfig
from app.services.matching.service import MatchingService, extract_feature_display_id

router = APIRouter()


@router.post(
    "/projects/{project_id}/matching-runs",
    response_model=MatchingRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start Matching Run",
    description="Executes a spatial candidate search and multi-signal feature reconciliation run across project datasets.",
)
async def create_matching_run(
    project_id: uuid.UUID,
    data: MatchingRunCreateRequest,
    db: Annotated[AsyncSession, SessionDep],
) -> MatchingRunRead:
    config = None
    if data.configuration:
        config = MatchingConfig(**data.configuration.model_dump())

    try:
        run = await MatchingService.create_and_run_matching(
            db=db,
            project_id=project_id,
            source_dataset_id=data.source_dataset_id,
            candidate_dataset_ids=data.candidate_dataset_ids,
            config=config,
        )
        return MatchingRunRead.model_validate(run)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during matching run: {str(exc)}",
        )


@router.get(
    "/projects/{project_id}/matching-runs",
    response_model=MatchingRunListResponse,
    summary="List Matching Runs",
    description="Retrieves a list of previous matching analysis runs for a project.",
)
async def list_matching_runs(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> MatchingRunListResponse:
    runs, total = await MatchingService.list_matching_runs(db, project_id=project_id, skip=skip, limit=limit)
    return MatchingRunListResponse(
        items=[MatchingRunRead.model_validate(r) for r in runs],
        total=total,
    )


@router.get(
    "/matching-runs/{run_id}",
    response_model=MatchingRunRead,
    summary="Get Matching Run Summary",
    description="Fetches aggregate statistics and configuration for a specific matching run.",
)
async def get_matching_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> MatchingRunRead:
    run = await MatchingService.get_matching_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Matching run with ID '{run_id}' not found.",
        )
    return MatchingRunRead.model_validate(run)


@router.get(
    "/matching-runs/{run_id}/matches",
    response_model=FeatureMatchListResponse,
    summary="List Run Matches",
    description="Retrieves filtered and sorted feature match results for a matching run.",
)
async def get_run_matches(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    status: Optional[str] = Query(None, description="Filter by status: matched, possible_match, conflict, unmatched"),
    candidate_role: Optional[str] = Query(None, description="Filter by candidate role: BEST, SECONDARY, AMBIGUOUS, CONFLICT, UNMATCHED"),
    is_best_only: Optional[bool] = Query(None, description="Only return best candidate records"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum overall confidence score"),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum overall confidence score"),
    source_dataset_id: Optional[uuid.UUID] = Query(None),
    candidate_dataset_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> FeatureMatchListResponse:
    run = await MatchingService.get_matching_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Matching run with ID '{run_id}' not found.",
        )

    matches, total = await MatchingService.get_run_matches(
        db=db,
        run_id=run_id,
        status=status,
        candidate_role=candidate_role,
        is_best_only=is_best_only,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        source_dataset_id=source_dataset_id,
        candidate_dataset_id=candidate_dataset_id,
        skip=skip,
        limit=limit,
    )

    items: list[FeatureMatchListItem] = []
    for m in matches:
        src_id_str = extract_feature_display_id(m.source_feature) or "N/A"
        cand_id_str = extract_feature_display_id(m.candidate_feature)

        items.append(
            FeatureMatchListItem(
                id=m.id,
                match_run_id=m.match_run_id,
                project_id=m.project_id,
                source_feature_id=m.source_feature_id,
                candidate_feature_id=m.candidate_feature_id,
                source_dataset_id=m.source_dataset_id,
                candidate_dataset_id=m.candidate_dataset_id,
                source_identifier=src_id_str,
                candidate_identifier=cand_id_str,
                source_geometry_type=m.source_feature.geometry_type if m.source_feature else "Unknown",
                candidate_geometry_type=m.candidate_feature.geometry_type if m.candidate_feature else None,
                source_dataset_name=m.source_dataset.name if m.source_dataset else "Source Dataset",
                candidate_dataset_name=m.candidate_dataset.name if m.candidate_dataset else None,
                spatial_score=m.spatial_score,
                centroid_score=m.centroid_score,
                area_score=m.area_score,
                geometry_score=m.geometry_score,
                attribute_score=m.attribute_score,
                overall_score=m.overall_score,
                status=m.status,
                rank=m.rank,
                is_best_candidate=m.is_best_candidate,
                candidate_role=m.candidate_role,
                score_gap=m.score_gap,
                candidate_count=m.candidate_count,
                review_status=m.review_status,
                explanation=m.explanation,
                created_at=m.created_at,
            )
        )

    return FeatureMatchListResponse(items=items, total=total)


@router.get(
    "/matching-runs/{run_id}/review-queue",
    response_model=ReviewQueueResponse,
    summary="Get Review Queue",
    description="Retrieves prioritized candidate relationships requiring human review (AMBIGUOUS, CONFLICT, POSSIBLE_MATCH, PENDING).",
)
async def get_review_queue(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    category: Optional[str] = Query(None, description="Category filter: pending, ambiguous, conflict, possible, reviewed, accepted, rejected, flagged, all"),
    decision: Optional[str] = Query(None, description="Direct decision filter: ACCEPTED, REJECTED, FLAGGED, PENDING"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ReviewQueueResponse:
    run = await MatchingService.get_matching_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Matching run with ID '{run_id}' not found.",
        )

    queue_data = await MatchingService.get_review_queue(
        db=db,
        run_id=run_id,
        category=category,
        decision=decision,
        skip=skip,
        limit=limit,
    )
    return ReviewQueueResponse(**queue_data)


@router.get(
    "/matching-runs/{run_id}/review-statistics",
    response_model=ReviewStatisticsResponse,
    summary="Get Review Statistics",
    description="Computes run-level aggregate counts of human review decisions (pending, accepted, rejected, flagged).",
)
async def get_review_statistics(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> ReviewStatisticsResponse:
    run = await MatchingService.get_matching_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Matching run with ID '{run_id}' not found.",
        )

    stats = await MatchingService.get_review_statistics(db=db, run_id=run_id)
    return ReviewStatisticsResponse(**stats)


@router.post(
    "/matching-runs/{run_id}/seed-demo-reviews",
    response_model=ReviewStatisticsResponse,
    summary="Seed Deterministic Demo Reviews",
    description="Seeds demonstration human decisions (1 accepted, 1 rejected, 1 flagged) for prototype evaluation.",
)
async def seed_demo_reviews(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> ReviewStatisticsResponse:
    run = await MatchingService.get_matching_run(db, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Matching run with ID '{run_id}' not found.",
        )

    stats = await MatchingService.seed_demo_reviews(db=db, run_id=run_id)
    return ReviewStatisticsResponse(**stats)


@router.get(
    "/matching-runs/{run_id}/source-features/{feature_id}/candidates",
    response_model=list[SourceFeatureCandidateItem],
    summary="Get Candidates for Source Feature",
    description="Retrieves all evaluated candidate matches for a single source feature, ordered by rank.",
)
async def get_source_feature_candidates(
    run_id: uuid.UUID,
    feature_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> list[SourceFeatureCandidateItem]:
    candidates = await MatchingService.get_source_feature_candidates(db, run_id=run_id, feature_id=feature_id)
    return [SourceFeatureCandidateItem(**c) for c in candidates]


@router.get(
    "/matching-runs/{run_id}/source-features/{feature_id}/summary",
    response_model=SourceFeatureSummaryResponse,
    summary="Get Source Feature Match Summary",
    description="Retrieves aggregated summary for a source feature with candidates list, best candidate, second-best score, and score gap.",
)
async def get_source_feature_summary(
    run_id: uuid.UUID,
    feature_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> SourceFeatureSummaryResponse:
    summary = await MatchingService.get_source_feature_summary(db, run_id=run_id, feature_id=feature_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source feature '{feature_id}' not found in matching run '{run_id}'.",
        )
    return SourceFeatureSummaryResponse(**summary)


@router.get(
    "/matches/{match_id}",
    response_model=MatchDetailResponse,
    summary="Get Match Details",
    description="Retrieves complete explanation breakdown, geometries, and review history for a feature match pair.",
)
@router.get(
    "/feature-matches/{match_id}",
    response_model=MatchDetailResponse,
    include_in_schema=False,
)
async def get_match_detail(
    match_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> MatchDetailResponse:
    detail = await MatchingService.get_match_detail(db, match_id=match_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature match with ID '{match_id}' not found.",
        )
    return MatchDetailResponse(**detail)


@router.post(
    "/matches/{match_id}/review",
    response_model=MatchReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Human Review Decision",
    description="Records an ACCEPTED, REJECTED, or FLAGGED decision with optional comments. Preserves original machine scores untouched.",
)
@router.post(
    "/feature-matches/{match_id}/review",
    response_model=MatchReviewResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def record_match_review(
    match_id: uuid.UUID,
    data: MatchReviewCreateInput,
    db: Annotated[AsyncSession, SessionDep],
) -> MatchReviewResponse:
    try:
        review = await MatchingService.record_match_review(
            db=db,
            match_id=match_id,
            decision=data.decision,
            comment=data.comment,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature match with ID '{match_id}' not found.",
        )

    return MatchReviewResponse(**review)

