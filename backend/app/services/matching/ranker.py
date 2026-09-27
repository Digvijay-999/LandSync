from typing import List, Dict, Any, Optional
from collections import defaultdict
from app.models.matching import FeatureMatch
from app.services.matching.config import MatchingConfig


class CandidateRanker:
    """
    Ranks candidate matches per source feature, determines best/secondary/ambiguous roles,
    calculates score gaps, and computes run-level quality metrics.
    """

    @classmethod
    def rank_matches_for_run(
        cls,
        matches: List[FeatureMatch],
        config: MatchingConfig,
    ) -> Dict[str, Any]:
        """
        Groups all FeatureMatch records by source_feature_id, assigns ranks,
        evaluates roles and score gaps, and returns run-level quality metrics.
        """
        # Group matches by source feature
        source_groups: Dict[Any, List[FeatureMatch]] = defaultdict(list)
        for m in matches:
            source_groups[m.source_feature_id].append(m)

        for source_id, group in source_groups.items():
            cls._rank_source_group(group, config)

        # Compute quality metrics
        quality_metrics = cls.compute_quality_metrics(source_groups)
        return quality_metrics

    @classmethod
    def _rank_source_group(
        cls,
        group: List[FeatureMatch],
        config: MatchingConfig,
    ) -> None:
        """
        Ranks candidates for a single source feature and assigns candidate roles and score gaps.
        """
        # Filter for actual candidate matches (where candidate_feature_id is not None)
        valid_candidates = [m for m in group if m.candidate_feature_id is not None]

        if not valid_candidates:
            # Source feature with no candidates within spatial tolerance
            for m in group:
                m.rank = 1
                m.is_best_candidate = False
                m.candidate_role = "UNMATCHED"
                m.score_gap = None
                m.candidate_count = 0
            return

        # Sort candidates descending by overall_score (deterministic secondary sort by UUID string)
        valid_candidates.sort(
            key=lambda m: (m.overall_score, str(m.candidate_feature_id or "")),
            reverse=True,
        )

        cand_count = len(valid_candidates)
        m1 = valid_candidates[0]
        m2 = valid_candidates[1] if cand_count >= 2 else None
        score_gap = round(m1.overall_score - m2.overall_score, 4) if m2 else None

        # Check for ambiguity (near tie between top candidates within tie tolerance)
        is_ambiguous = (
            cand_count >= 2
            and score_gap is not None
            and score_gap <= config.best_candidate_tie_tolerance
            and m1.overall_score >= config.possible_threshold
        )

        for idx, m in enumerate(valid_candidates, start=1):
            m.rank = idx
            m.candidate_count = cand_count
            m.score_gap = score_gap

            if is_ambiguous:
                # Top candidates within tie tolerance are marked AMBIGUOUS
                if round(m1.overall_score - m.overall_score, 4) <= config.best_candidate_tie_tolerance:
                    m.candidate_role = "AMBIGUOUS"
                    m.is_best_candidate = False
                else:
                    m.candidate_role = "SECONDARY"
                    m.is_best_candidate = False
            elif idx == 1:
                # Rank 1 candidate
                if m.status == "conflict":
                    m.candidate_role = "CONFLICT"
                    m.is_best_candidate = False
                elif m.status == "unmatched":
                    m.candidate_role = "UNMATCHED"
                    m.is_best_candidate = False
                else:
                    m.candidate_role = "BEST"
                    m.is_best_candidate = True
            else:
                # Rank >= 2 candidates
                m.is_best_candidate = False
                if m.status == "conflict":
                    m.candidate_role = "CONFLICT"
                else:
                    m.candidate_role = "SECONDARY"

    @classmethod
    def compute_quality_metrics(
        cls,
        source_groups: Dict[Any, List[FeatureMatch]],
    ) -> Dict[str, Any]:
        """
        Calculates run-level candidate quality metrics based on source feature ranking results.
        """
        total_source_features = len(source_groups)
        features_with_candidates = 0
        features_with_no_candidates = 0
        features_with_one_candidate = 0
        features_with_multiple_candidates = 0
        features_with_unambiguous_best = 0
        features_with_ambiguous_best = 0
        features_with_conflict = 0

        for source_id, group in source_groups.items():
            valid_candidates = [m for m in group if m.candidate_feature_id is not None]
            c_count = len(valid_candidates)

            if c_count == 0:
                features_with_no_candidates += 1
            else:
                features_with_candidates += 1
                if c_count == 1:
                    features_with_one_candidate += 1
                else:
                    features_with_multiple_candidates += 1

                # Check top candidate's role
                top_m = min(valid_candidates, key=lambda m: m.rank or 999)
                if top_m.candidate_role == "BEST":
                    features_with_unambiguous_best += 1
                elif top_m.candidate_role == "AMBIGUOUS":
                    features_with_ambiguous_best += 1
                elif top_m.candidate_role == "CONFLICT":
                    features_with_conflict += 1

        return {
            "total_source_features": total_source_features,
            "features_with_candidates": features_with_candidates,
            "features_with_no_candidates": features_with_no_candidates,
            "features_with_one_candidate": features_with_one_candidate,
            "features_with_multiple_candidates": features_with_multiple_candidates,
            "features_with_unambiguous_best": features_with_unambiguous_best,
            "features_with_ambiguous_best": features_with_ambiguous_best,
            "features_with_conflict": features_with_conflict,
        }
