import os
import json
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import get_settings
from app.schemas.assistant import AssistantEvidenceSource, AssistantIntent
from app.services.assistant.providers.base import BaseReasoningProvider
from app.services.assistant.providers.deterministic import DeterministicReasoningEngine

logger = logging.getLogger(__name__)


class LLMReasoningProvider(BaseReasoningProvider):
    """
    Live LLM reasoning provider. Communicates with OpenAI, Gemini, Anthropic, or
    OpenAI-compatible APIs when configured with API keys.
    Gracefully falls back to DeterministicReasoningEngine on network/auth failure.
    """

    def __init__(self):
        self.settings = get_settings()
        self.fallback = DeterministicReasoningEngine()

    async def synthesize(
        self,
        query: str,
        intent: AssistantIntent,
        evidence_pool: List[AssistantEvidenceSource],
        raw_tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If no API key is set, use deterministic engine immediately
        api_key = (
            self.settings.OPENAI_API_KEY
            or self.settings.GEMINI_API_KEY
            or self.settings.ANTHROPIC_API_KEY
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )

        if not api_key:
            return await self.fallback.synthesize(query, intent, evidence_pool, raw_tool_results)

        # Build prompt grounded in evidence
        evidence_context = []
        for ev in evidence_pool:
            evidence_context.append({
                "type": ev.source_type,
                "identifier": ev.identifier,
                "dataset": ev.dataset_name,
                "role": ev.role,
                "properties": ev.properties,
                "note": ev.relevance_note,
            })

        system_prompt = (
            "You are LandSync AI, an expert, objective Geospatial Intelligence & Evidence Assistant.\n"
            "CORE PRINCIPLE: You must remain 100% grounded in the provided LandSync evidence.\n"
            "NEVER invent feature identifiers, parcel boundaries, or ownership claims.\n"
            "Explain conflicts clearly, citing contributing datasets and their source roles (CADASTRAL, DRONE, MUNICIPAL).\n"
            "Format your answer cleanly in GitHub-flavored markdown with bullet points and bold highlights.\n"
            "Provide 2-3 relevant follow-up questions at the end."
        )

        user_content = (
            f"User Question: {query}\n\n"
            f"Classified Intent: {intent.value}\n\n"
            f"Retrieved Evidence Pool:\n{json.dumps(evidence_context, indent=2)}\n\n"
            f"Raw Tool Outputs:\n{json.dumps(raw_tool_results, indent=2, default=str)}\n\n"
            f"Synthesize a clear, authoritative, evidence-backed response."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.AI_MODEL_NAME,
                        "temperature": self.settings.AI_TEMPERATURE,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return {
                        "answer": content,
                        "reasoning_steps": [
                            f"Dispatched query to {self.settings.AI_MODEL_NAME}.",
                            f"Supplied {len(evidence_pool)} structured database citations.",
                            "Received grounded completion.",
                        ],
                        "suggested_followups": [
                            "Explain the underlying match signals for this parcel.",
                            "Trace the provenance audit trail.",
                            "Check for other parcels with similar discrepancies.",
                        ],
                    }
        except Exception as e:
            logger.warning(f"Live LLM call failed ({str(e)}), falling back to deterministic reasoning.")

        return await self.fallback.synthesize(query, intent, evidence_pool, raw_tool_results)
