"""Data models for Level 7 Context Selection Engine and Fact Provenance Tiers."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from vera.context.provenance import FactProvenance
from vera.models.base import VeraBaseModel


class FactTier(str, Enum):
    """5 explicit fact relevance tiers for context selection."""

    MANDATORY = "mandatory"
    HIGH_VALUE = "high_value"
    SUPPORTING = "supporting"
    IRRELEVANT = "irrelevant"
    UNAVAILABLE = "unavailable"


class SelectedFact(VeraBaseModel):
    """A discrete verified fact extracted from context with full audit provenance."""

    key: str = Field(..., min_length=1, description="Semantic identifier (e.g. merchant_name, research_paper_trial_n)")
    value: Any = Field(..., description="Fact value (primitive, dict, or structured object)")
    tier: FactTier = Field(..., description="Assigned relevance tier")
    provenance: FactProvenance = Field(..., description="Audit origin, scope, version, and dotted JSON path")
    priority_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Arbitrated priority (0.0=lowest, 1.0=highest)")
    relevance_reason: str = Field(..., min_length=1, description="Deterministic justification for tier placement")
    is_stale: bool = Field(default=False, description="True if fact has been superseded, expired, or lapsed")


class UnavailableFact(VeraBaseModel):
    """Explicit record of a desired fact that is absent from context (prevents hallucination)."""

    key: str = Field(..., min_length=1, description="Name of missing fact")
    expected_scope: str = Field(..., description="Context scope where fact was sought (category, merchant, customer, trigger)")
    importance: str = Field(default="standard", description="'critical' if outreach cannot function, 'standard' otherwise")
    reason: str = Field(..., description="Explanation of why this fact was sought and not found")


class SelectionBundle(VeraBaseModel):
    """Container holding the 5 fact tiers selected for message generation."""

    mandatory_facts: List[SelectedFact] = Field(default_factory=list, description="Must-have operational and compliance facts")
    high_value_facts: List[SelectedFact] = Field(default_factory=list, description="Concrete anchors (prices, citations, slots, deltas)")
    supporting_facts: List[SelectedFact] = Field(default_factory=list, description="Enriching secondary context (locality, peer benchmarks)")
    irrelevant_facts: List[SelectedFact] = Field(default_factory=list, description="Filtered facts with no bearing on this message")
    unavailable_facts: List[UnavailableFact] = Field(default_factory=list, description="Required or desirable facts missing from payload")
    context_versions_used: Dict[str, int] = Field(default_factory=dict, description="Active context versions evaluated")
    total_facts_considered: int = Field(default=0, ge=0, description="Total facts evaluated during selection")

    def get_fact(self, key: str) -> Optional[SelectedFact]:
        """Finds a selected fact across active tiers (mandatory, high_value, supporting)."""
        for fact in self.mandatory_facts + self.high_value_facts + self.supporting_facts:
            if fact.key == key:
                return fact
        return None

    def has_fact(self, key: str) -> bool:
        """Returns True if fact exists in mandatory, high_value, or supporting tiers."""
        return self.get_fact(key) is not None

    def verify_provenance(self) -> bool:
        """Verifies that every selected fact contains valid, well-formed provenance metadata."""
        for fact in self.mandatory_facts + self.high_value_facts + self.supporting_facts + self.irrelevant_facts:
            if not fact.provenance or not fact.provenance.entity_id or not fact.provenance.field_path:
                return False
            if fact.provenance.context_version < 1:
                return False
        return True

    def tier_counts(self) -> Dict[str, int]:
        """Returns summary counts of facts per tier."""
        return {
            "mandatory": len(self.mandatory_facts),
            "high_value": len(self.high_value_facts),
            "supporting": len(self.supporting_facts),
            "irrelevant": len(self.irrelevant_facts),
            "unavailable": len(self.unavailable_facts),
        }

    def to_prompt_context(self, max_tokens: int = 1000) -> str:
        """
        Renders the selected facts into a concise, token-efficient, formatted string
        strictly grounded in context for LLM prompt composition.
        """
        lines = ["=== VERIFIED CONTEXT FACTS (ZERO HALLUCINATION REQUIRED) ==="]

        if self.mandatory_facts:
            lines.append("\n[MANDATORY FACTS]")
            for f in self.mandatory_facts:
                lines.append(f"- {f.key}: {f.value} (source: {f.provenance.scope}.{f.provenance.field_path} v{f.provenance.context_version})")

        if self.high_value_facts:
            lines.append("\n[HIGH-VALUE ANCHORS]")
            for f in self.high_value_facts:
                lines.append(f"- {f.key}: {f.value} (source: {f.provenance.scope}.{f.provenance.field_path} v{f.provenance.context_version})")

        if self.supporting_facts:
            lines.append("\n[SUPPORTING CONTEXT]")
            for f in self.supporting_facts:
                lines.append(f"- {f.key}: {f.value}")

        if self.unavailable_facts:
            lines.append("\n[UNAVAILABLE DATA — DO NOT INVENT]")
            for u in self.unavailable_facts:
                lines.append(f"- {u.key}: NOT PROVIDED ({u.reason})")

        return "\n".join(lines)
