"""Unit tests for ContextEnvelope, ContextAck, and ContextVersionRecord models."""

import unittest
from pydantic import ValidationError
from vera.models.context_version import (
    ContextAck,
    ContextEnvelope,
    ContextScope,
    ContextVersionRecord,
)


class TestContextVersionModel(unittest.TestCase):
    """Test suite for Context versioning models."""

    def test_valid_context_envelope(self):
        envelope = ContextEnvelope(
            scope=ContextScope.CATEGORY,
            context_id="dentists",
            version=1,
            payload={"slug": "dentists", "voice": {"tone": "peer_clinical"}},
            delivered_at="2026-04-26T09:45:00Z",
        )
        self.assertEqual(envelope.scope, ContextScope.CATEGORY)
        self.assertEqual(envelope.version, 1)

    def test_context_ack_success(self):
        ack = ContextAck(
            accepted=True,
            ack_id="ack_dentists_v1",
            stored_at="2026-04-26T09:45:00.123Z",
        )
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.ack_id, "ack_dentists_v1")

    def test_context_ack_conflict_409(self):
        ack = ContextAck(
            accepted=False,
            reason="stale_version",
            current_version=3,
        )
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.reason, "stale_version")
        self.assertEqual(ack.current_version, 3)

    def test_version_boundary(self):
        # Version < 1 must fail
        with self.assertRaises(ValidationError):
            ContextEnvelope(
                scope=ContextScope.MERCHANT,
                context_id="m_001",
                version=0,
                payload={},
                delivered_at="2026-04-26T10:00:00Z",
            )

    def test_serialization_roundtrip(self):
        record = ContextVersionRecord(
            scope=ContextScope.TRIGGER,
            context_id="trg_001",
            version=2,
            stored_at="2026-04-26T10:00:00Z",
            payload={"kind": "perf_dip"},
        )
        json_data = record.to_json()
        deserialized = ContextVersionRecord.from_json(json_data)
        self.assertEqual(record.context_id, deserialized.context_id)
        self.assertEqual(record.version, deserialized.version)


if __name__ == "__main__":
    unittest.main()
