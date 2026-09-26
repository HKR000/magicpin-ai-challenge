"""Decision tracking models for proactive and reactive arbitration."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import Field
from vera.models.base import VeraBaseModel
from vera.models.intent import IntentType


class DecisionType(str, Enum):
    """Categorization of engine decision."""

    PROACTIVE_SEND = "proactive_send"
    PROACTIVE_SKIP = "proactive_skip"
    REPLY_SEND = "reply_send"
    REPLY_WAIT = "reply_wait"
    REPLY_END = "reply_end"


class SuppressionResult(VeraBaseModel):
    """Result of evaluating a trigger's suppression key."""

    suppression_key: str = Field(..., min_length=1, description="Deduplication key evaluated")
    is_suppressed: bool = Field(..., description="Whether send should be suppressed")
    reason: Optional[str] = Field(default=None, description="Explanation if suppressed")


class ProactiveDecision(VeraBaseModel):
    """Reasoning record for deciding whether to send an outbound proactive message."""

    decision_type: DecisionType = Field(..., description="Send or Skip")
    trigger_id: Optional[str] = Field(default=None, description="Trigger ID selected")
    merchant_id: str = Field(..., min_length=1, description="Merchant target")
    customer_id: Optional[str] = Field(default=None, description="Customer target if applicable")
    selected_signal: str = Field(..., min_length=1, description="Core signal driving this decision")
    selected_offer_id: Optional[str] = Field(default=None, description="Catalog offer bound to this message")
    rationale: str = Field(..., min_length=1, description="Full explanation of why this action was decided")
    suppression: SuppressionResult = Field(..., description="Suppression check audit")


class ReactiveDecision(VeraBaseModel):
    """Reasoning record for deciding how to respond to an inbound message."""

    decision_type: DecisionType = Field(..., description="Send, Wait, or End")
    conversation_id: str = Field(..., min_length=1, description="Thread identifier")
    intent_detected: IntentType = Field(..., description="Inbound intent that governed this decision")
    rationale: str = Field(..., min_length=1, description="Strategic reason for this reactive action")
    wait_seconds: Optional[int] = Field(default=None, ge=1, description="Back-off seconds if decision_type is REPLY_WAIT")
