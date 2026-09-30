import re
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, TypedDict
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, START, END

from app.schemas.assistant import (
    AssistantIntent,
    AssistantEvidenceSource,
    AssistantQueryRequest,
    AssistantQueryResponse,
)
from app.services.assistant.tools import (
    get_project_summary,
    get_unified_record_evidence,
    get_conflict_evidence,
    get_provenance_trail,
    find_records_near_coordinates,
    find_records_in_bbox,
    compare_feature_geometries,
    search_unified_records_by_attributes,
    search_source_features,
    search_evidence_knowledge_base,
)
from app.services.assistant.verifier import EvidenceVerifier
from app.services.assistant.providers.llm_provider import LLMReasoningProvider

logger = logging.getLogger(__name__)


class AssistantState(TypedDict, total=False):
    """Internal graph execution state for the LandSync Evidence Assistant."""
    query: str
    project_id: uuid.UUID
    context_record_id: Optional[uuid.UUID]
    context_conflict_id: Optional[uuid.UUID]
    context_match_id: Optional[uuid.UUID]
    db: AsyncSession
    intent: AssistantIntent
    plan: List[str]
    executed_workers: List[str]
    raw_tool_results: Dict[str, Any]
    evidence_pool: List[AssistantEvidenceSource]
    retrieved_documents: List[Dict[str, Any]]
    reasoning_steps: List[str]
    raw_answer: str
    final_answer: str
    cited_sources: List[AssistantEvidenceSource]
    suggested_followups: List[str]
    grounded_score: float
    error: Optional[str]


def planner_node(state: AssistantState) -> Dict[str, Any]:
    """
    Supervisor / Planner Node:
    Analyzes user query and context parameters, classifies intent, and constructs
    a sequential multi-worker investigation plan.
    """
    query = state.get("query", "").lower()
    ctx_conflict = state.get("context_conflict_id")
    ctx_record = state.get("context_record_id")

    reasoning_steps = list(state.get("reasoning_steps", []))

    # Determine intent & multi-step plan
    is_complex = any(k in query for k in [
        "final value determined", "complete investigation", "detailed report",
        "lineage and conflict", "discrepancies and provenance", "multi-step",
        "full report", "comprehensive analysis",
    ]) or (
        ("why is" in query or "how was" in query)
        and any(k in query for k in ["final value", "how was it determined", "lineage", "timeline and conflict"])
    )

    if is_complex:
        intent = AssistantIntent.COMPLEX_INVESTIGATION
        plan = ["db_worker", "spatial_worker", "rag_worker"]
        reasoning_steps.append("Supervisor: Intent classified as COMPLEX_INVESTIGATION. Formulated 3-step investigation plan [db_worker -> spatial_worker -> rag_worker].")

    elif ctx_conflict or any(k in query for k in [
        "conflict", "discrepancy", "mismatch", "incompatible", "why is this flagged",
        "why was it resolved", "attribute conflict", "unresolved"
    ]):
        intent = AssistantIntent.CONFLICT_EXPLANATION
        plan = ["db_worker", "rag_worker"]
        reasoning_steps.append("Supervisor: Intent classified as CONFLICT_EXPLANATION. Formulated plan [db_worker -> rag_worker].")

    elif any(k in query for k in ["near", "nearby", "proximity", "distance", "within", "radius", "meters", "around", "coords", "lat", "lon"]) or re.search(r"[-+]?\d+\.\d+[\s,]+[-+]?\d+\.\d+", query):
        intent = AssistantIntent.SPATIAL_PROXIMITY
        plan = ["spatial_worker", "db_worker"]
        reasoning_steps.append("Supervisor: Intent classified as SPATIAL_PROXIMITY. Formulated plan [spatial_worker -> db_worker].")

    elif any(k in query for k in ["provenance", "history", "timeline", "audit", "lineage", "who accepted", "who reviewed", "trace", "trail"]):
        intent = AssistantIntent.PROVENANCE_TRACE
        plan = ["db_worker", "rag_worker"]
        reasoning_steps.append("Supervisor: Intent classified as PROVENANCE_TRACE. Formulated plan [db_worker -> rag_worker].")

    elif any(k in query for k in ["compare", "comparison", "iou", "overlap difference", "area delta", "cadastral vs drone", "cadastral vs", "drone vs"]):
        intent = AssistantIntent.DATASET_COMPARISON
        plan = ["spatial_worker", "db_worker"]
        reasoning_steps.append("Supervisor: Intent classified as DATASET_COMPARISON. Formulated plan [spatial_worker -> db_worker].")

    elif any(k in query for k in ["semantic", "rag", "concept", "meaning", "related documents", "knowledge base"]):
        intent = AssistantIntent.SEMANTIC_SEARCH
        plan = ["rag_worker", "db_worker"]
        reasoning_steps.append("Supervisor: Intent classified as SEMANTIC_SEARCH. Formulated plan [rag_worker -> db_worker].")

    elif re.search(r"\b(ulr|cad|drn)[-_][a-z0-9]+\b", query) or (ctx_record and not any(k in query for k in ["search", "find", "all parcels", "show all"])):
        intent = AssistantIntent.RECORD_INVESTIGATION
        plan = ["db_worker", "rag_worker"]
        reasoning_steps.append("Supervisor: Intent classified as RECORD_INVESTIGATION. Formulated plan [db_worker -> rag_worker].")

    elif any(k in query for k in ["find", "search", "residential", "commercial", "agricultural", "zoning", "land use", "owner", "address", "show all"]):
        intent = AssistantIntent.ATTRIBUTE_SEARCH
        plan = ["db_worker"]
        reasoning_steps.append("Supervisor: Intent classified as ATTRIBUTE_SEARCH. Formulated plan [db_worker].")

    elif any(k in query for k in ["overview", "summary", "how many", "status", "what is this project", "project summary", "dataset count", "progress"]):
        intent = AssistantIntent.PROJECT_OVERVIEW
        plan = ["db_worker"]
        reasoning_steps.append("Supervisor: Intent classified as PROJECT_OVERVIEW. Formulated plan [db_worker].")

    else:
        intent = AssistantIntent.GENERAL_GIS_QUERY
        plan = ["db_worker", "rag_worker"]
        reasoning_steps.append("Supervisor: Intent classified as GENERAL_GIS_QUERY. Formulated plan [db_worker -> rag_worker].")

    return {
        "intent": intent,
        "plan": plan,
        "executed_workers": [],
        "raw_tool_results": state.get("raw_tool_results", {}),
        "evidence_pool": list(state.get("evidence_pool", [])),
        "retrieved_documents": list(state.get("retrieved_documents", [])),
        "reasoning_steps": reasoning_steps,
    }


