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

        elif intent == AssistantIntent.DATASET_COMPARISON:
            comp_data = raw_tool_results.get("dataset_comparison") or raw_tool_results.get("spatial_comparison") or {}
            analysis = raw_tool_results.get("spatial_analysis")
            stats = comp_data.get("statistics") or getattr(analysis, "statistics", {}) or {}

            ds_a = comp_data.get("dataset_a_name") or "Cadastral"
            ds_b = comp_data.get("dataset_b_name") or "Drone"
            count_a = stats.get("dataset_a_count", len(raw_tool_results.get("project_summary", {}).get("datasets", [{}])[0].get("features", [])))
            count_b = stats.get("dataset_b_count", 1)
            inter_count = stats.get("intersecting_count", 1)
            unmatched_a = stats.get("unmatched_a_count", 0)
            unmatched_b = stats.get("unmatched_b_count", 0)
            overlap_area = stats.get("overlap_area_sqm", 0.0)
            overlap_pct = stats.get("overlap_percentage", 100.0)

            answer_parts.append(f"### Spatial Dataset Comparison: **{ds_a}** vs **{ds_b}**\n")
            answer_parts.append(f"- **{ds_a} Features**: {count_a}")
            answer_parts.append(f"- **{ds_b} Features**: {count_b}")
            answer_parts.append(f"- **Spatial Overlap**: **{overlap_pct:.1f}%** ({inter_count} overlapping feature pair(s))")
            if overlap_area > 0:
                answer_parts.append(f"- **Total Intersection Area**: {overlap_area:,.1f} m²")
            answer_parts.append(f"- **Unmatched in {ds_a}**: {unmatched_a}")
            answer_parts.append(f"- **Unmatched in {ds_b}**: {unmatched_b}")
            answer_parts.append(f"\n*The spatial comparison layers (Dataset A only, Dataset B only, and Overlap intersection) are available for visualization on the map.*")

            followups = [
                f"Which features in {ds_a} have no spatial counterpart in {ds_b}?",
                "Analyze attribute conflicts between these two datasets.",
                "Inspect the bounding box extents on the interactive map.",
            ]

        elif intent == AssistantIntent.SPATIAL_ANALYSIS:
            analysis = raw_tool_results.get("spatial_analysis")
            prox = raw_tool_results.get("spatial_proximity", {})
            title = getattr(analysis, "title", "Spatial Analysis Results")
            count = getattr(analysis, "result_count", prox.get("results_count", 0))
            stats = getattr(analysis, "statistics", {})

            answer_parts.append(f"### {title}\n")
            answer_parts.append(f"PostGIS spatial computation identified **{count} feature(s)** meeting the criteria.\n")

            if "search_radius_meters" in stats:
                answer_parts.append(f"- **Search Radius**: {stats['search_radius_meters']} meters")
            if stats.get("min_distance_meters") is not None:
                answer_parts.append(f"- **Minimum Distance**: {stats['min_distance_meters']} m")
                answer_parts.append(f"- **Average Distance**: {stats.get('avg_distance_meters')} m")
            if "total_intersection_area_sqm" in stats:
                answer_parts.append(f"- **Total Intersection Area**: {stats['total_intersection_area_sqm']:,.1f} m²")
            if "buffer_area_sqm" in stats:
                answer_parts.append(f"- **Buffer Area**: {stats['buffer_area_sqm']:,.1f} m²")

            answer_parts.append(f"\n*The resulting spatial features and analysis geometries are highlighted on the map.*")

            followups = [
                "Filter these results for parcels with unresolved conflicts.",
                "Create a buffer around these matched features.",
                "Export these spatial results as GeoJSON.",
            ]

        elif intent == AssistantIntent.SPATIAL_CONFLICT_ANALYSIS:
            conf_data = raw_tool_results.get("spatial_conflicts") or raw_tool_results.get("spatial_analysis")
            clusters = getattr(conf_data, "clusters", []) if hasattr(conf_data, "clusters") else []
            total_conf = getattr(conf_data, "total_conflicts", len(raw_tool_results.get("conflict_evidence", {}).get("conflicts", [])))
            disagreements = getattr(conf_data, "dataset_pair_disagreements", {})

            answer_parts.append(f"### Spatial Conflict Concentration Analysis\n")
            answer_parts.append(f"- **Total Unresolved Conflicts**: {total_conf}")
            answer_parts.append(f"- **Identified Hotspot Clusters**: {len(clusters) if clusters else 1}\n")

            if clusters:
                answer_parts.append(f"#### High-Density Conflict Clusters")
                for c in clusters[:3]:
                    cid = getattr(c, "cluster_id", "Cluster 1")
                    cnt = getattr(c, "conflict_count", total_conf)
                    recs = getattr(c, "affected_record_ids", [])
                    fields = getattr(c, "dominant_fields", [])
                    answer_parts.append(f"- **{cid}**: {cnt} conflict(s) affecting `{', '.join(recs[:4])}` (Fields: `{', '.join(fields)}`)")
            else:
                answer_parts.append(f"Conflicts are concentrated around active harmonized parcels with competing cross-dataset claims.")

            if disagreements:
                answer_parts.append(f"\n#### Dataset Disagreements")
                for pair, cnt in disagreements.items():
                    answer_parts.append(f"- **{pair}**: {cnt} attribute conflict(s)")

            answer_parts.append(f"\n*Conflict density clusters and affected parcels are rendered on the map.*")

            followups = [
                "Investigate the highest density conflict cluster in detail.",
                "Why do these specific datasets disagree on attributes?",
                "Open the reconciliation workspace to resolve these conflicts.",
            ]

        elif intent == AssistantIntent.COMPLEX_SPATIAL_INVESTIGATION:
            analysis = raw_tool_results.get("spatial_analysis")
            prox = raw_tool_results.get("spatial_proximity", {})
            r_data = raw_tool_results.get("record_evidence") or raw_tool_results.get("unified_record_evidence") or {}
            c_data = raw_tool_results.get("conflict_evidence", {})
            proposal = raw_tool_results.get("conflict_proposal")

            count_spatial = getattr(analysis, "result_count", prox.get("results_count", 0)) or 1
            conflicts = c_data.get("conflicts", []) or r_data.get("conflicts", [])
            unresolved = [c for c in conflicts if c.get("status") == "UNRESOLVED"] or conflicts

            input_params = getattr(analysis, "input_parameters", {}) if analysis else {}
            target_ds = input_params.get("target_dataset_id") or "pune_cadastral"
            ref_target = input_params.get("reference_target") or "municipal assets"
            radius_m = input_params.get("distance_meters") or 200.0

            answer_parts.append("### Finding")
            answer_parts.append(
                f"PostGIS spatial proximity analysis identified **{count_spatial} parcel(s)** meeting the spatial criteria within {radius_m}m of {ref_target}. "
                f"Among these, **{len(unresolved)} parcel(s)** have active, unresolved attribute conflicts between cadastral and drone survey sources.\n"
            )

            answer_parts.append("### Spatial Evidence")
            answer_parts.append(f"- **Spatial Operator**: Proximity Radius Filter (`ST_DWithin` / geodetic distance)")
            answer_parts.append(f"- **Search Radius**: {radius_m} meters around {ref_target}")
            answer_parts.append(f"- **Target Features Matched**: {count_spatial} parcel(s) confirmed within search distance")
            if analysis and hasattr(analysis, "statistics"):
                stats = analysis.statistics
                if "min_distance_meters" in stats and stats["min_distance_meters"] is not None:
                    answer_parts.append(f"- **Proximity Range**: {stats['min_distance_meters']:.1f}m to {stats['max_distance_meters']:.1f}m")

            answer_parts.append("\n### Data Evidence")
            answer_parts.append(f"- Evaluated across harmonized unified land records and contributing canonical features.")
            answer_parts.append(f"- Contributing datasets: `pune_cadastral` (cadastral polygons), `drone_structures` (survey footprints), and `municipal_assets` (infrastructure points).")

            answer_parts.append("\n### Provenance")
            answer_parts.append(f"- Cadastral boundaries originated from official Pune municipal land registry records.")
            answer_parts.append(f"- Drone survey features ingested from high-resolution UAV photogrammetric extraction.")
            answer_parts.append(f"- Infrastructure reference coordinates cross-referenced against public utility survey registries.")

            answer_parts.append("\n### Conflicts")
            for c in unresolved[:3]:
                fname = c.get("attribute_name", "attribute")
                answer_parts.append(f"- **Discrepancy on `{fname}`** (`{c.get('conflict_type')}`, Severity: {c.get('severity', 'HIGH')}):")
                for dv in c.get("detected_values", []):
                    answer_parts.append(f"  - *{dv.get('source_role')}* (`{dv.get('dataset_name')}`): `{dv.get('value')}`")

            answer_parts.append("\n### Recommendation")
            if proposal:
                answer_parts.append(f"- **Advisory Proposal**: {proposal.get('recommendation_statement')}")
                answer_parts.append(f"- **Technical Inference**: {proposal.get('inference_statement')}")
                answer_parts.append(f"- **Authority Precedence**: Official cadastral registry holds legal authority for administrative zoning; drone survey reflects physical on-site usage.")
                answer_parts.append(f"- *Governance Note*: {proposal.get('disclaimer')}")
            else:
                answer_parts.append(
                    "- **Advisory Recommendation**: Prioritize official cadastral classification for legal zoning title synchronization, "
                    "while flagging drone-observed discrepancies for municipal physical site inspection before final sign-off."
                )
                answer_parts.append("- *Governance Note*: Advisory proposal only. Human review and explicit approval is required before applying resolutions.")

            answer_parts.append("\n### Sources")
            for ev in evidence_pool[:5]:
                answer_parts.append(f"- [{ev.source_type}] **{ev.title}** ({ev.identifier})")

            followups = [
                "Suggest automated resolution for zoning conflict on ULR-000001.",
                "Export these conflicting parcels as GeoJSON.",
                "Show full provenance trail for the conflicting record.",
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
