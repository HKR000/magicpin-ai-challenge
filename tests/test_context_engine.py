"""Unit tests for Vera ContextEngine."""

import unittest
from vera.context.engine import ContextEngine
from vera.models.context_version import ContextScope
from vera.models.conversation import ConversationStage, Role


class TestContextEngine(unittest.TestCase):
    """Comprehensive test suite for ContextEngine."""

    def setUp(self):
        self.engine = ContextEngine()

    def _sample_dentist_category(self):
        return {
            "slug": "dentists",
            "display_name": "Dentists",
            "voice": {
                "tone": "peer_clinical",
                "register": "respectful_collegial",
                "code_mix": "hindi_english_natural",
                "vocab_allowed": ["scaling", "caries"],
                "vocab_taboo": ["guaranteed"],
                "salutation_examples": ["Dr. {first_name}"],
                "tone_examples": ["Worth a look"],
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
                    "id": "d_001",
                    "kind": "research",
                    "title": "Fluoride recall trial",
                    "source": "JIDA Oct 2026 p.14",
                    "summary": "38% caries reduction",
                }
            ],
            "patient_content_library": [],
            "seasonal_beats": [],
            "trend_signals": [],
        }

    def _sample_merchant(self, mid="m_001_drmeera", calls=18, views=2410):
        return {
            "merchant_id": mid,
            "category_slug": "dentists",
            "identity": {
                "name": "Dr. Meera's Dental Clinic",
                "city": "Delhi",
                "locality": "Lajpat Nagar",
                "verified": True,
                "languages": ["en", "hi"],
                "owner_first_name": "Meera",
            },
            "subscription": {
                "status": "active",
                "plan": "Pro",
                "days_remaining": 82,
            },
            "performance": {
                "window_days": 30,
                "views": views,
                "calls": calls,
                "directions": 45,
                "ctr": 0.021,
            },
            "offers": [
                {
                    "id": "o_001",
                    "title": "Dental Cleaning @ ₹299",
                    "status": "active",
                }
            ],
            "conversation_history": [],
            "customer_aggregate": {
                "total_unique_ytd": 540,
                "lapsed_180d_plus": 78,
                "retention_6mo_pct": 0.38,
            },
            "signals": ["ctr_below_peer_median"],
        }

    def _sample_customer(self, cid="c_001_priya", mid="m_001_drmeera"):
        return {
            "customer_id": cid,
            "merchant_id": mid,
            "identity": {
                "name": "Priya",
                "phone_redacted": "<phone>",
                "language_pref": "hi-en mix",
            },
            "relationship": {
                "first_visit": "2025-11-04",
                "last_visit": "2026-05-12",
                "visits_total": 4,
                "services_received": ["cleaning"],
            },
            "state": "lapsed_soft",
            "preferences": {
                "preferred_slots": "weekday_evening",
                "channel": "whatsapp",
            },
            "consent": {
                "opted_in_at": "2025-11-04",
                "scope": ["recall_reminders"],
            },
        }

    def _sample_trigger(self, tid="trg_001", mid="m_001_drmeera", cid=None, scope="merchant"):
        return {
            "id": tid,
            "scope": scope,
            "kind": "research_digest",
            "source": "external",
            "merchant_id": mid,
            "customer_id": cid,
            "payload": {"top_item_id": "d_001"},
            "urgency": 2,
            "suppression_key": "research:dentists:2026-W17",
            "expires_at": "2026-05-03T00:00:00Z",
        }

    # =========================================================================
    # 1. INITIAL CONTEXT INGESTION & RETRIEVAL
    # =========================================================================

    def test_initial_context_ingestion_and_retrieval(self):
        cat_data = self._sample_dentist_category()
        res = self.engine.ingest(
            scope=ContextScope.CATEGORY,
            context_id="dentists",
            version=1,
            payload=cat_data,
        )
        self.assertTrue(res.accepted)
        self.assertEqual(res.ack_id, "ack_dentists_v1")
        self.assertEqual(res.current_version, 1)

        # Retrieval
        cat = self.engine.get_category("dentists")
        self.assertIsNotNone(cat)
        self.assertEqual(cat.slug, "dentists")
        self.assertEqual(cat.voice.tone, "peer_clinical")

        # Counts
        counts = self.engine.get_counts()
        self.assertEqual(counts["category"], 1)
        self.assertEqual(counts["merchant"], 0)

    # =========================================================================
    # 2. VERSIONING & IDEMPOTENCY
    # =========================================================================

    def test_idempotent_repost_same_version(self):
        m_data = self._sample_merchant()
        res1 = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, m_data)
        self.assertTrue(res1.accepted)

        # Re-post same version
        res2 = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, m_data)
        self.assertTrue(res2.accepted)
        self.assertEqual(res2.reason, "idempotent_no_op")
        self.assertEqual(res2.current_version, 1)

    def test_stale_update_rejection_409(self):
        m_data = self._sample_merchant()
        # Ingest version 2
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 2, m_data)

        # Attempt to ingest version 1 (stale)
        res_stale = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, m_data)
        self.assertFalse(res_stale.accepted)
        self.assertEqual(res_stale.reason, "stale_version")
        self.assertEqual(res_stale.current_version, 2)

    # =========================================================================
    # 3. CONTEXT UPDATE & CHANGE TRACKING (DELTA DETECTION)
    # =========================================================================

    def test_higher_version_update_and_change_tracking(self):
        m_data_v1 = self._sample_merchant(calls=18, views=2410)
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, m_data_v1)

        # Update with performance shift (calls dropped to 9, views increased to 3000)
        m_data_v2 = self._sample_merchant(calls=9, views=3000)
        res_v2 = self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 2, m_data_v2)

        self.assertTrue(res_v2.accepted)
        self.assertEqual(res_v2.current_version, 2)

        # Verify changed fields were accurately identified
        changed_paths = {change.field_path: (change.old_value, change.new_value) for change in res_v2.changed_fields}
        self.assertIn("performance.calls", changed_paths)
        self.assertEqual(changed_paths["performance.calls"], (18, 9))
        self.assertIn("performance.views", changed_paths)
        self.assertEqual(changed_paths["performance.views"], (2410, 3000))

        # Check retrieval reflects v2
        m = self.engine.get_merchant("m_001_drmeera")
        self.assertEqual(m.performance.calls, 9)
        self.assertEqual(m.performance.views, 3000)

        # Check stored entity history
        stored = self.engine.get_stored_entity(ContextScope.MERCHANT, "m_001_drmeera")
        self.assertEqual(stored.version, 2)
        self.assertEqual(stored.version_history, [1])

    # =========================================================================
    # 4. PROVENANCE TRACKING
    # =========================================================================

    def test_provenance_tracking(self):
        m_data = self._sample_merchant(calls=18)
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, m_data, source="phase1_warmup")

        # Query provenance
        prov_calls = self.engine.provenance.get_provenance("m_001_drmeera", "performance.calls")
        self.assertEqual(len(prov_calls), 1)
        self.assertEqual(prov_calls[0].value, 18)
        self.assertEqual(prov_calls[0].context_version, 1)
        self.assertEqual(prov_calls[0].source, "phase1_warmup")

        # Now update to v2
        m_data_v2 = self._sample_merchant(calls=35)
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 2, m_data_v2, source="adaptive_injection")

        # Provenance should reflect new version and source
        prov_calls_v2 = self.engine.provenance.get_provenance("m_001_drmeera", "performance.calls")
        self.assertEqual(prov_calls_v2[0].value, 35)
        self.assertEqual(prov_calls_v2[0].context_version, 2)
        self.assertEqual(prov_calls_v2[0].source, "adaptive_injection")

        # Search by value
        hits = self.engine.provenance.search_value("Dr. Meera's Dental Clinic")
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].field_path, "identity.name")

    # =========================================================================
    # 5. MULTIPLE ENTITIES & CONTEXT ASSEMBLY
    # =========================================================================

    def test_context_assembly_complete(self):
        # Ingest Category
        self.engine.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_dentist_category())
        # Ingest Merchant
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant("m_001_drmeera"))
        # Ingest Trigger
        self.engine.ingest(ContextScope.TRIGGER, "trg_001", 1, self._sample_trigger("trg_001", "m_001_drmeera"))

        bundle, err = self.engine.assemble_context(
            merchant_id="m_001_drmeera",
            trigger_id="trg_001",
        )
        self.assertIsNone(err)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.category.slug, "dentists")
        self.assertEqual(bundle.merchant.merchant_id, "m_001_drmeera")
        self.assertEqual(bundle.trigger.id, "trg_001")
        self.assertIsNone(bundle.customer)

    def test_context_assembly_with_customer(self):
        self.engine.ingest(ContextScope.CATEGORY, "dentists", 1, self._sample_dentist_category())
        self.engine.ingest(ContextScope.MERCHANT, "m_001_drmeera", 1, self._sample_merchant("m_001_drmeera"))
        self.engine.ingest(ContextScope.CUSTOMER, "c_001_priya", 1, self._sample_customer("c_001_priya", "m_001_drmeera"))
        self.engine.ingest(
            ContextScope.TRIGGER,
            "trg_002",
            1,
            self._sample_trigger("trg_002", "m_001_drmeera", cid="c_001_priya", scope="customer"),
        )

        bundle, err = self.engine.assemble_context(
            merchant_id="m_001_drmeera",
            trigger_id="trg_002",
            customer_id="c_001_priya",
        )
        self.assertIsNone(err)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.customer.customer_id, "c_001_priya")

    def test_context_assembly_missing_entity_errors(self):
        # Missing trigger
        bundle, err = self.engine.assemble_context(merchant_id="m_missing", trigger_id="trg_missing")
        self.assertIsNone(bundle)
        self.assertIn("Trigger 'trg_missing' not found", err)

        # Trigger exists but merchant missing
        self.engine.ingest(ContextScope.TRIGGER, "trg_solo", 1, self._sample_trigger("trg_solo", "m_ghost"))
        bundle2, err2 = self.engine.assemble_context(merchant_id="m_ghost", trigger_id="trg_solo")
        self.assertIsNone(bundle2)
        self.assertIn("Merchant 'm_ghost' not found", err2)

    def test_multiple_merchants_and_triggers_isolation(self):
        # Ingest 3 merchants
        for i in range(1, 4):
            mid = f"m_00{i}"
            self.engine.ingest(ContextScope.MERCHANT, mid, 1, self._sample_merchant(mid, calls=i * 10))

        counts = self.engine.get_counts()
        self.assertEqual(counts["merchant"], 3)
        self.assertEqual(self.engine.get_merchant("m_001").performance.calls, 10)
        self.assertEqual(self.engine.get_merchant("m_003").performance.calls, 30)

    # =========================================================================
    # 6. CONVERSATION STATE MANAGEMENT
    # =========================================================================

    def test_conversation_lifecycle_in_context_engine(self):
        conv = self.engine.create_or_get_conversation(
            conversation_id="conv_test_1",
            merchant_id="m_001_drmeera",
            trigger_id="trg_001",
        )
        self.assertEqual(conv.stage, ConversationStage.INITIATED)
        self.assertEqual(conv.auto_reply_count, 0)

        # Add outbound turn from vera
        turn1 = self.engine.add_turn(
            conversation_id="conv_test_1",
            from_role=Role.VERA,
            message="Hi Dr. Meera",
            action_taken="send",
        )
        self.assertEqual(turn1.turn_number, 1)

        # Inbound merchant turn
        turn2 = self.engine.add_turn(
            conversation_id="conv_test_1",
            from_role=Role.MERCHANT,
            message="Yes please",
            detected_intent="commitment",
        )
        self.assertEqual(turn2.turn_number, 2)

        # Update stage
        self.engine.update_conversation_stage("conv_test_1", ConversationStage.ACTION_COMMITTED)
        self.assertEqual(self.engine.get_conversation("conv_test_1").stage, ConversationStage.ACTION_COMMITTED)

        # Auto reply counting
        c1 = self.engine.increment_auto_reply_count("conv_test_1")
        c2 = self.engine.increment_auto_reply_count("conv_test_1")
        self.assertEqual(c2, 2)
        self.engine.reset_auto_reply_count("conv_test_1")
        self.assertEqual(self.engine.get_conversation("conv_test_1").auto_reply_count, 0)


if __name__ == "__main__":
    unittest.main()
