"""Unit tests for Vera Decision Engine (Level 8)."""

import unittest

from vera.decision.engine import DecisionEngine
from vera.models.category import CategoryContext
from vera.models.conversation import ConversationState, ConversationTurn, Role, State
from vera.models.customer import CustomerContext
from vera.models.decision import (
    CommunicationObjective,
    Decision,
    DecisionRecipient,
    DecisionTrigger,
    ProposedActionType,
)
from vera.models.intent import IntentType
from vera.models.merchant import MerchantContext
from vera.models.trigger import TriggerContext


class TestDecisionEngine(unittest.TestCase):
    """Exhaustive test suite for Level 8 Decision Engine."""

    def setUp(self):
        self.engine = DecisionEngine()

    def _sample_category(self) -> dict:
        return {
            "slug": "dentists",
            "display_name": "Dentists",
            "voice": {
                "tone": "peer_clinical",
                "register": "respectful_collegial",
                "code_mix": "hindi_english_natural",
                "vocab_allowed": ["scaling", "caries", "fluoride"],
                "vocab_taboo": ["guaranteed", "100% cure"],
                "salutation_examples": ["Dr. {first_name}"],
                "tone_examples": ["Worth a quick look"],
            },
            "offer_catalog": [
                {
                    "id": "den_001",
                    "title": "Dental Cleaning @ ₹299",
                    "value": "299",
                    "audience": "new_user",
                    "type": "service_at_price",
                }
            ],
            "peer_stats": {
                "scope": "delhi_solo_practices",
                "avg_rating": 4.4,
                "avg_review_count": 62,
                "avg_ctr": 0.030,
            },
            "digest": [
                {
                    "id": "d_fluoride_2026",
                    "kind": "research",
                    "title": "Fluoride recall trial 2026",
                    "source": "JIDA Oct 2026 p.14",
                    "summary": "38% caries reduction in 12-month follow up",
                    "trial_n": 412,
                }
            ],
            "patient_content_library": [],
            "seasonal_beats": [],
            "trend_signals": [],
        }

    def _sample_merchant(self) -> dict:
        return {
            "merchant_id": "m_001_drmeera",
            "category_slug": "dentists",
            "identity": {
                "name": "Dr. Meera's Dental Clinic",
                "city": "Delhi",
                "locality": "Indiranagar",
                "owner_first_name": "Meera",
                "languages": ["hi", "en"],
                "place_id": "ChIJ_demo_place_id",
            },
            "subscription": {
                "plan": "Pro",
                "status": "active",
                "days_remaining": 14,
            },
            "customer_aggregate": {
                "high_risk_adult_count": 84,
                "total_unique_ytd": 420,
            },
            "performance": {
                "window_days": 30,
                "views": 2500,
                "calls": 45,
                "directions": 30,
                "ctr": 0.028,
                "delta_7d": {
                    "calls_pct": -0.22,
                    "views_pct": -0.05,
                },
            },
            "offers": [
                {
                    "id": "off_act_001",
                    "title": "Preventive Scaling & Polish",
                    "service": "scaling",
                    "price_inr": 499,
                    "status": "active",
                }
            ],
        }

    def _sample_trigger(self, kind="research_digest", scope="merchant", payload=None) -> dict:
        p = payload or {"top_item_id": "d_fluoride_2026"}
        return {
            "id": f"trg_{kind}_001",
            "kind": kind,
            "scope": scope,
            "source": "internal",
            "urgency": 2,
            "merchant_id": "m_001_drmeera",
            "suppression_key": f"test:{kind}:2026",
            "expires_at": "2026-05-03T00:00:00Z",
            "payload": p,
        }

    def _sample_customer(self) -> dict:
        return {
            "customer_id": "cust_999",
            "merchant_id": "m_001_drmeera",
            "identity": {
                "name": "Rahul Sharma",
                "language_pref": "en",
            },
            "state": "active",
            "relationship": {
                "first_visit": "2025-01-10",
                "last_visit": "2026-03-15",
                "visits_total": 3,
                "services_received": ["cleaning"],
            },
            "preferences": {
                "preferred_slots": "Saturday morning",
                "channel": "whatsapp",
            },
            "consent": {
                "opted_in_at": "2025-01-10",
                "scope": ["recall_reminders"],
            },
        }

    # =========================================================================
    # 1. DECISION OBJECT INTEGRITY
    # =========================================================================
    def test_decision_object_structure(self):
        """Verify complete conceptual Decision object structure and types."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.engine.decide(category=cat, merchant=mer, trigger=trg)

        self.assertIsInstance(decision, Decision)
        self.assertEqual(decision.actor, "vera")
        self.assertEqual(decision.recipient.recipient_id, "m_001_drmeera")
        self.assertEqual(decision.recipient.name, "Meera")
        self.assertEqual(decision.recipient.recipient_role, "merchant")
        self.assertEqual(decision.trigger.kind, "research_digest")
        self.assertEqual(decision.objective, CommunicationObjective.PITCH_RESEARCH_CAMPAIGN)
        self.assertEqual(decision.proposed_action.action_type, ProposedActionType.PITCH_OFFER)
        self.assertEqual(decision.conversation_state, State.INITIAL)
        self.assertTrue(decision.response_required)
        self.assertFalse(decision.stop_required)
        self.assertTrue(len(decision.rationale) > 0)
        self.assertIsNotNone(decision.selected_facts)
        self.assertTrue(decision.selected_facts.verify_provenance())

    # =========================================================================
    # 2. TRIGGER CONNECTED TO OBJECTIVE
    # =========================================================================
    def test_trigger_connected_to_objective_research_digest(self):
        """research_digest trigger connects to PITCH_RESEARCH_CAMPAIGN."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)
        self.assertEqual(d.objective, CommunicationObjective.PITCH_RESEARCH_CAMPAIGN)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.PITCH_OFFER)
        self.assertEqual(d.proposed_action.target_id, "d_fluoride_2026")

    def test_trigger_connected_to_objective_perf_dip(self):
        """perf_dip trigger connects to RECOVER_PERFORMANCE_DIP."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(
            self._sample_trigger(kind="perf_dip", payload={"metric": "calls", "delta_pct": -0.22})
        )

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)
        self.assertEqual(d.objective, CommunicationObjective.RECOVER_PERFORMANCE_DIP)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.PITCH_OFFER)
        self.assertEqual(d.proposed_action.payload["delta_pct"], -0.22)

    def test_trigger_connected_to_objective_recall_due(self):
        """recall_due trigger connects to RE_ENGAGE_LAPSED_CUSTOMER with customer slots."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(
            self._sample_trigger(kind="recall_due", scope="customer", payload={"service_due": "scaling"})
        )
        cust = CustomerContext.model_validate(self._sample_customer())

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg, customer=cust)
        self.assertEqual(d.objective, CommunicationObjective.RE_ENGAGE_LAPSED_CUSTOMER)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.SUGGEST_TIME_SLOTS)
        self.assertEqual(d.recipient.recipient_role, "customer")
        self.assertEqual(d.recipient.name, "Rahul Sharma")
        self.assertEqual(d.proposed_action.payload["slots"], "Saturday morning")

    def test_trigger_connected_to_objective_renewal_due(self):
        """renewal_due trigger connects to RENEW_PLATFORM_SUBSCRIPTION."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="renewal_due"))

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)
        self.assertEqual(d.objective, CommunicationObjective.RENEW_PLATFORM_SUBSCRIPTION)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.RENEW_SUBSCRIPTION)
        self.assertEqual(d.proposed_action.payload["days_remaining"], 14)

    def test_trigger_connected_to_objective_unverified_gbp(self):
        """unverified_gbp trigger connects to VERIFY_GOOGLE_BUSINESS_PROFILE."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="unverified_gbp"))

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)
        self.assertEqual(d.objective, CommunicationObjective.VERIFY_GOOGLE_BUSINESS_PROFILE)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.VERIFY_PROFILE_LINK)

    # =========================================================================
    # 3. CONTEXT CONNECTED TO DECISION
    # =========================================================================
    def test_context_connected_to_decision(self):
        """Selected facts with provenance are attached to the Decision."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)
        self.assertTrue(len(d.selected_facts.mandatory_facts) > 0)
        self.assertTrue(len(d.selected_facts.high_value_facts) > 0)
        self.assertTrue(d.selected_facts.verify_provenance())

    # =========================================================================
    # 4. STOPPING DECISIONS SUPPORTED
    # =========================================================================
    def test_hostile_opt_out_triggers_stopping_decision(self):
        """Hostile opt-out requires stopping and suppresses future outreach."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            intent=IntentType.HOSTILE_OPT_OUT,
        )

        self.assertTrue(d.stop_required)
        self.assertTrue(d.response_required)
        self.assertEqual(d.objective, CommunicationObjective.CONFIRM_OPT_OUT)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.CONFIRM_TERMINATION)

    def test_user_rejection_triggers_stopping_decision(self):
        """Rejection produces polite close and requires stopping."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            intent=IntentType.REJECTION,
        )

        self.assertTrue(d.stop_required)
        self.assertTrue(d.response_required)
        self.assertEqual(d.objective, CommunicationObjective.HANDLE_REJECTION)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.NO_OP)

    def test_single_auto_reply_backs_off_without_sending(self):
        """Single auto-reply backs off silently (response_required=False, stop_required=False)."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        conv = ConversationState(
            conversation_id="conv_auto_1",
            merchant_id="m_001_drmeera",
            current_state=State.WAITING,
            auto_reply_count=0,
            last_message_at="2026-05-12T10:00:00Z",
        )

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            conversation=conv,
            intent=IntentType.AUTO_REPLY,
        )

        self.assertFalse(d.response_required)
        self.assertFalse(d.stop_required)
        self.assertEqual(d.objective, CommunicationObjective.AWAIT_USER_RESPONSE)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.BACK_OFF_AND_WAIT)

    def test_repeated_auto_reply_suppresses_and_stops(self):
        """Repeated auto-reply halts output (response_required=False, stop_required=True)."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        conv = ConversationState(
            conversation_id="conv_auto_2",
            merchant_id="m_001_drmeera",
            current_state=State.WAITING,
            auto_reply_count=1,  # Already seen one auto-reply
            last_message_at="2026-05-12T10:00:00Z",
        )

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            conversation=conv,
            intent=IntentType.AUTO_REPLY,
        )

        self.assertFalse(d.response_required)
        self.assertTrue(d.stop_required)
        self.assertEqual(d.objective, CommunicationObjective.SUPPRESS_AUTO_REPLY_LOOP)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.NO_OP)

    def test_terminal_conversation_state_requires_stop(self):
        """Conversation already in State.STOPPED requires stop and no response."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        conv = ConversationState(
            conversation_id="conv_stopped",
            merchant_id="m_001_drmeera",
            current_state=State.STOPPED,
            is_active=False,
            last_message_at="2026-05-12T10:00:00Z",
        )

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            conversation=conv,
        )

        self.assertFalse(d.response_required)
        self.assertTrue(d.stop_required)
        self.assertEqual(d.objective, CommunicationObjective.CONCLUDE_COMPLETED)

    # =========================================================================
    # 5. INBOUND INTENT ARBITRATION
    # =========================================================================
    def test_inbound_inquiry_proposes_pricing_quote(self):
        """Inquiry intent arbitrates to ANSWER_MERCHANT_INQUIRY and QUOTE_PRICING."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            intent=IntentType.INQUIRY,
        )

        self.assertTrue(d.response_required)
        self.assertFalse(d.stop_required)
        self.assertEqual(d.objective, CommunicationObjective.ANSWER_MERCHANT_INQUIRY)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.QUOTE_PRICING)

    def test_inbound_commitment_proposes_execution_and_stops(self):
        """Commitment intent arbitrates to EXECUTE_COMMITTED_ACTION and stops."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        d = self.engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            intent=IntentType.COMMITMENT,
        )

        self.assertTrue(d.response_required)
        self.assertTrue(d.stop_required)
        self.assertEqual(d.objective, CommunicationObjective.EXECUTE_COMMITTED_ACTION)
        self.assertEqual(d.proposed_action.action_type, ProposedActionType.EXECUTE_CAMPAIGN)

    # =========================================================================
    # 6. NO GENERATION DEPENDENCY & SERIALIZATION
    # =========================================================================
    def test_no_generation_dependency_and_serialization(self):
        """Decisions contain pure data models, no generated copywriting text, serializable."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        d = self.engine.decide(category=cat, merchant=mer, trigger=trg)

        # Confirm JSON serialization roundtrip
        json_str = d.to_json()
        deserialized = Decision.from_json(json_str)
        self.assertEqual(d.actor, deserialized.actor)
        self.assertEqual(d.recipient.recipient_id, deserialized.recipient.recipient_id)
        self.assertEqual(d.objective, deserialized.objective)
        self.assertEqual(d.proposed_action.action_type, deserialized.proposed_action.action_type)
        self.assertEqual(d.response_required, deserialized.response_required)
        self.assertEqual(d.stop_required, deserialized.stop_required)

    def test_context_engine_decide_integration(self):
        """Verify ContextEngine.decide(...) end-to-end integration."""
        from vera.context.engine import ContextEngine
        from vera.models.context_version import ContextScope

        ce = ContextEngine()
        ce.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_category())
        ce.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant())
        ce.ingest(ContextScope.TRIGGER, "trg_research_digest_001", 1, self._sample_trigger(kind="research_digest"))

        decision, err = ce.decide(
            merchant_id="m_001_drmeera",
            trigger_id="trg_research_digest_001",
        )
        self.assertIsNone(err)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.objective, CommunicationObjective.PITCH_RESEARCH_CAMPAIGN)
        self.assertEqual(decision.recipient.recipient_id, "m_001_drmeera")
        self.assertTrue(decision.response_required)
        self.assertFalse(decision.stop_required)


if __name__ == "__main__":
    unittest.main()