async def db_worker_node(state: AssistantState) -> Dict[str, Any]:
    """
    Database Worker Specialist:
    Executes parameterized, read-only SQL queries to extract project summaries,
    unified land records, contributing features, attribute conflicts, and provenance.
    """
    db: AsyncSession = state["db"]
    project_id: uuid.UUID = state["project_id"]
    query: str = state.get("query", "")
    intent: AssistantIntent = state.get("intent", AssistantIntent.GENERAL_GIS_QUERY)
    ctx_record_id: Optional[uuid.UUID] = state.get("context_record_id")
    ctx_conflict_id: Optional[uuid.UUID] = state.get("context_conflict_id")

    reasoning_steps = list(state.get("reasoning_steps", []))
    raw_results = dict(state.get("raw_tool_results", {}))
    evidence_pool = list(state.get("evidence_pool", []))
    executed_workers = list(state.get("executed_workers", []))

    # Base project summary
    if "project_summary" not in raw_results:
        summary = await get_project_summary(db, project_id)
        raw_results["project_summary"] = summary
        reasoning_steps.append(f"DB Worker: Retrieved project summary ({summary.get('total_datasets', 0)} datasets, {summary.get('unified_records', {}).get('total', 0)} records).")

        for ds in summary.get("datasets", []):
            evidence_pool.append(
                AssistantEvidenceSource(
                    source_type="DATASET",
                    identifier=ds["name"],
                    title=f"Dataset: {ds['name']}",
                    dataset_name=ds["name"],
                    role=ds.get("geometry_type"),
                    properties=ds,
                    relevance_note=f"Ingested dataset with {ds.get('feature_count')} canonical features.",
                )
            )

    # Resolve target record identifier
    record_target = None
    if ctx_record_id:
        record_target = str(ctx_record_id)
    else:
        rec_match = re.search(r"\b(ULR-[A-Za-z0-9_-]+|CAD-[A-Za-z0-9_-]+|DRN-[A-Za-z0-9_-]+)\b", query, re.IGNORECASE)
        if rec_match:
            record_target = rec_match.group(1)

    if record_target:
        rec_evidence = await get_unified_record_evidence(db, project_id, record_target)
        raw_results["record_evidence"] = rec_evidence
        raw_results["unified_record_evidence"] = rec_evidence
        reasoning_steps.append(f"DB Worker: Retrieved unified record evidence for '{record_target}'.")

        if "error" not in rec_evidence:
            evidence_pool.append(
                AssistantEvidenceSource(
                    source_type="UNIFIED_RECORD",
                    identifier=rec_evidence["record_identifier"],
                    title=f"Unified Record {rec_evidence['record_identifier']}",
                    role=rec_evidence.get("geometry_source_role"),
                    properties={
                        "status": rec_evidence.get("status"),
                        "area": rec_evidence.get("canonical_area"),
                        "attributes": rec_evidence.get("canonical_attributes", {}),
                    },
                    relevance_note=f"Canonical harmonized record with status {rec_evidence.get('status')}.",
                )
            )

            for s in rec_evidence.get("contributing_sources", []):
                evidence_pool.append(
                    AssistantEvidenceSource(
                        source_type="SOURCE_FEATURE",
                        identifier=s["feature_identifier"],
                        title=f"Source Feature ({s.get('source_role')})",
                        role=s.get("source_role"),
                        properties=s.get("properties", {}),
                        relevance_note=f"Source feature contributing to {rec_evidence['record_identifier']}.",
                    )
                )

            for c in rec_evidence.get("conflicts", []):
                evidence_pool.append(
                    AssistantEvidenceSource(
                        source_type="ATTRIBUTE_CONFLICT",
                        identifier=f"{rec_evidence['record_identifier']}:{c['attribute_name']}",
                        title=f"Conflict: {c['attribute_name']} ({c['status']})",
                        properties=c,
                        relevance_note=f"{c['severity']} severity conflict on {c['attribute_name']}.",
                    )
                )

        prov_trail = await get_provenance_trail(db, project_id, record_target)
        raw_results["provenance_trail"] = prov_trail
        reasoning_steps.append(f"DB Worker: Retrieved provenance timeline ({prov_trail.get('events_count', 0)} events).")

    # Conflict specific lookup
    if intent in (AssistantIntent.CONFLICT_EXPLANATION, AssistantIntent.COMPLEX_INVESTIGATION) or ctx_conflict_id:
        target_conf = str(ctx_conflict_id) if ctx_conflict_id else "land_use"
        for attr in ["land_use", "area", "zoning", "address", "owner", "elevation"]:
            if attr in query:
                target_conf = attr
                break

        conf_res = await get_conflict_evidence(db, project_id, target_conf, ctx_record_id)
        raw_results["conflict_evidence"] = conf_res
        reasoning_steps.append(f"DB Worker: Retrieved conflict details for '{target_conf}' ({len(conf_res.get('conflicts', []))} records affected).")

        for c in conf_res.get("conflicts", []):
            rec_id_str = c.get("record_identifier") or c.get("record_id", "Unknown")
            evidence_pool.append(
                AssistantEvidenceSource(
                    source_type="ATTRIBUTE_CONFLICT",
                    identifier=f"{rec_id_str}:{c['attribute_name']}",
                    title=f"Discrepancy: {c['attribute_name']} [{c['status']}]",
                    properties=c,
                    relevance_note=f"{c.get('severity')} conflict with detected values {c.get('detected_values')}.",
                )
            )

    # Attribute search
    if intent == AssistantIntent.ATTRIBUTE_SEARCH:
        clean_q = re.sub(r"\b(find|search|show|parcels|all|with|for)\b", "", query, flags=re.IGNORECASE).strip() or query
        s_res = await search_unified_records_by_attributes(db, project_id, clean_q)
        f_res = await search_source_features(db, project_id, clean_q)
        raw_results["attribute_search"] = s_res
        raw_results["source_feature_search"] = f_res
        reasoning_steps.append(f"DB Worker: Attribute search found {s_res.get('results_count', 0)} unified records and {f_res.get('results_count', 0)} features.")

        for r in s_res.get("records", []):
            evidence_pool.append(
                AssistantEvidenceSource(
                    source_type="UNIFIED_RECORD",
                    identifier=r["record_identifier"],
                    title=f"Record {r['record_identifier']}",
                    properties=r,
                    relevance_note=f"Matched on field '{r.get('matched_field')}'.",
                )
            )

    executed_workers.append("db_worker")
    return {
        "raw_tool_results": raw_results,
        "evidence_pool": evidence_pool,
        "executed_workers": executed_workers,
        "reasoning_steps": reasoning_steps,
    }


