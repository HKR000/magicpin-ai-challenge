"""Transition definitions, input/result models, and exceptions for Vera state machine."""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from pydantic import Field

from vera.conversation.states import State, is_terminal_state
from vera.models.base import VeraBaseModel
from vera.models.intent import IntentType


class InvalidTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(
        self,
        from_state: State,
        to_state: Optional[State] = None,
        intent: Optional[IntentType | str] = None,
        reason: str = "Invalid transition attempted",
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.intent = intent
        self.reason = reason
        msg = f"Cannot transition from {from_state.value}"
        if to_state:
            msg += f" to {to_state.value}"
        if intent:
            msg += f" with intent '{intent}'"
        msg += f": {reason}"
        super().__init__(msg)


class TransitionInput(VeraBaseModel):
    """Input payload to evaluate a state transition."""

    current_state: State = Field(..., description="Current conversation state")
    user_intent: IntentType = Field(..., description="Classified intent of the inbound turn")
    raw_message: str = Field(default="", description="Inbound text content")
    turn_number: int = Field(default=1, ge=1, description="Sequence turn counter")
    auto_reply_count: int = Field(default=0, ge=0, description="Consecutive auto replies detected")
    consecutive_repeated_messages: int = Field(
        default=0, ge=0, description="Consecutive identical user messages detected"
    )
    context_data: Dict[str, Any] = Field(
        default_factory=dict, description="Current context facts (category, merchant, customer, trigger)"
    )
    is_proactive_send: bool = Field(
        default=False, description="True if transition is triggered by an outbound proactive dispatch"
    )


class TransitionResult(VeraBaseModel):
    """Output result of applying transition logic."""

    valid: bool = Field(..., description="Whether the transition was legally valid")
    from_state: State = Field(..., description="Origin state before transition")
    to_state: State = Field(..., description="Target state after transition")
    action: str = Field(..., description="Action to take: 'send', 'wait', or 'end'")
    wait_seconds: Optional[int] = Field(
        default=None, description="Recommended back-off seconds if action is 'wait'"
    )
    rationale: str = Field(..., min_length=1, description="Deterministic explanation of why this transition occurred")
    context_updates_applied: Dict[str, Any] = Field(
        default_factory=dict, description="Context modifications or version updates reflected in state"
    )
    error: Optional[str] = Field(
        default=None, description="Error explanation if valid is False"
    )
    user_intent: Optional[IntentType] = Field(
        default=None, description="Inbound intent that triggered transition"
    )


class TransitionRule:
    """Represents a discrete, testable transition rule."""

    def __init__(
        self,
        from_state: State,
        target_state: State,
        action: str,
        intent: Optional[IntentType] = None,
        condition: Optional[Callable[[TransitionInput], bool]] = None,
        rationale: str = "",
        wait_seconds: Optional[int] = None,
    ):
        self.from_state = from_state
        self.target_state = target_state
        self.action = action
        self.intent = intent
        self.condition = condition
        self.rationale = rationale
        self.wait_seconds = wait_seconds

    def matches(self, inp: TransitionInput) -> bool:
        if self.from_state != inp.current_state:
            return False
        if self.intent is not None and self.intent != inp.user_intent:
            return False
        if self.condition is not None:
            return bool(self.condition(inp))
        return True
