"""Conversation and multi-turn state models."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field
from vera.conversation.states import State, is_terminal_state
from vera.models.base import VeraBaseModel


class Role(str, Enum):
    """Participant role in conversation."""

    VERA = "vera"
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    SYSTEM = "system"


class ConversationStage(str, Enum):
    """Lifecycle stage of a dialogue (legacy & backward-compatible)."""

    INITIATED = "initiated"
    QUALIFYING = "qualifying"
    ACTION_COMMITTED = "action_committed"
    WAITING = "waiting"
    ENDED = "ended"


class ConversationTurn(VeraBaseModel):
    """Single message turn in an ongoing conversation."""

    turn_number: int = Field(..., ge=1, description="1-indexed sequence counter of turn")
    from_role: Role = Field(..., description="Role of the sender")
    message: str = Field(..., min_length=1, description="Message text")
    timestamp: str = Field(..., description="ISO timestamp when turn was sent/received")
    detected_intent: Optional[str] = Field(default=None, description="Intent classified for this turn")
    action_taken: Optional[str] = Field(default=None, description="Action executed in response")


class ConversationState(VeraBaseModel):
    """In-flight conversation session state."""

    conversation_id: str = Field(..., min_length=1, description="Unique conversation thread identifier")
    merchant_id: str = Field(..., min_length=1, description="Associated merchant ID")
    customer_id: Optional[str] = Field(default=None, description="Associated customer ID if customer-facing")
    trigger_id: Optional[str] = Field(default=None, description="Originating trigger ID that initiated conversation")
    stage: ConversationStage = Field(default=ConversationStage.INITIATED, description="Current legacy stage in lifecycle")
    current_state: State = Field(default=State.INITIAL, description="Explicit Level 6 conversation state")
    turns: List[ConversationTurn] = Field(default_factory=list, description="Ordered history of conversation turns")
    auto_reply_count: int = Field(default=0, ge=0, description="Consecutive auto-replies detected")
    consecutive_repeated_messages: int = Field(
        default=0, ge=0, description="Consecutive identical user messages detected"
    )
    last_user_message: Optional[str] = Field(
        default=None, description="Last inbound user message for repetition detection"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Session metadata, context tracking, and version history"
    )
    last_message_at: str = Field(..., description="ISO timestamp of last activity")
    is_active: bool = Field(default=True, description="Whether conversation is still accepting interactive turns")

    def set_state(self, new_state: State):
        """Sets current state, synchronizes legacy stage, and updates active flag."""
        self.current_state = new_state
        # Synchronize legacy stage
        if new_state == State.INITIAL:
            self.stage = ConversationStage.INITIATED
        elif new_state in {State.PITCHED, State.INTERESTED, State.QUESTION}:
            self.stage = ConversationStage.QUALIFYING
        elif new_state == State.WAITING:
            self.stage = ConversationStage.WAITING
        elif new_state == State.ACTION_PENDING:
            self.stage = ConversationStage.ACTION_COMMITTED
        elif new_state in {State.COMPLETED, State.REJECTED, State.STOPPED}:
            self.stage = ConversationStage.ENDED

        if is_terminal_state(new_state):
            self.is_active = False

    def record_inbound_message(self, message: str):
        """Checks for identical message repetition and updates repetition counters."""
        normalized = message.strip().lower()
        if self.last_user_message is not None and normalized == self.last_user_message:
            self.consecutive_repeated_messages += 1
        else:
            self.consecutive_repeated_messages = 0
            self.last_user_message = normalized