async def spatial_worker_node(state: AssistantState) -> Dict[str, Any]:
    """
    Spatial Worker Specialist:
    Executes PostGIS and Shapely geometric operations (coordinate proximity,
    bounding box filtering, pairwise IoU and centroid distance comparison).
    """
    db: AsyncSession = state["db"]
    project_id: uuid.UUID = state["project_id"]
    query: str = state.get("query", "")
    ctx_record_id: Optional[uuid.UUID] = state.get("context_record_id")

    reasoning_steps = list(state.get("reasoning_steps", []))
    raw_results = dict(state.get("raw_tool_results", {}))
    evidence_pool = list(state.get("evidence_pool", []))
    executed_workers = list(state.get("executed_workers", []))

    # Parse coordinates or use context record centroid
    coord_match = re.search(r"([-+]?\d+\.\d+)[\s,]+([-+]?\d+\.\d+)", query)
    lat = 18.520
    lon = 73.850
    radius = 150.0

    if coord_match:
        lat = float(coord_match.group(1))
        lon = float(coord_match.group(2))
        reasoning_steps.append(f"Spatial Worker: Parsed coordinates [{lat}, {lon}].")
    elif ctx_record_id:
        r_ev = raw_results.get("record_evidence") or await get_unified_record_evidence(db, project_id, str(ctx_record_id))
        if "error" not in r_ev and r_ev.get("canonical_attributes", {}).get("_centroid"):
            c = r_ev["canonical_attributes"]["_centroid"]
            lat, lon = c[0], c[1]
            reasoning_steps.append(f"Spatial Worker: Using context record centroid [{lat}, {lon}].")

    prox_res = await find_records_near_coordinates(db, project_id, lat, lon, radius_meters=radius)
    raw_results["spatial_proximity"] = prox_res
    reasoning_steps.append(f"Spatial Worker: Executed proximity search within {radius}m (matches={prox_res.get('results_count', 0)}).")

    for r in prox_res.get("records", []):
        evidence_pool.append(
            AssistantEvidenceSource(
                source_type="UNIFIED_RECORD",
                identifier=r["record_identifier"],
                title=f"Nearby Record {r['record_identifier']} ({r.get('distance_meters')}m)",
                properties=r,
                relevance_note=f"Located {r.get('distance_meters')}m away with status {r.get('status')}.",
            )
        )

    # Check for pairwise comparison
    f_matches = re.findall(r"\b(CAD-[A-Za-z0-9_-]+|DRN-[A-Za-z0-9_-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", query, re.IGNORECASE)
    if len(f_matches) >= 2:
        comp_res = await compare_feature_geometries(db, project_id, f_matches[0], f_matches[1])
        raw_results["spatial_comparison"] = comp_res
        reasoning_steps.append(f"Spatial Worker: Computed geometric delta between '{f_matches[0]}' and '{f_matches[1]}' (IoU: {comp_res.get('spatial_metrics', {}).get('intersection_over_union')}).")

    executed_workers.append("spatial_worker")
    return {
        "raw_tool_results": raw_results,
        "evidence_pool": evidence_pool,
        "executed_workers": executed_workers,
        "reasoning_steps": reasoning_steps,
    }


