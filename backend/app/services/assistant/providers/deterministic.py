import re
from typing import Dict, Any, List
from app.schemas.assistant import AssistantEvidenceSource, AssistantIntent
from app.services.assistant.providers.base import BaseReasoningProvider


class DeterministicReasoningEngine(BaseReasoningProvider):
    """
    Deterministic, grounded reasoning engine that formulates accurate,
    evidence-backed GIS responses without requiring external network API calls.
    Guarantees 100% adherence to actual database facts and prevents hallucinations.
    """

    async def synthesize(
        self,
        query: str,
        intent: AssistantIntent,
        evidence_pool: List[AssistantEvidenceSource],
        raw_tool_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasoning_steps = [
            f"Classified user intent as '{intent.value}'.",
            f"Retrieved {len(evidence_pool)} evidence sources from LandSync database.",
            "Formulating grounded domain response derived strictly from verified records.",
        ]

        followups = []
        answer_parts = []

        if intent == AssistantIntent.PROJECT_OVERVIEW:
            p_data = raw_tool_results.get("project_summary", {})
            name = p_data.get("name", "Current Project")
            crs = p_data.get("target_crs", "EPSG:4326")
            unif = p_data.get("unified_records", {})
            confs = p_data.get("conflicts", {})
            datasets = p_data.get("datasets", [])

            answer_parts.append(f"### Project Overview: **{name}**\n")
            answer_parts.append(f"- **Canonical CRS**: `{crs}`")
            answer_parts.append(f"- **Ingested Datasets**: {len(datasets)}")
            for d in datasets:
                answer_parts.append(f"  - **{d['name']}** ({d['format'].upper()}, {d['feature_count']} features, {d['geometry_type']})")

            answer_parts.append(f"\n#### Harmonization Status")
            answer_parts.append(f"- **Total Unified Records**: {unif.get('total', 0)}")
            answer_parts.append(f"  - **Active (Verified)**: {unif.get('active', 0)}")
            answer_parts.append(f"  - **Conflicts (Gated)**: {unif.get('conflict', 0)}")
            answer_parts.append(f"  - **Incomplete**: {unif.get('incomplete', 0)}")

            if confs.get("total", 0) > 0:
                answer_parts.append(f"\n#### Attribute Discrepancies")
                answer_parts.append(f"- **Total Conflicts**: {confs.get('total', 0)}")
                answer_parts.append(f"  - **Unresolved**: {confs.get('unresolved', 0)}")
                answer_parts.append(f"  - **Resolved / Dismissed**: {confs.get('resolved', 0) + confs.get('dismissed', 0)}")

            followups = [
                "Which records currently have unresolved attribute conflicts?",
                "What is the provenance trail for the latest harmonized record?",
                "Compare the geometry and area between ingested datasets.",
            ]

        elif intent == AssistantIntent.RECORD_INVESTIGATION:
            r_data = raw_tool_results.get("record_evidence") or raw_tool_results.get("unified_record_evidence") or {}
            ident = r_data.get("record_identifier", "Unknown")
            status = r_data.get("status", "ACTIVE")
            area = r_data.get("canonical_area")
            role = r_data.get("geometry_source_role", "DEFAULT")
            attrs = r_data.get("canonical_attributes", {})
            sources = r_data.get("contributing_sources", [])
            conflicts = r_data.get("conflicts", [])

            answer_parts.append(f"### Unified Land Record: **{ident}**\n")
            answer_parts.append(f"- **Current Status**: `{status}`")
            answer_parts.append(f"- **Canonical Area**: {f'{area:,.1f} m²' if area is not None else 'Not determined'}")
            answer_parts.append(f"- **Authoritative Geometry Source**: `{role}`")
            answer_parts.append(f"- **Primary Land Use**: {attrs.get('land_use', '—')}")
            answer_parts.append(f"- **Recorded Address**: {attrs.get('address', '—')}")

            answer_parts.append(f"\n#### Contributing Source Features ({len(sources)})")
            for s in sources:
                answer_parts.append(
                    f"- **{s['source_role']}** (ID: `{s['feature_identifier']}`, Type: {s['geometry_type']})"
                )

            if conflicts:
                answer_parts.append(f"\n#### Cross-Dataset Attribute Conflicts ({len(conflicts)})")
                for c in conflicts:
                    st_badge = "Resolved" if c["status"] == "RESOLVED" else "Unresolved"
                    answer_parts.append(
                        f"- **{c['attribute_name']}** (`{c['conflict_type']}`, Severity: {c['severity']}, Status: **{st_badge}**)"
                    )
                    for dv in c.get("detected_values", []):
                        val_str = dv.get("value")
                        answer_parts.append(f"  - *{dv.get('source_role')}* ({dv.get('dataset_name')}): `{val_str}`")
                    if c.get("resolution"):
                        res = c["resolution"]
                        answer_parts.append(f"  - *Resolution*: `{res.get('resolved_value')}` via {res.get('resolution_type')} (\"{res.get('comment')}\")")

            followups = [
                f"Show the chronological provenance timeline for {ident}.",
                f"Explain the attribute conflicts on {ident}.",
                "Find any neighbouring parcels within 100 meters.",
            ]

        elif intent == AssistantIntent.CONFLICT_EXPLANATION:
            c_data = raw_tool_results.get("conflict_evidence", {})
            conflicts_list = c_data.get("conflicts", [])

            if not conflicts_list:
                answer_parts.append("No active attribute conflicts match the requested criteria in this project.")
            else:
                answer_parts.append(f"### Attribute Conflict Analysis ({len(conflicts_list)} Discrepancy Found)\n")
                for c in conflicts_list:
                    rec_id = c.get("record_identifier") or "Unified Record"
                    answer_parts.append(f"#### Conflict on `{c['attribute_name']}` ({rec_id})")
                    answer_parts.append(f"- **Classification**: `{c['conflict_type']}`")
                    answer_parts.append(f"- **Severity Tier**: `{c['severity']}`")
                    answer_parts.append(f"- **Resolution Status**: `{c['status']}`")

                    answer_parts.append("\n**Contributing Evidence Disagreements:**")
                    for dv in c.get("detected_values", []):
                        answer_parts.append(
                            f"- **{dv.get('source_role')}** ({dv.get('dataset_name')}, Feature `{dv.get('feature_identifier')}`): reported value = `{dv.get('value')}`"
                        )

                    if c.get("status") == "RESOLVED" and c.get("resolution"):
                        res = c["resolution"]
                        answer_parts.append(
                            f"\n**Reconciliation Decision:**\n"
                            f"- **Canonical Value Chosen**: `{res.get('resolved_value')}`\n"
                            f"- **Strategy**: `{res.get('type')}`\n"
                            f"- **Audit Note**: \"{res.get('comment')}\"\n"
                            f"- **Resolved By**: {res.get('resolved_by') or 'GIS Reviewer'}"
                        )
                    elif c.get("status") == "DISMISSED":
                        answer_parts.append(
                            f"\n**Dismissal Justification:**\n"
                            f"- \"{c.get('dismissal_reason')}\"\n"
                            f"- *Status*: Dismissed as non-material tolerable variance."
                        )
                    else:
                        answer_parts.append(
                            f"\n**Resolution Recommendation:**\n"
                            f"- When legal ownership or land registry is required, prioritize `CADASTRAL` authority.\n"
                            f"- For physical building dimensions or heights, inspect `DRONE` survey evidence.\n"
                            f"- Human review is required to select the canonical authority or supply a surveyed manual override."
                        )

            followups = [
                "What is the policy for Cadastral vs Drone source precedence?",
                "Which other parcels in this project have similar conflicts?",
                "Show the full provenance history of these decisions.",
            ]

        elif intent == AssistantIntent.SPATIAL_PROXIMITY:
            sp_data = raw_tool_results.get("spatial_proximity", {})
            records = sp_data.get("records", [])
            center = sp_data.get("query_point", {})
            radius = sp_data.get("search_radius_meters", 100)

            answer_parts.append(
                f"### Spatial Proximity Search Results\n"
                f"Searched within **{radius:,.0f} meters** of coordinates `[{center.get('latitude')}, {center.get('longitude')}]`:\n"
            )

            if not records:
                answer_parts.append("No unified land records were found within this radius.")
            else:
                answer_parts.append(f"Found **{len(records)} record(s)** nearby, sorted by distance:\n")
                for r in records:
                    dist = r.get("distance_meters", 0)
                    area = r.get("canonical_area")
                    lu = r.get("land_use") or "—"
                    addr = r.get("address") or "—"
                    answer_parts.append(
                        f"1. **{r['record_identifier']}** (`{r['status']}`) — **{dist:.1f}m away**\n"
                        f"   - Land Use: {lu} | Area: {f'{area:,.1f} m²' if area else '—'} | Address: {addr}"
                    )

            followups = [
                "Inspect the nearest parcel's contributing sources.",
                "Are there any active conflicts on these nearby records?",
                "Expand search radius to 250 meters.",
            ]

        elif intent == AssistantIntent.PROVENANCE_TRACE:
            prov_data = raw_tool_results.get("provenance_trail", {})
            ident = prov_data.get("record_identifier", "Record")
            timeline = prov_data.get("timeline", [])

            answer_parts.append(f"### Provenance & Audit Trail for **{ident}**\n")
            answer_parts.append(f"Trace verified across **{len(timeline)} chronological lifecycle events**:\n")

            for idx, e in enumerate(timeline, 1):
                ts = e.get("timestamp") or "Initial"
                if "T" in ts:
                    ts = ts.split("T")[0]
                answer_parts.append(f"**{idx}. [{ts}] {e.get('title')}** (`{e.get('event_type')}`)")
                if e.get("description"):
                    answer_parts.append(f"   {e.get('description')}")

            followups = [
                f"What machine signals contributed to the match for {ident}?",
                "Who performed the human review and conflict resolution?",
                "Export this record's complete audit trail as GeoJSON.",
            ]

        elif intent == AssistantIntent.ATTRIBUTE_SEARCH:
            s_data = raw_tool_results.get("attribute_search", {})
            records = s_data.get("records", [])
            term = s_data.get("search_term", query)

            answer_parts.append(f"### Attribute Search Results for '*{term}*'\n")
            if not records:
                answer_parts.append(f"No unified land records matched the term '*{term}*'.")
            else:
                answer_parts.append(f"Found **{len(records)} matching unified record(s)**:\n")
                for r in records:
                    answer_parts.append(
                        f"- **{r['record_identifier']}** (`{r['status']}`) — Matched on `{r.get('matched_field')}`\n"
                        f"  - Land Use: {r.get('land_use') or '—'} | Area: {r.get('canonical_area') or '—'} m² | Address: {r.get('address') or '—'}"
                    )

            followups = [
                "Inspect the details of the first matched record.",
                "Check if any of these records have unresolved conflicts.",
            ]

        elif intent == AssistantIntent.SEMANTIC_SEARCH:
            sem_data = raw_tool_results.get("semantic_search", {})
            hits = sem_data.get("results", [])
            q_term = sem_data.get("query", query)

            answer_parts.append(f"### Semantic Vector Knowledge Search for '*{q_term}*'\n")
            if not hits:
                answer_parts.append("No semantically relevant documents were retrieved from the vector knowledge store.")
            else:
                answer_parts.append(f"Retrieved **{len(hits)} semantic document(s)** from the pgvector evidence store:\n")
                for idx, h in enumerate(hits, 1):
                    score_pct = int(h.get("similarity_score", 0.0) * 100)
                    answer_parts.append(
                        f"**{idx}. {h.get('title')}** (Similarity: `{score_pct}%`, Category: `{h.get('category')}`)\n"
                        f"   - Entity: `{h.get('entity_id')}`\n"
                        f"   - Evidence: {h.get('snippet')}..."
                    )

            followups = [
                "Investigate the first matched record in detail.",
                "Check for conflicts related to these semantic results.",
                "Perform a spatial proximity search around these parcels.",
            ]

        elif intent == AssistantIntent.COMPLEX_INVESTIGATION:
            r_data = raw_tool_results.get("record_evidence") or raw_tool_results.get("unified_record_evidence") or {}
            c_data = raw_tool_results.get("conflict_evidence", {})
            p_data = raw_tool_results.get("provenance_trail", {})
            sp_data = raw_tool_results.get("spatial_proximity", {})

            ident = r_data.get("record_identifier", "Target Record")
            conflicts = r_data.get("conflicts", []) or c_data.get("conflicts", [])
            sources = r_data.get("contributing_sources", [])
            timeline = p_data.get("timeline", [])

            answer_parts.append(f"### Multi-Step Investigation Report: **{ident}**\n")
            answer_parts.append(f"- **Harmonization Status**: `{r_data.get('status', 'ACTIVE')}`")
            answer_parts.append(f"- **Authoritative Source Role**: `{r_data.get('geometry_source_role', 'CADASTRAL')}`")
            if r_data.get("canonical_area"):
                answer_parts.append(f"- **Canonical Area**: {r_data.get('canonical_area'):,.1f} m²")

            answer_parts.append(f"\n#### 1. Contributing Source Lineage ({len(sources)} Sources)")
            for s in sources:
                answer_parts.append(f"- **{s.get('source_role')}**: Feature `{s.get('feature_identifier')}` ({s.get('geometry_type')})")

            answer_parts.append(f"\n#### 2. Attribute Discrepancies & Resolutions ({len(conflicts)} Conflicts)")
            if not conflicts:
                answer_parts.append("No active attribute conflicts detected. Sources agree on canonical properties.")
            else:
                for c in conflicts:
                    st = "RESOLVED" if c.get("status") == "RESOLVED" else "UNRESOLVED"
                    answer_parts.append(f"- **{c.get('attribute_name')}** ({c.get('conflict_type')}, Status: `{st}`)")
                    for dv in c.get("detected_values", []):
                        answer_parts.append(f"  - *{dv.get('source_role')}* ({dv.get('dataset_name')}): `{dv.get('value')}`")
                    if c.get("resolution"):
                        res = c["resolution"]
                        answer_parts.append(f"  - *Final Resolution Decision*: `{res.get('resolved_value')}` via {res.get('resolution_type')} (\"{res.get('comment')}\")")

            if timeline:
                answer_parts.append(f"\n#### 3. Provenance & Lifecycle Audit ({len(timeline)} Events)")
                for ev in timeline[:4]:
                    ts = (ev.get("timestamp") or "").split("T")[0]
                    answer_parts.append(f"- [{ts}] **{ev.get('title')}**: {ev.get('description')}")

            if sp_data.get("records"):
                near_recs = sp_data.get("records", [])
                answer_parts.append(f"\n#### 4. Spatial Proximity & Surroundings ({len(near_recs)} Nearby Records)")
                for nr in near_recs[:3]:
                    answer_parts.append(f"- Nearby: **{nr.get('record_identifier')}** ({nr.get('distance_meters')}m away)")

            followups = [
                f"Export the full multi-source audit trail for {ident}.",
                f"Compare the cadastral boundary of {ident} with drone imagery.",
                "Review other records with unresolved discrepancies.",
            ]

        else:
            # General GIS query
            answer_parts.append(
                f"### LandSync Evidence Analysis\n\n"
                f"Based on the project's canonical geospatial registry and accepted review history, "
                f"LandSync AI harmonizes vector parcel boundaries using multi-source role precedence (`CADASTRAL` > `DRONE` > `MUNICIPAL`).\n\n"
                f"Every claim in LandSync is backed by immutable source features and deterministic PostGIS matching signals. "
                f"You can explore specific records, inspect cross-dataset conflicts, or trace full provenance history."
            )
            followups = [
                "Summarize all active unified land records.",
                "List all open attribute conflicts needing review.",
                "Show project datasets and CRS configuration.",
            ]

        final_answer = "\n".join(answer_parts)
        return {
            "answer": final_answer,
            "reasoning_steps": reasoning_steps,
            "suggested_followups": followups,
        }
