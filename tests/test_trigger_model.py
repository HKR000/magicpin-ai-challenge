"""Unit tests for TriggerContext and related models."""

import unittest
from pydantic import ValidationError
from vera.models.trigger import (
    TriggerContext,
    TriggerKind,
    TriggerScope,
    TriggerSource,
)


class TestTriggerModel(unittest.TestCase):
    """Test suite for Trigger domain models."""

    def _sample_merchant_trigger(self):
        return {
            "id": "trg_001_research_digest",
            "scope": "merchant",
            "kind": "research_digest",
            "source": "external",
            "merchant_id": "m_001_drmeera",
            "customer_id": None,
            "payload": {"top_item_id": "d_001"},
            "urgency": 2,
            "suppression_key": "research:dentists:2026-W17",
            "expires_at": "2026-05-03T00:00:00Z",
        }

    def _sample_customer_trigger(self):
        return {
            "id": "trg_002_recall_priya",
            "scope": "customer",
            "kind": "recall_due",
            "source": "internal",
            "merchant_id": "m_001_drmeera",
            "customer_id": "c_001_priya",
            "payload": {"service_due": "6_month_cleaning"},
            "urgency": 3,
            "suppression_key": "recall:c_001:6mo",
            "expires_at": "2026-11-30T00:00:00Z",
        }

    def test_valid_merchant_trigger(self):
        data = self._sample_merchant_trigger()
        trigger = TriggerContext.from_dict(data)
        self.assertEqual(trigger.id, "trg_001_research_digest")
        self.assertEqual(trigger.scope, TriggerScope.MERCHANT)
        self.assertEqual(trigger.source, TriggerSource.EXTERNAL)
        self.assertIsNone(trigger.customer_id)
        self.assertEqual(trigger.urgency, 2)

    def test_valid_customer_trigger(self):
        data = self._sample_customer_trigger()
        trigger = TriggerContext.from_dict(data)
        self.assertEqual(trigger.scope, TriggerScope.CUSTOMER)
        self.assertEqual(trigger.customer_id, "c_001_priya")

    def test_customer_trigger_requires_customer_id(self):
        data = self._sample_customer_trigger()
        data["customer_id"] = None
        with self.assertRaises(ValidationError) as ctx:
            TriggerContext.from_dict(data)
        self.assertIn("customer_id is required when trigger scope is 'customer'", str(ctx.exception))

    def test_serialization_roundtrip(self):
        data = self._sample_merchant_trigger()
        trigger = TriggerContext.from_dict(data)
        serialized_json = trigger.to_json()
        deserialized = TriggerContext.from_json(serialized_json)
        self.assertEqual(trigger.id, deserialized.id)
        self.assertEqual(trigger.suppression_key, deserialized.suppression_key)

    def test_urgency_boundaries(self):
        data = self._sample_merchant_trigger()
        # Urgency < 1 must fail
        data["urgency"] = 0
        with self.assertRaises(ValidationError):
            TriggerContext.from_dict(data)

        # Urgency > 5 must fail
        data["urgency"] = 6
        with self.assertRaises(ValidationError):
            TriggerContext.from_dict(data)

        # Urgency 1 and 5 must pass
        data["urgency"] = 1
        t1 = TriggerContext.from_dict(data)
        self.assertEqual(t1.urgency, 1)

        data["urgency"] = 5
        t5 = TriggerContext.from_dict(data)
        self.assertEqual(t5.urgency, 5)

    def test_invalid_enum_scope(self):
        data = self._sample_merchant_trigger()
        data["scope"] = "unsupported_scope"
        with self.assertRaises(ValidationError):
            TriggerContext.from_dict(data)


if __name__ == "__main__":
    unittest.main()
