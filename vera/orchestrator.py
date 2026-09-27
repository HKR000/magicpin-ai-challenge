"""Unified Vera Orchestrator (Level 11) - End-to-end conversational AI engine."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from vera.composer.engine import MessageComposer
from vera.context.engine import ContextEngine, IngestionOutcome
from vera.conversation.transitions import TransitionResult
from vera.decision.engine import DecisionEngine
from vera.intent.classifier import IntentClassifier
from vera.models.context_version import ContextScope
from vera.models.conversation import ConversationState, Role, State
from vera.models.decision import (
    CommunicationObjective,
    Decision,
    DecisionRecipient,
    DecisionTrigger,
    ProposedAction,
    ProposedActionType,
)
from vera.models.intent import DetectedIntent, IntentType
from vera.models.message import ComposedMessage, CtaType, SendAsIdentity
from vera.models.validation import OutputValidationReport
from vera.trigger.engine import TriggerIntelligenceEngine
from vera.validator.engine import OutputValidator


class Vera:
    """
    Unified end-to-end Vera conversational loop integrating:
    Context + Trigger + Intent + State + Decision + Context Selection + Generation + Validation.
    """

    def __init__(
        self,
        context_engine: Optional[ContextEngine] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        decision_engine: Optional[DecisionEngine] = None,
        composer: Optional[MessageComposer] = None,
        validator: Optional[OutputValidator] = None,
        trigger_engine: Optional[TriggerIntelligenceEngine] = None,
    ):
        self.context_engine = context_engine or ContextEngine()
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.decision_engine = decision_engine or DecisionEngine()
        self.composer = composer or MessageComposer()
        self.validator = validator or OutputValidator()
        self.trigger_engine = trigger_engine or TriggerIntelligenceEngine(self.context_engine)

    # =========================================================================
    # 1. CONTEXT INGESTION & UPDATES
    # =========================================================================

    def ingest_context(
        self,
        scope: ContextScope | str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
        delivered_at: Optional[str] = None,
        source: str = "orchestrator_push",
    ) -> IngestionOutcome:
        """Atomic context update with strict versioning and provenance tracking."""
        return self.context_engine.ingest(
            scope=scope,
            context_id=context_id,
            version=version,
            payload=payload,
            delivered_at=delivered_at,
            source=source,
        )

    # =========================================================================
    # 2. PROACTIVE INITIATION LOOP
    # =========================================================================

    def handle_proactive_trigger(
        self,
        trigger_id: str,
        merchant_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Tuple[Optional[ComposedMessage], Optional[Decision], Optional[str]]:
        """
        Executes proactive pipeline:
        Trigger -> Context Assembly -> State Transition -> Decision -> Selection -> Generation -> Validation.

        Returns (composed_message, decision, error_reason).
        """
        trigger = self.context_engine.get_trigger(trigger_id)
        if not trigger:
            return None, None, f"Trigger '{trigger_id}' not found"

        target_mid = merchant_id or trigger.merchant_id
        target_cid = customer_id or trigger.customer_id
        conv_id = conversation_id or f"conv_{target_mid}_{trigger_id}"

        # REM-03: Validate customer consent if trigger is customer-scoped
        trg_scope = trigger.scope.value if hasattr(trigger.scope, "value") else str(trigger.scope)
        if trg_scope == "customer" or target_cid:
            if not target_cid:
                return None, None, f"Customer trigger '{trigger_id}' missing customer_id"
            cust = self.context_engine.get_customer(target_cid)
            if not cust:
                return None, None, f"Customer '{target_cid}' does not exist in store"
            if not self.trigger_engine._check_customer_consent(trigger, cust):
                return None, None, f"Customer consent scope does not permit {trigger.kind} outreach"

        # Initialize or retrieve conversation
        conv = self.context_engine.create_or_get_conversation(
            conversation_id=conv_id,
            merchant_id=target_mid,
            customer_id=target_cid,
            trigger_id=trigger_id,
        )

        # Transition state machine: INITIAL -> PITCHED
        trans = self.context_engine.transition_conversation(
            conversation_id=conv_id,
            user_intent=IntentType.UNKNOWN,
            is_proactive_send=True,
        )

        # Produce Level 8 Decision (embeds Level 7 Context Selection)
        decision, err = self.context_engine.decide(
            merchant_id=target_mid,
            trigger_id=trigger_id,
            customer_id=target_cid,
            conversation_id=conv_id,
        )
        if err or not decision:
            return None, None, err or "Failed to synthesize decision"

        if not decision.response_required:
            return None, decision, None

        # Level 9 & 10: Compose and independently validate
        previous_messages = [t.message for t in conv.turns if t.message]
        report = self.validator.validate_and_repair(
            decision=decision,
            composer=self.composer,
            previous_messages=previous_messages,
            max_retries=2,
        )

        if not report.is_valid or not report.final_body:
            return None, decision, "Output validation rejected generated message and fallback"

        composed = ComposedMessage(
            body=report.final_body,
            cta=self._determine_cta(decision),
            send_as=SendAsIdentity.MERCHANT_ON_BEHALF if decision.recipient.recipient_role == "customer" else SendAsIdentity.VERA,
            suppression_key=decision.trigger.suppression_key,
            rationale=decision.rationale,
            grounded_facts=[f.key for f in decision.selected_facts.high_value_facts],
            is_validated=True,
            validation_notes=[d.observation or "" for d in report.dimensions.values() if d.observation],
        )

        # Record outbound turn into state machine persistence
        self.context_engine.add_turn(
            conversation_id=conv_id,
            from_role=Role.VERA,
            message=composed.body,
            action_taken=decision.proposed_action.action_type.value if hasattr(decision.proposed_action.action_type, "value") else "send",
        )

        return composed, decision, None

    # =========================================================================
    # 3. REACTIVE CONVERSATION LOOP
    # =========================================================================

    def handle_reactive_message(
        self,
        conversation_id: str,
        message: str,
        from_role: str = "merchant",
        received_at: Optional[str] = None,
        override_intent: Optional[IntentType] = None,
    ) -> Tuple[Optional[ComposedMessage], Optional[Decision], Optional[TransitionResult]]:
        """
        Executes reactive pipeline:
        Message -> Intent -> State Machine -> Context Assembly -> Decision -> Selection -> Generation -> Validation.

        Returns (composed_message, decision, transition_result).
        """
        conv = self.context_engine.get_conversation(conversation_id)
        if not conv:
            raise ValueError(f"Conversation '{conversation_id}' not found")

        # 1. Level 4: Intent Classification
        if override_intent is not None:
            detected_intent = override_intent
        else:
            classified = self.intent_classifier.classify(message)
            detected_intent = classified.intent_type

        # 2. Level 6: State Machine Transition (BEFORE incrementing auto-reply count)
        trans = self.context_engine.transition_conversation(
            conversation_id=conversation_id,
            user_intent=detected_intent,
            message=message,
        )

        if detected_intent == IntentType.AUTO_REPLY:
            self.context_engine.increment_auto_reply_count(conversation_id)
        elif detected_intent in {IntentType.INTEREST, IntentType.COMMITMENT, IntentType.INQUIRY}:
            self.context_engine.reset_auto_reply_count(conversation_id)

        # 3. Record inbound turn
        ts = received_at or (datetime.utcnow().isoformat() + "Z")
        self.context_engine.add_turn(
            conversation_id=conversation_id,
            from_role=from_role,
            message=message,
            timestamp=ts,
            detected_intent=detected_intent.value,
            action_taken=trans.action,
        )

        # If transition decided to end or wait silently:
        if trans.action == "wait":
            decision = Decision(
                actor="vera",
                recipient=DecisionRecipient(
                    recipient_id=conv.merchant_id,
                    recipient_role="merchant",
                    name="Partner",
                ),
                trigger=DecisionTrigger(
                    trigger_id=conv.trigger_id or "reactive_trigger",
                    kind="auto_reply_wait",
                    scope="merchant",
                    suppression_key=f"wait:{conversation_id}",
                ),
                objective=CommunicationObjective.AWAIT_USER_RESPONSE,
                selected_facts=self.context_engine.state_machine._get_empty_bundle() if hasattr(self.context_engine.state_machine, "_get_empty_bundle") else self._empty_bundle(),
                proposed_action=ProposedAction(action_type=ProposedActionType.BACK_OFF_AND_WAIT, payload={"wait_seconds": trans.wait_seconds or 1800}),
                conversation_state=conv.current_state,
                response_required=False,
                stop_required=False,
                rationale=trans.rationale,
            )
            return None, decision, trans

        if trans.action == "end":
            if detected_intent == IntentType.REJECTION:
                end_objective = CommunicationObjective.HANDLE_REJECTION
            elif detected_intent == IntentType.HOSTILE_OPT_OUT:
                end_objective = CommunicationObjective.CONFIRM_OPT_OUT
            elif detected_intent == IntentType.AUTO_REPLY:
                end_objective = CommunicationObjective.SUPPRESS_AUTO_REPLY_LOOP
            else:
                end_objective = CommunicationObjective.CONCLUDE_COMPLETED

            needs_close_message = end_objective in {CommunicationObjective.HANDLE_REJECTION, CommunicationObjective.CONFIRM_OPT_OUT}
            decision = Decision(
                actor="vera",
                recipient=DecisionRecipient(
                    recipient_id=conv.merchant_id or "unknown",
                    recipient_role="merchant",
                    name="Partner",
                ),
                trigger=DecisionTrigger(
                    trigger_id=conv.trigger_id or "reactive_trigger",
                    kind="terminal_end",
                    scope="merchant",
                    suppression_key=f"end:{conversation_id}",
                ),
                objective=end_objective,
                selected_facts=self._empty_bundle(),
                proposed_action=ProposedAction(action_type=ProposedActionType.NO_OP),
                conversation_state=conv.current_state,
                response_required=needs_close_message,
                stop_required=True,
                rationale=trans.rationale,
            )

            composed = None
            if needs_close_message:
                composed = self.composer.compose(decision)

            return composed, decision, trans

        # 4. Synthesize Level 8 Decision with Level 7 Context Selection
        target_tid = conv.trigger_id
        if not target_tid:
            triggers = list(self.context_engine._triggers.keys())
            target_tid = triggers[0] if triggers else "trg_fallback"

        decision, err = self.context_engine.decide(
            merchant_id=conv.merchant_id,
            trigger_id=target_tid,
            customer_id=conv.customer_id,
            conversation_id=conversation_id,
            intent=detected_intent,
        )
        if err or not decision:
            fallback_decision = Decision(
                actor="vera",
                recipient=DecisionRecipient(
                    recipient_id=conv.merchant_id or "unknown",
                    recipient_role="merchant",
                    name="Partner",
                ),
                trigger=DecisionTrigger(
                    trigger_id=target_tid or "fallback",
                    kind="fallback_end",
                    scope="merchant",
                    suppression_key=f"fallback:{conversation_id}",
                ),
                objective=CommunicationObjective.CONFIRM_OPT_OUT,
                selected_facts=self._empty_bundle(),
                proposed_action=ProposedAction(action_type=ProposedActionType.NO_OP),
                conversation_state=conv.current_state,
                response_required=False,
                stop_required=True,
                rationale=f"Graceful fallback: {err or 'Context unavailable'}",
            )
            return None, fallback_decision, trans

        # If decision requires no response (silent stop / wait)
        if not decision.response_required:
            return None, decision, trans

        # 5. Level 9 & 10: Compose and Validate message with repetition prevention
        previous_messages = [t.message for t in conv.turns if t.message]
        report = self.validator.validate_and_repair(
            decision=decision,
            composer=self.composer,
            previous_messages=previous_messages,
            max_retries=2,
        )

        if not report.is_valid or not report.final_body:
            fallback = self.validator.generate_safe_fallback(decision)
            final_body = fallback.body
        else:
            final_body = report.final_body

        composed = ComposedMessage(
            body=final_body,
            cta=self._determine_cta(decision),
            send_as=SendAsIdentity.MERCHANT_ON_BEHALF if decision.recipient.recipient_role == "customer" else SendAsIdentity.VERA,
            suppression_key=decision.trigger.suppression_key,
            rationale=decision.rationale,
            grounded_facts=[f.key for f in decision.selected_facts.high_value_facts],
            is_validated=True,
            validation_notes=[d.observation or "" for d in report.dimensions.values() if d.observation],
        )

        # 6. Record Vera response turn
        self.context_engine.add_turn(
            conversation_id=conversation_id,
            from_role=Role.VERA,
            message=composed.body,
            action_taken=trans.action,
        )

        return composed, decision, trans

    def _determine_cta(self, decision: Decision) -> CtaType:
        if decision.objective in {
            CommunicationObjective.CONFIRM_OPT_OUT,
            CommunicationObjective.HANDLE_REJECTION,
            CommunicationObjective.EXECUTE_COMMITTED_ACTION,
            CommunicationObjective.SUPPRESS_AUTO_REPLY_LOOP,
            CommunicationObjective.CONCLUDE_COMPLETED,
        }:
            return CtaType.NONE
        if decision.objective == CommunicationObjective.RECOVER_PERFORMANCE_DIP:
            return CtaType.CHOICE
        return CtaType.BINARY

    def _empty_bundle(self):
        from vera.models.selection import SelectionBundle
        return SelectionBundle(
            mandatory_facts=[],
            high_value_facts=[],
            supporting_facts=[],
            irrelevant_facts=[],
            unavailable_facts=[],
            context_versions_used={},
            total_facts_considered=0,
        )
