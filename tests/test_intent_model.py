"""Unit tests for Intent classification models."""

import unittest
from pydantic import ValidationError
from vera.models.intent import (
    DetectedIntent,
    IntentType,
)


class TestIntentModel(unittest.TestCase):
    """Test suite for Intent models."""

    def test_valid_detected_intent(self):
        intent = DetectedIntent(
            intent_type=IntentType.COMMITMENT,
            confidence=0.98,
            raw_text="Ok let's do it. What's next?",
            signals_detected=["commitment_verb", "positive_agreement"],
            transition_recommended="action_committed",
        )
        self.assertEqual(intent.intent_type, IntentType.COMMITMENT)
        self.assertEqual(intent.confidence, 0.98)
        self.assertEqual(len(intent.signals_detected), 2)

    def test_confidence_boundaries(self):
        # Confidence < 0.0 must fail
        with self.assertRaises(ValidationError):
            DetectedIntent(
                intent_type=IntentType.AUTO_REPLY,
                confidence=-0.1,
                raw_text="Thank you",
            )

        # Confidence > 1.0 must fail
        with self.assertRaises(ValidationError):
            DetectedIntent(
                intent_type=IntentType.AUTO_REPLY,
                confidence=1.05,
                raw_text="Thank you",
            )

        # Confidence 0.0 and 1.0 succeed
        i0 = DetectedIntent(intent_type=IntentType.UNKNOWN, confidence=0.0, raw_text="huh?")
        self.assertEqual(i0.confidence, 0.0)

        i1 = DetectedIntent(intent_type=IntentType.AUTO_REPLY, confidence=1.0, raw_text="auto")
        self.assertEqual(i1.confidence, 1.0)

    def test_serialization_roundtrip(self):
        intent = DetectedIntent(
            intent_type=IntentType.HOSTILE_OPT_OUT,
            confidence=0.95,
            raw_text="Stop messaging me. This is spam.",
            signals_detected=["stop_keyword", "spam_keyword"],
        )
        json_data = intent.to_json()
        deserialized = DetectedIntent.from_json(json_data)
        self.assertEqual(intent.intent_type, deserialized.intent_type)
        self.assertEqual(intent.raw_text, deserialized.raw_text)


if __name__ == "__main__":
    unittest.main()
