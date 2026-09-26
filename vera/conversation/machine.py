"""Core conversation state machine engine implementing deterministic transitions."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from vera.conversation.states import (
    ACTIVE_STATES,
    STATE_DESCRIPTIONS,
    TERMINAL_STATES,
    State,
    is_terminal_state,
)
from vera.conversation.transitions import (
    InvalidTransitionError,
    TransitionInput,
    TransitionResult,
)
from vera.models.intent import IntentType

if TYPE_CHECKING:
    from vera.models.conversation import ConversationState


class ConversationStateMachine:
    """Deterministic finite state machine for Vera multi-turn conversations."""

    def __init__(self, strict: bool = False):
        """
        Args:
            strict: If True, raises InvalidTransitionError on invalid transition attempts.
                    If False, returns TransitionResult(valid=False, action='end') to preserve stability.
        """
        self.strict = strict

    def evaluate_transition(self, inp: TransitionInput) -> TransitionResult:
        """
        Calculates the next state based on:
        CURRENT STATE + USER INTENT + CURRENT CONTEXT -> NEXT STATE
        """
        current_state = inp.current_state
        intent = inp.user_intent
        context = inp.context_data or {}
        context_updates: Dict[str, Any] = {}

        # ---------------------------------------------------------------------
        # 1. Terminal State Check: Transitions from terminal states are invalid
        # ---------------------------------------------------------------------
        if is_terminal_state(current_state):
            err_msg = f"Cannot transition from terminal state {current_state.value}"
            if self.strict:
                raise InvalidTransitionError(
                    from_state=current_state,
                    to_state=current_state,
                    intent=intent,
                    reason=err_msg,
                )
            return TransitionResult(
                valid=False,
                from_state=current_state,
                to_state=current_state,
                action="end",
                rationale=f"Conversation in terminal state {current_state.value}; rejecting further input turns",
                error=err_msg,
            )

        # ---------------------------------------------------------------------
        # 2. Context Updates Tracking
        # ---------------------------------------------------------------------
        # Check for context updates (e.g. context version bump, subscription changes)
        merchant_ctx = context.get("merchant", {})
        if isinstance(merchant_ctx, dict):
            sub_info = merchant_ctx.get("subscription", {})
            if isinstance(sub_info, dict) and sub_info.get("status") == "lapsed":
                context_updates["subscription_status"] = "lapsed"

        current_version = context.get("version")
        if current_version is not None:
            context_updates["observed_context_version"] = current_version

        # ---------------------------------------------------------------------
        # 3. Repeated Messages Loop Breaker (Spam Prevention)
        # ---------------------------------------------------------------------
        if inp.consecutive_repeated_messages >= 3:
            return TransitionResult(
                valid=True,
                from_state=current_state,
                to_state=State.STOPPED,
                action="end",
                rationale=(
                    f"Consecutive identical message threshold reached ({inp.consecutive_repeated_messages} times); "
                    "halting to avoid infinite repetition loop"
                ),
                context_updates_applied=context_updates,
            )

        # ---------------------------------------------------------------------
        # 4. Proactive Dispatch Handling (Outbound Send)
        # ---------------------------------------------------------------------
        if inp.is_proactive_send:
            if current_state == State.INITIAL:
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.PITCHED,
                    action="send",
                    rationale="Outbound hook/pitch sent to recipient; awaiting response",
                    context_updates_applied=context_updates,
                )
            elif current_state in {State.WAITING, State.INTERESTED, State.QUESTION}:
                # Subsequent proactive touch or follow-up
                return TransitionResult(
                    valid=True,
                    from_state=current_state,
                    to_state=State.PITCHED,
                    action="send",
                    rationale=f"Follow-up proactive message dispatched from {current_state.value}",
                    context_updates_applied=context_updates,
                )
            else:
                err_msg = f"Cannot proactively dispatch message from state {current_state.value}"
                if self.strict:
                    raise InvalidTransitionError(
                        from_state=current_state,
                        to_state=State.PITCHED,
                        reason=err_msg,
                    )
                return TransitionResult(
                    valid=False,
                    from_state=current_state,
                    to_state=current_state,
                    action="end",
                    rationale=err_msg,
                    error=err_msg,
                )

        # ---------------------------------------------------------------------
        # 5. Rejection Handling -> REJECTED
        # ---------------------------------------------------------------------
        if intent == IntentType.REJECTION:
            return TransitionResult(
                valid=True,
                from_state=current_state,
                to_state=State.REJECTED,
                action="end",
                rationale="User declined proposal; gracefully concluding dialogue",
                context_updates_applied=context_updates,
            )

        # ---------------------------------------------------------------------
        # 6. Severe Opt-Out & Hostility Handling -> STOPPED
        # ---------------------------------------------------------------------
        if intent == IntentType.HOSTILE_OPT_OUT:
            return TransitionResult(
                valid=True,
                from_state=current_state,
                to_state=State.STOPPED,
                action="end",
                rationale="User expressed hostility or explicit opt-out; immediately halting conversation thread",
                context_updates_applied=context_updates,
            )

        # ---------------------------------------------------------------------
        # 6. Generic Auto-Replies (WhatsApp Business Canned Greetings)
        # ---------------------------------------------------------------------
        if intent == IntentType.AUTO_REPLY:
            # Turn 1 auto-reply: Pause and back off
            if inp.auto_reply_count <= 0:
                return TransitionResult(
                    valid=True,
                    from_state=current_state,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=900,  # 15 minutes back-off
                    rationale="Automated business greeting detected on turn 1; backing off 15m for human respondent",
                    context_updates_applied=context_updates,
                )
            else:
                # Turn 2+ repeating auto-reply: Stop to avoid turn wastage
                return TransitionResult(
                    valid=True,
                    from_state=current_state,
                    to_state=State.STOPPED,
                    action="end",
                    rationale=(
                        f"Detected repeating automated response ({inp.auto_reply_count + 1} times); "
                        "terminating dialogue to prevent auto-reply turn wastage"
                    ),
                    context_updates_applied=context_updates,
                )

        # ---------------------------------------------------------------------
        # 7. State-Specific Reactive Handling
        # ---------------------------------------------------------------------

        # --- A. From INITIAL ---
        if current_state == State.INITIAL:
            if intent == IntentType.COMMITMENT:
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.ACTION_PENDING,
                    action="send",
                    rationale="User initiated conversation with immediate commitment; entering action pending",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INQUIRY:
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="User initiated conversation with an inquiry; entering question state",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INTEREST:
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.INTERESTED,
                    action="send",
                    rationale="User initiated conversation with general interest; entering interested state",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                # User asking for time or friction objection
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=1800,
                    rationale="User indicated friction or asked to connect later; entering waiting state",
                    context_updates_applied=context_updates,
                )
            else:
                return TransitionResult(
                    valid=True,
                    from_state=State.INITIAL,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="Direct inbound message on initial state routed to question/clarification",
                    context_updates_applied=context_updates,
                )

        # --- B. From PITCHED ---
        if current_state == State.PITCHED:
            if intent == IntentType.COMMITMENT:
                # Context check: If merchant subscription is lapsed, highlight context update
                sub_status = context_updates.get("subscription_status")
                if sub_status == "lapsed":
                    return TransitionResult(
                        valid=True,
                        from_state=State.PITCHED,
                        to_state=State.QUESTION,
                        action="send",
                        rationale=(
                            "Commitment received but merchant subscription is lapsed in current context; "
                            "prompting renewal qualification before execution"
                        ),
                        context_updates_applied=context_updates,
                    )
                return TransitionResult(
                    valid=True,
                    from_state=State.PITCHED,
                    to_state=State.ACTION_PENDING,
                    action="send",
                    rationale="User accepted / committed to pitch; transitioning directly to action execution",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                # User hesitates or says busy / call later
                return TransitionResult(
                    valid=True,
                    from_state=State.PITCHED,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=1800,
                    rationale="User requested delayed follow-up or raised timing friction; entering waiting state",
                    context_updates_applied=context_updates,
                )
            elif intent in {IntentType.INQUIRY, IntentType.OFF_TOPIC}:
                return TransitionResult(
                    valid=True,
                    from_state=State.PITCHED,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="User asked question or sought clarification on pitch; answering with context facts",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INTEREST:
                return TransitionResult(
                    valid=True,
                    from_state=State.PITCHED,
                    to_state=State.INTERESTED,
                    action="send",
                    rationale="User expressed warm curiosity about pitch; providing detailed context",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.UNKNOWN:
                # Ambiguous reply; stay in PITCHED or ask short binary clarification
                return TransitionResult(
                    valid=True,
                    from_state=State.PITCHED,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="Unrecognized inbound turn; requesting concise clarification without repeating pitch",
                    context_updates_applied=context_updates,
                )

        # --- C. From INTERESTED ---
        if current_state == State.INTERESTED:
            if intent == IntentType.COMMITMENT:
                return TransitionResult(
                    valid=True,
                    from_state=State.INTERESTED,
                    to_state=State.ACTION_PENDING,
                    action="send",
                    rationale="User converted from interest to commitment; transitioning to action pending",
                    context_updates_applied=context_updates,
                )
            elif intent in {IntentType.INQUIRY, IntentType.OFF_TOPIC}:
                return TransitionResult(
                    valid=True,
                    from_state=State.INTERESTED,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="Interested user asked specific question; answering grounded in context",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INTEREST:
                return TransitionResult(
                    valid=True,
                    from_state=State.INTERESTED,
                    to_state=State.INTERESTED,
                    action="send",
                    rationale="User continues expressing interest; offering concrete next step",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                return TransitionResult(
                    valid=True,
                    from_state=State.INTERESTED,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=1800,
                    rationale="User asked for time after showing interest; pausing dialogue",
                    context_updates_applied=context_updates,
                )

        # --- D. From QUESTION ---
        if current_state == State.QUESTION:
            if intent == IntentType.COMMITMENT:
                return TransitionResult(
                    valid=True,
                    from_state=State.QUESTION,
                    to_state=State.ACTION_PENDING,
                    action="send",
                    rationale="Question resolved and user committed; proceeding to action execution",
                    context_updates_applied=context_updates,
                )
            elif intent in {IntentType.INQUIRY, IntentType.OFF_TOPIC, IntentType.UNKNOWN}:
                return TransitionResult(
                    valid=True,
                    from_state=State.QUESTION,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="User asked follow-up question or clarification; answering factually",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INTEREST:
                return TransitionResult(
                    valid=True,
                    from_state=State.QUESTION,
                    to_state=State.INTERESTED,
                    action="send",
                    rationale="User satisfied with answer and expressed interest; presenting offer",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                return TransitionResult(
                    valid=True,
                    from_state=State.QUESTION,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=1800,
                    rationale="User noted time constraint after inquiry; entering waiting state",
                    context_updates_applied=context_updates,
                )

        # --- E. From WAITING ---
        if current_state == State.WAITING:
            if intent == IntentType.COMMITMENT:
                return TransitionResult(
                    valid=True,
                    from_state=State.WAITING,
                    to_state=State.ACTION_PENDING,
                    action="send",
                    rationale="User resumed dialogue from wait state with commitment; moving to action pending",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.INTEREST:
                return TransitionResult(
                    valid=True,
                    from_state=State.WAITING,
                    to_state=State.INTERESTED,
                    action="send",
                    rationale="User resumed dialogue from wait state with interest",
                    context_updates_applied=context_updates,
                )
            elif intent in {IntentType.INQUIRY, IntentType.OFF_TOPIC, IntentType.UNKNOWN}:
                return TransitionResult(
                    valid=True,
                    from_state=State.WAITING,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="User resumed dialogue with a question",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                return TransitionResult(
                    valid=True,
                    from_state=State.WAITING,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=3600,
                    rationale="User still busy / requesting more time; extending wait window",
                    context_updates_applied=context_updates,
                )

        # --- F. From ACTION_PENDING ---
        if current_state == State.ACTION_PENDING:
            if intent == IntentType.COMMITMENT:
                # Second confirmation or acknowledgment of completion -> COMPLETED
                return TransitionResult(
                    valid=True,
                    from_state=State.ACTION_PENDING,
                    to_state=State.COMPLETED,
                    action="send",
                    rationale="Pending action confirmed and fulfilled; conversation successfully completed",
                    context_updates_applied=context_updates,
                )
            elif intent in {IntentType.INQUIRY, IntentType.UNKNOWN}:
                return TransitionResult(
                    valid=True,
                    from_state=State.ACTION_PENDING,
                    to_state=State.QUESTION,
                    action="send",
                    rationale="User asked clarification regarding pending action execution",
                    context_updates_applied=context_updates,
                )
            elif intent == IntentType.QUALIFICATION:
                return TransitionResult(
                    valid=True,
                    from_state=State.ACTION_PENDING,
                    to_state=State.WAITING,
                    action="wait",
                    wait_seconds=1800,
                    rationale="User asked to pause pending action execution",
                    context_updates_applied=context_updates,
                )

        # ---------------------------------------------------------------------
        # 8. Unhandled or Illegal Transition Fallback
        # ---------------------------------------------------------------------
        err_msg = (
            f"No valid transition defined from state {current_state.value} "
            f"for intent {intent.value}."
        )
        if self.strict:
            raise InvalidTransitionError(
                from_state=current_state,
                intent=intent,
                reason=err_msg,
            )

        # Fallback for unexpected cases preserves current state safely
        return TransitionResult(
            valid=False,
            from_state=current_state,
            to_state=current_state,
            action="send",
            rationale=f"Unhandled transition from {current_state.value}; maintaining state safely",
            error=err_msg,
            context_updates_applied=context_updates,
        )

    def complete_action(
        self, state: ConversationState, rationale: str = "Action successfully executed"
    ) -> TransitionResult:
        """
        Explicitly completes an action from ACTION_PENDING, transitioning to COMPLETED.
        """
        current_state = getattr(state, "current_state", State.ACTION_PENDING)
        if current_state != State.ACTION_PENDING:
            err_msg = f"Cannot complete action from state {current_state.value}; must be in ACTION_PENDING"
            if self.strict:
                raise InvalidTransitionError(
                    from_state=current_state,
                    to_state=State.COMPLETED,
                    reason=err_msg,
                )
            return TransitionResult(
                valid=False,
                from_state=current_state,
                to_state=current_state,
                action="end",
                rationale=err_msg,
                error=err_msg,
            )

        return TransitionResult(
            valid=True,
            from_state=State.ACTION_PENDING,
            to_state=State.COMPLETED,
            action="send",
            rationale=rationale,
        )

    def reject(
        self, state: ConversationState, rationale: str = "User declined proposal"
    ) -> TransitionResult:
        """
        Transitions active conversation to REJECTED terminal state.
        """
        current_state = getattr(state, "current_state", State.INITIAL)
        if is_terminal_state(current_state):
            err_msg = f"Cannot reject already terminal conversation in state {current_state.value}"
            if self.strict:
                raise InvalidTransitionError(
                    from_state=current_state,
                    to_state=State.REJECTED,
                    reason=err_msg,
                )
            return TransitionResult(
                valid=False,
                from_state=current_state,
                to_state=current_state,
                action="end",
                rationale=err_msg,
                error=err_msg,
            )

        return TransitionResult(
            valid=True,
            from_state=current_state,
            to_state=State.REJECTED,
            action="end",
            rationale=rationale,
        )

    def stop(
        self, state: ConversationState, rationale: str = "Conversation manually or automatically stopped"
    ) -> TransitionResult:
        """
        Transitions conversation to STOPPED terminal state.
        """
        current_state = getattr(state, "current_state", State.INITIAL)
        if is_terminal_state(current_state):
            err_msg = f"Cannot stop already terminal conversation in state {current_state.value}"
            if self.strict:
                raise InvalidTransitionError(
                    from_state=current_state,
                    to_state=State.STOPPED,
                    reason=err_msg,
                )
            return TransitionResult(
                valid=False,
                from_state=current_state,
                to_state=current_state,
                action="end",
                rationale=err_msg,
                error=err_msg,
            )

        return TransitionResult(
            valid=True,
            from_state=current_state,
            to_state=State.STOPPED,
            action="end",
            rationale=rationale,
        )
