"""Unit tests for TriggerIntelligenceEngine."""

import unittest
from vera.context.engine import ContextEngine
from vera.models.context_version import ContextScope
from vera.trigger.decision import ReasonCode, RejectionReason
from vera.trigger.engine import TriggerIntelligenceEngine
from vera.trigger.suppression import SuppressionStore


class TestTriggerEngine(unittest.TestCase):
    """Comprehensive test suite for trigger intelligence arbitration."""

    def setUp(self):
        self.context_engine = ContextEngine()
        self.suppression_store = SuppressionStore()
        self.trigger_engine = TriggerIntelligenceEngine(
            context_engine=self.context_engine,
            suppression_store=self.suppression_store,
        )

        # Preload standard Category (Dentists)
        self.context_engine.ingest(
            ContextScope.CATEGORY,
            "dentists",
            1,
            {
                "slug": "dentists",
                "voice": {"tone": "peer_clinical"},
                "peer_stats": {"avg_rating": 4.4, "avg_review_count": 60, "avg_ctr": 0.03},
                "digest": [
                    {
                        "id": "d_fluoride",
                        "kind": "research",
                        "title": "Fluoride 3mo recall trial",
                        "source": "JIDA Oct 2026 p.14",
                        "patient_segment": "high_risk_adults",
                        "summary": "38% caries reduction",
                    }
                ],
            },
        )

        # Preload Dentist Merchant (Dr. Meera)
        self.context_engine.ingest(
            ContextScope.MERCHANT,
            "m_001_drmeera",
            1,
            {
                "merchant_id": "m_001_drmeera",
                "category_slug": "dentists",
                "identity": {
                    "name": "Dr. Meera's Dental Clinic",
                    "city": "Delhi",
                    "locality": "Lajpat Nagar",
                    "verified": True,
                    "languages": ["en", "hi"],
                },
                "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
                "performance": {
                    "views": 2410,
                    "calls": 18,
                    "directions": 45,
                    "ctr": 0.021,
                    "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05},
                },
                "offers": [{"id": "o_001", "title": "Cleaning @ ₹299", "status": "active"}],
                "customer_aggregate": {
                    "total_unique_ytd": 540,
                    "lapsed_180d_plus": 78,
                    "high_risk_adult_count": 124,
                },
                "signals": ["high_risk_adult_cohort", "ctr_below_peer_median"],
            },
        )

        # Preload Customer (Priya)
        self.context_engine.ingest(
            ContextScope.CUSTOMER,
            "c_001_priya",
            1,
            {
                "customer_id": "c_001_priya",
                "merchant_id": "m_001_drmeera",
                "identity": {"name": "Priya", "language_pref": "hi-en mix"},
                "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 4},
                "state": "lapsed_soft",
                "preferences": {"channel": "whatsapp"},
                "consent": {"opted_in_at": "2025-11-04", "scope": ["recall_reminders"]},
            },
        )

    # 1. No triggers
    def test_no_triggers(self):
        decision = self.trigger_engine.evaluate_triggers([])
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.reason_code, ReasonCode.NO_TRIGGERS_AVAILABLE)
        self.assertIsNone(decision.selected_trigger)

    # 2. One valid trigger
    def test_one_valid_trigger(self):
        trg_data = {
            "id": "trg_001",
            "scope": "merchant",
            "kind": "research_digest",
            "source": "external",
            "merchant_id": "m_001_drmeera",
            "customer_id": None,
            "payload": {"category": "dentists", "top_item_id": "d_fluoride"},
            "urgency": 2,
            "suppression_key": "research:dentists:2026-W17",
            "expires_at": "2026-05-10T00:00:00Z",
        }
        self.context_engine.ingest(ContextScope.TRIGGER, "trg_001", 1, trg_data)

        decision = self.trigger_engine.evaluate_triggers(["trg_001"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "send")
        self.assertEqual(decision.reason_code, ReasonCode.TRIGGER_SELECTED)
        self.assertIsNotNone(decision.selected_trigger)
        self.assertEqual(decision.selected_trigger.id, "trg_001")
        self.assertEqual(decision.priority, 2)
        self.assertIn("cohort_match", decision.supporting_context)

    # 3. Multiple triggers ranking (higher urgency / impact wins)
    def test_multiple_triggers_ranking(self):
        # Trigger A: urgency 2 (research)
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_research",
            1,
            {
                "id": "trg_research",
                "scope": "merchant",
                "kind": "research_digest",
                "source": "external",
                "merchant_id": "m_001_drmeera",
                "payload": {"category": "dentists"},
                "urgency": 2,
                "suppression_key": "research:2026",
                "expires_at": "2026-05-10T00:00:00Z",
            },
        )
        # Trigger B: urgency 4 (regulation change - high priority)
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_regulation",
            1,
            {
                "id": "trg_regulation",
                "scope": "merchant",
                "kind": "regulation_change",
                "source": "external",
                "merchant_id": "m_001_drmeera",
                "payload": {"deadline_iso": "2026-12-15"},
                "urgency": 4,
                "suppression_key": "compliance:2026",
                "expires_at": "2026-12-15T00:00:00Z",
            },
        )

        decision = self.trigger_engine.evaluate_triggers(
            ["trg_research", "trg_regulation"], now_iso="2026-04-26T10:00:00Z"
        )
        self.assertEqual(decision.decision_type, "send")
        self.assertEqual(decision.selected_trigger.id, "trg_regulation")
        self.assertEqual(decision.priority, 4)

    # 4. Duplicate triggers within tick
    def test_duplicate_triggers_deduplication(self):
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_dup_1",
            1,
            {
                "id": "trg_dup_1",
                "scope": "merchant",
                "kind": "perf_spike",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "payload": {},
                "urgency": 2,
                "suppression_key": "perf_spike:m_001",
                "expires_at": "2026-05-10T00:00:00Z",
            },
        )

        decision = self.trigger_engine.evaluate_triggers(
            ["trg_dup_1", "trg_dup_1"], now_iso="2026-04-26T10:00:00Z"
        )
        self.assertEqual(decision.decision_type, "send")
        self.assertEqual(len(decision.candidate_evaluations), 2)
        self.assertEqual(decision.candidate_evaluations[1].rejection_reason, RejectionReason.DUPLICATE_CANDIDATE)

    # 5. Expired trigger
    def test_expired_trigger_rejected(self):
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_expired",
            1,
            {
                "id": "trg_expired",
                "scope": "merchant",
                "kind": "festival_upcoming",
                "source": "external",
                "merchant_id": "m_001_drmeera",
                "payload": {},
                "urgency": 2,
                "suppression_key": "festival:past",
                "expires_at": "2026-04-20T00:00:00Z",
            },
        )
        # Simulation clock is 2026-04-26 (after April 20)
        decision = self.trigger_engine.evaluate_triggers(["trg_expired"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.reason_code, ReasonCode.ALL_TRIGGERS_EXPIRED)
        self.assertEqual(decision.candidate_evaluations[0].rejection_reason, RejectionReason.EXPIRED)

    # 6. Irrelevant trigger (Category mismatch)
    def test_irrelevant_category_mismatch(self):
        # Trigger specifies restaurants but merchant is dentist
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_restaurant",
            1,
            {
                "id": "trg_restaurant",
                "scope": "merchant",
                "kind": "festival_upcoming",
                "source": "external",
                "merchant_id": "m_001_drmeera",
                "payload": {"category": "restaurants"},
                "urgency": 2,
                "suppression_key": "festival:res",
                "expires_at": "2026-05-10T00:00:00Z",
            },
        )
        decision = self.trigger_engine.evaluate_triggers(["trg_restaurant"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.candidate_evaluations[0].rejection_reason, RejectionReason.CATEGORY_MISMATCH)

    # 7. Already handled trigger (Suppression)
    def test_already_handled_trigger_suppressed(self):
        trg_data = {
            "id": "trg_suppress_test",
            "scope": "merchant",
            "kind": "curious_ask_due",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "payload": {},
            "urgency": 1,
            "suppression_key": "curious_ask:m_001:2026-W17",
            "expires_at": "2026-05-10T00:00:00Z",
        }
        self.context_engine.ingest(ContextScope.TRIGGER, "trg_suppress_test", 1, trg_data)

        # First evaluation: selected and auto-suppressed
        d1 = self.trigger_engine.evaluate_triggers(["trg_suppress_test"], now_iso="2026-04-26T10:00:00Z", auto_suppress=True)
        self.assertEqual(d1.decision_type, "send")
        self.assertEqual(d1.selected_trigger.id, "trg_suppress_test")

        # Second evaluation (e.g. next tick): must be suppressed!
        d2 = self.trigger_engine.evaluate_triggers(["trg_suppress_test"], now_iso="2026-04-26T10:05:00Z")
        self.assertEqual(d2.decision_type, "skip")
        self.assertEqual(d2.reason_code, ReasonCode.ALL_TRIGGERS_SUPPRESSED)
        self.assertIn("trg_suppress_test", d2.suppressed_triggers)
        self.assertEqual(d2.candidate_evaluations[0].rejection_reason, RejectionReason.SUPPRESSED)

    # 8. Updated trigger version handling
    def test_updated_trigger_version(self):
        trg_v1 = {
            "id": "trg_update",
            "scope": "merchant",
            "kind": "perf_spike",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "payload": {"delta": 0.10},
            "urgency": 1,
            "suppression_key": "perf_spike:m_001_v1",
            "expires_at": "2026-05-10T00:00:00Z",
        }
        self.context_engine.ingest(ContextScope.TRIGGER, "trg_update", 1, trg_v1)

        # Push v2 with increased urgency
        trg_v2 = dict(trg_v1)
        trg_v2["urgency"] = 4
        self.context_engine.ingest(ContextScope.TRIGGER, "trg_update", 2, trg_v2)

        decision = self.trigger_engine.evaluate_triggers(["trg_update"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "send")
        self.assertEqual(decision.selected_trigger.urgency, 4)
        self.assertEqual(decision.priority, 4)

    # 9. Conflicting triggers: tie-breaking
    def test_conflicting_triggers_tie_breaking(self):
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_alpha",
            1,
            {
                "id": "trg_alpha",
                "scope": "merchant",
                "kind": "curious_ask_due",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "payload": {},
                "urgency": 2,
                "suppression_key": "suppress:alpha",
                "expires_at": "2026-05-10T00:00:00Z",
            },
        )
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_beta",
            1,
            {
                "id": "trg_beta",
                "scope": "merchant",
                "kind": "curious_ask_due",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "payload": {},
                "urgency": 2,
                "suppression_key": "suppress:beta",
                "expires_at": "2026-05-10T00:00:00Z",
            },
        )

        decision = self.trigger_engine.evaluate_triggers(["trg_beta", "trg_alpha"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "send")
        # Tied score -> alphabetical order deterministic selection
        self.assertEqual(decision.selected_trigger.id, "trg_alpha")

    # 10. Customer trigger consent checking
    def test_customer_trigger_consent_rejection(self):
        # Create customer without recall_reminders consent
        self.context_engine.ingest(
            ContextScope.CUSTOMER,
            "c_no_consent",
            1,
            {
                "customer_id": "c_no_consent",
                "merchant_id": "m_001_drmeera",
                "identity": {"name": "NoConsent"},
                "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 1},
                "state": "active",
                "preferences": {},
                "consent": {"opted_in_at": "2025-11-04", "scope": ["promotional_offers"]},  # Missing recall_reminders
            },
        )
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_cx_recall",
            1,
            {
                "id": "trg_cx_recall",
                "scope": "customer",
                "kind": "recall_due",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "customer_id": "c_no_consent",
                "payload": {"service_due": "cleaning"},
                "urgency": 3,
                "suppression_key": "recall:c_no_consent",
                "expires_at": "2026-11-30T00:00:00Z",
            },
        )
        decision = self.trigger_engine.evaluate_triggers(["trg_cx_recall"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.candidate_evaluations[0].rejection_reason, RejectionReason.CUSTOMER_CONSENT_MISSING)

    def test_customer_promotional_trigger_rejected_if_only_reminders_consent(self):
        # Create customer with only reminders consent (no promotional/marketing)
        self.context_engine.ingest(
            ContextScope.CUSTOMER,
            "c_reminders_only",
            1,
            {
                "customer_id": "c_reminders_only",
                "merchant_id": "m_001_drmeera",
                "identity": {"name": "RemindersOnly"},
                "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 2},
                "state": "active",
                "preferences": {"reminder_opt_in": True},
                "consent": {"opted_in_at": "2025-11-04", "scope": ["reminders"]},  # Only reminders
            },
        )
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_cx_promo",
            1,
            {
                "id": "trg_cx_promo",
                "scope": "customer",
                "kind": "promotional_offer",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "customer_id": "c_reminders_only",
                "payload": {"offer": "20% off whitening"},
                "urgency": 2,
                "suppression_key": "promo:c_reminders_only",
                "expires_at": "2026-11-30T00:00:00Z",
            },
        )
        decision = self.trigger_engine.evaluate_triggers(["trg_cx_promo"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.candidate_evaluations[0].rejection_reason, RejectionReason.CUSTOMER_CONSENT_MISSING)

    def test_customer_reminder_rejected_if_reminder_opt_in_false(self):
        # Create customer with recall_reminders scope but reminder_opt_in is False
        self.context_engine.ingest(
            ContextScope.CUSTOMER,
            "c_opted_out_reminders",
            1,
            {
                "customer_id": "c_opted_out_reminders",
                "merchant_id": "m_001_drmeera",
                "identity": {"name": "OptedOutReminders"},
                "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 2},
                "state": "active",
                "preferences": {"reminder_opt_in": False},
                "consent": {"opted_in_at": "2025-11-04", "scope": ["recall_reminders"]},
            },
        )
        self.context_engine.ingest(
            ContextScope.TRIGGER,
            "trg_cx_recall_optout",
            1,
            {
                "id": "trg_cx_recall_optout",
                "scope": "customer",
                "kind": "recall_due",
                "source": "internal",
                "merchant_id": "m_001_drmeera",
                "customer_id": "c_opted_out_reminders",
                "payload": {"service_due": "cleaning"},
                "urgency": 3,
                "suppression_key": "recall:c_opted_out_reminders",
                "expires_at": "2026-11-30T00:00:00Z",
            },
        )
        decision = self.trigger_engine.evaluate_triggers(["trg_cx_recall_optout"], now_iso="2026-04-26T10:00:00Z")
        self.assertEqual(decision.decision_type, "skip")
        self.assertEqual(decision.candidate_evaluations[0].rejection_reason, RejectionReason.CUSTOMER_CONSENT_MISSING)


if __name__ == "__main__":
    unittest.main()
