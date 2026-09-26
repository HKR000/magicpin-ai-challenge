"""Verified intent categories and classification mappings for the Vera engine."""

from __future__ import annotations
from enum import Enum
from vera.models.intent import IntentType


class IntentCategory(str, Enum):
    """Fine-grained intent categories verified from challenge specification."""

    ACCEPTANCE = "acceptance"
    REJECTION = "rejection"
    QUESTION = "question"
    CLARIFICATION = "clarification"
    INTEREST = "interest"
    CONFIRMATION = "confirmation"
    OBJECTION = "objection"
    GENERIC_AUTO_REPLY = "generic_auto_reply"
    OFF_TOPIC = "off_topic"
    HOSTILE = "hostile"
    UNKNOWN = "unknown"

    def to_model_intent(self) -> IntentType:
        """Map fine-grained category to core model IntentType enum."""
        mapping = {
            IntentCategory.ACCEPTANCE: IntentType.COMMITMENT,
            IntentCategory.REJECTION: IntentType.HOSTILE_OPT_OUT,
            IntentCategory.QUESTION: IntentType.INQUIRY,
            IntentCategory.CLARIFICATION: IntentType.INQUIRY,
            IntentCategory.INTEREST: IntentType.QUALIFICATION,
            IntentCategory.CONFIRMATION: IntentType.COMMITMENT,
            IntentCategory.OBJECTION: IntentType.QUALIFICATION,
            IntentCategory.GENERIC_AUTO_REPLY: IntentType.AUTO_REPLY,
            IntentCategory.OFF_TOPIC: IntentType.OFF_TOPIC,
            IntentCategory.HOSTILE: IntentType.HOSTILE_OPT_OUT,
            IntentCategory.UNKNOWN: IntentType.UNKNOWN,
        }
        return mapping.get(self, IntentType.UNKNOWN)
