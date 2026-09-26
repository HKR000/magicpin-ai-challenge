"""Unit tests for CustomerContext and related CRM models."""

import unittest
from pydantic import ValidationError
from vera.models.customer import (
    CustomerConsent,
    CustomerContext,
    CustomerIdentity,
    CustomerPreferences,
    CustomerRelationship,
    CustomerState,
)


class TestCustomerModel(unittest.TestCase):
    """Test suite for Customer domain models."""

    def _sample_valid_customer_dict(self):
        return {
            "customer_id": "c_001_priya_for_m001",
            "merchant_id": "m_001_drmeera",
            "identity": {
                "name": "Priya",
                "phone_redacted": "<phone>",
                "language_pref": "hi-en mix",
                "age_band": "25-35",
            },
            "relationship": {
                "first_visit": "2025-11-04",
                "last_visit": "2026-05-12",
                "visits_total": 4,
                "services_received": ["cleaning", "cleaning", "whitening", "cleaning"],
                "lifetime_value": 1696.0,
            },
            "state": "lapsed_soft",
            "preferences": {
                "preferred_slots": "weekday_evening",
                "channel": "whatsapp",
                "reminder_opt_in": True,
            },
            "consent": {
                "opted_in_at": "2025-11-04",
                "scope": ["recall_reminders", "appointment_reminders"],
            },
        }

    def test_valid_customer_creation(self):
        data = self._sample_valid_customer_dict()
        customer = CustomerContext.from_dict(data)
        self.assertEqual(customer.customer_id, "c_001_priya_for_m001")
        self.assertEqual(customer.identity.name, "Priya")
        self.assertEqual(customer.state, CustomerState.LAPSED_SOFT)
        self.assertEqual(customer.relationship.visits_total, 4)

    def test_serialization_roundtrip(self):
        data = self._sample_valid_customer_dict()
        customer = CustomerContext.from_dict(data)
        serialized_json = customer.to_json()
        deserialized = CustomerContext.from_json(serialized_json)
        self.assertEqual(customer.customer_id, deserialized.customer_id)
        self.assertEqual(customer.state, deserialized.state)

    def test_missing_required_fields(self):
        data = self._sample_valid_customer_dict()
        del data["relationship"]
        with self.assertRaises(ValidationError):
            CustomerContext.from_dict(data)

    def test_wrong_types(self):
        data = self._sample_valid_customer_dict()
        data["relationship"]["visits_total"] = "invalid_number"
        with self.assertRaises(ValidationError):
            CustomerContext.from_dict(data)

    def test_invalid_lifecycle_state(self):
        data = self._sample_valid_customer_dict()
        data["state"] = "unknown_state_invalid"
        with self.assertRaises(ValidationError):
            CustomerContext.from_dict(data)

    def test_nullable_fields_for_anonymous_walk_ins(self):
        # Mr. Sharma or anonymous walk-in with null phone or null opt-in date
        data = self._sample_valid_customer_dict()
        data["identity"]["phone_redacted"] = None
        data["consent"]["opted_in_at"] = None
        customer = CustomerContext.from_dict(data)
        self.assertIsNone(customer.identity.phone_redacted)
        self.assertIsNone(customer.consent.opted_in_at)


if __name__ == "__main__":
    unittest.main()
