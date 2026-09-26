"""Adversarial and independent unit tests for Level 10 Output Validation."""

import unittest

from vera.composer.engine import MessageComposer
from vera.decision.engine import DecisionEngine
from vera.models.category import CategoryContext
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
from vera.models.selection import FactTier, SelectedFact, SelectionBundle, UnavailableFact
from vera.models.trigger import TriggerContext
from vera.models.validation import OutputValidationReport, ValidationDimension
from vera.validator.engine import OutputValidator


class TestOutputValidator(unittest.TestCase):
    """Exhaustive adversarial test suite for independent OutputValidator."""

    def setUp(self):
        self.validator = OutputValidator()
        self.decision_engine = DecisionEngine()
        self.composer = MessageComposer()

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

    def _sample_trigger(self, kind="research_digest", scope="merchant") -> dict:
        return {
            "id": f"trg_{kind}_001",
            "kind": kind,
            "scope": scope,
            "source": "internal",
            "urgency": 2,
            "merchant_id": "m_001_drmeera",
            "suppression_key": f"test:{kind}:2026",
            "expires_at": "2026-05-03T00:00:00Z",
            "payload": {"top_item_id": "d_fluoride_2026"},
        }

    def _build_test_decision(self, kind="research_digest", scope="merchant") -> Decision:
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind=kind, scope=scope))
        return self.decision_engine.decide(category=cat, merchant=mer, trigger=trg)

    # =========================================================================
    # 1. VALIDATOR INDEPENDENCE FROM COMPOSER
    # =========================================================================
    def test_validator_runs_independently(self):
        """Validator operates as an independent audit engine without invoking Composer."""
        decision = self._build_test_decision()

        handcrafted_msg = ComposedMessage(
            body="Dr. Meera, JIDA Oct 2026 published trial on 38% caries reduction. Reply YES to review.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Manual audit",
        )

        report = self.validator.validate(handcrafted_msg, decision)
        self.assertIsInstance(report, OutputValidationReport)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.dimensions), 13)

    # =========================================================================
    # 2. DETECT UNSUPPORTED FACTS & HALLUCINATIONS
    # =========================================================================
    def test_detects_ungrounded_fabricated_prices(self):
        """Adversarial test: catches fabricated currency/price claims not in context."""
        decision = self._build_test_decision()

        # Adversarial message asserting ungrounded ₹19 price
        adversarial_msg = ComposedMessage(
            body="Dr. Meera, dental cleaning now at ₹19 for a limited time! Reply YES to claim.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Adversarial ungrounded price test",
        )

        report = self.validator.validate(adversarial_msg, decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.HALLUCINATION.value].passed)
        self.assertTrue(any("Ungrounded currency claim '₹19'" in err.message for err in report.failures))

    def test_detects_unavailable_place_id_hallucination(self):
        """Adversarial test: catches assertions of attributes marked as UnavailableFact."""
        decision = self._build_test_decision()
        # Inject unavailable merchant_place_id
        decision.selected_facts.unavailable_facts.append(
            UnavailableFact(
                key="merchant_place_id",
                expected_scope="merchant",
                importance="critical",
                reason="Google Place ID missing",
            )
        )

        adversarial_msg = ComposedMessage(
            body="Dr. Meera, click maps.google.com/place_id=123 to verify your clinic. Reply YES.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Adversarial unavailable link test",
        )

        report = self.validator.validate(adversarial_msg, decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.HALLUCINATION.value].passed)
        self.assertTrue(any("place_id is unavailable" in err.message for err in report.failures))

    # =========================================================================
    # 3. DETECT REPETITION & EXCESSIVE SIMILARITY
    # =========================================================================
    def test_detects_exact_repetition(self):
        """Adversarial test: detects exact identical message from previous turn."""
        decision = self._build_test_decision()
        sent_body = "Dr. Meera, JIDA Oct 2026 published trial on 38% caries reduction. Reply YES."

        msg = ComposedMessage(
            body=sent_body,
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Repetition test",
        )

        report = self.validator.validate(msg, decision, previous_messages=[sent_body])
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.REPETITION.value].passed)
        self.assertTrue(any("Identical message was already sent" in err.message for err in report.failures))

    def test_detects_high_similarity_repetition(self):
        """Adversarial test: detects excessive word similarity (>85%) with previous message."""
        decision = self._build_test_decision()
        prev = "Dr. Meera, JIDA Oct 2026 published findings on 38% caries reduction. Reply YES to review draft."
        # Candidate only changes 1 word
        curr = "Dr. Meera, JIDA Oct 2026 published findings on 38% caries reduction. Reply YES to confirm draft."

        msg = ComposedMessage(
            body=curr,
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Similarity test",
        )

        report = self.validator.validate(msg, decision, previous_messages=[prev])
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.REPETITION.value].passed)

    # =========================================================================
    # 4. DETECT WRONG-CONTEXT MESSAGES
    # =========================================================================
    def test_detects_wrong_recipient_role_and_crm_leak(self):
        """Adversarial test: catches internal merchant CRM metrics leaked to customer."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(kind="recall_due", scope="customer"))
        cust = CustomerContext.model_validate(
            {
                "customer_id": "c_999",
                "merchant_id": "m_001_drmeera",
                "identity": {"name": "Priya", "language_pref": "en"},
                "state": "active",
                "relationship": {"first_visit": "2025-01-10", "last_visit": "2026-03-15", "visits_total": 2},
                "preferences": {"preferred_slots": "Saturday morning", "channel": "whatsapp"},
                "consent": {"opted_in_at": "2025-01-10", "scope": ["recall_reminders"]},
            }
        )


        customer_decision = self.decision_engine.decide(category=cat, merchant=mer, trigger=trg, customer=cust)

        # Adversarial message: sends as VERA and leaks CRM delta_7d
        adversarial_msg = ComposedMessage(
            body="Hi Priya, our delta_7d metrics show lower views so book your scaling. Reply 1.",
            cta=CtaType.CHOICE,
            send_as=SendAsIdentity.VERA,  # Wrong! Must be MERCHANT_ON_BEHALF
            suppression_key="supp_test",
            rationale="Adversarial customer leak test",
        )

        report = self.validator.validate(adversarial_msg, customer_decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.CUSTOMER_FIT.value].passed)
        self.assertTrue(any("delta_7d" in err.message or "MERCHANT_ON_BEHALF" in err.message for err in report.failures))

    def test_detects_wrong_merchant_salutation(self):
        """Adversarial test: catches mismatched doctor/merchant salutation."""
        decision = self._build_test_decision()

        adversarial_msg = ComposedMessage(
            body="Dr. Rajesh, JIDA Oct 2026 published trial on caries. Reply YES to review.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Wrong doctor name",
        )

        report = self.validator.validate(adversarial_msg, decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.MERCHANT_FIT.value].passed)
        self.assertTrue(any("salutation missing owner name" in err.message.lower() for err in report.failures))

    # =========================================================================
    # 5. REJECT MALFORMED OUTPUTS
    # =========================================================================
    def test_rejects_empty_and_bloated_length(self):
        """Adversarial test: rejects empty body and walls of text (>600 chars)."""
        decision = self._build_test_decision()

        empty_msg = ComposedMessage(
            body="Hi.",  # 3 chars, below 15-char minimum
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Short body test",
        )
        report_empty = self.validator.validate(empty_msg, decision)
        self.assertFalse(report_empty.is_valid)
        self.assertFalse(report_empty.dimensions[ValidationDimension.LENGTH.value].passed)


        bloated_body = "Dr. Meera, " + ("this is a very long bloated paragraph explaining dental hygiene " * 20)
        bloated_msg = ComposedMessage(
            body=bloated_body,
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Bloated body test",
        )
        report_bloated = self.validator.validate(bloated_msg, decision)
        self.assertFalse(report_bloated.is_valid)
        self.assertFalse(report_bloated.dimensions[ValidationDimension.LENGTH.value].passed)

    def test_rejects_taboo_vocabulary(self):
        """Adversarial test: rejects messages containing forbidden taboo words."""
        decision = self._build_test_decision()

        taboo_msg = ComposedMessage(
            body="Dr. Meera, we offer guaranteed 100% cure for all caries patients. Reply YES.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Taboo test",
        )

        report = self.validator.validate(taboo_msg, decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.CATEGORY_FIT.value].passed)
        self.assertTrue(any("Category taboo vocabulary detected" in err.message for err in report.failures))

    def test_rejects_internal_reasoning_tokens(self):
        """Adversarial test: rejects messages leaking debug/reasoning tokens."""
        decision = self._build_test_decision()

        leak_msg = ComposedMessage(
            body="Dr. Meera, [REDACTED_INTERNAL] priority_score: 0.95. Reply YES.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Leak test",
        )

        report = self.validator.validate(leak_msg, decision)
        self.assertFalse(report.is_valid)
        self.assertFalse(report.dimensions[ValidationDimension.FORMAT.value].passed)

    # =========================================================================
    # 6. REPAIR AND SAFE FALLBACK PIPELINE
    # =========================================================================
    def test_repair_fixes_taboo_words_and_revalidates(self):
        """Repair mechanism replaces taboo word with clinical phrasing and re-validates."""
        decision = self._build_test_decision()

        taboo_msg = ComposedMessage(
            body="Dr. Meera, JIDA published findings on fluoride. Guaranteed results for your patients. Reply YES.",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="supp_test",
            rationale="Repair test",
        )

        initial_report = self.validator.validate(taboo_msg, decision)
        self.assertFalse(initial_report.is_valid)

        repaired_msg = self.validator.repair_message(taboo_msg, decision, initial_report)
        self.assertNotIn("guaranteed", repaired_msg.body.lower())
        self.assertIn("clinically supported", repaired_msg.body.lower())

        second_report = self.validator.validate(repaired_msg, decision)
        self.assertTrue(second_report.is_valid)

    def test_exhausted_retries_triggers_safe_fallback(self):
        """When retries are exhausted on an invalid output, safe fallback is deployed."""
        decision = self._build_test_decision()

        class BrokenComposer:
            """Adversarial mock composer that persistently returns invalid taboo output."""
            def compose(self, d, previous_messages=None):
                return ComposedMessage(
                    body="Dr. Meera, guaranteed cure for everyone with 100% cure! [REDACTED]",
                    cta=CtaType.BINARY,
                    send_as=SendAsIdentity.VERA,
                    suppression_key="supp_test",
                    rationale="Broken generator",
                )

        report = self.validator.validate_and_repair(
            decision=decision,
            composer=BrokenComposer(),
            max_retries=1,
        )

        self.assertTrue(report.is_valid)
        self.assertTrue(report.used_fallback)
        self.assertIsNotNone(report.final_body)
        self.assertNotIn("guaranteed", report.final_body.lower())
        self.assertNotIn("[redacted", report.final_body.lower())
        self.assertIn("Dr. Meera", report.final_body)

    def test_context_engine_compose_and_validate_integration(self):
        """Verify end-to-end ContextEngine.compose_and_validate integration."""
        from vera.context.engine import ContextEngine
        from vera.models.context_version import ContextScope

        ce = ContextEngine()
        ce.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_category())
        ce.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant())
        ce.ingest(ContextScope.TRIGGER, "trg_research_digest_001", 1, self._sample_trigger(kind="research_digest"))

        report, err = ce.compose_and_validate(
            merchant_id="m_001_drmeera",
            trigger_id="trg_research_digest_001",
        )
        self.assertIsNone(err)
        self.assertIsNotNone(report)
        self.assertTrue(report.is_valid)
        self.assertIsNotNone(report.final_body)
        self.assertIn("Dr. Meera", report.final_body)
        self.assertEqual(len(report.dimensions), 13)


if __name__ == "__main__":
    unittest.main()

