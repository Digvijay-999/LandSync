import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConflictSourceValue(BaseModel):
    """
    Represents the attribute value contributed by a specific source feature.
    """

    source_role: str = Field(..., description="Role of the source (e.g. CADASTRAL, DRONE, MUNICIPAL)")
    dataset_id: Optional[uuid.UUID] = Field(None, description="Originating dataset ID")
    dataset_name: str = Field(..., description="Originating dataset name")
    dataset_version: Optional[int] = Field(None, description="Originating dataset version")
    feature_id: uuid.UUID = Field(..., description="Canonical feature ID")
    feature_identifier: str = Field(..., description="Human-readable feature or parcel identifier")
    value: Any = Field(..., description="The conflicting attribute value from this source")


class ConflictResolutionRead(BaseModel):
    """
    Representation of an audit-verified human conflict resolution.
    """

    id: uuid.UUID
    conflict_id: uuid.UUID
    resolution_type: str = Field(..., description="SOURCE_SELECTION, MANUAL_VALUE, or DISMISSED")
    selected_source_feature_id: Optional[uuid.UUID] = None
    selected_source_role: Optional[str] = None
    resolved_value: Any
    comment: str
    resolved_by: Optional[str] = None
    resolved_at: datetime

    model_config = {"from_attributes": True}


class AttributeConflictRead(BaseModel):
    """
    Full representation of an attribute conflict on a UnifiedLandRecord.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    unified_land_record_id: uuid.UUID
    record_identifier: Optional[str] = None
    attribute_name: str
    conflict_type: str
    severity: str
    status: str
    detected_values: List[ConflictSourceValue] = Field(default_factory=list)
    resolution: Optional[ConflictResolutionRead] = None
    dismissal_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConflictResolveInput(BaseModel):
    """
    Payload for resolving an AttributeConflict.
    """

    resolution_type: str = Field(
        ...,
        description="Resolution type: SOURCE_SELECTION or MANUAL_VALUE",
    )
    selected_source_feature_id: Optional[uuid.UUID] = Field(
        None,
        description="Required if resolution_type is SOURCE_SELECTION",
    )
    manual_value: Optional[Any] = Field(
        None,
        description="Required if resolution_type is MANUAL_VALUE (cannot be empty)",
    )
    comment: str = Field(
        ...,
        min_length=1,
        description="Required audit explanation and reason for the decision",
    )
    resolved_by: Optional[str] = Field(
        "Human Reviewer",
        description="Reviewer identity or role",
    )


class ConflictDismissInput(BaseModel):
    """
    Payload for dismissing an AttributeConflict.
    """

    reason: str = Field(
        ...,
        min_length=1,
        description="Required explanation for dismissing the detected conflict",
    )
    resolved_by: Optional[str] = Field(
        "Human Reviewer",
        description="Reviewer identity or role",
    )


class ConflictListResponse(BaseModel):
    """
    Paginated list of attribute conflicts.
    """

    items: List[AttributeConflictRead]
    total: int
    skip: int
    limit: int


class ConflictSummaryResponse(BaseModel):
    """
    Project-level conflict dashboard statistics.
    """

    project_id: uuid.UUID
    total_conflicts: int
    unresolved_conflicts: int
    resolved_conflicts: int
    dismissed_conflicts: int
    records_with_conflicts: int
    by_attribute: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
