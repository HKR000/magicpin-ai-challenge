"""Intent classification engine supporting English, Hinglish, Hindi, and colloquial typos."""

from __future__ import annotations
import re
import unicodedata
from typing import List, Optional, Tuple

from vera.intent.categories import IntentCategory
from vera.intent.patterns import (
    ACCEPTANCE_PATTERNS,
    AUTO_REPLY_PATTERNS,
    CLARIFICATION_PATTERNS,
    CONFIRMATION_PATTERNS,
    HOSTILE_PATTERNS,
    INTEREST_PATTERNS,
    OBJECTION_PATTERNS,
    OFF_TOPIC_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    QUESTION_PATTERNS,
    REJECTION_PATTERNS,
    SHORT_ACCEPTANCE,
    SHORT_REJECTION,
)
from vera.models.intent import DetectedIntent


class IntentClassifier:
    """Classifies user conversational turns into verified challenge intent categories."""

    def normalize(self, text: str) -> str:
        """Normalizes text by trimming, handling repeated characters, and lowercasing."""
        if not text:
            return ""
        norm = unicodedata.normalize("NFKC", text).strip().lower()
        # Normalize elongated common words (e.g., 'yeeessss' -> 'yes', 'noooo' -> 'no', 'stopppp' -> 'stop')
        norm = re.sub(r"\by+e+s+\b", "yes", norm)
        norm = re.sub(r"\bn+o+\b", "no", norm)
        norm = re.sub(r"\bs+t+o+p+\b", "stop", norm)
        # Collapse 3+ repeating letters down to 2 (e.g., 'haaaan' -> 'haan')
        norm = re.sub(r"([a-z])\1{2,}", r"\1\1", norm)
        return norm

    def classify(self, text: str) -> DetectedIntent:
        """Classifies an incoming turn with strict confidence calibration and UNKNOWN fallback."""
        raw_text = text if text is not None else ""
        clean = self.normalize(raw_text)

        if not clean:
            return DetectedIntent(
                intent_type=IntentCategory.UNKNOWN.to_model_intent(),
                confidence=0.0,
                raw_text=raw_text,
                signals_detected=["empty_input"],
                transition_recommended=None,
            )

        # 1. High-Priority: Auto-Reply Detection (WhatsApp Business Canned Greetings)
        for pattern in AUTO_REPLY_PATTERNS:
            if pattern.search(clean) or pattern.search(raw_text):
                return DetectedIntent(
                    intent_type=IntentCategory.GENERIC_AUTO_REPLY.to_model_intent(),
                    confidence=0.98,
                    raw_text=raw_text,
                    signals_detected=["auto_reply_pattern", pattern.pattern[:30]],
                    transition_recommended="wait_or_end",
                )

        # 1b. High-Priority: Prompt Injection / Adversarial Jailbreak Detection
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(clean) or pattern.search(raw_text):
                return DetectedIntent(
                    intent_type=IntentCategory.HOSTILE.to_model_intent(),
                    confidence=0.99,
                    raw_text=raw_text,
                    signals_detected=["prompt_injection_blocked", pattern.pattern[:30]],
                    transition_recommended="end",
                )

        # 2. Hostile / Severe Opt-out
        for pattern in HOSTILE_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.HOSTILE.to_model_intent(),
                    confidence=0.96,
                    raw_text=raw_text,
                    signals_detected=["hostile_opt_out", pattern.pattern[:30]],
                    transition_recommended="end",
                )

        # 3. Off-Topic Inquiries (GST, cricket, weather) - checked before general questions
        for pattern in OFF_TOPIC_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.OFF_TOPIC.to_model_intent(),
                    confidence=0.92,
                    raw_text=raw_text,
                    signals_detected=["off_topic_query", pattern.pattern[:30]],
                    transition_recommended="redirect_or_end",
                )

        # 4. Short Exact Token Matches (Very high confidence)
        token_clean = clean.strip(" .!?,:;\"'~`-")
        if token_clean in SHORT_ACCEPTANCE or clean in SHORT_ACCEPTANCE:
            return DetectedIntent(
                intent_type=IntentCategory.ACCEPTANCE.to_model_intent(),
                confidence=0.95,
                raw_text=raw_text,
                signals_detected=["short_affirmative", token_clean],
                transition_recommended="action_committed",
            )

        if token_clean in SHORT_REJECTION or clean in SHORT_REJECTION:
            return DetectedIntent(
                intent_type=IntentCategory.REJECTION.to_model_intent(),
                confidence=0.95,
                raw_text=raw_text,
                signals_detected=["short_negative", token_clean],
                transition_recommended="end",
            )

        # 5. Clarification Patterns
        for pattern in CLARIFICATION_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.CLARIFICATION.to_model_intent(),
                    confidence=0.90,
                    raw_text=raw_text,
                    signals_detected=["clarification_seek", pattern.pattern[:30]],
                    transition_recommended="clarify",
                )

        # 6. Explicit Acceptance / Commitment ("ok let's do it", "update profile", "send abstract")
        for pattern in ACCEPTANCE_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.ACCEPTANCE.to_model_intent(),
                    confidence=0.94,
                    raw_text=raw_text,
                    signals_detected=["explicit_acceptance", pattern.pattern[:30]],
                    transition_recommended="action_committed",
                )

        # 7. Explicit Rejection
        for pattern in REJECTION_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.REJECTION.to_model_intent(),
                    confidence=0.92,
                    raw_text=raw_text,
                    signals_detected=["explicit_rejection", pattern.pattern[:30]],
                    transition_recommended="end",
                )

        # 8. Confirmation Patterns ("slot 1", "that's correct", "wednesday works")
        for pattern in CONFIRMATION_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.CONFIRMATION.to_model_intent(),
                    confidence=0.90,
                    raw_text=raw_text,
                    signals_detected=["confirmation_selected", pattern.pattern[:30]],
                    transition_recommended="action_committed",
                )

        # 9. Objections ("too expensive", "busy right now", "baad mein")
        for pattern in OBJECTION_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.OBJECTION.to_model_intent(),
                    confidence=0.86,
                    raw_text=raw_text,
                    signals_detected=["objection_friction", pattern.pattern[:30]],
                    transition_recommended="address_objection",
                )

        # 10. Question / Inquiry Patterns
        for pattern in QUESTION_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.QUESTION.to_model_intent(),
                    confidence=0.88,
                    raw_text=raw_text,
                    signals_detected=["question_inquiry", pattern.pattern[:30]],
                    transition_recommended="answer_inquiry",
                )

        # 11. Interest Patterns ("tell me more", "sounds interesting", "aur batao")
        for pattern in INTEREST_PATTERNS:
            if pattern.search(clean):
                return DetectedIntent(
                    intent_type=IntentCategory.INTEREST.to_model_intent(),
                    confidence=0.85,
                    raw_text=raw_text,
                    signals_detected=["interest_curiosity", pattern.pattern[:30]],
                    transition_recommended="qualify",
                )

        # 12. Fallback: Unknown remains Unknown (Zero forcing of arbitrary categories)
        return DetectedIntent(
            intent_type=IntentCategory.UNKNOWN.to_model_intent(),
            confidence=0.20,
            raw_text=raw_text,
            signals_detected=["unrecognized_tokens"],
            transition_recommended=None,
        )
