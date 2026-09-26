"""Unit tests for ConversationState and ConversationTurn models."""

import unittest
from pydantic import ValidationError
from vera.models.conversation import (
    ConversationStage,
    ConversationState,
    ConversationTurn,
    Role,
)


class TestConversationModel(unittest.TestCase):
    """Test suite for Conversation state tracking models."""

    def test_valid_turn_and_state(self):
        turn1 = ConversationTurn(
            turn_number=1,
            from_role=Role.VERA,
            message="Hi Dr. Meera, JIDA Oct issue landed...",
            timestamp="2026-04-26T10:00:00Z",
            action_taken="send",
        )
        turn2 = ConversationTurn(
            turn_number=2,
            from_role=Role.MERCHANT,
            message="Yes please send the abstract",
            timestamp="2026-04-26T10:01:00Z",
            detected_intent="commitment",
        )

        state = ConversationState(
            conversation_id="conv_001",
            merchant_id="m_001_drmeera",
            customer_id=None,
            trigger_id="trg_001",
            stage=ConversationStage.ACTION_COMMITTED,
            turns=[turn1, turn2],
            auto_reply_count=0,
            last_message_at="2026-04-26T10:01:00Z",
            is_active=True,
        )

        self.assertEqual(state.conversation_id, "conv_001")
        self.assertEqual(len(state.turns), 2)
        self.assertEqual(state.stage, ConversationStage.ACTION_COMMITTED)

    def test_serialization_roundtrip(self):
        state = ConversationState(
            conversation_id="conv_002",
            merchant_id="m_002",
            last_message_at="2026-04-26T10:00:00Z",
        )
        json_data = state.to_json()
        deserialized = ConversationState.from_json(json_data)
        self.assertEqual(state.conversation_id, deserialized.conversation_id)
        self.assertEqual(state.stage, ConversationStage.INITIATED)
        self.assertTrue(deserialized.is_active)

    def test_turn_number_validation(self):
        # Turn number < 1 must fail
        with self.assertRaises(ValidationError):
            ConversationTurn(
                turn_number=0,
                from_role=Role.VERA,
                message="Hello",
                timestamp="2026-04-26T10:00:00Z",
            )

    def test_invalid_role(self):
        with self.assertRaises(ValidationError):
            ConversationTurn(
                turn_number=1,
                from_role="invalid_role",
                message="Hello",
                timestamp="2026-04-26T10:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
