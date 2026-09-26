"""Machine-readable decision objects and candidate evaluation models for trigger intelligence."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel
from vera.models.trigger import TriggerContext


class ReasonCode(str, Enum):
    """Machine-readable outcome code for trigger arbitration."""

    TRIGGER_SELECTED = "TRIGGER_SELECTED"
    NO_TRIGGERS_AVAILABLE = "NO_TRIGGERS_AVAILABLE"
    ALL_TRIGGERS_INVALID = "ALL_TRIGGERS_INVALID"
    ALL_TRIGGERS_EXPIRED = "ALL_TRIGGERS_EXPIRED"
    ALL_TRIGGERS_IRRELEVANT = "ALL_TRIGGERS_IRRELEVANT"
    ALL_TRIGGERS_SUPPRESSED = "ALL_TRIGGERS_SUPPRESSED"


class RejectionReason(str, Enum):
    """Why a candidate trigger was disqualified."""

    EXPIRED = "EXPIRED"
    SUPPRESSED = "SUPPRESSED"
    MERCHANT_NOT_FOUND = "MERCHANT_NOT_FOUND"
    CATEGORY_MISMATCH = "CATEGORY_MISMATCH"
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    CUSTOMER_CONSENT_MISSING = "CUSTOMER_CONSENT_MISSING"
    UNAPPLICABLE_STATUS = "UNAPPLICABLE_STATUS"
    LOW_URGENCY_RANK = "LOW_URGENCY_RANK"
    DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"


class CandidateEvaluation(VeraBaseModel):
    """Evaluation record for a candidate trigger considered during arbitration."""

    trigger_id: str = Field(..., min_length=1, description="Trigger ID considered")
    kind: str = Field(..., min_length=1, description="Trigger kind")
    urgency: int = Field(..., ge=1, le=5, description="Trigger base urgency")
    is_valid: bool = Field(..., description="Passed schema and reference integrity")
    is_relevant: bool = Field(..., description="Matches current merchant/category/customer state")
    is_suppressed: bool = Field(..., description="Suppressed by active deduplication key")
    is_expired: bool = Field(..., description="Trigger past expiration ISO timestamp")
    rank_score: float = Field(default=0.0, description="Computed multi-factor relevance and priority score")
    rejection_reason: Optional[RejectionReason] = Field(default=None, description="Disqualification category if dropped")
    rejection_details: Optional[str] = Field(default=None, description="Concise explanation if rejected")


class TriggerDecision(VeraBaseModel):
    """Deterministic, machine-readable trigger arbitration decision."""

    selected_trigger: Optional[TriggerContext] = Field(default=None, description="The chosen trigger, or None if skip")
    reason_code: ReasonCode = Field(..., description="Overall decision outcome reason code")
    objective: str = Field(..., min_length=1, description="Concise operational objective for this decision")
    priority: int = Field(default=0, ge=0, le=5, description="Arbitrated priority level (0 if skip)")
    supporting_context: Dict[str, Any] = Field(default_factory=dict, description="Key fact anchors justifying selection")
    suppressed_triggers: List[str] = Field(default_factory=list, description="IDs of triggers active but suppressed")
    candidate_evaluations: List[CandidateEvaluation] = Field(default_factory=list, description="Audit of all candidate evaluations")
    decision_type: str = Field(..., description="'send' if a trigger was selected, otherwise 'skip'")
