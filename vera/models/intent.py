"""Intent classification models for conversation understanding."""

from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel


class IntentType(str, Enum):
    """Classified conversational intent of an inbound merchant/customer message."""

    COMMITMENT = "commitment"
    QUALIFICATION = "qualification"
    AUTO_REPLY = "auto_reply"
    HOSTILE_OPT_OUT = "hostile_opt_out"
    INQUIRY = "inquiry"
    OFF_TOPIC = "off_topic"
    INTEREST = "interest"
    REJECTION = "rejection"
    UNKNOWN = "unknown"


class DetectedIntent(VeraBaseModel):
    """Analysis result from inbound turn intent classification."""

    intent_type: IntentType = Field(..., description="Classified intent family")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    raw_text: str = Field(default="", description="Original inbound message text")
    signals_detected: List[str] = Field(default_factory=list, description="Keywords or structural patterns detected")
    transition_recommended: Optional[str] = Field(default=None, description="Suggested lifecycle transition (e.g., action_committed, end, wait)")
