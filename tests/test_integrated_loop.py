"""Unit and integration test suite for Level 11 Integrated Vera Loop."""

import unittest

from vera.models.context_version import ContextScope
from vera.models.conversation import State
from vera.models.decision import CommunicationObjective, ProposedActionType
from vera.models.intent import IntentType
from vera.orchestrator import Vera


class TestIntegratedVeraLoop(unittest.TestCase):
    """End-to-end integration tests for the unified Vera Loop."""

    def setUp(self):
        self.vera = Vera()

        # Seed realistic category, merchant, trigger, and customer
        self.cat_data = {
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
                    "id": "den_clean_499",
                    "title": "Preventive Scaling & Polish",
                    "value": "499",
                    "audience": "all",
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

        self.mer_data = {
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

        self.trg_research = {
            "id": "trg_research_001",
            "kind": "research_digest",
            "scope": "merchant",
            "source": "internal",
            "urgency": 2,
            "merchant_id": "m_001_drmeera",
            "suppression_key": "research:dentists:2026-W17",
            "expires_at": "2026-05-03T00:00:00Z",
            "payload": {"top_item_id": "d_fluoride_2026"},
        }

        self.cust_data = {
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

        # Ingest baseline seed context
        self.vera.ingest_context(ContextScope.CATEGORY, "dentists", 1, self.cat_data)
        self.vera.ingest_context(ContextScope.MERCHANT, "m_001_drmeera", 1, self.mer_data)
        self.vera.ingest_context(ContextScope.TRIGGER, "trg_research_001", 1, self.trg_research)
        self.vera.ingest_context(ContextScope.CUSTOMER, "cust_999", 1, self.cust_data)

    # =========================================================================
    # 1. PROACTIVE PIPELINE: trigger -> decision -> message
    # =========================================================================
    def test_proactive_pipeline(self):
        """Proactive trigger fires: trigger -> context -> decision -> message."""
        composed, decision, err = self.vera.handle_proactive_trigger(
            trigger_id="trg_research_001",
            conversation_id="conv_proactive_test",
        )

        self.assertIsNone(err)
        self.assertIsNotNone(decision)
        self.assertIsNotNone(composed)

        # State transition check
        conv = self.vera.context_engine.get_conversation("conv_proactive_test")
        self.assertIsNotNone(conv)
        self.assertEqual(conv.current_state, State.PITCHED)
        self.assertEqual(len(conv.turns), 1)

        # Decision check
        self.assertEqual(decision.objective, CommunicationObjective.PITCH_RESEARCH_CAMPAIGN)
        self.assertEqual(decision.proposed_action.action_type, ProposedActionType.PITCH_OFFER)

        # Message check
        self.assertTrue(composed.is_validated)
        self.assertIn("Dr. Meera", composed.body)
        self.assertIn("JIDA Oct 2026", composed.body)
        self.assertIn("38% caries reduction", composed.body)

    # =========================================================================
    # 2. REACTIVE PIPELINE: message -> intent -> state -> decision -> response
    # =========================================================================
    def test_reactive_pipeline(self):
        """Inbound question from merchant: message -> intent -> state -> decision -> response."""
        # Initial proactive pitch
        conv_id = "conv_reactive_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        # Inbound question from merchant
        inbound_msg = "Can you clarify who qualifies for this program?"
        composed, decision, trans = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=inbound_msg,
            override_intent=IntentType.INQUIRY,
        )

        self.assertIsNotNone(trans)
        self.assertEqual(trans.user_intent, IntentType.INQUIRY)
        self.assertEqual(trans.to_state, State.QUESTION)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.objective, CommunicationObjective.ANSWER_MERCHANT_INQUIRY)

        self.assertIsNotNone(composed)
        self.assertTrue(composed.is_validated)
        self.assertIn("campaign", composed.body.lower())

    # =========================================================================
    # 3. ACCEPTANCE: pitch -> acceptance -> correct action -> stopping state
    # =========================================================================
    def test_acceptance_flow(self):
        """Merchant accepts pitch: pitch -> commitment -> execute campaign -> terminal state."""
        conv_id = "conv_acceptance_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        # Merchant says "Yes, go ahead and schedule this!"
        accept_msg = "Yes, go ahead and schedule this for our patients!"
        composed, decision, trans = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=accept_msg,
        )

        self.assertEqual(trans.user_intent, IntentType.COMMITMENT)
        self.assertEqual(trans.to_state, State.ACTION_PENDING)

        self.assertEqual(decision.objective, CommunicationObjective.EXECUTE_COMMITTED_ACTION)
        self.assertEqual(decision.proposed_action.action_type, ProposedActionType.EXECUTE_CAMPAIGN)
        self.assertTrue(decision.stop_required)

        self.assertIsNotNone(composed)
        self.assertIn("scheduled the campaign", composed.body)

    # =========================================================================
    # 4. QUESTION: pitch -> question -> answer -> next state
    # =========================================================================
    def test_question_flow(self):
        """Merchant asks pricing question: pitch -> question -> quote -> next state."""
        conv_id = "conv_question_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        # Merchant asks "How much does it cost?"
        q_msg = "What is the pricing for this?"
        composed, decision, trans = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=q_msg,
        )

        self.assertEqual(trans.user_intent, IntentType.INQUIRY)
        self.assertEqual(trans.to_state, State.QUESTION)

        self.assertEqual(decision.objective, CommunicationObjective.ANSWER_MERCHANT_INQUIRY)
        self.assertEqual(decision.proposed_action.action_type, ProposedActionType.QUOTE_PRICING)
        self.assertFalse(decision.stop_required)

        self.assertIsNotNone(composed)
        self.assertIn("pricing", composed.body.lower())
        self.assertIn("Reply YES to proceed", composed.body)

    # =========================================================================
    # 5. REJECTION: pitch -> rejection -> appropriate stop
    # =========================================================================
    def test_rejection_flow(self):
        """Merchant rejects proposal: pitch -> rejection -> polite close -> stop."""
        conv_id = "conv_rejection_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        reject_msg = "No thanks, we are not interested right now."
        composed, decision, trans = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=reject_msg,
            override_intent=IntentType.REJECTION,
        )

        self.assertEqual(trans.user_intent, IntentType.REJECTION)
        self.assertEqual(trans.to_state, State.REJECTED)

        self.assertEqual(decision.objective, CommunicationObjective.HANDLE_REJECTION)
        self.assertTrue(decision.stop_required)

        self.assertIsNotNone(composed)
        self.assertIn("No problem at all", composed.body)

    # =========================================================================
    # 6. AUTO-REPLY: pitch -> generic auto-reply -> correct handling
    # =========================================================================
    def test_auto_reply_handling(self):
        """Auto-reply Turn 1 backs off silently; Turn 2 halts loop."""
        conv_id = "conv_autoreply_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        # Turn 1: Out of office automated reply
        ooo_msg = "Thank you for contacting Dr. Meera Dental. We are currently away from the clinic until Monday."
        composed1, decision1, trans1 = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=ooo_msg,
        )

        # Must back off silently without sending a message
        self.assertEqual(trans1.action, "wait")
        self.assertEqual(trans1.to_state, State.WAITING)
        self.assertIsNone(composed1)
        self.assertFalse(decision1.response_required)
        self.assertFalse(decision1.stop_required)

        # Turn 2: Second consecutive automated reply
        composed2, decision2, trans2 = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message=ooo_msg,
        )

        # Loop broken: state transitions to STOPPED
        self.assertEqual(trans2.action, "end")
        self.assertEqual(trans2.to_state, State.STOPPED)
        self.assertIsNone(composed2)
        self.assertTrue(decision2.stop_required)

    # =========================================================================
    # 7. CONTEXT UPDATE: conversation -> context update -> behavior adaptation
    # =========================================================================
    def test_context_update_adapts_behavior(self):
        """Ingesting context v2 immediately changes decisions and message output."""
        conv_id = "conv_context_update_test"

        # Baseline: initial pitch cites 14 days remaining
        trg_renewal = {
            "id": "trg_renew_001",
            "kind": "renewal_due",
            "scope": "merchant",
            "source": "internal",
            "urgency": 3,
            "merchant_id": "m_001_drmeera",
            "suppression_key": "renew:dentists:2026",
            "expires_at": "2026-05-03T00:00:00Z",
            "payload": {},
        }
        self.vera.ingest_context(ContextScope.TRIGGER, "trg_renew_001", 1, trg_renewal)

        comp1, dec1, err1 = self.vera.handle_proactive_trigger("trg_renew_001", conversation_id=conv_id)
        self.assertIn("14 days remaining", comp1.body)
        self.assertEqual(dec1.selected_facts.context_versions_used["merchant"], 1)

        # Push context v2 with only 2 days remaining (critical urgency!)
        updated_mer = dict(self.mer_data)
        updated_mer["subscription"] = {
            "plan": "Pro",
            "status": "expiring",
            "days_remaining": 2,
        }
        outcome = self.vera.ingest_context(ContextScope.MERCHANT, "m_001_drmeera", 2, updated_mer)
        self.assertTrue(outcome.accepted)

        # Subsequent reactive inquiry immediately reflects v2 context!
        comp2, dec2, trans2 = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message="When exactly is my renewal due?",
        )

        self.assertIsNotNone(dec2)
        self.assertEqual(dec2.selected_facts.context_versions_used["merchant"], 2)
        days_fact = next(f for f in dec2.selected_facts.high_value_facts if f.key == "subscription_days_remaining")
        self.assertEqual(days_fact.value, 2)
        self.assertEqual(days_fact.provenance.context_version, 2)

    # =========================================================================
    # 8. REPETITION: message -> follow-up -> materially new response
    # =========================================================================
    def test_repetition_avoidance_in_multi_turn(self):
        """Subsequent turns avoid repeating previously pitched study text."""
        conv_id = "conv_repetition_test"
        comp1, dec1, err1 = self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)
        self.assertIn("JIDA Oct 2026", comp1.body)

        # Merchant asks a question
        comp2, dec2, trans2 = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message="Can you explain more about this campaign?",
            override_intent=IntentType.INQUIRY,
        )

        # Follow up message must NOT repeat the JIDA citation
        self.assertIsNotNone(comp2)
        self.assertNotIn("JIDA Oct 2026", comp2.body)
        self.assertIn("campaign", comp2.body.lower())
        self.assertNotEqual(comp1.body, comp2.body)

    # =========================================================================
    # 9. HOSTILE OPT-OUT
    # =========================================================================
    def test_hostile_opt_out_immediate_stop(self):
        """Hostile opt out stops communication immediately and confirms."""
        conv_id = "conv_optout_test"
        self.vera.handle_proactive_trigger("trg_research_001", conversation_id=conv_id)

        comp, dec, trans = self.vera.handle_reactive_message(
            conversation_id=conv_id,
            message="STOP! STOP MESSAGING ME! REMOVE MY NUMBER NOW!",
        )

        self.assertEqual(trans.to_state, State.STOPPED)
        self.assertTrue(dec.stop_required)
        self.assertEqual(dec.objective, CommunicationObjective.CONFIRM_OPT_OUT)
        self.assertIn("opted you out", comp.body)

    # =========================================================================
    # 10. TEARDOWN ENDPOINT
    # =========================================================================
    def test_teardown_endpoint_wipes_context_and_state(self):
        """POST /v1/teardown wipes all loaded contexts and conversation state."""
        from starlette.testclient import TestClient
        from bot import app, auto_load_seeds

        client = TestClient(app)

        # Verify healthz endpoint is reachable
        h_before = client.get("/v1/healthz")
        self.assertEqual(h_before.status_code, 200)

        # Issue teardown
        td_resp = client.post("/v1/teardown", json={"wipe": True})
        self.assertEqual(td_resp.status_code, 200)
        td_json = td_resp.json()
        self.assertTrue(td_json.get("accepted"))
        self.assertTrue(td_json.get("wiped"))

        # Verify contexts wiped to zero
        h_after = client.get("/v1/healthz")
        self.assertEqual(h_after.status_code, 200)
        counts = h_after.json().get("contexts_loaded", {})
        self.assertEqual(counts.get("category", 0), 0)
        self.assertEqual(counts.get("merchant", 0), 0)
        self.assertEqual(counts.get("customer", 0), 0)
        self.assertEqual(counts.get("trigger", 0), 0)

        # Reload seeds for any subsequent tests/server usage
        auto_load_seeds()

    # =========================================================================
    # 11. CUSTOMER CONSENT SCOPE ENFORCEMENT IN TICK
    # =========================================================================
    def test_customer_consent_scope_enforcement_in_tick(self):
        """POST /v1/tick enforces customer consent scopes, suppressing unauthorized marketing outreach."""
        from starlette.testclient import TestClient
        from bot import app, engine, vera

        client = TestClient(app)

        # Ingest category and merchant into server engine
        engine.ingest("category", "dentists", 1, self.cat_data)
        engine.ingest("merchant", "m_001_drmeera", 1, self.mer_data)

        # 1. Ingest customer with only reminders consent (no promotional/marketing)
        cust_reminders = {
            "customer_id": "c_rem_loop",
            "merchant_id": "m_001_drmeera",
            "identity": {"name": "RemindersOnly"},
            "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 2},
            "state": "active",
            "preferences": {"reminder_opt_in": True},
            "consent": {"opted_in_at": "2025-11-04", "scope": ["reminders"]},
        }
        engine.ingest("customer", "c_rem_loop", 1, cust_reminders)

        # 2. Ingest customer with promotional marketing consent
        cust_promo = {
            "customer_id": "c_promo_loop",
            "merchant_id": "m_001_drmeera",
            "identity": {"name": "PromoAllowed"},
            "relationship": {"first_visit": "2025-11-04", "last_visit": "2026-05-12", "visits_total": 2},
            "state": "active",
            "preferences": {"reminder_opt_in": True},
            "consent": {"opted_in_at": "2025-11-04", "scope": ["promotional_offers"]},
        }
        engine.ingest("customer", "c_promo_loop", 1, cust_promo)

        # 3. Create promotional trigger targeting reminders-only customer (MUST BE SUPPRESSED)
        trg_unauthorized = {
            "id": "trg_unauth_promo",
            "scope": "customer",
            "kind": "promotional_offer",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "customer_id": "c_rem_loop",
            "payload": {"offer": "50% off teeth whitening"},
            "urgency": 2,
            "suppression_key": "promo:c_rem_loop",
            "expires_at": "2026-12-31T00:00:00Z",
        }
        engine.ingest("trigger", "trg_unauth_promo", 1, trg_unauthorized)

        # 4. Create service recall trigger targeting reminders customer (MUST BE DISPATCHED)
        trg_authorized_recall = {
            "id": "trg_auth_recall",
            "scope": "customer",
            "kind": "recall_due",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "customer_id": "c_rem_loop",
            "payload": {"service_due": "cleaning"},
            "urgency": 3,
            "suppression_key": "recall:c_rem_loop",
            "expires_at": "2026-12-31T00:00:00Z",
        }
        engine.ingest("trigger", "trg_auth_recall", 1, trg_authorized_recall)

        # 5. Create promotional trigger targeting promo customer (MUST BE DISPATCHED)
        trg_authorized_promo = {
            "id": "trg_auth_promo",
            "scope": "customer",
            "kind": "promotional_offer",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "customer_id": "c_promo_loop",
            "payload": {"offer": "Summer festive package"},
            "urgency": 1,
            "suppression_key": "promo:c_promo_loop",
            "expires_at": "2026-12-31T00:00:00Z",
        }
        engine.ingest("trigger", "trg_auth_promo", 1, trg_authorized_promo)

        # Call POST /v1/tick with all 3 triggers
        resp = client.post(
            "/v1/tick",
            json={
                "now": "2026-06-01T10:00:00Z",
                "available_triggers": ["trg_unauth_promo", "trg_auth_recall", "trg_auth_promo"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        actions = resp.json().get("actions", [])
        dispatched_trigger_ids = [a["trigger_id"] for a in actions]

        # trg_unauth_promo MUST NOT be dispatched due to missing marketing consent
        self.assertNotIn("trg_unauth_promo", dispatched_trigger_ids)

        # trg_auth_recall should be dispatched as customer opted in to reminders
        self.assertIn("trg_auth_recall", dispatched_trigger_ids)


if __name__ == "__main__":
    unittest.main()
