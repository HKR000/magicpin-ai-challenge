"""Unit tests for Vera Message Composer (Level 9)."""

import unittest

from vera.composer.engine import MessageComposer
from vera.composer.validator import MessageValidationError, MessageValidator
from vera.decision.engine import DecisionEngine
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
from vera.models.intent import IntentType
from vera.models.merchant import MerchantContext
from vera.models.message import ComposedMessage, CtaType, SendAsIdentity
from vera.models.selection import FactTier, SelectedFact, SelectionBundle
from vera.models.trigger import TriggerContext


class TestMessageComposer(unittest.TestCase):
    """Exhaustive test suite for Level 9 Message Composer."""

    def setUp(self):
        self.decision_engine = DecisionEngine()
        self.composer = MessageComposer()
        self.validator = MessageValidator()

    def _sample_category(self) -> dict:
        return {
            "slug": "dentists",
            "display_name": "Dentists",
            "voice": {
                "tone": "peer_clinical",
                "register": "respectful_collegial",
                "code_mix": "hindi_english_natural",
                "vocab_allowed": ["scaling", "caries", "fluoride"],
                "vocab_taboo": ["guaranteed", "100% cure", "cheapest"],
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
    # 1. GENERATION & OUTPUT SCHEMA VALIDATION
    # =========================================================================
    def test_generation_output_schema_validated(self):
        """ComposedMessage adheres to complete output schema and is valid."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertIsInstance(msg, ComposedMessage)
        self.assertTrue(len(msg.body) > 0)
        self.assertEqual(msg.cta, CtaType.BINARY)
        self.assertEqual(msg.send_as, SendAsIdentity.VERA)
        self.assertEqual(msg.suppression_key, decision.trigger.suppression_key)
        self.assertTrue(msg.is_validated)
        self.assertTrue(any("PASS" in note for note in msg.validation_notes))

    # =========================================================================
    # 2. FACTS GROUNDED (ZERO FABRICATION / HALLUCINATION)
    # =========================================================================
    def test_facts_grounded_in_selected_context(self):
        """Claims in message are anchored strictly on verified facts."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        # Check that verified facts appear in the text
        self.assertIn("Dr. Meera", msg.body)
        self.assertIn("JIDA Oct 2026", msg.body)
        self.assertIn("38% caries reduction", msg.body)
        self.assertIn("84", msg.body)  # 84 adult cohort
        self.assertIn("digest_item_source", msg.grounded_facts)

    def test_performance_dip_message_grounded(self):
        """Performance dip message uses concrete metrics and active offer."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(
            self._sample_trigger(kind="perf_dip", payload={"metric": "calls", "delta_pct": -0.22})
        )

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertIn("22%", msg.body)
        self.assertIn("Preventive Scaling & Polish", msg.body)
        self.assertIn("perf_calls_delta_7d", msg.grounded_facts)

    # =========================================================================
    # 3. CONTEXT-SPECIFIC MESSAGES & ATTRIBUTION
    # =========================================================================
    def test_customer_facing_message_uses_merchant_on_behalf(self):
        """Customer-facing message uses merchant_on_behalf identity and customer slots."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(
            self._sample_trigger(kind="recall_due", scope="customer", payload={"service_due": "preventive dental cleaning"})
        )
        cust = CustomerContext.model_validate(self._sample_customer())

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg, customer=cust)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertEqual(msg.send_as, SendAsIdentity.MERCHANT_ON_BEHALF)
        self.assertEqual(msg.cta, CtaType.CHOICE)
        self.assertIn("Rahul", msg.body)
        self.assertIn("Saturday morning", msg.body)
        self.assertIn("Dr. Meera's Dental Clinic", msg.body)

    # =========================================================================
    # 4. PREVIOUS MESSAGES CONSIDERED & REPETITION CONTROLLED
    # =========================================================================
    def test_repetition_controlled_in_follow_up(self):
        """When research paper was already discussed, composer avoids repeating trial headline."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)

        # Previous message in dialogue history
        prev_msg = (
            "Dr. Meera, Worth a quick look: JIDA Oct 2026 p.14 published new findings on 38% caries reduction."
        )

        follow_up = self.composer.compose(decision, previous_messages=[prev_msg])

        self.assertIsNotNone(follow_up)
        # Should NOT repeat the raw study text
        self.assertNotIn("JIDA Oct 2026", follow_up.body)
        self.assertIn("Following up on the preventive recall program", follow_up.body)
        self.assertIn("Reply YES to launch", follow_up.body)

    def test_validator_rejects_duplicate_message(self):
        """MessageValidator rejects message if identical to previous message."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        # Validate against identical previous message
        is_valid, notes = self.validator.validate(msg, decision, previous_messages=[msg.body])
        self.assertFalse(is_valid)
        self.assertTrue(any("Identical message already sent" in n for n in notes))

    # =========================================================================
    # 5. TABOO VOCABULARY & INTERNAL LEAKAGE PREVENTION
    # =========================================================================
    def test_validator_rejects_taboo_words(self):
        """Validator strictly rejects messages containing category taboo vocabulary."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        # Tamper with body to inject taboo word
        msg.body = msg.body + " Guaranteed results for all patients."
        is_valid, notes = self.validator.validate(msg, decision)
        self.assertFalse(is_valid)
        self.assertTrue(any("Category taboo word detected" in n for n in notes))

    def test_validator_rejects_internal_reasoning_tokens(self):
        """Validator rejects any leaked debug/internal reasoning tokens."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="research_digest"))

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
        msg = self.composer.compose(decision)

        # Tamper with body to inject internal token
        msg.body = msg.body + " Internal reasoning: [REDACTED_CRM]"
        is_valid, notes = self.validator.validate(msg, decision)
        self.assertFalse(is_valid)
        self.assertTrue(any("Internal reasoning/debug token leaked" in n for n in notes))

    # =========================================================================
    # 6. STOPPING DECISIONS RETURN NO MESSAGE (SILENCE)
    # =========================================================================
    def test_composer_returns_none_when_response_not_required(self):
        """When decision.response_required is False, composer returns None."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        # Auto reply on Turn 1 backs off silently
        conv = ConversationState(
            conversation_id="conv_auto_silent",
            merchant_id="m_001_drmeera",
            current_state=State.WAITING,
            auto_reply_count=0,
            last_message_at="2026-05-12T10:00:00Z",
        )

        decision = self.decision_engine.decide(
            category=cat,
            merchant=mer,
            trigger=trg,
            conversation=conv,
            intent=IntentType.AUTO_REPLY,
        )

        self.assertFalse(decision.response_required)
        msg = self.composer.compose(decision)
        self.assertIsNone(msg)

    # =========================================================================
    # 7. INBOUND INTENT COMPOSITION (INQUIRY, COMMITMENT, OPT-OUT)
    # =========================================================================
    def test_compose_inquiry_response(self):
        """Inquiry produces direct pricing quote with actionable confirmation CTA."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg, intent=IntentType.INQUIRY)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertIn("pricing", msg.body.lower())
        self.assertIn("Reply YES to proceed", msg.body)

    def test_compose_commitment_execution_response(self):
        """Commitment produces confirmation message with CtaType.NONE."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg, intent=IntentType.COMMITMENT)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertEqual(msg.cta, CtaType.NONE)
        self.assertIn("scheduled the campaign", msg.body)

    def test_compose_opt_out_response(self):
        """Hostile opt out produces polite unsubscribe confirmation."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg, intent=IntentType.HOSTILE_OPT_OUT)
        msg = self.composer.compose(decision)

        self.assertIsNotNone(msg)
        self.assertEqual(msg.cta, CtaType.NONE)
        self.assertIn("opted you out", msg.body)

    def test_context_engine_compose_end_to_end(self):
        """Verify ContextEngine.compose(...) integration end to end."""
        from vera.context.engine import ContextEngine
        from vera.models.context_version import ContextScope

        ce = ContextEngine()
        ce.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_category())
        ce.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant())
        ce.ingest(ContextScope.TRIGGER, "trg_research_digest_001", 1, self._sample_trigger(kind="research_digest"))

        composed, err = ce.compose(
            merchant_id="m_001_drmeera",
            trigger_id="trg_research_digest_001",
        )
        self.assertIsNone(err)
        self.assertIsNotNone(composed)
        self.assertTrue(composed.is_validated)
        self.assertIn("Dr. Meera", composed.body)
        self.assertIn("JIDA Oct 2026", composed.body)
        self.assertEqual(composed.cta, CtaType.BINARY)

    def test_proactive_template_params_extraction_across_all_objectives(self):
        """Verify template_name and template_params are populated across all proactive objectives."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())

        proactive_objectives = [
            (CommunicationObjective.PITCH_RESEARCH_CAMPAIGN, "research_digest"),
            (CommunicationObjective.RECOVER_PERFORMANCE_DIP, "perf_dip"),
            (CommunicationObjective.RE_ENGAGE_LAPSED_CUSTOMER, "customer_lapsed_soft"),
            (CommunicationObjective.RENEW_PLATFORM_SUBSCRIPTION, "renewal_due"),
            (CommunicationObjective.VERIFY_GOOGLE_BUSINESS_PROFILE, "gmb_unverified"),
            (CommunicationObjective.PROMOTE_FESTIVE_PACKAGE, "festive_event"),
            (CommunicationObjective.OPTIMIZE_RESTAURANT_SURGE, "match_night_surge"),
            (CommunicationObjective.DRIVE_FITNESS_MEMBERSHIP, "fitness_lull"),
            (CommunicationObjective.AUDIT_PHARMACY_COMPLIANCE, "schedule_h1_refill"),
            (CommunicationObjective.DEFEND_LOCAL_COMPETITION, "competitor_opened"),
            (CommunicationObjective.PROMOTE_SEASONAL_OFFER, "seasonal_beat"),
        ]

        for obj, kind in proactive_objectives:
            trg = TriggerContext.model_validate(self._sample_trigger(kind=kind))
            decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)
            # Override objective to test this branch deterministically
            decision.objective = obj
            msg = self.composer.compose(decision)

            self.assertIsNotNone(msg, f"Message should not be None for {obj}")
            self.assertIsNotNone(msg.template_name, f"template_name should be set for {obj}")
            self.assertTrue(len(msg.template_name) > 0, f"template_name should be non-empty for {obj}")
            self.assertIsNotNone(msg.template_params, f"template_params should not be None for {obj}")
            self.assertIsInstance(msg.template_params, list, f"template_params must be a list for {obj}")
            self.assertGreaterEqual(len(msg.template_params), 2, f"template_params must have >= 2 items for {obj}")
            for param in msg.template_params:
                self.assertIsInstance(param, str, f"Parameter must be str in {obj}")
                self.assertTrue(len(param) > 0, f"Parameter must not be empty in {obj}")


if __name__ == "__main__":
    unittest.main()