async def rag_worker_node(state: AssistantState) -> Dict[str, Any]:
    """
    RAG / Semantic Vector Search Specialist:
    Queries the PostgreSQL pgvector evidence store to retrieve contextually relevant
    unstructured and structured evidence documents.
    """
    db: AsyncSession = state["db"]
    project_id: uuid.UUID = state["project_id"]
    query: str = state.get("query", "")

    reasoning_steps = list(state.get("reasoning_steps", []))
    raw_results = dict(state.get("raw_tool_results", {}))
    evidence_pool = list(state.get("evidence_pool", []))
    retrieved_documents = list(state.get("retrieved_documents", []))
    executed_workers = list(state.get("executed_workers", []))

    sem_res = await search_evidence_knowledge_base(db, project_id, query, limit=5)
    raw_results["semantic_search"] = sem_res
    retrieved_documents.extend(sem_res.get("results", []))
    evidence_pool.extend(sem_res.get("evidence_sources", []))

    reasoning_steps.append(f"RAG Worker: Retrieved {sem_res.get('results_count', 0)} semantic evidence documents from PostgreSQL vector knowledge base.")

    executed_workers.append("rag_worker")
    return {
        "raw_tool_results": raw_results,
        "evidence_pool": evidence_pool,
        "retrieved_documents": retrieved_documents,
        "executed_workers": executed_workers,
        "reasoning_steps": reasoning_steps,
    }


