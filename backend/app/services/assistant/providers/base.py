from abc import ABC, abstractmethod
from typing import Dict, Any, List
from app.schemas.assistant import AssistantEvidenceSource, AssistantIntent


class BaseReasoningProvider(ABC):
    """Abstract base class for reasoning providers (LLM and deterministic fallback)."""

    @abstractmethod
    async def synthesize(
        self,
        query: str,
        intent: AssistantIntent,
        evidence_pool: List[AssistantEvidenceSource],
        raw_tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Synthesizes a grounded answer, reasoning steps, and follow-up suggestions
        based strictly on the retrieved evidence pool.
        """
        pass
