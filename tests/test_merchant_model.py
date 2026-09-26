"""Unit tests for MerchantContext and related models."""

import unittest
from pydantic import ValidationError
from vera.models.merchant import (
    CustomerAggregate,
    MerchantContext,
    MerchantIdentity,
    MerchantOffer,
    PerformanceSnapshot,
    Subscription,
)


class TestMerchantModel(unittest.TestCase):
    """Test suite for Merchant domain models."""

    def _sample_valid_merchant_dict(self):
        return {
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "category_slug": "dentists",
            "identity": {
                "name": "Dr. Meera's Dental Clinic",
                "city": "Delhi",
                "locality": "Lajpat Nagar",
                "place_id": "ChIJ_TEST_001",
                "verified": True,
                "languages": ["en", "hi"],
                "owner_first_name": "Meera",
                "established_year": 2018,
            },
            "subscription": {
                "status": "active",
                "plan": "Pro",
                "days_remaining": 82,
                "renewed_at": "2026-02-04",
            },
            "performance": {
                "window_days": 30,
                "views": 2410,
                "calls": 18,
                "directions": 45,
                "ctr": 0.021,
                "leads": 9,
                "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05, "ctr_pct": 0.02},
            },
            "offers": [
                {
                    "id": "o_001",
                    "title": "Dental Cleaning @ ₹299",
                    "status": "active",
                    "started": "2026-03-01",
                }
            ],
            "conversation_history": [
                {
                    "ts": "2026-04-24T10:12:00Z",
                    "from": "vera",
                    "body": "Profile audit done.",
                    "engagement": "merchant_replied",
                }
            ],
            "customer_aggregate": {
                "total_unique_ytd": 540,
                "lapsed_180d_plus": 78,
                "retention_6mo_pct": 0.38,
            },
            "signals": ["stale_posts:22d", "ctr_below_peer_median"],
            "review_themes": [
                {
                    "theme": "wait_time",
                    "sentiment": "neg",
                    "occurrences_30d": 3,
                    "common_quote": "30 min wait",
                }
            ],
        }

    def test_valid_merchant_creation(self):
        data = self._sample_valid_merchant_dict()
        merchant = MerchantContext.from_dict(data)
        self.assertEqual(merchant.merchant_id, "m_001_drmeera_dentist_delhi")
        self.assertEqual(merchant.identity.name, "Dr. Meera's Dental Clinic")
        self.assertEqual(merchant.subscription.status, "active")
        self.assertEqual(merchant.performance.views, 2410)
        self.assertEqual(merchant.conversation_history[0].from_role, "vera")

    def test_serialization_roundtrip(self):
        data = self._sample_valid_merchant_dict()
        merchant = MerchantContext.from_dict(data)
        serialized_json = merchant.to_json()
        deserialized = MerchantContext.from_json(serialized_json)
        self.assertEqual(merchant.merchant_id, deserialized.merchant_id)
        self.assertEqual(merchant.identity.city, deserialized.identity.city)
        self.assertEqual(merchant.performance.ctr, deserialized.performance.ctr)

    def test_missing_required_fields(self):
        # Missing merchant_id
        data = self._sample_valid_merchant_dict()
        del data["merchant_id"]
        with self.assertRaises(ValidationError) as ctx:
            MerchantContext.from_dict(data)
        self.assertIn("merchant_id", str(ctx.exception))

        # Missing identity
        data2 = self._sample_valid_merchant_dict()
        del data2["identity"]
        with self.assertRaises(ValidationError):
            MerchantContext.from_dict(data2)

    def test_wrong_types(self):
        # views as string with letters
        data = self._sample_valid_merchant_dict()
        data["performance"]["views"] = "invalid_number"
        with self.assertRaises(ValidationError):
            MerchantContext.from_dict(data)

    def test_empty_values(self):
        # Empty merchant_id
        data = self._sample_valid_merchant_dict()
        data["merchant_id"] = ""
        with self.assertRaises(ValidationError):
            MerchantContext.from_dict(data)

    def test_boundary_values(self):
        # Negative views must fail
        data = self._sample_valid_merchant_dict()
        data["performance"]["views"] = -10
        with self.assertRaises(ValidationError):
            MerchantContext.from_dict(data)

        # Established year out of realistic bounds
        data["performance"]["views"] = 100
        data["identity"]["established_year"] = 1500
        with self.assertRaises(ValidationError):
            MerchantContext.from_dict(data)

    def test_expired_subscription_support(self):
        # Merchant with expired subscription using days_since_expiry
        data = self._sample_valid_merchant_dict()
        data["subscription"] = {
            "status": "expired",
            "plan": "Pro",
            "days_since_expiry": 38,
        }
        merchant = MerchantContext.from_dict(data)
        self.assertEqual(merchant.subscription.status, "expired")
        self.assertEqual(merchant.subscription.days_since_expiry, 38)
        self.assertIsNone(merchant.subscription.days_remaining)


if __name__ == "__main__":
    unittest.main()
