"""Message composition and action payload models."""

from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import Field, field_validator
from vera.models.base import VeraBaseModel


class SendAsIdentity(str, Enum):
    """Outbound sender identity."""

    VERA = "vera"
    MERCHANT_ON_BEHALF = "merchant_on_behalf"


class CtaType(str, Enum):
    """Shape and cognitive commitment level of the Call to Action."""

    BINARY = "binary"
    CHOICE = "choice"
    OPEN_ENDED = "open_ended"
    NONE = "none"


class ActionType(str, Enum):
    """Decision action returned from reactive /v1/reply."""

    SEND = "send"
    WAIT = "wait"
    END = "end"


class ComposedMessage(VeraBaseModel):
    """Internal representation of a drafted WhatsApp communication."""

    body: str = Field(..., min_length=1, description="Message text")
    cta: CtaType = Field(default=CtaType.BINARY, description="Primary CTA structure")
    send_as: SendAsIdentity = Field(default=SendAsIdentity.VERA, description="Sender identity")
    suppression_key: str = Field(..., min_length=1, description="Deduplication key")
    rationale: str = Field(..., min_length=1, description="Reasoning and expected business outcome")
    template_name: Optional[str] = Field(default=None, description="Meta pre-approved template identifier")
    template_params: Optional[List[str]] = Field(default=None, description="Template parameter substitutions")
    grounded_facts: List[str] = Field(default_factory=list, description="Keys of facts from selected_facts that ground claims")
    is_validated: bool = Field(default=True, description="Whether message passed validation audit")
    validation_notes: List[str] = Field(default_factory=list, description="Validation audit details")



class ProactiveAction(VeraBaseModel):
    """Single outbound action payload emitted in POST /v1/tick."""

    conversation_id: str = Field(..., min_length=1, description="Unique conversation thread identifier")
    merchant_id: str = Field(..., min_length=1, description="Target merchant ID")
    customer_id: Optional[str] = Field(default=None, description="Target customer ID if customer-facing")
    send_as: SendAsIdentity = Field(..., description="Sender attribution: vera or merchant_on_behalf")
    trigger_id: str = Field(..., min_length=1, description="Initiating trigger context ID")
    template_name: str = Field(..., min_length=1, description="Meta WhatsApp template name")
    template_params: List[str] = Field(default_factory=list, description="Positional parameter array")
    body: str = Field(..., min_length=1, description="Rendered outbound message body")
    cta: str = Field(..., min_length=1, description="CTA description or classification")
    suppression_key: str = Field(..., min_length=1, description="Suppression deduplication key")
    rationale: str = Field(..., min_length=1, description="Judge-visible reasoning for this send")


class TickResponse(VeraBaseModel):
    """Response envelope for POST /v1/tick."""

    actions: List[ProactiveAction] = Field(default_factory=list, max_length=20, description="List of proactive actions (max 20)")


class ReplyAction(VeraBaseModel):
    """Decision response emitted for POST /v1/reply."""

    action: ActionType = Field(..., description="Action decision: send, wait, or end")
    body: Optional[str] = Field(default=None, description="Outbound message text (required if action == send)")
    cta: Optional[str] = Field(default=None, description="CTA classification if action == send")
    wait_seconds: Optional[int] = Field(default=None, ge=1, description="Seconds to back off if action == wait")
    rationale: str = Field(..., min_length=1, description="Reasoning for this reactive decision")

    @field_validator("body")
    @classmethod
    def validate_send_body(cls, v: Optional[str], info) -> Optional[str]:
        action = info.data.get("action")
        if action == ActionType.SEND and (not v or not v.strip()):
            raise ValueError("body cannot be empty when action is 'send'")
        return v

    @field_validator("wait_seconds")
    @classmethod
    def validate_wait_seconds(cls, v: Optional[int], info) -> Optional[int]:
        action = info.data.get("action")
        if action == ActionType.WAIT and (v is None or v <= 0):
            raise ValueError("wait_seconds must be a positive integer when action is 'wait'")
        return v