async def synthesize_node(state: AssistantState) -> Dict[str, Any]:
    """
    Synthesis Node:
    Consolidates evidence from all dispatched worker agents and invokes the reasoning
    engine to formulate an objective, grounded answer.
    """
    provider = LLMReasoningProvider()
    query = state.get("query", "")
    intent = state.get("intent", AssistantIntent.GENERAL_GIS_QUERY)
    evidence_pool = state.get("evidence_pool", [])
    raw_results = state.get("raw_tool_results", {})
    reasoning_steps = list(state.get("reasoning_steps", []))

    reasoning_steps.append(f"Synthesizer: Formulating grounded response across {len(evidence_pool)} evidence sources.")

    synthesis = await provider.synthesize(
        query=query,
        intent=intent,
        evidence_pool=evidence_pool,
        raw_tool_results=raw_results,
    )

    steps = synthesis.get("reasoning_steps", [])
    reasoning_steps.extend(steps)

    return {
        "raw_answer": synthesis.get("answer", ""),
        "reasoning_steps": reasoning_steps,
        "suggested_followups": synthesis.get("suggested_followups", []),
    }


def verifier_node(state: AssistantState) -> Dict[str, Any]:
    """
    Grounding Verifier Node:
    Cross-checks synthesized claims against actual database records, extracts citations,
    and computes the factual grounding score.
    """
    raw_answer = state.get("raw_answer", "")
    evidence_pool = state.get("evidence_pool", [])
    reasoning_steps = list(state.get("reasoning_steps", []))

    final_answer, cited_sources, score = EvidenceVerifier.verify_and_ground(
        answer_text=raw_answer,
        evidence_pool=evidence_pool,
    )

    reasoning_steps.append(
        f"Verifier: Verified response with {len(cited_sources)} grounded citations (Grounded score: {score:.2f})."
    )

    return {
        "final_answer": final_answer,
        "cited_sources": cited_sources,
        "grounded_score": score,
        "reasoning_steps": reasoning_steps,
    }


def route_supervisor(state: AssistantState) -> str:
    """
    Conditional routing function:
    Determines the next unexecuted specialist worker according to the supervisor plan.
    """
    plan = state.get("plan", [])
    executed = state.get("executed_workers", [])

    for worker in plan:
        if worker not in executed:
            return worker

    return "synthesize"


