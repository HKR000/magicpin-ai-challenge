"""Comprehensive unit and integration tests for Level 6 Conversation State Machine."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from vera.context.engine import ContextEngine
from vera.conversation.machine import ConversationStateMachine
from vera.conversation.persistence import ConversationStore
from vera.conversation.states import (
    ACTIVE_STATES,
    STATE_DESCRIPTIONS,
    TERMINAL_STATES,
    State,
    is_active_state,
    is_terminal_state,
)
from vera.conversation.transitions import (
    InvalidTransitionError,
    TransitionInput,
    TransitionResult,
)
from vera.intent.classifier import IntentClassifier
from vera.models.conversation import (
    ConversationStage,
    ConversationState,
    ConversationTurn,
    Role,
)
from vera.models.intent import IntentType


class TestConversationStates(unittest.TestCase):
    """Test suite for state definitions, categorization, and helper predicates."""

    def test_all_required_states_defined(self):
        """All 9 challenge states must be explicitly present with correct enum values."""
        expected_states = {
            "INITIAL",
            "PITCHED",
            "WAITING",
            "INTERESTED",
            "QUESTION",
            "ACTION_PENDING",
            "COMPLETED",
            "REJECTED",
            "STOPPED",
        }
        actual_states = {s.value for s in State}
        self.assertEqual(expected_states, actual_states)

    def test_terminal_and_active_partitioning(self):
        """States must be cleanly partitioned into terminal and active subsets."""
        self.assertEqual(
            TERMINAL_STATES,
            {State.COMPLETED, State.REJECTED, State.STOPPED},
        )
        self.assertEqual(
            ACTIVE_STATES,
            {
                State.INITIAL,
                State.PITCHED,
                State.WAITING,
                State.INTERESTED,
                State.QUESTION,
                State.ACTION_PENDING,
            },
        )
        # Disjoint check
        self.assertEqual(len(TERMINAL_STATES.intersection(ACTIVE_STATES)), 0)
        # Union equals all states
        self.assertEqual(TERMINAL_STATES.union(ACTIVE_STATES), set(State))

    def test_predicates(self):
        """Test is_terminal_state and is_active_state helpers."""
        self.assertTrue(is_terminal_state(State.COMPLETED))
        self.assertTrue(is_terminal_state(State.REJECTED))
        self.assertTrue(is_terminal_state(State.STOPPED))
        self.assertTrue(is_terminal_state("stopped"))
        self.assertFalse(is_terminal_state(State.PITCHED))

        self.assertTrue(is_active_state(State.INITIAL))
        self.assertTrue(is_active_state(State.PITCHED))
        self.assertTrue(is_active_state(State.WAITING))
        self.assertTrue(is_active_state(State.INTERESTED))
        self.assertTrue(is_active_state(State.QUESTION))
        self.assertTrue(is_active_state(State.ACTION_PENDING))
        self.assertFalse(is_active_state(State.STOPPED))
        self.assertFalse(is_active_state("unknown_state"))

    def test_state_descriptions(self):
        """Every defined state must have an explicit explanatory description."""
        for state in State:
            self.assertIn(state, STATE_DESCRIPTIONS)
            self.assertGreater(len(STATE_DESCRIPTIONS[state]), 10)


class TestConversationTransitions(unittest.TestCase):
    """Test suite for valid and deterministic transitions."""

    def setUp(self):
        self.sm = ConversationStateMachine(strict=True)

    # 1. Proactive Send from INITIAL
    def test_proactive_send_transitions_to_pitched(self):
        inp = TransitionInput(
            current_state=State.INITIAL,
            user_intent=IntentType.UNKNOWN,
            is_proactive_send=True,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.from_state, State.INITIAL)
        self.assertEqual(res.to_state, State.PITCHED)
        self.assertEqual(res.action, "send")

    # 2. Acceptance / Commitment
    def test_acceptance_transitions_to_action_pending(self):
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.COMMITMENT,
            raw_message="Yes please update our Google profile",
            turn_number=2,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.ACTION_PENDING)
        self.assertEqual(res.action, "send")

    def test_acceptance_from_interested_and_question(self):
        for start_state in [State.INTERESTED, State.QUESTION, State.WAITING]:
            inp = TransitionInput(
                current_state=start_state,
                user_intent=IntentType.COMMITMENT,
                raw_message="Let's do it",
            )
            res = self.sm.evaluate_transition(inp)
            self.assertTrue(res.valid)
            self.assertEqual(res.to_state, State.ACTION_PENDING)

    # 3. Rejection
    def test_rejection_transitions_to_rejected(self):
        state = ConversationState(
            conversation_id="conv_rej_1",
            merchant_id="m_001",
            current_state=State.PITCHED,
            last_message_at="2026-04-26T10:00:00Z",
        )
        res = self.sm.reject(state, rationale="Merchant declined promotion")
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.REJECTED)
        self.assertEqual(res.action, "end")

    # 4. Questions & Clarification
    def test_question_transitions_to_question(self):
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.INQUIRY,
            raw_message="How much will the dental varnish campaign cost?",
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.QUESTION)
        self.assertEqual(res.action, "send")

    def test_clarification_in_question_state(self):
        inp = TransitionInput(
            current_state=State.QUESTION,
            user_intent=IntentType.INQUIRY,
            raw_message="Which photos will be uploaded to GBP?",
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.QUESTION)
        self.assertEqual(res.action, "send")

    # 5. Interest
    def test_interest_transitions_to_interested(self):
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.INTEREST,
            raw_message="Sounds interesting, tell me more details",
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.INTERESTED)
        self.assertEqual(res.action, "send")

    # 6. Waiting & Friction Objections
    def test_waiting_on_qualification_friction(self):
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.QUALIFICATION,
            raw_message="Busy right now with a patient, call back later",
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.WAITING)
        self.assertEqual(res.action, "wait")
        self.assertGreater(res.wait_seconds, 0)

    # 7. Action Pending to Completed
    def test_action_completion(self):
        state = ConversationState(
            conversation_id="conv_comp_1",
            merchant_id="m_001",
            current_state=State.ACTION_PENDING,
            last_message_at="2026-04-26T10:00:00Z",
        )
        res = self.sm.complete_action(state, rationale="GBP photos updated successfully")
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.COMPLETED)
        self.assertEqual(res.action, "send")


class TestInvalidTransitions(unittest.TestCase):
    """Test suite ensuring illegal transitions and terminal boundaries are strictly guarded."""

    def setUp(self):
        self.sm_strict = ConversationStateMachine(strict=True)
        self.sm_lenient = ConversationStateMachine(strict=False)

    def test_transition_from_completed_terminal_state(self):
        """Attempting to transition from COMPLETED must fail."""
        inp = TransitionInput(
            current_state=State.COMPLETED,
            user_intent=IntentType.COMMITMENT,
            raw_message="One more thing",
        )
        with self.assertRaises(InvalidTransitionError) as ctx:
            self.sm_strict.evaluate_transition(inp)
        self.assertIn("terminal state COMPLETED", str(ctx.exception))

        # Lenient mode returns invalid result with action end
        res = self.sm_lenient.evaluate_transition(inp)
        self.assertFalse(res.valid)
        self.assertEqual(res.to_state, State.COMPLETED)
        self.assertEqual(res.action, "end")

    def test_transition_from_stopped_terminal_state(self):
        """Attempting to transition from STOPPED must fail."""
        inp = TransitionInput(
            current_state=State.STOPPED,
            user_intent=IntentType.INQUIRY,
            raw_message="Wait, are you still there?",
        )
        with self.assertRaises(InvalidTransitionError):
            self.sm_strict.evaluate_transition(inp)

        res = self.sm_lenient.evaluate_transition(inp)
        self.assertFalse(res.valid)
        self.assertEqual(res.to_state, State.STOPPED)
        self.assertEqual(res.action, "end")

    def test_transition_from_rejected_terminal_state(self):
        """Attempting to transition from REJECTED must fail."""
        inp = TransitionInput(
            current_state=State.REJECTED,
            user_intent=IntentType.INTEREST,
            raw_message="Actually maybe I am interested",
        )
        with self.assertRaises(InvalidTransitionError):
            self.sm_strict.evaluate_transition(inp)

        res = self.sm_lenient.evaluate_transition(inp)
        self.assertFalse(res.valid)
        self.assertEqual(res.to_state, State.REJECTED)
        self.assertEqual(res.action, "end")

    def test_invalid_complete_action_from_initial(self):
        """Cannot call complete_action on a state that is not ACTION_PENDING."""
        state = ConversationState(
            conversation_id="conv_err_1",
            merchant_id="m_001",
            current_state=State.INITIAL,
            last_message_at="2026-04-26T10:00:00Z",
        )
        with self.assertRaises(InvalidTransitionError):
            self.sm_strict.complete_action(state)

        res = self.sm_lenient.complete_action(state)
        self.assertFalse(res.valid)
        self.assertEqual(res.action, "end")


class TestStoppingStatesAndAutoReplies(unittest.TestCase):
    """Test suite covering generic auto-replies, hostility opt-outs, and repeated spam."""

    def setUp(self):
        self.sm = ConversationStateMachine(strict=False)

    def test_hostile_opt_out_stopping_state(self):
        """Opt-outs must immediately trigger STOPPED with action=end."""
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.HOSTILE_OPT_OUT,
            raw_message="Stop messaging me! Unsubscribe.",
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.STOPPED)
        self.assertEqual(res.action, "end")
        self.assertIn("hostility or explicit opt-out", res.rationale)

    def test_generic_auto_reply_turn_one_waits(self):
        """First auto-reply detected must pause and back off into WAITING."""
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.AUTO_REPLY,
            raw_message="Thank you for contacting us. We will respond shortly.",
            auto_reply_count=0,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.WAITING)
        self.assertEqual(res.action, "wait")
        self.assertEqual(res.wait_seconds, 900)

    def test_generic_auto_reply_turn_two_stops_turn_wastage(self):
        """Repeated canned auto-reply (turn 2+) must immediately transition to STOPPED."""
        inp = TransitionInput(
            current_state=State.WAITING,
            user_intent=IntentType.AUTO_REPLY,
            raw_message="Thank you for contacting us. We will respond shortly.",
            auto_reply_count=1,  # Already had 1 auto reply
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.STOPPED)
        self.assertEqual(res.action, "end")
        self.assertIn("prevent auto-reply turn wastage", res.rationale)

    def test_consecutive_repeated_user_messages_spam_breaker(self):
        """Repeating identical message 3+ times triggers loop breaker and transitions to STOPPED."""
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.INQUIRY,
            raw_message="what is this?",
            consecutive_repeated_messages=3,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.to_state, State.STOPPED)
        self.assertEqual(res.action, "end")
        self.assertIn("identical message threshold reached", res.rationale)


class TestContextUpdatesReflected(unittest.TestCase):
    """Test suite ensuring that current context facts and updates influence transitions."""

    def setUp(self):
        self.sm = ConversationStateMachine(strict=True)

    def test_context_subscription_lapsed_blocks_direct_execution(self):
        """If merchant subscription is lapsed in context, commitment transitions to question/qualification."""
        context_data = {
            "merchant": {
                "merchant_id": "m_001",
                "subscription": {
                    "status": "lapsed",
                    "days_remaining": 0,
                },
            },
            "version": 3,
        }
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.COMMITMENT,
            raw_message="Yes update my profile",
            context_data=context_data,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        # Instead of ACTION_PENDING, routes to QUESTION for renewal qualification
        self.assertEqual(res.to_state, State.QUESTION)
        self.assertEqual(res.context_updates_applied.get("subscription_status"), "lapsed")
        self.assertIn("subscription is lapsed", res.rationale)

    def test_context_version_bump_tracked(self):
        """Context version bump is captured in transition result updates."""
        context_data = {
            "merchant": {"merchant_id": "m_002"},
            "version": 4,
        }
        inp = TransitionInput(
            current_state=State.PITCHED,
            user_intent=IntentType.INTEREST,
            raw_message="Tell me more",
            context_data=context_data,
        )
        res = self.sm.evaluate_transition(inp)
        self.assertTrue(res.valid)
        self.assertEqual(res.context_updates_applied.get("observed_context_version"), 4)


class TestConversationPersistence(unittest.TestCase):
    """Test suite covering thread-safe in-memory and disk snapshot persistence."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = ConversationStore(persistence_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_lifecycle(self):
        conv = ConversationState(
            conversation_id="conv_p1",
            merchant_id="m_100",
            current_state=State.PITCHED,
            last_message_at="2026-04-26T12:00:00Z",
        )
        self.store.save(conv)
        self.assertTrue(self.store.exists("conv_p1"))
        retrieved = self.store.get("conv_p1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.conversation_id, "conv_p1")
        self.assertEqual(retrieved.current_state, State.PITCHED)

    def test_file_persistence_rehydration(self):
        """State saved to store must persist to disk and rehydrate in a fresh store instance."""
        conv = ConversationState(
            conversation_id="conv_disk_1",
            merchant_id="m_200",
            current_state=State.ACTION_PENDING,
            last_message_at="2026-04-26T12:00:00Z",
            metadata={"source": "test_rehydration"},
        )
        self.store.save(conv)

        # Create fresh store pointing to same directory
        fresh_store = ConversationStore(persistence_dir=self.temp_dir)
        loaded = fresh_store.get("conv_disk_1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.current_state, State.ACTION_PENDING)
        self.assertEqual(loaded.metadata["source"], "test_rehydration")

    def test_snapshot_dump_and_restore(self):
        conv1 = ConversationState(
            conversation_id="conv_s1",
            merchant_id="m_1",
            current_state=State.INITIAL,
            last_message_at="2026-04-26T12:00:00Z",
        )
        conv2 = ConversationState(
            conversation_id="conv_s2",
            merchant_id="m_2",
            current_state=State.COMPLETED,
            last_message_at="2026-04-26T12:00:00Z",
        )
        self.store.save(conv1)
        self.store.save(conv2)

        snapshot_path = Path(self.temp_dir) / "snapshot.json"
        self.store.save_snapshot_file(snapshot_path)
        self.assertTrue(snapshot_path.exists())

        new_store = ConversationStore()
        new_store.load_snapshot_file(snapshot_path)
        self.assertEqual(new_store.count(), 2)
        self.assertEqual(new_store.get("conv_s2").current_state, State.COMPLETED)

    def test_list_active_filters_terminal(self):
        conv1 = ConversationState(
            conversation_id="conv_a1",
            merchant_id="m_1",
            current_state=State.PITCHED,
            is_active=True,
            last_message_at="2026-04-26T12:00:00Z",
        )
        conv2 = ConversationState(
            conversation_id="conv_t1",
            merchant_id="m_2",
            current_state=State.STOPPED,
            is_active=False,
            last_message_at="2026-04-26T12:00:00Z",
        )
        self.store.save(conv1)
        self.store.save(conv2)

        active = self.store.list_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].conversation_id, "conv_a1")


