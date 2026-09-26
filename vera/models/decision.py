"""Decision tracking models for proactive and reactive arbitration (Level 8)."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel
from vera.models.conversation import State
from vera.models.intent import IntentType
from vera.models.selection import SelectionBundle


class DecisionType(str, Enum):
    """Categorization of engine decision."""

    PROACTIVE_SEND = "proactive_send"
    PROACTIVE_SKIP = "proactive_skip"
    REPLY_SEND = "reply_send"
    REPLY_WAIT = "reply_wait"
    REPLY_END = "reply_end"


class CommunicationObjective(str, Enum):
    """Strategic purpose of communication (WHY are we communicating)."""

    PITCH_RESEARCH_CAMPAIGN = "pitch_research_campaign"
    RECOVER_PERFORMANCE_DIP = "recover_performance_dip"
    RE_ENGAGE_LAPSED_CUSTOMER = "re_engage_lapsed_customer"
    RENEW_PLATFORM_SUBSCRIPTION = "renew_platform_subscription"
    VERIFY_GOOGLE_BUSINESS_PROFILE = "verify_google_business_profile"
    PROMOTE_SEASONAL_OFFER = "promote_seasonal_offer"
    ANSWER_MERCHANT_INQUIRY = "answer_merchant_inquiry"
    EXECUTE_COMMITTED_ACTION = "execute_committed_action"
    CONFIRM_OPT_OUT = "confirm_opt_out"
    SUPPRESS_AUTO_REPLY_LOOP = "suppress_auto_reply_loop"
    HANDLE_REJECTION = "handle_rejection"
    CLARIFY_QUESTION = "clarify_question"
    AWAIT_USER_RESPONSE = "await_user_response"
    CONCLUDE_COMPLETED = "conclude_completed"
    OFF_TOPIC_DEFLECT = "off_topic_deflect"


class ProposedActionType(str, Enum):
    """Categorization of proposed call-to-action (WHAT action should Vera propose)."""

    PITCH_OFFER = "pitch_offer"
    SUGGEST_TIME_SLOTS = "suggest_time_slots"
    QUOTE_PRICING = "quote_pricing"
    EXECUTE_CAMPAIGN = "execute_campaign"
    REQUEST_CLARIFICATION = "request_clarification"
    VERIFY_PROFILE_LINK = "verify_profile_link"
    RENEW_SUBSCRIPTION = "renew_subscription"
    CONFIRM_TERMINATION = "confirm_termination"
    BACK_OFF_AND_WAIT = "back_off_and_wait"
    NO_OP = "no_op"


class ProposedAction(VeraBaseModel):
    """Concrete, structured proposal without natural language copywriting."""

    action_type: ProposedActionType = Field(..., description="Action family")
    target_id: Optional[str] = Field(default=None, description="Offer ID, slot, or resource identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action parameters (price, slots, metrics)")
    cta_prompt: Optional[str] = Field(default=None, description="Strategic direction for downstream CTA generation")


class DecisionRecipient(VeraBaseModel):
    """Target persona receiving communication (WHO is being addressed)."""

    recipient_id: str = Field(..., min_length=1, description="Merchant or Customer unique identifier")
    recipient_role: str = Field(..., description="'merchant' or 'customer'")
    name: Optional[str] = Field(default=None, description="Salutation name of target persona")
    preferred_language: str = Field(default="en", description="Preferred language code")
    channel: str = Field(default="whatsapp", description="Delivery channel")


class DecisionTrigger(VeraBaseModel):
    """Audit snapshot of trigger event initiating this decision (WHAT trigger caused this)."""

    trigger_id: str = Field(..., min_length=1, description="Unique trigger ID")
    kind: str = Field(..., min_length=1, description="Trigger event family")
    scope: str = Field(..., description="'merchant' or 'customer'")
    urgency: int = Field(default=2, ge=1, le=5, description="Urgency priority 1-5")
    suppression_key: str = Field(..., min_length=1, description="Deduplication key")


class Decision(VeraBaseModel):
    """
    Structured Level 8 Decision object.
    Defines WHO, WHY, WHAT trigger, WHAT objective, WHAT facts, WHAT proposed action,
    SHOULD respond, and SHOULD stop before any text generation happens.
    """

    actor: str = Field(default="vera", description="Initiator / speaker entity")
    recipient: DecisionRecipient = Field(..., description="WHO is being addressed")
    intent: Optional[str] = Field(default=None, description="Inbound detected intent or proactive initiation")
    trigger: DecisionTrigger = Field(..., description="WHAT trigger caused this")
    objective: CommunicationObjective = Field(..., description="WHAT objective are we pursuing (WHY)")
    selected_facts: SelectionBundle = Field(..., description="WHAT facts matter (from Level 7 Context Selection)")
    proposed_action: ProposedAction = Field(..., description="WHAT action should Vera propose")
    conversation_state: State = Field(..., description="Current conversation state machine stage")
    response_required: bool = Field(..., description="SHOULD Vera respond with a message")
    stop_required: bool = Field(..., description="SHOULD Vera stop communicating")
    rationale: str = Field(..., min_length=1, description="Deterministic decision explanation")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


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

