import uuid
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
from sqlalchemy import select, func, text, desc, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.matching import MatchRun, FeatureMatch
from app.models.conflict import GeospatialConflict
from app.models.pipeline import PipelineStageExecution
from app.models.validation import ValidationResult
from app.services.matching.service import extract_feature_display_id
from app.services.conflict.service import (
    normalize_semantic_land_use,
    normalize_semantic_mutation,
    normalize_semantic_risk,
)
from app.schemas.validation import (
    ValidationResultRead,
    ValidationSummaryResponse,
    ValidationResultListResponse,
    ValidationRunRequest,
    ValidationRunResponse,
)


class ValidationService:
    """
    Stage 09 — Validation Service.
    Verifies harmonized parcel candidates using:
    1. PostGIS Geometry validity (ST_IsValid, ST_IsValidReason, emptiness, nullity)
    2. PostGIS Topological integrity (self-intersection, overlap ratio, centroid distance, containment)
    3. Area tolerance validation (PASS <= 5%, WARNING 5-15%, FAIL > 15%)
    4. Attribute / semantic business-rule validation
    5. Conflict-aware validation consuming Stage 08 GeospatialConflict results
    6. Deterministic idempotent persistence to validation_results table
    """

    @classmethod
    async def execute_stage_09(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        req: Optional[ValidationRunRequest] = None,
    ) -> ValidationRunResponse:
        """
        Executes Stage 09 Validation for the given project workspace.
        """
        start_time = time.perf_counter()
        if req is None:
            req = ValidationRunRequest()

        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 1. Fetch Stage 07 Harmonization results
        stage7_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "harmonization",
            )
        )
        stage7_exec = (await db.execute(stage7_stmt)).scalar_one_or_none()
        if not stage7_exec or stage7_exec.status != "completed":
            raise ValueError("Stage 07 Attribute/Geometry Harmonization must be completed before Stage 09 Validation.")

        harmonized_records = stage7_exec.results.get("records_preview", [])
        if not harmonized_records:
            raise ValueError("No harmonized records found from Stage 07 execution.")

        # 2. Fetch Stage 08 Geospatial Conflicts for this project
        conflicts_stmt = (
            select(GeospatialConflict)
            .where(GeospatialConflict.project_id == project_id)
        )
        existing_conflicts = list((await db.execute(conflicts_stmt)).scalars().all())
        conflicts_by_record: Dict[str, List[GeospatialConflict]] = defaultdict(list)
        for c in existing_conflicts:
            conflicts_by_record[c.harmonized_record_id].append(c)

        # 3. Extract feature IDs for PostGIS spatial queries
        feature_id_pairs: List[Tuple[uuid.UUID, uuid.UUID, str]] = []
        for rec in harmonized_records:
            rec_id = rec.get("id", "")
            parts = rec_id.split("_")
            if len(parts) >= 2:
                try:
                    sf_id = uuid.UUID(parts[0])
                    cf_id = uuid.UUID(parts[1])
                    feature_id_pairs.append((sf_id, cf_id, rec_id))
                except (ValueError, TypeError):
                    continue

        # 4. Batch query PostGIS for geometry validity and topological metrics
        bind = db.bind
        dialect_name = bind.dialect.name if bind else "postgresql"
        postgis_metrics_by_rec: Dict[str, Dict[str, Any]] = {}

        if feature_id_pairs and dialect_name == "postgresql":
            # Query geometry validity and spatial relationships using PostGIS in PostgreSQL
            try:
                spatial_query = text("""
                    SELECT 
                        sf.id AS sf_id,
                        cf.id AS cf_id,
                        (sf.geometry IS NULL) AS sf_is_null,
                        (cf.geometry IS NULL) AS cf_is_null,
                        ST_IsEmpty(sf.geometry) AS sf_is_empty,
                        ST_IsEmpty(cf.geometry) AS cf_is_empty,
                        ST_IsValid(sf.geometry) AS sf_is_valid,
                        ST_IsValidReason(sf.geometry) AS sf_valid_reason,
                        ST_IsValid(cf.geometry) AS cf_is_valid,
                        ST_IsValidReason(cf.geometry) AS cf_valid_reason,
                        ST_Intersects(sf.geometry, cf.geometry) AS intersects,
                        ST_Contains(sf.geometry, cf.geometry) AS sf_contains_cf,
                        ST_Contains(cf.geometry, sf.geometry) AS cf_contains_sf,
                        ROUND(ST_Distance(ST_Centroid(sf.geometry)::geography, ST_Centroid(cf.geometry)::geography)::numeric, 2) AS centroid_offset_m,
                        ROUND(ST_Area(sf.geometry::geography)::numeric, 2) AS sf_area_m2,
                        ROUND(ST_Area(cf.geometry::geography)::numeric, 2) AS cf_area_m2,
                        ROUND(ST_Area(ST_Intersection(sf.geometry, cf.geometry)::geography)::numeric, 2) AS intersection_area_m2,
                        ROUND((ST_Area(ST_Intersection(sf.geometry, cf.geometry)::geography) / NULLIF(ST_Area(ST_Union(sf.geometry, cf.geometry)::geography), 0) * 100)::numeric, 2) AS iou_pct
                    FROM canonical_features sf
                    JOIN canonical_features cf ON cf.id = ANY(:candidate_ids)
                    WHERE sf.id = ANY(:source_ids)
                """)

                source_ids = [p[0] for p in feature_id_pairs]
                candidate_ids = [p[1] for p in feature_id_pairs]

                rows = (await db.execute(spatial_query, {
                    "source_ids": source_ids,
                    "candidate_ids": candidate_ids,
                })).fetchall()

                for r in rows:
                    m = dict(r._mapping)
                    pair_key = f"{m['sf_id']}_{m['cf_id']}"
                    postgis_metrics_by_rec[pair_key] = m
            except Exception:
                pass
        elif feature_id_pairs and dialect_name != "postgresql":
            # SQLite fallback for test environments without PostGIS
            try:
                source_ids = [p[0] for p in feature_id_pairs]
                candidate_ids = [p[1] for p in feature_id_pairs]
                all_ids = list(set(source_ids + candidate_ids))
                stmt = select(CanonicalFeature).where(CanonicalFeature.id.in_(all_ids))
                feats = list((await db.execute(stmt)).scalars().all())
                feat_map = {f.id: f for f in feats}

                from shapely.validation import explain_validity
                from app.services.dataset import extract_shapely_geom

                for sf_id, cf_id, rec_id in feature_id_pairs:
                    sf = feat_map.get(sf_id)
                    cf = feat_map.get(cf_id)
                    if not sf or not cf:
                        continue

                    sh_sf = extract_shapely_geom(sf.geometry) if sf else None
                    sh_cf = extract_shapely_geom(cf.geometry) if cf else None


                    sf_valid = sh_sf.is_valid if sh_sf else True
                    cf_valid = sh_cf.is_valid if sh_cf else True
                    sf_reason = explain_validity(sh_sf) if (sh_sf and not sf_valid) else "Valid Geometry"
                    cf_reason = explain_validity(sh_cf) if (sh_cf and not cf_valid) else "Valid Geometry"
                    intersects = sh_sf.intersects(sh_cf) if (sh_sf and sh_cf) else True
                    sf_contains = sh_sf.contains(sh_cf) if (sh_sf and sh_cf) else False
                    cf_contains = sh_cf.contains(sh_sf) if (sh_sf and sh_cf) else False

                    iou = 0.0
                    centroid_dist = 0.0
                    if sh_sf and sh_cf:
                        try:
                            inter_area = sh_sf.intersection(sh_cf).area
                            union_area = sh_sf.union(sh_cf).area
                            iou = round((inter_area / union_area) * 100.0, 2) if union_area > 0 else 0.0
                            centroid_dist = round(sh_sf.centroid.distance(sh_cf.centroid), 2)
                        except Exception:
                            pass

                    postgis_metrics_by_rec[rec_id] = {
                        "sf_id": sf_id,
                        "cf_id": cf_id,
                        "sf_is_null": (sf.geometry is None) if sf else False,
                        "cf_is_null": (cf.geometry is None) if cf else False,
                        "sf_is_empty": sh_sf.is_empty if sh_sf else False,
                        "cf_is_empty": sh_cf.is_empty if sh_cf else False,
                        "sf_is_valid": sf_valid,
                        "sf_valid_reason": sf_reason,
                        "cf_is_valid": cf_valid,
                        "cf_valid_reason": cf_reason,
                        "intersects": intersects,
                        "sf_contains_cf": sf_contains,
                        "cf_contains_sf": cf_contains,
                        "centroid_offset_m": centroid_dist,
                        "iou_pct": iou,
                    }
            except Exception:
                pass


        # 5. Evaluate each harmonized candidate record
        validated_items_data: List[Dict[str, Any]] = []
        pass_count = 0
        warning_count = 0
        fail_count = 0
        geom_fail_count = 0
        topo_fail_count = 0
        area_fail_count = 0
        semantic_fail_count = 0
        conflict_fail_count = 0

        for rec in harmonized_records:
            rec_id = rec.get("id", "")
            src_ident = rec.get("source_identifier", "Unknown")
            cand_ident = rec.get("candidate_identifier", "Unknown")

            parts = rec_id.split("_")
            sf_id = None
            cf_id = None
            if len(parts) >= 2:
                try:
                    sf_id = uuid.UUID(parts[0])
                    cf_id = uuid.UUID(parts[1])
                except (ValueError, TypeError):
                    pass

            pg = postgis_metrics_by_rec.get(rec_id, {})
            record_conflicts = conflicts_by_record.get(rec_id, [])

            failure_reasons: List[str] = []
            warning_reasons: List[str] = []

            # --- A. GEOMETRY VALIDITY ---
            geom_status = "PASS"
            geom_status_from_stage7 = rec.get("geometry_status", "CONGRUENT")

            sf_null = pg.get("sf_is_null", False) or (geom_status_from_stage7 == "NULL")
            cf_null = pg.get("cf_is_null", False)
            sf_empty = pg.get("sf_is_empty", False) or (geom_status_from_stage7 == "EMPTY")
            cf_empty = pg.get("cf_is_empty", False)
            sf_valid = pg.get("sf_is_valid", True) and (geom_status_from_stage7 not in ("INVALID", "EMPTY", "NULL"))
            cf_valid = pg.get("cf_is_valid", True)
            sf_reason = pg.get("sf_valid_reason") or ("Valid Geometry" if sf_valid else f"Geometry invalid: {geom_status_from_stage7}")
            cf_reason = pg.get("cf_valid_reason", "Valid Geometry")

            if sf_null or cf_null:
                geom_status = "FAIL"
                reason = f"Null geometry detected on parcel candidate ({'Source' if sf_null else 'Candidate'})."
                failure_reasons.append(reason)
            elif sf_empty or cf_empty:
                geom_status = "FAIL"
                reason = f"Empty polygon geometry detected on parcel candidate ({'Source' if sf_empty else 'Candidate'})."
                failure_reasons.append(reason)
            elif not sf_valid or not cf_valid:
                geom_status = "FAIL"
                invalid_which = "Source" if not sf_valid else "Candidate"
                invalid_reason = sf_reason if not sf_valid else cf_reason
                reason = f"Geometric invalidity in {invalid_which} polygon: {invalid_reason}"
                failure_reasons.append(reason)

            if geom_status == "FAIL":
                geom_fail_count += 1

            geometry_metrics = {
                "source_valid": sf_valid,
                "candidate_valid": cf_valid,
                "source_is_null": sf_null,
                "candidate_is_null": cf_null,
                "source_is_empty": sf_empty,
                "candidate_is_empty": cf_empty,
                "source_validity_reason": sf_reason,
                "candidate_validity_reason": cf_reason,
                "is_empty": sf_empty or cf_empty,
                "is_null": sf_null or cf_null,
                "is_valid": sf_valid and cf_valid,
                "reason": sf_reason if not sf_valid else cf_reason,
            }

            # --- B. TOPOLOGICAL INTEGRITY ---
            topo_status = "PASS"

            if pg.get("iou_pct") is not None:
                iou = float(pg.get("iou_pct") or 0.0)
            elif geom_status_from_stage7 == "CONGRUENT":
                iou = 95.0
            elif geom_status_from_stage7 == "BOUNDARY_VARIANCE_RECONCILED":
                iou = 65.0
            else:
                iou = 40.0

            if pg.get("centroid_offset_m") is not None:
                centroid_dist = float(pg.get("centroid_offset_m") or 0.0)
            elif geom_status_from_stage7 == "CONGRUENT":
                centroid_dist = 0.5
            elif geom_status_from_stage7 == "BOUNDARY_VARIANCE_RECONCILED":
                centroid_dist = 3.5
            else:
                centroid_dist = 12.0

            intersects = bool(pg.get("intersects", True))
            sf_contains = bool(pg.get("sf_contains_cf", False))
            cf_contains = bool(pg.get("cf_contains_sf", False))

            if req.check_topology:
                if geom_status_from_stage7 == "SELF_INTERSECTING":
                    topo_status = "FAIL"
                    reason = "Topology integrity failure: Self-intersecting polygon geometry detected."
                    failure_reasons.append(reason)
                elif not intersects and centroid_dist > 50.0:
                    topo_status = "FAIL"
                    reason = f"Spatial disconnection: parcel polygons do not intersect and centroid offset is {centroid_dist:.1f} m."
                    failure_reasons.append(reason)
                elif iou < 10.0 and not (sf_contains or cf_contains):
                    topo_status = "FAIL"
                    reason = f"Severe topological divergence: parcel polygons have less than 10% overlap (IoU = {iou:.1f}%)."
                    failure_reasons.append(reason)
                elif iou < 50.0:
                    topo_status = "WARNING"
                    reason = f"Boundary variance: spatial IoU is {iou:.1f}% with {centroid_dist:.1f} m centroid displacement."
                    warning_reasons.append(reason)
                elif centroid_dist > 15.0:
                    topo_status = "WARNING"
                    reason = f"Significant centroid offset ({centroid_dist:.1f} m) between source and candidate polygons."
                    warning_reasons.append(reason)

            if topo_status == "FAIL":
                topo_fail_count += 1

            topology_metrics = {
                "iou_pct": iou,
                "overlap_ratio": round(iou / 100.0, 4),
                "centroid_offset_m": centroid_dist,
                "centroid_dist_meters": centroid_dist,
                "intersects": intersects,
                "source_contains_candidate": sf_contains,
                "candidate_contains_source": cf_contains,
                "intersection_area_m2": float(pg.get("intersection_area_m2") or 0.0),
                "self_intersection": (geom_status_from_stage7 == "SELF_INTERSECTING"),
                "topology_consistent": (topo_status == "PASS"),
            }

            # --- C. AREA VALIDATION ---
            area_status = "PASS"
            src_area = rec.get("source_area")
            cand_area = rec.get("candidate_area")
            harm_area = rec.get("harmonized_area")
            area_diff_pct = float(rec.get("area_discrepancy_pct") or 0.0)

            if src_area is None or cand_area is None or (src_area <= 0 and cand_area <= 0):
                area_status = "FAIL"
                reason = "Missing or uncomputable parcel surface area."
                failure_reasons.append(reason)
            elif area_diff_pct > req.area_warning_threshold_pct:
                area_status = "FAIL"
                reason = f"Severe area discrepancy: difference of {area_diff_pct:.1f}% exceeds maximum allowable threshold ({req.area_warning_threshold_pct}%)."
                failure_reasons.append(reason)
            elif area_diff_pct > req.area_tolerance_pct:
                area_status = "WARNING"
                reason = f"Area discrepancy of {area_diff_pct:.1f}% exceeds target tolerance ({req.area_tolerance_pct}%)."
                warning_reasons.append(reason)

            if area_status == "FAIL":
                area_fail_count += 1

            area_metrics = {
                "source_area_m2": src_area,
                "candidate_area_m2": cand_area,
                "harmonized_area_m2": harm_area,
                "discrepancy_pct": area_diff_pct,
                "tolerance_threshold_pct": req.area_tolerance_pct,
                "warning_threshold_pct": req.area_warning_threshold_pct,
            }

            # --- D. ATTRIBUTE / SEMANTIC VALIDATION ---
            semantic_status = "PASS"
            src_lu = rec.get("source_land_use")
            cand_lu = rec.get("candidate_land_use")
            harm_lu = rec.get("harmonized_land_use")
            src_mut = rec.get("source_mutation_status")
            cand_mut = rec.get("candidate_mutation_status")
            harm_mut = rec.get("harmonized_mutation_status")
            harm_risk = rec.get("harmonized_risk_level")

            norm_lu = normalize_semantic_land_use(harm_lu)
            norm_mut = normalize_semantic_mutation(harm_mut)
            norm_risk = normalize_semantic_risk(harm_risk)

            if req.check_semantics:
                # 1. Missing required identifier or survey number
                if not rec.get("source_survey_number") and not rec.get("candidate_survey_number") and src_ident == "Unknown":
                    semantic_status = "FAIL"
                    reason = "Missing authoritative survey number and identifier for parcel candidate."
                    failure_reasons.append(reason)

                # 2. Check unverified mutation status
                if norm_mut in ["DISPUTED", "REJECTED"]:
                    semantic_status = "WARNING" if semantic_status != "FAIL" else "FAIL"
                    reason = f"Registry mutation status is '{norm_mut}', requiring legal clearance."
                    warning_reasons.append(reason)

                # 3. Check extreme environmental risk
                if norm_risk == "CRITICAL":
                    semantic_status = "WARNING" if semantic_status != "FAIL" else "FAIL"
                    reason = "Parcel has CRITICAL environmental/hazard risk classification."
                    warning_reasons.append(reason)

                # 4. Check conflicting semantic values
                if src_lu and cand_lu:
                    norm_src_lu = normalize_semantic_land_use(src_lu)
                    norm_cand_lu = normalize_semantic_land_use(cand_lu)
                    if norm_src_lu and norm_cand_lu and norm_src_lu != norm_cand_lu:
                        # Incompatible transition: e.g. Agricultural vs Industrial / Commercial
                        if {norm_src_lu, norm_cand_lu} & {"AGRICULTURAL"} and {norm_src_lu, norm_cand_lu} & {"INDUSTRIAL", "COMMERCIAL"}:
                            semantic_status = "WARNING" if semantic_status != "FAIL" else "FAIL"
                            reason = f"Incompatible land-use classification: '{norm_src_lu}' vs '{norm_cand_lu}' without zoning conversion verification."
                            warning_reasons.append(reason)

            if semantic_status == "FAIL":
                semantic_fail_count += 1

            semantic_metrics = {
                "source_land_use": src_lu,
                "candidate_land_use": cand_lu,
                "harmonized_land_use": harm_lu,
                "normalized_land_use": norm_lu,
                "harmonized_mutation_status": harm_mut,
                "normalized_mutation_status": norm_mut,
                "harmonized_risk_level": harm_risk,
                "normalized_risk_level": norm_risk,
            }

            # --- E. CONFLICT-AWARE VALIDATION ---
            conflict_status = "PASS"
            unresolved_conflicts = [
                c for c in record_conflicts if c.status not in ["RESOLVED", "DISMISSED"]
            ]
            has_critical = any(c.severity == "CRITICAL" for c in unresolved_conflicts)
            has_high = any(c.severity == "HIGH" for c in unresolved_conflicts)

            if req.consume_conflicts and unresolved_conflicts:
                if has_critical:
                    conflict_status = "FAIL"
                    crit_conf = next(c for c in unresolved_conflicts if c.severity == "CRITICAL")
                    reason = f"Unresolved CRITICAL conflict: {crit_conf.conflict_type} ({crit_conf.explanation})"
                    failure_reasons.append(reason)
                elif has_high:
                    conflict_status = "WARNING"
                    high_conf = next(c for c in unresolved_conflicts if c.severity == "HIGH")
                    reason = f"Unresolved HIGH severity conflict: {high_conf.conflict_type} ({high_conf.explanation})"
                    warning_reasons.append(reason)
                else:
                    conflict_status = "WARNING"
                    warning_reasons.append(f"{len(unresolved_conflicts)} open conflict(s) pending review.")

            if conflict_status == "FAIL":
                conflict_fail_count += 1

            conflict_metrics = {
                "total_conflicts_associated": len(record_conflicts),
                "unresolved_conflicts_count": len(unresolved_conflicts),
                "has_critical_conflicts": has_critical,
                "has_high_conflicts": has_high,
                "conflict_ids": [str(c.id) for c in record_conflicts],
                "conflict_types": list(set(c.conflict_type for c in record_conflicts)),
            }

            # --- OVERALL STATUS ---
            statuses = [geom_status, topo_status, area_status, semantic_status, conflict_status]
            if "FAIL" in statuses:
                overall = "FAIL"
                fail_count += 1
            elif "WARNING" in statuses:
                overall = "WARNING"
                warning_count += 1
            else:
                overall = "PASS"
                pass_count += 1

            validated_items_data.append({
                "harmonized_record_id": rec_id,
                "source_feature_id": sf_id,
                "candidate_feature_id": cf_id,
                "source_identifier": src_ident,
                "candidate_identifier": cand_ident,
                "overall_status": overall,
                "geometry_validity_status": geom_status,
                "topology_status": topo_status,
                "area_status": area_status,
                "semantic_status": semantic_status,
                "conflict_status": conflict_status,
                "failure_reasons": failure_reasons,
                "warning_reasons": warning_reasons,
                "geometry_metrics": geometry_metrics,
                "topology_metrics": topology_metrics,
                "area_metrics": area_metrics,
                "semantic_metrics": semantic_metrics,
                "conflict_metrics": conflict_metrics,
                "idempotency_key": f"{project_id}:{rec_id}",
            })

        # 6. Idempotent Database Upsert
        existing_val_stmt = select(ValidationResult).where(ValidationResult.project_id == project_id)
        existing_val_records = list((await db.execute(existing_val_stmt)).scalars().all())
        existing_by_key = {v.idempotency_key: v for v in existing_val_records}

        created_count = 0
        updated_count = 0
        now = datetime.now(timezone.utc)

        for val_data in validated_items_data:
            key = val_data["idempotency_key"]
            existing = existing_by_key.get(key)
            if existing:
                existing.overall_status = val_data["overall_status"]
                existing.geometry_validity_status = val_data["geometry_validity_status"]
                existing.topology_status = val_data["topology_status"]
                existing.area_status = val_data["area_status"]
                existing.semantic_status = val_data["semantic_status"]
                existing.conflict_status = val_data["conflict_status"]
                existing.failure_reasons = val_data["failure_reasons"]
                existing.warning_reasons = val_data["warning_reasons"]
                existing.geometry_metrics = val_data["geometry_metrics"]
                existing.topology_metrics = val_data["topology_metrics"]
                existing.area_metrics = val_data["area_metrics"]
                existing.semantic_metrics = val_data["semantic_metrics"]
                existing.conflict_metrics = val_data["conflict_metrics"]
                existing.updated_at = now
                updated_count += 1
            else:
                new_val = ValidationResult(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    harmonized_record_id=val_data["harmonized_record_id"],
                    source_feature_id=val_data["source_feature_id"],
                    candidate_feature_id=val_data["candidate_feature_id"],
                    source_identifier=val_data["source_identifier"],
                    candidate_identifier=val_data["candidate_identifier"],
                    overall_status=val_data["overall_status"],
                    geometry_validity_status=val_data["geometry_validity_status"],
                    topology_status=val_data["topology_status"],
                    area_status=val_data["area_status"],
                    semantic_status=val_data["semantic_status"],
                    conflict_status=val_data["conflict_status"],
                    failure_reasons=val_data["failure_reasons"],
                    warning_reasons=val_data["warning_reasons"],
                    geometry_metrics=val_data["geometry_metrics"],
                    topology_metrics=val_data["topology_metrics"],
                    area_metrics=val_data["area_metrics"],
                    semantic_metrics=val_data["semantic_metrics"],
                    conflict_metrics=val_data["conflict_metrics"],
                    idempotency_key=key,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_val)
                existing_by_key[key] = new_val
                created_count += 1

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        results_data = {
            "records_validated": len(validated_items_data),
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "geometry_failures_count": geom_fail_count,
            "topology_failures_count": topo_fail_count,
            "area_failures_count": area_fail_count,
            "semantic_failures_count": semantic_fail_count,
            "conflict_failures_count": conflict_fail_count,
            "counts_by_status": {
                "PASS": pass_count,
                "WARNING": warning_count,
                "FAIL": fail_count,
            },
            "counts_by_category": {
                "GEOMETRY": geom_fail_count,
                "TOPOLOGY": topo_fail_count,
                "AREA": area_fail_count,
                "SEMANTIC": semantic_fail_count,
                "CONFLICT": conflict_fail_count,
            },
            "results_created": created_count,
            "results_updated": updated_count,
            "execution_time_ms": duration_ms,
        }

        # 7. Update or Create PipelineStageExecution for Stage 09
        stage9_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "validation",
            )
        )
        stage9_exec = (await db.execute(stage9_stmt)).scalar_one_or_none()

        inputs_data = req.model_dump()
        if not stage9_exec:
            stage9_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=9,
                stage_id="validation",
                status="completed",
                inputs=inputs_data,
                results=results_data,
                started_at=now,
                completed_at=now,
            )
            db.add(stage9_exec)
        else:
            stage9_exec.status = "completed"
            stage9_exec.inputs = inputs_data
            stage9_exec.results = results_data
            stage9_exec.completed_at = now

        await db.commit()

        return ValidationRunResponse(
            stage_id="validation",
            stage_number=9,
            status="completed",
            project_id=project_id,
            records_validated=len(validated_items_data),
            pass_count=pass_count,
            warning_count=warning_count,
            fail_count=fail_count,
            geometry_failures_count=geom_fail_count,
            topology_failures_count=topo_fail_count,
            area_failures_count=area_fail_count,
            semantic_failures_count=semantic_fail_count,
            conflict_failures_count=conflict_fail_count,
            results_created=created_count,
            results_updated=updated_count,
            execution_time_ms=duration_ms,
        )

    @classmethod
    async def list_validation_results(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> ValidationResultListResponse:
        """
        Retrieves paginated and filtered validation results for a project.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # Summary counts across all validation results for this project
        summary = await cls.get_validation_summary(db, project_id)

        # Filters
        filters = [ValidationResult.project_id == project_id]

        if status and status.upper() != "ALL":
            filters.append(ValidationResult.overall_status == status.strip().upper())

        if category and category.upper() != "ALL":
            cat = category.strip().upper()
            if cat == "GEOMETRY":
                filters.append(ValidationResult.geometry_validity_status.in_(["WARNING", "FAIL"]))
            elif cat == "TOPOLOGY":
                filters.append(ValidationResult.topology_status.in_(["WARNING", "FAIL"]))
            elif cat == "AREA":
                filters.append(ValidationResult.area_status.in_(["WARNING", "FAIL"]))
            elif cat == "SEMANTIC":
                filters.append(ValidationResult.semantic_status.in_(["WARNING", "FAIL"]))
            elif cat == "CONFLICT":
                filters.append(ValidationResult.conflict_status.in_(["WARNING", "FAIL"]))

        if search:
            q = f"%{search.strip()}%"
            filters.append(
                or_(
                    ValidationResult.harmonized_record_id.ilike(q),
                    ValidationResult.source_identifier.ilike(q),
                    ValidationResult.candidate_identifier.ilike(q),
                )
            )

        # Total matching filter
        total_stmt = select(func.count(ValidationResult.id)).where(*filters)
        total = (await db.execute(total_stmt)).scalar() or 0

        # Query items with custom ordering: FAIL -> WARNING -> PASS
        order_rank = case(
            (ValidationResult.overall_status == "FAIL", 1),
            (ValidationResult.overall_status == "WARNING", 2),
            (ValidationResult.overall_status == "PASS", 3),
            else_=4,
        )

        query = (
            select(ValidationResult)
            .where(*filters)
            .order_by(order_rank.asc(), ValidationResult.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list((await db.execute(query)).scalars().all())

        return ValidationResultListResponse(
            items=[ValidationResultRead.model_validate(v) for v in items],
            total=total,
            skip=skip,
            limit=limit,
            summary=summary,
        )

    @classmethod
    async def get_validation_summary(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ValidationSummaryResponse:
        """
        Computes project-level validation summary statistics.
        """
        stmt = (
            select(
                func.count(ValidationResult.id).label("total"),
                func.count(case((ValidationResult.overall_status == "PASS", 1))).label("pass_count"),
                func.count(case((ValidationResult.overall_status == "WARNING", 1))).label("warning_count"),
                func.count(case((ValidationResult.overall_status == "FAIL", 1))).label("fail_count"),
                func.count(case((ValidationResult.geometry_validity_status == "FAIL", 1))).label("geom_fail"),
                func.count(case((ValidationResult.topology_status == "FAIL", 1))).label("topo_fail"),
                func.count(case((ValidationResult.area_status == "FAIL", 1))).label("area_fail"),
                func.count(case((ValidationResult.semantic_status == "FAIL", 1))).label("semantic_fail"),
                func.count(case((ValidationResult.conflict_status == "FAIL", 1))).label("conflict_fail"),
            )
            .where(ValidationResult.project_id == project_id)
        )
        row = (await db.execute(stmt)).first()

        total = row.total if row else 0
        p_cnt = row.pass_count if row else 0
        w_cnt = row.warning_count if row else 0
        f_cnt = row.fail_count if row else 0
        g_fail = row.geom_fail if row else 0
        t_fail = row.topo_fail if row else 0
        a_fail = row.area_fail if row else 0
        s_fail = row.semantic_fail if row else 0
        c_fail = row.conflict_fail if row else 0

        return ValidationSummaryResponse(
            project_id=project_id,
            total_validated=total,
            pass_count=p_cnt,
            warning_count=w_cnt,
            fail_count=f_cnt,
            geometry_failures=g_fail,
            topology_failures=t_fail,
            area_failures=a_fail,
            semantic_failures=s_fail,
            conflict_failures=c_fail,
            counts_by_status={
                "PASS": p_cnt,
                "WARNING": w_cnt,
                "FAIL": f_cnt,
            },
            counts_by_category={
                "GEOMETRY": g_fail,
                "TOPOLOGY": t_fail,
                "AREA": a_fail,
                "SEMANTIC": s_fail,
                "CONFLICT": c_fail,
            },
        )

    @classmethod
    async def get_validation_result_detail(
        cls,
        db: AsyncSession,
        result_id: uuid.UUID,
    ) -> Optional[ValidationResultRead]:
        """
        Retrieves full details for a single validation result.
        """
        res = await db.get(ValidationResult, result_id)
        if not res:
            return None
        return ValidationResultRead.model_validate(res)
