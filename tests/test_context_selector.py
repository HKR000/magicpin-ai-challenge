"""Unit tests for Vera Context Selection Engine (Level 7)."""

import unittest
from datetime import datetime

from vera.context.engine import ContextEngine
from vera.context.provenance import FactProvenance
from vera.context.selector import ContextSelector
from vera.models.category import CategoryContext
from vera.models.context_version import ContextScope
from vera.models.conversation import ConversationState, ConversationTurn, Role, State
from vera.models.customer import CustomerContext
from vera.models.intent import DetectedIntent, IntentType
from vera.models.merchant import MerchantContext
from vera.models.selection import FactTier, SelectedFact, SelectionBundle, UnavailableFact
from vera.models.trigger import TriggerContext


class TestContextSelector(unittest.TestCase):
    """Exhaustive test suite for Context Selection Engine."""

    def setUp(self):
        self.engine = ContextEngine()
        self.selector = ContextSelector()

    def _sample_category(self, slug="dentists", extra_digest=False) -> dict:
        digest = [
            {
                "id": "d_fluoride_2026",
                "kind": "research",
                "title": "Fluoride recall trial 2026",
                "source": "JIDA Oct 2026 p.14",
                "summary": "38% caries reduction in 12-month follow up",
                "trial_n": 412,
            }
        ]
        if extra_digest:
            for i in range(1, 15):
                digest.append(
                    {
                        "id": f"d_unrelated_{i}",
                        "kind": "market_trend" if i % 2 == 0 else "regulatory",
                        "title": f"Unrelated Dental Trend #{i}",
                        "source": f"Dental Journal #{i}",
                        "summary": f"Summary of unrelated dental finding #{i}",
                    }
                )

        return {
            "slug": slug,
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
                    "id": "cat_clean_299",
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
            "digest": digest,
            "patient_content_library": [],
            "seasonal_beats": [],
            "trend_signals": [],
        }

    def _sample_merchant(
        self,
        mid="m_001_drmeera",
        expired_offer=False,
        minimal=False,
    ) -> dict:
        if minimal:
            return {
                "merchant_id": mid,
                "category_slug": "dentists",
                "identity": {
                    "name": "Meera Dental Clinic",
                    "city": "Delhi",
                    "locality": "Lajpat Nagar",
                    "owner_first_name": None,
                    "place_id": None,
                    "languages": [],
                },
                "subscription": {
                    "status": "active",
                    "plan": "Basic",
                },
                "performance": {
                    "window_days": 30,
                    "views": 100,
                    "calls": 5,
                    "directions": 2,
                    "ctr": 0.02,
                },
                "customer_aggregate": {
                    "total_unique_ytd": 50,
                    "retention_6mo_pct": 0.2,
                },
                "offers": [],
            }

        offers = [
            {
                "id": "off_act_001",
                "title": "Preventive Scaling & Polish",
                "service": "scaling",
                "price_inr": 499,
                "status": "active",
            }
        ]
        if expired_offer:
            offers.append(
                {
                    "id": "off_exp_002",
                    "title": "Diwali 2025 Special Whitening",
                    "service": "whitening",
                    "price_inr": 999,
                    "status": "expired",
                }
            )

        return {
            "merchant_id": mid,
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
            "offers": offers,
        }

    def _sample_trigger(
        self,
        tid="trg_001",
        kind="perf_dip",
        scope="merchant",
        top_item_id="d_fluoride_2026",
    ) -> dict:
        return {
            "id": tid,
            "kind": kind,
            "scope": scope,
            "source": "internal",
            "urgency": 2,
            "merchant_id": "m_001_drmeera",
            "suppression_key": f"test:{tid}:{kind}",
            "expires_at": "2026-05-03T00:00:00Z",
            "payload": {
                "metric": "calls",
                "delta_pct": -0.22,
                "top_item_id": top_item_id,
            },
        }

    def _sample_customer(self, cid="cust_999", mid="m_001_drmeera") -> dict:
        return {
            "customer_id": cid,
            "merchant_id": mid,
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
    # 1. TEST LARGE CONTEXT
    # =========================================================================
    def test_large_context_filtering(self):
        """Do NOT send entire 500KB dataset. Filter dozens of unrelated digest items."""
        cat_raw = self._sample_category(extra_digest=True)
        mer_raw = self._sample_merchant(expired_offer=True)
        trg_raw = self._sample_trigger(top_item_id="d_fluoride_2026")

        cat = CategoryContext.model_validate(cat_raw)
        mer = MerchantContext.model_validate(mer_raw)
        trg = TriggerContext.model_validate(trg_raw)

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
            context_versions={"category": 1, "merchant": 1, "trigger": 1},
        )

        # 1. Relevant digest item is selected in mandatory & high-value
        mandatory_keys = [f.key for f in bundle.mandatory_facts]
        high_value_keys = [f.key for f in bundle.high_value_facts]
        irrelevant_keys = [f.key for f in bundle.irrelevant_facts]

        self.assertIn("digest_item_title", mandatory_keys)
        self.assertIn("digest_item_source", high_value_keys)
        self.assertIn("digest_item_trial_n", high_value_keys)

        # 2. Check that all 14 unrelated digest items are routed to irrelevant facts
        unrelated_irrelevant = [k for k in irrelevant_keys if k.startswith("unrelated_digest_")]
        self.assertEqual(len(unrelated_irrelevant), 14)

        # 3. Formatted prompt context must NOT contain any unrelated digest items
        prompt_ctx = bundle.to_prompt_context()
        self.assertIn("Fluoride recall trial 2026", prompt_ctx)
        self.assertNotIn("Unrelated Dental Trend", prompt_ctx)
        self.assertTrue(bundle.verify_provenance())

    # =========================================================================
    # 2. TEST SPARSE CONTEXT
    # =========================================================================
    def test_sparse_context_handles_missing_fields_gracefully(self):
        """Minimal merchant profile: handle gracefully and track unavailable facts."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant(minimal=True))
        trg = TriggerContext.model_validate(self._sample_trigger())

        bundle = self.selector.select(category=cat, merchant=mer, trigger=trg)

        # Name is present
        mandatory_keys = [f.key for f in bundle.mandatory_facts]
        self.assertIn("merchant_name", mandatory_keys)

        # Owner name and languages are not set, should not crash
        self.assertTrue(bundle.verify_provenance())

    # =========================================================================
    # 3. TEST CONFLICTING CONTEXT
    # =========================================================================
    def test_conflicting_context_filters_expired_stale_offers(self):
        """Active offer selected in high_value; expired offer filtered to irrelevant & marked stale."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant(expired_offer=True))
        trg = TriggerContext.model_validate(self._sample_trigger())

        bundle = self.selector.select(category=cat, merchant=mer, trigger=trg)

        high_value_keys = [f.key for f in bundle.high_value_facts]
        self.assertIn("active_offer_off_act_001", high_value_keys)

        irrelevant_facts = {f.key: f for f in bundle.irrelevant_facts}
        self.assertIn("expired_offer_off_exp_002", irrelevant_facts)
        exp_fact = irrelevant_facts["expired_offer_off_exp_002"]
        self.assertTrue(exp_fact.is_stale)
        self.assertIn("stale", exp_fact.relevance_reason.lower())

        # Ensure expired offer never leaks into generation context
        prompt_ctx = bundle.to_prompt_context()
        self.assertIn("Preventive Scaling & Polish", prompt_ctx)
        self.assertNotIn("Diwali 2025", prompt_ctx)
        self.assertTrue(bundle.verify_provenance())

    # =========================================================================
    # 4. TEST CHANGED CONTEXT & VERSION PROVENANCE
    # =========================================================================
    def test_changed_context_updates_version_provenance(self):
        """Ingest v1, update to v2, verify selected facts carry v2 provenance."""
        # 1. Ingest v1
        cat_outcome = self.engine.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_category())
        self.assertTrue(cat_outcome.accepted)
        mer_outcome = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant())
        self.assertTrue(mer_outcome.accepted)
        trg_outcome = self.engine.ingest(ContextScope.TRIGGER, "trg_001", 1, self._sample_trigger())
        self.assertTrue(trg_outcome.accepted)

        bundle_v1, err = self.engine.select_context("m_001_drmeera", "trg_001")
        self.assertIsNone(err)
        self.assertIsNotNone(bundle_v1)
        self.assertEqual(bundle_v1.context_versions_used["merchant"], 1)
        mer_fact_v1 = next(f for f in bundle_v1.mandatory_facts if f.key == "merchant_name")
        self.assertEqual(mer_fact_v1.provenance.context_version, 1)

        # 2. Ingest v2 of merchant with updated performance and name
        updated_mer = self._sample_merchant()
        updated_mer["identity"]["name"] = "Dr. Meera's Advanced Dental Care"
        updated_mer["performance"]["delta_7d"]["calls_pct"] = -0.35
        outcome = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 2, updated_mer)
        self.assertTrue(outcome.accepted)

        # 3. Select context with updated engine state
        bundle_v2, err = self.engine.select_context("m_001_drmeera", "trg_001")
        self.assertIsNone(err)
        self.assertIsNotNone(bundle_v2)
        self.assertEqual(bundle_v2.context_versions_used["merchant"], 2)
        mer_fact_v2 = next(f for f in bundle_v2.mandatory_facts if f.key == "merchant_name")
        self.assertEqual(mer_fact_v2.provenance.context_version, 2)
        self.assertEqual(mer_fact_v2.value, "Dr. Meera's Advanced Dental Care")

        # Performance delta updated
        perf_fact = next(f for f in bundle_v2.high_value_facts if f.key == "perf_calls_delta_7d")
        self.assertEqual(perf_fact.value, -0.35)
        self.assertEqual(perf_fact.provenance.context_version, 2)
        self.assertTrue(bundle_v2.verify_provenance())

    # =========================================================================
    # 5. TEST IRRELEVANT CONTEXT & LEAK PREVENTION
    # =========================================================================
    def test_irrelevant_context_isolation_customer_vs_merchant(self):
        """Prevent internal merchant metrics from leaking into customer-facing messages."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(
            {
                "id": "trg_recall_001",
                "kind": "recall_due",
                "scope": "customer",
                "source": "internal",
                "urgency": 2,
                "merchant_id": "m_001_drmeera",
                "customer_id": "cust_999",
                "suppression_key": "recall:cust_999:2026",
                "expires_at": "2026-05-03T00:00:00Z",
                "payload": {"service_due": "scaling"},
            }
        )
        cust = CustomerContext.model_validate(self._sample_customer())

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
            customer=cust,
        )

        # Customer name & preferences should be selected
        mandatory_keys = [f.key for f in bundle.mandatory_facts]
        high_value_keys = [f.key for f in bundle.high_value_facts]
        self.assertIn("customer_name", mandatory_keys)
        self.assertIn("customer_preferred_slots", high_value_keys)

        # Merchant internal metrics MUST be quarantined in irrelevant_facts
        irrelevant_keys = [f.key for f in bundle.irrelevant_facts]
        self.assertIn("merchant_subscription_internal", irrelevant_keys)
        self.assertIn("merchant_crm_aggregate", irrelevant_keys)
        self.assertIn("merchant_internal_views_calls", irrelevant_keys)
        self.assertIn("category_peer_benchmarks", irrelevant_keys)

        # Verify nothing leaked into generation prompt
        prompt_ctx = bundle.to_prompt_context()
        self.assertNotIn("Pro", prompt_ctx)
        self.assertNotIn("high_risk_adult_count", prompt_ctx)
        self.assertNotIn("peer_stats", prompt_ctx)
        self.assertIn("Rahul Sharma", prompt_ctx)
        self.assertTrue(bundle.verify_provenance())

    # =========================================================================
    # 6. TEST MISSING CONTEXT TRACKING
    # =========================================================================
    def test_missing_context_tracking(self):
        """Explicit tracking of unavailable facts to prevent LLM hallucinations."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        # Customer-scoped trigger without customer context
        trg = TriggerContext.model_validate(
            {
                "id": "trg_recall_002",
                "kind": "recall_due",
                "scope": "customer",
                "source": "internal",
                "urgency": 4,
                "merchant_id": "m_001_drmeera",
                "suppression_key": "recall:cust_missing:2026",
                "expires_at": "2026-05-03T00:00:00Z",
            }
        )

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
            customer=None,  # Intentionally missing!
        )

        unavail_keys = {u.key: u for u in bundle.unavailable_facts}
        self.assertIn("customer_context", unavail_keys)
        self.assertEqual(unavail_keys["customer_context"].importance, "critical")
        self.assertEqual(unavail_keys["customer_context"].expected_scope, "customer")

    def test_missing_place_id_for_gbp_trigger(self):
        """Missing Google Place ID when GBP trigger fires must be flagged as unavailable."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer_dict = self._sample_merchant()
        mer_dict["identity"]["place_id"] = None
        mer = MerchantContext.model_validate(mer_dict)

        trg = TriggerContext.model_validate(
            {
                "id": "trg_gbp_001",
                "kind": "unverified_gbp",
                "scope": "merchant",
                "source": "internal",
                "urgency": 3,
                "merchant_id": "m_001_drmeera",
                "suppression_key": "gbp:unverified:2026",
                "expires_at": "2026-05-03T00:00:00Z",
            }
        )

        bundle = self.selector.select(category=cat, merchant=mer, trigger=trg)
        unavail_keys = {u.key: u for u in bundle.unavailable_facts}
        self.assertIn("merchant_place_id", unavail_keys)
        self.assertEqual(unavail_keys["merchant_place_id"].importance, "critical")

    # =========================================================================
    # 7. TEST PROVENANCE PRESERVATION
    # =========================================================================
    def test_all_selected_facts_retain_provenance(self):
        """Every fact in every tier must have valid, verifiable provenance."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant(expired_offer=True))
        trg = TriggerContext.model_validate(self._sample_trigger())

        bundle = self.selector.select(category=cat, merchant=mer, trigger=trg)

        all_facts = (
            bundle.mandatory_facts
            + bundle.high_value_facts
            + bundle.supporting_facts
            + bundle.irrelevant_facts
        )
        self.assertGreater(len(all_facts), 10)

        for fact in all_facts:
            self.assertIsNotNone(fact.provenance)
            self.assertTrue(fact.provenance.is_valid())
            self.assertGreaterEqual(fact.provenance.context_version, 1)
            self.assertTrue(len(fact.provenance.field_path) > 0)
            self.assertTrue(len(fact.provenance.entity_id) > 0)

        self.assertTrue(bundle.verify_provenance())

    # =========================================================================
    # 8. TEST CONVERSATIONAL ADAPTATION & REPETITION AVOIDANCE
    # =========================================================================
    def test_conversational_adaptation_avoids_repetition(self):
        """Demote already-pitched research topics in subsequent conversational turns."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger(top_item_id="d_fluoride_2026"))

        # Conversation where research was already pitched in turn 1
        conv = ConversationState(
            conversation_id="conv_repeat_test",
            merchant_id="m_001_drmeera",
            current_state=State.INTERESTED,
            last_message_at="2026-05-12T10:05:00Z",
            turns=[
                ConversationTurn(
                    turn_number=1,
                    from_role=Role.VERA,
                    message="Dr. Meera, JIDA Oct fluoride trial showed 38% reduction in caries.",
                    timestamp="2026-05-12T10:00:00Z",
                ),
                ConversationTurn(
                    turn_number=2,
                    from_role=Role.MERCHANT,
                    message="Sounds interesting, how much does the campaign cost?",
                    detected_intent="inquiry",
                    timestamp="2026-05-12T10:05:00Z",
                ),

            ],
        )

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
            conversation=conv,
            intent=IntentType.INQUIRY,
        )

        # Research topic should be demoted from mandatory to supporting
        mandatory_keys = [f.key for f in bundle.mandatory_facts]
        supporting_keys = [f.key for f in bundle.supporting_facts]

        self.assertNotIn("digest_item_title", mandatory_keys)
        self.assertIn("digest_item_title", supporting_keys)

        demoted_fact = next(f for f in bundle.supporting_facts if f.key == "digest_item_title")
        self.assertIn("Already pitched", demoted_fact.relevance_reason)

    def test_inbound_commitment_injects_action_fact(self):
        """Inbound commitment intent injects mandatory execution mode fact."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer = MerchantContext.model_validate(self._sample_merchant())
        trg = TriggerContext.model_validate(self._sample_trigger())

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
            intent=IntentType.COMMITMENT,
        )

        mandatory_keys = [f.key for f in bundle.mandatory_facts]
        self.assertIn("execution_mode", mandatory_keys)

    def test_merchant_review_themes_extracted_and_ranked(self):
        """Review themes are extracted, ranked by occurrences, and exposed as supporting facts."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer_dict = self._sample_merchant()
        mer_dict["review_themes"] = [
            {
                "theme": "gentle painless treatment",
                "sentiment": "positive",
                "occurrences_30d": 42,
                "common_quote": "Doctor Meera made root canal completely painless!",
            },
            {
                "theme": "clean and hygienic clinic",
                "sentiment": "pos",
                "occurrences_30d": 18,
                "common_quote": "Spotless instruments and courteous staff.",
            },
            {
                "theme": "waiting room delay",
                "sentiment": "neg",
                "occurrences_30d": 5,
                "common_quote": "Had to wait 20 minutes past appointment time.",
            },
        ]
        mer = MerchantContext.model_validate(mer_dict)
        trg = TriggerContext.model_validate(self._sample_trigger(kind="competitor_opened"))

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            trigger=trg,
        )

        supporting_facts = {f.key: f.value for f in bundle.supporting_facts}
        self.assertIn("top_review_theme", supporting_facts)
        self.assertEqual(supporting_facts["top_review_theme"], "gentle painless treatment")
        self.assertIn("top_review_quote", supporting_facts)
        self.assertEqual(
            supporting_facts["top_review_quote"],
            "Doctor Meera made root canal completely painless!",
        )

    def test_negative_review_themes_marked_irrelevant_for_customers(self):
        """Negative review themes are marked IRRELEVANT for customer-facing triggers to prevent leakage."""
        cat = CategoryContext.model_validate(self._sample_category())
        mer_dict = self._sample_merchant()
        mer_dict["review_themes"] = [
            {
                "theme": "long wait time",
                "sentiment": "negative",
                "occurrences_30d": 12,
                "common_quote": "Waited 30 mins.",
            },
        ]
        mer = MerchantContext.model_validate(mer_dict)
        cust = CustomerContext.model_validate(self._sample_customer())
        trg = TriggerContext.model_validate(
            self._sample_trigger(
                kind="customer_lapsed_soft",
                scope="customer",
            )
        )

        bundle = self.selector.select(
            category=cat,
            merchant=mer,
            customer=cust,
            trigger=trg,
        )

        irrelevant_keys = [f.key for f in bundle.irrelevant_facts]
        self.assertIn("internal_review_neg_long wait time", irrelevant_keys)
        supporting_keys = [f.key for f in bundle.supporting_facts]
        self.assertNotIn("internal_review_neg_long wait time", supporting_keys)


if __name__ == "__main__":
    unittest.main()
