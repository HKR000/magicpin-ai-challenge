"""Vera Decision Engine (Level 8) - Core deterministic decision layer without generation dependency."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional

from vera.context.selector import ContextSelector
from vera.models.category import CategoryContext
from vera.models.conversation import ConversationState, State
from vera.models.customer import CustomerContext
from vera.models.decision import (
    CommunicationObjective,
    Decision,
    DecisionRecipient,
    DecisionTrigger,
    ProposedAction,
    ProposedActionType,
)
from vera.models.intent import DetectedIntent, IntentType
from vera.models.merchant import MerchantContext
from vera.models.selection import SelectionBundle
from vera.models.trigger import TriggerContext


class DecisionEngine:
    """
    Arbitrates communication decisions deterministically.
    Determines WHO is addressed, WHY communicate, WHAT trigger caused this,
    WHAT objective is pursued, WHAT facts matter, WHAT action to propose,
    and whether to respond or stop.
    """

    def __init__(self, selector: Optional[ContextSelector] = None):
        self.selector = selector or ContextSelector()

    def decide(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: Optional[CustomerContext] = None,
        conversation: Optional[ConversationState] = None,
        intent: Optional[DetectedIntent | IntentType | str] = None,
        context_versions: Optional[Dict[str, int]] = None,
    ) -> Decision:
        """
        Synthesizes context, conversation state, trigger, and intent into a structured Decision.
        Does not perform any natural-language generation.
        """
        # 1. Facts Selection via Level 7 ContextSelector (Zero-hallucination provenance)
        selection: SelectionBundle = self.selector.select(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            conversation=conversation,
            intent=intent,
            context_versions=context_versions,
        )

        # 2. WHO is being addressed? (Recipient)
        is_customer_facing = trigger.scope.value == "customer"
        if is_customer_facing and customer is not None:
            c_name = customer.identity.name if customer.identity else "Customer"
            c_lang = customer.identity.language_pref if customer.identity else "en"
            c_chan = (
                customer.preferences.channel
                if customer.preferences and customer.preferences.channel
                else "whatsapp"
            )
            recipient = DecisionRecipient(
                recipient_id=customer.customer_id,
                recipient_role="customer",
                name=c_name,
                preferred_language=c_lang,
                channel=c_chan,
            )
        else:
            m_name = (
                merchant.identity.owner_first_name or merchant.identity.name
                if merchant.identity
                else "Partner"
            )
            m_lang = (
                merchant.identity.languages[0]
                if merchant.identity and merchant.identity.languages
                else "en"
            )
            recipient = DecisionRecipient(
                recipient_id=merchant.merchant_id,
                recipient_role="merchant",
                name=m_name,
                preferred_language=m_lang,
                channel="whatsapp",
            )

        # 3. WHAT trigger caused this?
        trg_snap = DecisionTrigger(
            trigger_id=trigger.id,
            kind=trigger.kind.value if hasattr(trigger.kind, "value") else str(trigger.kind),
            scope=trigger.scope.value,
            urgency=trigger.urgency,
            suppression_key=trigger.suppression_key,
        )

        # 4. Resolve intent string
        intent_str = ""
        if intent:
            if isinstance(intent, DetectedIntent):
                intent_str = intent.intent_type.value
            elif isinstance(intent, IntentType):
                intent_str = intent.value
            elif isinstance(intent, str):
                intent_str = intent.lower()

        # 5. Conversation state
        conv_state = conversation.current_state if conversation else State.INITIAL

        # 6. Arbitrate Objective, Proposed Action, Response Required, Stop Required
        decision_meta = self._arbitrate_decision(
            trigger=trigger,
            conv_state=conv_state,
            intent_str=intent_str,
            conversation=conversation,
            selection=selection,
            merchant=merchant,
            customer=customer,
        )

        return Decision(
            actor="vera",
            recipient=recipient,
            intent=intent_str or "proactive_initiation",
            trigger=trg_snap,
            objective=decision_meta["objective"],
            selected_facts=selection,
            proposed_action=decision_meta["proposed_action"],
            conversation_state=conv_state,
            response_required=decision_meta["response_required"],
            stop_required=decision_meta["stop_required"],
            rationale=decision_meta["rationale"],
        )

    def _arbitrate_decision(
        self,
        trigger: TriggerContext,
        conv_state: State,
        intent_str: str,
        conversation: Optional[ConversationState],
        selection: SelectionBundle,
        merchant: MerchantContext,
        customer: Optional[CustomerContext],
    ) -> Dict[str, Any]:
        """Core rule table connecting state, intent, and trigger to objective & action."""
        payload = trigger.payload or {}
        top_item_id = payload.get("top_item_id")
        metric = payload.get("metric", "calls")
        delta_pct = payload.get("delta_pct")
        slots = payload.get("available_slots") or ["Saturday 11 AM", "Sunday 4 PM"]
        service_due = payload.get("service_due", "Preventive Dental Cleaning")

        # ---------------------------------------------------------------------
        # REACTION 1: Hostile opt-out / explicit unsubscribe
        # ---------------------------------------------------------------------
        if intent_str == "hostile_opt_out":
            return {
                "objective": CommunicationObjective.CONFIRM_OPT_OUT,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.CONFIRM_TERMINATION,
                    cta_prompt="Acknowledge opt-out politely, confirm suppression, and close",
                ),
                "response_required": True,
                "stop_required": True,
                "rationale": "User expressed hostile opt-out; terminate dialogue and suppress further contact",
            }

        # ---------------------------------------------------------------------
        # REACTION 2: Auto-reply / Out-of-Office handling
        # ---------------------------------------------------------------------
        if intent_str == "auto_reply":
            auto_count = conversation.auto_reply_count if conversation else 0
            if auto_count >= 1:
                # Second consecutive auto-reply: break loop completely
                return {
                    "objective": CommunicationObjective.SUPPRESS_AUTO_REPLY_LOOP,
                    "proposed_action": ProposedAction(action_type=ProposedActionType.NO_OP),
                    "response_required": False,
                    "stop_required": True,
                    "rationale": "Multiple automated replies detected; suppress output to break bot loop",
                }
            else:
                # First auto-reply: back off and wait without generating message
                return {
                    "objective": CommunicationObjective.AWAIT_USER_RESPONSE,
                    "proposed_action": ProposedAction(
                        action_type=ProposedActionType.BACK_OFF_AND_WAIT,
                        payload={"wait_seconds": 1800},
                    ),
                    "response_required": False,
                    "stop_required": False,
                    "rationale": "Single automated reply detected; back off and wait for user return",
                }

        # ---------------------------------------------------------------------
        # REACTION 3: User rejection ("no thanks", "not now", "busy")
        # ---------------------------------------------------------------------
        if intent_str == "rejection":
            return {
                "objective": CommunicationObjective.HANDLE_REJECTION,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.NO_OP,
                    cta_prompt="Gracefully acknowledge polite decline and cease outreach",
                ),
                "response_required": True,
                "stop_required": True,
                "rationale": "User declined proposal; send polite closing and cease outreach",
            }

        # ---------------------------------------------------------------------
        # REACTION 4: Terminal conversation state guard
        # ---------------------------------------------------------------------
        if conv_state in {State.STOPPED, State.COMPLETED} and not intent_str:
            return {
                "objective": CommunicationObjective.CONCLUDE_COMPLETED,
                "proposed_action": ProposedAction(action_type=ProposedActionType.NO_OP),
                "response_required": False,
                "stop_required": True,
                "rationale": f"Conversation is already in terminal state '{conv_state.value}'; no response required",
            }

        # ---------------------------------------------------------------------
        # REACTION 5: Explicit commitment ("yes do it", "go ahead")
        # ---------------------------------------------------------------------
        if intent_str == "commitment":
            return {
                "objective": CommunicationObjective.EXECUTE_COMMITTED_ACTION,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.EXECUTE_CAMPAIGN,
                    target_id=top_item_id or "default_campaign",
                    payload={"status": "confirmed", "mode": "immediate_execution"},
                    cta_prompt="Confirm campaign activation and provide summary of next steps",
                ),
                "response_required": True,
                "stop_required": True,
                "rationale": "User gave explicit go-ahead; execute action and confirm completion",
            }

        # ---------------------------------------------------------------------
        # REACTION 6: Inquiry ("how much does it cost?", "what's the pricing?")
        # ---------------------------------------------------------------------
        if intent_str in {"inquiry", "question"}:
            price_fact = next((f.value for f in selection.high_value_facts if "price" in f.key or "offer" in f.key), None)
            return {
                "objective": CommunicationObjective.ANSWER_MERCHANT_INQUIRY,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.QUOTE_PRICING,
                    payload={"pricing_detail": price_fact or "standard catalog rate"},
                    cta_prompt="Answer pricing inquiry directly with verified context and invite approval",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Inbound inquiry received; answer with specific pricing or operational detail",
            }

        # ---------------------------------------------------------------------
        # REACTION 7: Qualification ("who qualifies?", "what are the conditions?")
        # ---------------------------------------------------------------------
        if intent_str == "qualification":
            return {
                "objective": CommunicationObjective.CLARIFY_QUESTION,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.REQUEST_CLARIFICATION,
                    cta_prompt="Explain patient eligibility criteria and clinical parameters",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Qualification inquiry received; clarify eligibility parameters",
            }

        # ---------------------------------------------------------------------
        # REACTION 8: Off-topic deflection
        # ---------------------------------------------------------------------
        if intent_str == "off_topic":
            return {
                "objective": CommunicationObjective.OFF_TOPIC_DEFLECT,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.NO_OP,
                    cta_prompt="Politely acknowledge and steer conversation back to core proposal",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Off-topic message; gently steer back to original topic",
            }

        # ---------------------------------------------------------------------
        # PROACTIVE TRIGGERS: Map Trigger Kind -> Strategic Objective & Action
        # ---------------------------------------------------------------------
        trg_kind = trigger.kind.value if hasattr(trigger.kind, "value") else str(trigger.kind)

        if trg_kind == "research_digest":
            return {
                "objective": CommunicationObjective.PITCH_RESEARCH_CAMPAIGN,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.PITCH_OFFER,
                    target_id=top_item_id,
                    payload={"digest_id": top_item_id, "service": "fluoride_recall"},
                    cta_prompt="Pitch preventive dental campaign citing clinical study and high-risk patient volume",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Published clinical trial matches high-risk patient segment; pitch preventive campaign",
            }

        if trg_kind == "perf_dip":
            return {
                "objective": CommunicationObjective.RECOVER_PERFORMANCE_DIP,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.PITCH_OFFER,
                    payload={"metric": metric, "delta_pct": delta_pct},
                    cta_prompt="Highlight 7-day metric decline and pitch remedial featured listing promotion",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "7-day call volume dip detected; propose remedial featured promotion",
            }

        if trg_kind == "recall_due":
            # Preferred slots from customer preferences or trigger
            cust_slots = None
            if customer and customer.preferences and customer.preferences.preferred_slots:
                cust_slots = customer.preferences.preferred_slots
            return {
                "objective": CommunicationObjective.RE_ENGAGE_LAPSED_CUSTOMER,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.SUGGEST_TIME_SLOTS,
                    payload={"slots": cust_slots or slots, "service_due": service_due},
                    cta_prompt="Remind customer of overdue checkup and suggest convenient appointment slots",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Customer overdue for periodic recall visit; propose specific appointment slots",
            }

        if trg_kind == "renewal_due":
            days_rem = getattr(merchant.subscription, "days_remaining", 14) if merchant.subscription else 14
            return {
                "objective": CommunicationObjective.RENEW_PLATFORM_SUBSCRIPTION,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.RENEW_SUBSCRIPTION,
                    payload={"days_remaining": days_rem},
                    cta_prompt="Alert merchant to upcoming subscription expiration and offer renewal link",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Subscription nearing expiration; trigger proactive renewal alert",
            }

        if trg_kind == "unverified_gbp":
            return {
                "objective": CommunicationObjective.VERIFY_GOOGLE_BUSINESS_PROFILE,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.VERIFY_PROFILE_LINK,
                    cta_prompt="Guide merchant to verify GBP to restore local search placement",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Unverified GBP harms organic reach; urge profile claim & verification",
            }

        if trg_kind in {"festival_upcoming", "seasonal_beat"}:
            return {
                "objective": CommunicationObjective.PROMOTE_SEASONAL_OFFER,
                "proposed_action": ProposedAction(
                    action_type=ProposedActionType.PITCH_OFFER,
                    cta_prompt="Propose holiday festive bundle package for upcoming peak season",
                ),
                "response_required": True,
                "stop_required": False,
                "rationale": "Upcoming festive season presents elevated demand; pitch promotional bundle",
            }

        # Fallback proactive initiation
        return {
            "objective": CommunicationObjective.PITCH_RESEARCH_CAMPAIGN,
            "proposed_action": ProposedAction(action_type=ProposedActionType.PITCH_OFFER),
            "response_required": True,
            "stop_required": False,
            "rationale": f"Initiate proactive communication for trigger kind '{trg_kind}'",
        }
