"""Unit tests for ComposedMessage, ProactiveAction, and ReplyAction models."""

import unittest
from pydantic import ValidationError
from vera.models.message import (
    ActionType,
    ComposedMessage,
    CtaType,
    ProactiveAction,
    ReplyAction,
    SendAsIdentity,
    TickResponse,
)


class TestMessageModel(unittest.TestCase):
    """Test suite for Outbound and Reactive Message models."""

    def test_valid_composed_message(self):
        msg = ComposedMessage(
            body="Dr. Meera, JIDA's Oct issue landed...",
            cta=CtaType.BINARY,
            send_as=SendAsIdentity.VERA,
            suppression_key="research:dentists:2026-W17",
            rationale="External research digest relevant to high-risk adults",
            template_name="vera_research_v1",
            template_params=["Dr. Meera", "JIDA Oct issue"],
        )
        self.assertEqual(msg.send_as, SendAsIdentity.VERA)
        self.assertEqual(msg.cta, CtaType.BINARY)

    def test_proactive_action_serialization(self):
        action = ProactiveAction(
            conversation_id="conv_001",
            merchant_id="m_001_drmeera",
            customer_id=None,
            send_as=SendAsIdentity.VERA,
            trigger_id="trg_001",
            template_name="vera_research_v1",
            template_params=["Dr. Meera"],
            body="Dr. Meera, JIDA issue landed...",
            cta="open_ended",
            suppression_key="research:dentists:2026-W17",
            rationale="Clinical anchor outreach",
        )
        tick_resp = TickResponse(actions=[action])
        data = tick_resp.to_dict()
        self.assertEqual(len(data["actions"]), 1)
        self.assertEqual(data["actions"][0]["conversation_id"], "conv_001")

    def test_reply_action_send_requires_body(self):
        # action == send with None body must fail
        with self.assertRaises(ValidationError) as ctx:
            ReplyAction(action=ActionType.SEND, body=None, rationale="Testing")
        self.assertIn("body cannot be empty when action is 'send'", str(ctx.exception))

        # action == send with empty whitespace string must fail
        with self.assertRaises(ValidationError) as ctx:
            ReplyAction(action=ActionType.SEND, body="   ", rationale="Testing")
        self.assertIn("body cannot be empty when action is 'send'", str(ctx.exception))

        # action == send with valid body succeeds
        valid_send = ReplyAction(
            action=ActionType.SEND,
            body="Sending the draft now...",
            cta="binary",
            rationale="Honor merchant intent",
        )
        self.assertEqual(valid_send.action, ActionType.SEND)

    def test_reply_action_wait_requires_positive_seconds(self):
        # action == wait with None wait_seconds must fail
        with self.assertRaises(ValidationError) as ctx:
            ReplyAction(action=ActionType.WAIT, wait_seconds=None, rationale="Testing")
        self.assertIn("wait_seconds must be a positive integer", str(ctx.exception))

        # action == wait with 0 wait_seconds must fail
        with self.assertRaises(ValidationError):
            ReplyAction(action=ActionType.WAIT, wait_seconds=0, rationale="Testing")

        # action == wait with positive seconds succeeds
        valid_wait = ReplyAction(
            action=ActionType.WAIT,
            wait_seconds=1800,
            rationale="Back off 30 min",
        )
        self.assertEqual(valid_wait.wait_seconds, 1800)

    def test_reply_action_end(self):
        end_action = ReplyAction(
            action=ActionType.END,
            rationale="Auto-reply loop detected; gracefully terminating thread",
        )
        self.assertEqual(end_action.action, ActionType.END)
        self.assertIsNone(end_action.body)


if __name__ == "__main__":
    unittest.main()
