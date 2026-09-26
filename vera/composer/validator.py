"""Message Validation and Safety Audit Layer for Vera (Level 9)."""

from __future__ import annotations
import re
from typing import List, Optional, Set, Tuple

from vera.models.decision import Decision
from vera.models.message import ComposedMessage, CtaType, SendAsIdentity


class MessageValidationError(ValueError):
    """Raised when a generated message fails safety or grounding audits."""
    pass


class MessageValidator:
    """
    Validates drafted WhatsApp communications against safety rules,
    factual grounding, taboo constraints, and repetition filters.
    """

    FORBIDDEN_INTERNAL_TOKENS = [
        "[redacted",
        "irrelevant",
        "trigger_kind",
        "priority_score",
        "state.",
        "selectionbundle",
        "contextselector",
        "decision_type",
        "llm",
        "prompt",
        "internal_crm",
    ]

    def validate(
        self,
        message: ComposedMessage,
        decision: Decision,
        previous_messages: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Audits message for:
        1. Schema integrity
        2. Recipient / identity alignment
        3. Taboo vocabulary violations
        4. Internal reasoning leakage
        5. Factual grounding
        6. Unnecessary repetition
        7. Concision

        Returns (is_valid, validation_notes).
        """
        notes: List[str] = []
        body_lower = message.body.lower()

        # ---------------------------------------------------------------------
        # 1. Schema & Length Check
        # ---------------------------------------------------------------------
        if not message.body or not message.body.strip():
            notes.append("FAIL: Message body is empty")
            return False, notes

        if len(message.body) > 600:
            notes.append(f"FAIL: Message exceeds concision threshold ({len(message.body)} chars > 600)")
            return False, notes

        # ---------------------------------------------------------------------
        # 2. Recipient Role & Sender Attribution
        # ---------------------------------------------------------------------
        expected_sender = (
            SendAsIdentity.MERCHANT_ON_BEHALF
            if decision.recipient.recipient_role == "customer"
            else SendAsIdentity.VERA
        )
        if message.send_as != expected_sender:
            notes.append(
                f"FAIL: Sender identity mismatch. Expected '{expected_sender.value}' for {decision.recipient.recipient_role} recipient, got '{message.send_as.value}'"
            )
            return False, notes

        # ---------------------------------------------------------------------
        # 3. Taboo Vocabulary Audit
        # ---------------------------------------------------------------------
        taboo_words: Set[str] = set()
        for fact in decision.selected_facts.mandatory_facts:
            if fact.key == "category_vocab_taboo":
                if isinstance(fact.value, list):
                    for w in fact.value:
                        taboo_words.add(str(w).lower())
                elif isinstance(fact.value, str):
                    taboo_words.add(fact.value.lower())

        for taboo in taboo_words:
            if taboo and taboo in body_lower:
                notes.append(f"FAIL: Category taboo word detected in draft: '{taboo}'")
                return False, notes

        # ---------------------------------------------------------------------
        # 4. Internal Reasoning & Token Leakage Audit
        # ---------------------------------------------------------------------
        for token in self.FORBIDDEN_INTERNAL_TOKENS:
            if token in body_lower:
                notes.append(f"FAIL: Internal reasoning/debug token leaked in message: '{token}'")
                return False, notes

        # ---------------------------------------------------------------------
        # 5. Factual Grounding & Anti-Hallucination Audit
        # ---------------------------------------------------------------------
        # Ensure that facts marked unavailable are NOT asserted
        for unavail in decision.selected_facts.unavailable_facts:
            if unavail.key == "merchant_place_id" and ("maps.google.com" in body_lower or "place_id" in body_lower):
                notes.append("FAIL: Asserted Google Place link when merchant_place_id is unavailable")
                return False, notes
            if unavail.key == "customer_context" and decision.recipient.recipient_role == "customer":
                notes.append("FAIL: Generated customer message when customer_context is unavailable")
                return False, notes

        # Grounding check: verify that message records which facts it grounded
        if not message.grounded_facts:
            notes.append("WARN: No grounded facts explicitly attached to message")

        # ---------------------------------------------------------------------
        # 6. Repetition Control Audit
        # ---------------------------------------------------------------------
        if previous_messages:
            for prev in previous_messages:
                prev_clean = prev.strip().lower()
                # Exact match check
                if body_lower == prev_clean:
                    notes.append("FAIL: Identical message already sent in previous turn")
                    return False, notes

                # High substring similarity check (e.g. full 2nd half repeated)
                if len(body_lower) > 40 and body_lower in prev_clean:
                    notes.append("FAIL: Substantial duplicate phrasing of previous message")
                    return False, notes

        notes.append("PASS: All safety, taboo, grounding, and repetition checks passed")
        return True, notes
