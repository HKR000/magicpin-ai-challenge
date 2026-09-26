"""Context versioning and push envelope models."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel


class ContextScope(str, Enum):
    """Scope partition for context entities."""

    CATEGORY = "category"
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    TRIGGER = "trigger"


class ContextEnvelope(VeraBaseModel):
    """Payload pushed to POST /v1/context."""

    scope: ContextScope = Field(..., description="Entity scope: category, merchant, customer, trigger")
    context_id: str = Field(..., min_length=1, description="Entity identifier (slug, merchant_id, customer_id, trigger_id)")
    version: int = Field(..., ge=1, description="Monotonically increasing version counter")
    payload: Dict[str, Any] = Field(..., description="Raw entity payload dictionary")
    delivered_at: str = Field(..., min_length=1, description="ISO-8601 timestamp when pushed by judge")


class ContextAck(VeraBaseModel):
    """Response returned from POST /v1/context."""

    accepted: bool = Field(..., description="Whether version was accepted and stored")
    ack_id: Optional[str] = Field(default=None, description="Acknowledgment token (e.g., ack_dentists_v1)")
    stored_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp when written to store")
    reason: Optional[str] = Field(default=None, description="Rejection reason if accepted == False (e.g., stale_version)")
    current_version: Optional[int] = Field(default=None, description="Currently stored version when 409 conflict occurs")


class ContextVersionRecord(VeraBaseModel):
    """Internal storage record for versioned context."""

    scope: ContextScope = Field(..., description="Partition scope")
    context_id: str = Field(..., min_length=1, description="Entity identifier")
    version: int = Field(..., ge=1, description="Stored version")
    stored_at: str = Field(..., min_length=1, description="Storage timestamp")
    payload: Dict[str, Any] = Field(..., description="Stored entity payload")
