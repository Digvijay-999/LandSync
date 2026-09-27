from typing import Optional, Dict, Any, List, Tuple
from app.services.matching.config import MatchingConfig


class ScoringEngine:
    """
    Computes normalized weighted overall match scores with dynamic weight renormalization
    for non-applicable signals, generates explainable decision logs, and classifies matches.
    """

    @classmethod
    def evaluate_match(
        cls,
        spatial_score: Optional[float],
        centroid_score: Optional[float],
        area_score: Optional[float],
        geometry_score: Optional[float],
        attribute_score: Optional[float],
        attribute_details: Dict[str, Any],
        config: MatchingConfig,
        geom_type_a: str = "",
        geom_type_b: str = "",
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Calculates the overall score, assigns classification status, and constructs
        a detailed machine-readable explanation.
        Returns (overall_score, status, explanation_dict).
        """
        weights = config.get_weights_dict()
        signals = {
            "spatial_overlap": spatial_score,
            "centroid_distance": centroid_score,
            "area_similarity": area_score,
            "geometry_similarity": geometry_score,
            "attribute_similarity": attribute_score,
        }

        # 1. Dynamic Weight Renormalization
        applicable_weights: Dict[str, float] = {}
        weighted_sum = 0.0

        for signal_name, score in signals.items():
            if score is not None:
                w = weights.get(signal_name, 0.0)
                applicable_weights[signal_name] = w
                weighted_sum += w * score

        sum_weights = sum(applicable_weights.values())
        if sum_weights > 0.0:
            overall_score = float(weighted_sum / sum_weights)
        else:
            overall_score = 0.0

        overall_score = round(max(0.0, min(1.0, overall_score)), 4)

        # 2. Determine Classification Status
        status = cls.classify_status(
            overall_score=overall_score,
            spatial_score=spatial_score,
            centroid_score=centroid_score,
            area_score=area_score,
            attribute_score=attribute_score,
            config=config,
        )

        # 3. Construct Explainable Reasons
        reasons = cls.generate_reasons(
            overall_score=overall_score,
            status=status,
            spatial_score=spatial_score,
            centroid_score=centroid_score,
            area_score=area_score,
            geometry_score=geometry_score,
            attribute_score=attribute_score,
            attribute_details=attribute_details,
            geom_type_a=geom_type_a,
            geom_type_b=geom_type_b,
        )

        explanation = {
            "overall_score": overall_score,
            "status": status,
            "reasons": reasons,
            "component_scores": {
                "spatial_overlap": round(spatial_score, 4) if spatial_score is not None else None,
                "centroid_similarity": round(centroid_score, 4) if centroid_score is not None else None,
                "area_similarity": round(area_score, 4) if area_score is not None else None,
                "geometry_similarity": round(geometry_score, 4) if geometry_score is not None else None,
                "attribute_similarity": round(attribute_score, 4) if attribute_score is not None else None,
            },
            "applicable_weights": {k: round(v / sum_weights, 3) for k, v in applicable_weights.items()} if sum_weights > 0 else {},
            "attribute_alignments": attribute_details.get("matched_fields", []),
            "scoring_version": config.scoring_version,
        }

        return overall_score, status, explanation

    @classmethod
    def classify_status(
        cls,
        overall_score: float,
        spatial_score: Optional[float],
        centroid_score: Optional[float],
        area_score: Optional[float],
        attribute_score: Optional[float],
        config: MatchingConfig,
    ) -> str:
        """
        Classifies match into 'matched', 'possible_match', 'conflict', or 'unmatched'.
        Strictly distinguishes CONFLICT (spatial co-location with attribute/area contradiction)
        from UNMATCHED (spatially disjoint).
        """
        # Conflict Check: Strong spatial proximity or overlap BUT strong attribute or area disagreement
        has_spatial_presence = (
            (spatial_score is not None and spatial_score >= 0.50) or
            (centroid_score is not None and centroid_score >= 0.70)
        )
        has_severe_contradiction = (
            (attribute_score is not None and attribute_score < 0.25) or
            (area_score is not None and area_score < 0.35)
        )

        if has_spatial_presence and has_severe_contradiction:
            return "conflict"

        # Standard Threshold Hierarchy
        if overall_score >= config.matched_threshold:
            return "matched"
        elif overall_score >= config.possible_threshold:
            return "possible_match"
        elif overall_score >= config.conflict_threshold and has_spatial_presence:
            return "conflict"
        else:
            return "unmatched"

    @classmethod
    def generate_reasons(
        cls,
        overall_score: float,
        status: str,
        spatial_score: Optional[float],
        centroid_score: Optional[float],
        area_score: Optional[float],
        geometry_score: Optional[float],
        attribute_score: Optional[float],
        attribute_details: Dict[str, Any],
        geom_type_a: str,
        geom_type_b: str,
    ) -> List[str]:
        """
        Produces human-readable, deterministic explanations based on actual calculated signals.
        """
        reasons: List[str] = []

        # Overlap explanation
        if spatial_score is not None:
            if spatial_score >= 0.85:
                reasons.append(f"Strong spatial overlap ({spatial_score * 100:.1f}% IoU)")
            elif spatial_score >= 0.50:
                reasons.append(f"Moderate spatial intersection ({spatial_score * 100:.1f}% IoU)")
            elif spatial_score > 0.0:
                reasons.append(f"Minor boundary overlap ({spatial_score * 100:.1f}%)")
            else:
                reasons.append("No direct spatial intersection between feature boundaries")
        elif "point" in geom_type_a.lower() or "point" in geom_type_b.lower():
            reasons.append("Point geometry: areal overlap not applicable, evaluated on spatial proximity")

        # Centroid distance explanation
        if centroid_score is not None:
            if centroid_score >= 0.90:
                reasons.append(f"Centroids are co-located or nearly identical ({centroid_score * 100:.1f}% proximity)")
            elif centroid_score >= 0.60:
                reasons.append(f"Centroids are well within distance tolerance ({centroid_score * 100:.1f}% proximity)")
            else:
                reasons.append(f"Centroid distance approaches search tolerance threshold ({centroid_score * 100:.1f}% proximity)")

        # Area explanation
        if area_score is not None:
            if area_score >= 0.85:
                reasons.append(f"Consistent parcel/structure area ({area_score * 100:.1f}% match)")
            elif area_score < 0.40:
                reasons.append(f"Significant area discrepancy ({area_score * 100:.1f}% similarity)")

        # Attribute alignment explanation
        matched_fields = attribute_details.get("matched_fields", [])
        if matched_fields:
            high_matches = [m for m in matched_fields if m.get("similarity", 0) >= 0.80]
            mismatches = [m for m in matched_fields if m.get("similarity", 0) < 0.40]

            if high_matches:
                names = ", ".join(f"'{m['field_a']}'" for m in high_matches[:2])
                reasons.append(f"Corroborating attribute identifiers ({names})")
            if mismatches:
                mismatch_names = ", ".join(f"'{m['field_a']}' vs '{m['field_b']}'" for m in mismatches[:2])
                reasons.append(f"Attribute value discrepancy in {mismatch_names}")
        elif attribute_score is not None and attribute_score == 0.5:
            reasons.append("No common or semantically aligned attribute fields available")

        # Status summary reason
        if status == "matched":
            reasons.append(f"High multi-signal confidence ({overall_score * 100:.1f}%) confirms unified entity")
        elif status == "possible_match":
            reasons.append(f"Probable match ({overall_score * 100:.1f}%) with minor geometric or attribute variation")
        elif status == "conflict":
            reasons.append("Spatial alignment present but contradictory attributes or area suggest a conflict requiring review")
        elif status == "unmatched":
            reasons.append("Insufficient spatial or attribute similarity across all signals")

        return reasons
