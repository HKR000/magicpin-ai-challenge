"""Vera conversation state machine and dialogue lifecycle management."""

from vera.conversation.states import (
    ACTIVE_STATES,
    STATE_DESCRIPTIONS,
    TERMINAL_STATES,
    State,
    is_active_state,
    is_terminal_state,
)
from vera.conversation.transitions import (
    InvalidTransitionError,
    TransitionInput,
    TransitionResult,
    TransitionRule,
)
from vera.conversation.machine import ConversationStateMachine
from vera.conversation.persistence import ConversationStore

__all__ = [
    "State",
    "TERMINAL_STATES",
    "ACTIVE_STATES",
    "STATE_DESCRIPTIONS",
    "is_terminal_state",
    "is_active_state",
    "InvalidTransitionError",
    "TransitionInput",
    "TransitionResult",
    "TransitionRule",
    "ConversationStateMachine",
    "ConversationStore",
]
