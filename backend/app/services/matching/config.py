from typing import Dict, Any
from pydantic import BaseModel, Field


class MatchingConfig(BaseModel):
    """
    Centralized, configurable parameters for spatial candidate generation,
    scoring weights, classification thresholds, and algorithm versioning.
    """

    # Spatial tolerance for candidate generation (in meters)
    candidate_search_distance_meters: float = Field(
        default=50.0,
        ge=1.0,
        le=5000.0,
        description="Maximum distance (in meters) to search for candidate features in PostGIS.",
    )

    # Classification thresholds (0.0 to 1.0)
    matched_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum overall score to classify a pair as MATCHED.",
    )
    possible_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum overall score to classify a pair as POSSIBLE_MATCH.",
    )
    conflict_threshold: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Score floor below which pairs are considered UNMATCHED unless conflict criteria are met.",
    )

    # Signal weights (must sum to 1.0 when all applicable)
    spatial_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    area_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    centroid_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    geometry_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    attribute_weight: float = Field(default=0.10, ge=0.0, le=1.0)

    # Milestone 3.1: Best-candidate tie tolerance
    best_candidate_tie_tolerance: float = Field(
        default=0.015,
        ge=0.0,
        le=0.20,
        description="Score difference threshold below which the top two candidates are marked as AMBIGUOUS.",
    )

    # Algorithm scoring version
    scoring_version: str = Field(default="v1.1")

    def get_weights_dict(self) -> Dict[str, float]:
        return {
            "spatial_overlap": self.spatial_weight,
            "area_similarity": self.area_weight,
            "centroid_distance": self.centroid_weight,
            "geometry_similarity": self.geometry_weight,
            "attribute_similarity": self.attribute_weight,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
