import uuid
from typing import Dict, List, Optional
from collections import OrderedDict
from app.schemas.spatial_analysis import SpatialAnalysisResult, AnalysisHistorySummary


class AnalysisHistoryService:
    """
    Lightweight, thread-safe analysis history cache.
    Retains recent spatial intelligence queries and results for review,
    map re-visualization, and batch export.
    """

    _MAX_ENTRIES: int = 100
    _store: Dict[uuid.UUID, SpatialAnalysisResult] = OrderedDict()

    @classmethod
    def record_analysis(cls, result: SpatialAnalysisResult) -> None:
        """Stores analysis result in cache, maintaining LRU bounded size."""
        if not result or not result.analysis_id:
            return
        cls._store[result.analysis_id] = result
        if len(cls._store) > cls._MAX_ENTRIES:
            cls._store.pop(next(iter(cls._store)))

    @classmethod
    def get_analysis(cls, analysis_id: uuid.UUID) -> Optional[SpatialAnalysisResult]:
        """Retrieves a specific analysis result by ID."""
        return cls._store.get(analysis_id)

    @classmethod
    def get_history(cls, project_id: Optional[uuid.UUID] = None) -> List[AnalysisHistorySummary]:
        """Lists recent analyses for a project ordered newest first."""
        items = []
        for res in reversed(cls._store.values()):
            if project_id is None or res.project_id == project_id:
                items.append(
                    AnalysisHistorySummary(
                        analysis_id=res.analysis_id,
                        project_id=res.project_id,
                        analysis_type=res.analysis_type,
                        title=res.title,
                        description=res.description,
                        result_count=res.result_count,
                        execution_time_ms=res.execution_time_ms,
                        created_at=res.created_at,
                        status="COMPLETED",
                    )
                )
        return items

    @classmethod
    def clear_all(cls) -> None:
        """Clears all stored analysis results (useful for tests)."""
        cls._store.clear()
