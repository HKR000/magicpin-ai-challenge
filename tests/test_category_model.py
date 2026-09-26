"""Unit tests for CategoryContext and related models."""

import unittest
from pydantic import ValidationError
from vera.models.category import (
    CategoryContext,
    DigestItem,
    OfferTemplate,
    PatientContentItem,
    PeerStats,
    SeasonalBeat,
    TrendSignal,
    VoiceProfile,
)


class TestCategoryModel(unittest.TestCase):
    """Test suite for Category domain models."""

    def _sample_valid_category_dict(self):
        return {
            "slug": "dentists",
            "display_name": "Dentists",
            "voice": {
                "tone": "peer_clinical",
                "register": "respectful_collegial",
                "code_mix": "hindi_english_natural",
                "vocab_allowed": ["scaling", "caries"],
                "vocab_taboo": ["guaranteed", "100% cure"],
                "salutation_examples": ["Dr. {first_name}"],
                "tone_examples": ["Worth a look — JIDA Oct 2026 p.14"],
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
                "avg_views_30d": 1820,
                "avg_calls_30d": 12,
                "avg_directions_30d": 38,
                "avg_ctr": 0.030,
                "retention_6mo_pct": 0.42,
            },
            "digest": [
                {
                    "id": "d_001",
                    "kind": "research",
                    "title": "Fluoride recall trial",
                    "source": "JIDA Oct 2026 p.14",
                    "summary": "38% caries reduction",
                    "actionable": "Audit high-risk recalls",
                    "trial_n": 2100,
                }
            ],
            "patient_content_library": [
                {
                    "id": "pc_001",
                    "title": "Oral Health and Heart",
                    "channel": "whatsapp",
                    "length_seconds": 90,
                    "body": "Periodontal inflammation links to cardiovascular risk.",
                }
            ],
            "seasonal_beats": [{"month_range": "Nov-Feb", "note": "Bruxism spike"}],
            "trend_signals": [
                {
                    "query": "clear aligners delhi",
                    "delta_yoy": 0.62,
                    "segment_age": "28-45",
                    "skew": "female",
                }
            ],
            "regulatory_authorities": ["DCI", "IDA"],
            "professional_journals": ["JIDA"],
        }

    def test_valid_category_creation(self):
        data = self._sample_valid_category_dict()
        category = CategoryContext.from_dict(data)
        self.assertEqual(category.slug, "dentists")
        self.assertEqual(category.voice.tone, "peer_clinical")
        self.assertEqual(category.voice.register_style, "respectful_collegial")
        self.assertEqual(len(category.offer_catalog), 1)
        self.assertEqual(category.peer_stats.avg_rating, 4.4)
        self.assertEqual(category.digest[0].trial_n, 2100)

    def test_serialization_roundtrip(self):
        data = self._sample_valid_category_dict()
        category = CategoryContext.from_dict(data)
        serialized_json = category.to_json()
        deserialized = CategoryContext.from_json(serialized_json)
        self.assertEqual(category.slug, deserialized.slug)
        self.assertEqual(category.voice.tone, deserialized.voice.tone)
        self.assertEqual(category.peer_stats.avg_ctr, deserialized.peer_stats.avg_ctr)

    def test_missing_required_fields(self):
        # Missing slug
        data = self._sample_valid_category_dict()
        del data["slug"]
        with self.assertRaises(ValidationError) as ctx:
            CategoryContext.from_dict(data)
        self.assertIn("slug", str(ctx.exception))

        # Missing voice
        data2 = self._sample_valid_category_dict()
        del data2["voice"]
        with self.assertRaises(ValidationError) as ctx:
            CategoryContext.from_dict(data2)
        self.assertIn("voice", str(ctx.exception))

    def test_wrong_types(self):
        # avg_rating as non-numeric string
        data = self._sample_valid_category_dict()
        data["peer_stats"]["avg_rating"] = "not-a-number"
        with self.assertRaises(ValidationError):
            CategoryContext.from_dict(data)

    def test_empty_values(self):
        # Empty slug
        data = self._sample_valid_category_dict()
        data["slug"] = ""
        with self.assertRaises(ValidationError):
            CategoryContext.from_dict(data)

    def test_unexpected_fields_in_strict_models(self):
        # VoiceProfile forbids extra fields
        voice_data = {
            "tone": "peer_clinical",
            "forbidden_extra": "should_fail",
        }
        with self.assertRaises(ValidationError):
            VoiceProfile.from_dict(voice_data)

    def test_boundary_values(self):
        # avg_rating > 5.0 must fail
        data = self._sample_valid_category_dict()
        data["peer_stats"]["avg_rating"] = 5.5
        with self.assertRaises(ValidationError):
            CategoryContext.from_dict(data)

        # avg_rating < 0.0 must fail
        data["peer_stats"]["avg_rating"] = -0.5
        with self.assertRaises(ValidationError):
            CategoryContext.from_dict(data)

        # avg_ctr > 1.0 must fail
        data["peer_stats"]["avg_rating"] = 4.0
        data["peer_stats"]["avg_ctr"] = 1.5
        with self.assertRaises(ValidationError):
            CategoryContext.from_dict(data)


if __name__ == "__main__":
    unittest.main()