def build_assistant_graph() -> Any:
    """Constructs and compiles the multi-step LangGraph StateGraph."""
    workflow = StateGraph(AssistantState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("db_worker", db_worker_node)
    workflow.add_node("spatial_worker", spatial_worker_node)
    workflow.add_node("rag_worker", rag_worker_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("verifier", verifier_node)

    # Entry point to supervisor/planner
    workflow.add_edge(START, "planner")

    # Dynamic conditional routing from planner to planned workers
    workflow.add_conditional_edges(
        "planner",
        route_supervisor,
        {
            "db_worker": "db_worker",
            "spatial_worker": "spatial_worker",
            "rag_worker": "rag_worker",
            "synthesize": "synthesize",
        },
    )

    # Dynamic routing after worker execution (loops to next worker or advances to synthesis)
    for worker_name in ["db_worker", "spatial_worker", "rag_worker"]:
        workflow.add_conditional_edges(
            worker_name,
            route_supervisor,
            {
                "db_worker": "db_worker",
                "spatial_worker": "spatial_worker",
                "rag_worker": "rag_worker",
                "synthesize": "synthesize",
            },
        )

    workflow.add_edge("synthesize", "verifier")
    workflow.add_edge("verifier", END)

    return workflow.compile()


# Compile reusable singleton graph instance
_assistant_graph = build_assistant_graph()


class AssistantOrchestrator:
    """
    Top-level orchestrator for the LandSync Evidence Assistant.
    Coordinates multi-step LangGraph graph execution, metrics tracking, and response formatting.
    """

    @classmethod
    async def run_query(
        cls,
        db: AsyncSession,
        request: AssistantQueryRequest,
    ) -> AssistantQueryResponse:
        """
        Executes the multi-step assistant pipeline for a user query.
        Guarantees strictly read-only execution with zero database mutations.
        """
        start_time = time.perf_counter()

        initial_state: AssistantState = {
            "query": request.query,
            "project_id": request.project_id,
            "context_record_id": request.context_record_id,
            "context_conflict_id": request.context_conflict_id,
            "context_match_id": request.context_match_id,
            "db": db,
            "reasoning_steps": ["Initiating multi-step LandSync Assistant orchestration pipeline."],
        }

        try:
            final_state = await _assistant_graph.ainvoke(initial_state)
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            return AssistantQueryResponse(
                query=request.query,
                project_id=request.project_id,
                intent=final_state.get("intent", AssistantIntent.GENERAL_GIS_QUERY),
                answer=final_state.get("final_answer", "Unable to formulate answer."),
                reasoning_steps=final_state.get("reasoning_steps", []),
                evidence_sources=final_state.get("cited_sources", []),
                suggested_followups=final_state.get("suggested_followups", []),
                grounded_score=final_state.get("grounded_score", 1.0),
                execution_time_ms=latency_ms,
            )

        except Exception as e:
            logger.exception("Error executing assistant graph pipeline")
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return AssistantQueryResponse(
                query=request.query,
                project_id=request.project_id,
                intent=AssistantIntent.GENERAL_GIS_QUERY,
                answer=f"An error occurred while analyzing the evidence: {str(e)}",
                reasoning_steps=[f"Pipeline failed: {str(e)}"],
                evidence_sources=[],
                suggested_followups=["Try asking about the project overview or specific parcel identifier."],
                grounded_score=0.0,
                execution_time_ms=latency_ms,
            )

    @classmethod
    async def get_suggested_questions(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        context_record_id: Optional[uuid.UUID] = None,
    ) -> List[str]:
        """Generates dynamic, high-value investigation prompts for the current context."""
        summary = await get_project_summary(db, project_id)

        if context_record_id:
            rec_res = await get_unified_record_evidence(db, project_id, str(context_record_id))
            ident = rec_res.get("record_identifier", "this record")
            status = rec_res.get("status", "ACTIVE")

            questions = [
                f"What datasets and source features contributed to record {ident}?",
                f"What is the complete provenance and audit trail for {ident}?",
            ]
            if status == "CONFLICT" or rec_res.get("conflicts_count", 0) > 0:
                questions.append(f"Why is {ident} flagged with attribute conflicts and how can it be resolved?")
            else:
                questions.append(f"Find other unified records within 100 meters of {ident}.")
            return questions

        # Project level questions
        unresolved_conflicts = summary.get("conflicts", {}).get("unresolved", 0)
        total_records = summary.get("unified_records", {}).get("total", 0)

        questions = [
            "Provide an executive overview of this LandSync project and harmonization status.",
        ]

        if unresolved_conflicts > 0:
            questions.append(f"Why are {unresolved_conflicts} attribute conflicts unresolved and what actions are recommended?")

        if total_records > 0:
            questions.append("Find all parcels with commercial or residential land use.")
            questions.append("Compare parcel boundaries and geometry deltas between cadastral and drone datasets.")
        else:
            questions.append("What datasets have been ingested and what are their spatial coordinate reference systems?")

        return questions
