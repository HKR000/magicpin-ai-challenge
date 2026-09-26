"""Unit tests for ProactiveDecision and ReactiveDecision models."""

import unittest
from pydantic import ValidationError
from vera.models.decision import (
    DecisionType,
    ProactiveDecision,
    ReactiveDecision,
    SuppressionResult,
)
from vera.models.intent import IntentType


class TestDecisionModel(unittest.TestCase):
    """Test suite for Decision tracking models."""

    def test_proactive_decision_send(self):
        decision = ProactiveDecision(
            decision_type=DecisionType.PROACTIVE_SEND,
            trigger_id="trg_001",
            merchant_id="m_001_drmeera",
            customer_id=None,
            selected_signal="jida_fluoride_digest_release",
            selected_offer_id="den_001",
            rationale="High-risk adult cohort matches trial segment",
            suppression=SuppressionResult(
                suppression_key="research:dentists:2026-W17",
                is_suppressed=False,
            ),
        )
        self.assertEqual(decision.decision_type, DecisionType.PROACTIVE_SEND)
        self.assertFalse(decision.suppression.is_suppressed)

    def test_reactive_decision_wait(self):
        decision = ReactiveDecision(
            decision_type=DecisionType.REPLY_WAIT,
            conversation_id="conv_001",
            intent_detected=IntentType.QUALIFICATION,
            rationale="Merchant asked for 30 minutes before deciding",
            wait_seconds=1800,
        )
        self.assertEqual(decision.decision_type, DecisionType.REPLY_WAIT)
        self.assertEqual(decision.wait_seconds, 1800)

    def test_serialization_roundtrip(self):
        decision = ReactiveDecision(
            decision_type=DecisionType.REPLY_END,
            conversation_id="conv_002",
            intent_detected=IntentType.AUTO_REPLY,
            rationale="Repeated canned auto-reply; exit loop",
        )
        json_data = decision.to_json()
        deserialized = ReactiveDecision.from_json(json_data)
        self.assertEqual(decision.decision_type, deserialized.decision_type)
        self.assertEqual(decision.intent_detected, deserialized.intent_detected)


if __name__ == "__main__":
    unittest.main()