class TestContextEngineStateMachineIntegration(unittest.TestCase):
    """End-to-end integration tests between ContextEngine, Classifier, and StateMachine."""

    def setUp(self):
        self.engine = ContextEngine()
        self.classifier = IntentClassifier()

    def test_full_commitment_flow(self):
        """Simulate full pitch -> commit -> completed lifecycle."""
        conv_id = "flow_commit_1"
        conv = self.engine.create_or_get_conversation(
            conversation_id=conv_id,
            merchant_id="m_flow_1",
        )
        self.assertEqual(conv.current_state, State.INITIAL)

        # Turn 1: Proactive pitch dispatch
        t1 = self.engine.transition_conversation(
            conversation_id=conv_id,
            user_intent=IntentType.UNKNOWN,
            is_proactive_send=True,
        )
        self.assertEqual(t1.to_state, State.PITCHED)
        self.assertEqual(conv.current_state, State.PITCHED)

        # Turn 2: User responds with commitment
        user_msg = "Yes please update the clinic hours immediately"
        detected = self.classifier.classify(user_msg)
        self.assertEqual(detected.intent_type, IntentType.COMMITMENT)

        t2 = self.engine.transition_conversation(
            conversation_id=conv_id,
            user_intent=detected.intent_type,
            message=user_msg,
        )
        self.assertEqual(t2.to_state, State.ACTION_PENDING)
        self.assertEqual(t2.action, "send")
        self.assertEqual(conv.current_state, State.ACTION_PENDING)

        # Turn 3: Complete action
        t3 = self.engine.state_machine.complete_action(conv, rationale="Clinic hours updated on GBP")
        self.assertEqual(t3.to_state, State.COMPLETED)
        conv.set_state(State.COMPLETED)
        self.assertFalse(conv.is_active)

    def test_full_auto_reply_loop_break(self):
        """Simulate Turn 1 auto-reply (wait) followed by Turn 2 auto-reply (stop)."""
        conv_id = "flow_autoreply_1"
        conv = self.engine.create_or_get_conversation(
            conversation_id=conv_id,
            merchant_id="m_flow_2",
        )
        # Send pitch
        self.engine.transition_conversation(conv_id, user_intent=IntentType.UNKNOWN, is_proactive_send=True)

        # Inbound Turn 1: Auto reply
        canned_msg = "Thank you for contacting us! Our team will respond shortly."
        detected1 = self.classifier.classify(canned_msg)
        self.assertEqual(detected1.intent_type, IntentType.AUTO_REPLY)

        t1 = self.engine.transition_conversation(conv_id, user_intent=detected1.intent_type, message=canned_msg)
        self.assertEqual(t1.to_state, State.WAITING)
        self.assertEqual(t1.action, "wait")
        self.engine.increment_auto_reply_count(conv_id)

        # Inbound Turn 2: Second identical auto reply
        detected2 = self.classifier.classify(canned_msg)
        t2 = self.engine.transition_conversation(conv_id, user_intent=detected2.intent_type, message=canned_msg)
        self.assertEqual(t2.to_state, State.STOPPED)
        self.assertEqual(t2.action, "end")
        self.assertFalse(conv.is_active)


if __name__ == "__main__":
    unittest.main()
