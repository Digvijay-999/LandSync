import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ConflictSourceReference(BaseModel):
    source_name: str
    feature_id: Optional[str] = None
    value: Any = None
    source_type: Optional[str] = None
    authority_weight: Optional[float] = None
    timestamp: Optional[datetime] = None


class ConflictResolutionProposal(BaseModel):
    proposal_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conflict_id: uuid.UUID
    project_id: uuid.UUID
    unified_land_record_id: uuid.UUID
    record_identifier: str
    attribute_name: str
    conflicting_values: List[Dict[str, Any]]
    
    # Grounded Proposal Fields
    recommended_value: Any
    recommended_source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Separation of Facts, Inferences, and Recommendations
    fact_statement: str = Field(..., description="Objective statement of observed values across sources")
    inference_statement: str = Field(..., description="Technical inference regarding root cause of discrepancy")
    recommendation_statement: str = Field(..., description="Actionable advisory recommendation for human reviewer")
    
    reasoning: str
    supporting_evidence: List[str] = Field(default_factory=list)
    source_references: List[ConflictSourceReference] = Field(default_factory=list)
    
    # Safety and Governance
    requires_human_approval: bool = True
    is_advisory_only: bool = True
    disclaimer: str = (
        "ADVISORY RECOMMENDATION ONLY: This AI proposal has not modified any unified records or conflicts. "
        "Formal resolution requires manual verification and explicit human approval."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
