"""Explicit conversation states and properties for Vera dialogue management."""

from __future__ import annotations
from enum import Enum
from typing import Dict, Set


class State(str, Enum):
    """Explicit conversation states adhering to Vera challenge requirements."""

    INITIAL = "INITIAL"
    PITCHED = "PITCHED"
    WAITING = "WAITING"
    INTERESTED = "INTERESTED"
    QUESTION = "QUESTION"
    ACTION_PENDING = "ACTION_PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    STOPPED = "STOPPED"


# Set of terminal states where conversation lifecycle concludes
TERMINAL_STATES: Set[State] = {
    State.COMPLETED,
    State.REJECTED,
    State.STOPPED,
}

# Set of active states that accept ongoing interaction
ACTIVE_STATES: Set[State] = {
    State.INITIAL,
    State.PITCHED,
    State.WAITING,
    State.INTERESTED,
    State.QUESTION,
    State.ACTION_PENDING,
}

# Human-readable state definitions
STATE_DESCRIPTIONS: Dict[State, str] = {
    State.INITIAL: "Conversation session created; no proactive outreach sent yet.",
    State.PITCHED: "Proactive outreach / hook message dispatched; awaiting user reaction.",
    State.WAITING: "Conversation temporarily paused or backed off (e.g., auto-reply or user asked for time).",
    State.INTERESTED: "User responded with curiosity or general positive interest.",
    State.QUESTION: "User inquired about details, pricing, process, or requested clarification.",
    State.ACTION_PENDING: "User agreed/committed; action scheduled, pending execution or confirmation.",
    State.COMPLETED: "Goal or action successfully fulfilled and acknowledged. Terminal state.",
    State.REJECTED: "User explicitly or softly declined the proposal. Terminal state.",
    State.STOPPED: "Conversation halted due to opt-out, hostility, or repeated auto-replies. Terminal state.",
}


def is_terminal_state(state: State | str) -> bool:
    """Returns True if the state is terminal (completed, rejected, or stopped)."""
    if isinstance(state, str):
        try:
            state = State(state.upper())
        except ValueError:
            return False
    return state in TERMINAL_STATES


def is_active_state(state: State | str) -> bool:
    """Returns True if the state is active and accepting turns."""
    if isinstance(state, str):
        try:
            state = State(state.upper())
        except ValueError:
            return False
    return state in ACTIVE_STATES
