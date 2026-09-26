"""Vera Context Engine package."""

from vera.context.diff import ChangeType, FieldChange, compute_payload_diff
from vera.context.engine import (
    AssembledContext,
    ContextEngine,
    IngestionOutcome,
    StoredEntity,
)
from vera.context.provenance import FactProvenance, ProvenanceTracker


def __getattr__(name: str):
    if name == "ContextSelector":
        from vera.context.selector import ContextSelector
        return ContextSelector
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "ContextEngine",
    "ContextSelector",
    "StoredEntity",
    "IngestionOutcome",
    "AssembledContext",
    "FactProvenance",
    "ProvenanceTracker",
    "ChangeType",
    "FieldChange",
    "compute_payload_diff",
]


