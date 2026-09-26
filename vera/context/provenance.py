"""Context provenance tracking for facts across entities and versions."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel


class FactProvenance(VeraBaseModel):
    """Provenance record tracking origin, entity, and version for a fact."""

    entity_id: str = Field(..., min_length=1, description="Entity identifier (slug, merchant_id, etc.)")
    scope: str = Field(..., min_length=1, description="Entity partition (category, merchant, customer, trigger)")
    field_path: str = Field(..., min_length=1, description="Dotted path of field (e.g., identity.name, performance.views)")
    value: Any = Field(..., description="Current value of the fact")
    context_version: int = Field(..., ge=1, description="Context version that introduced or updated this value")
    source: str = Field(default="context_push", description="Origin of this update (e.g., initial_load, adaptive_injection)")
    recorded_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z", description="Audit timestamp")


class ProvenanceTracker:
    """Thread-safe index for tracking fact provenance across all entities."""

    def __init__(self):
        # (entity_id, field_path) -> FactProvenance
        self._index: Dict[tuple[str, str], FactProvenance] = {}
        # entity_id -> set of field_paths
        self._entity_fields: Dict[str, set[str]] = {}

    def record_fact(
        self,
        entity_id: str,
        scope: str,
        field_path: str,
        value: Any,
        version: int,
        source: str = "context_push",
        recorded_at: Optional[str] = None,
    ) -> FactProvenance:
        """Record or update provenance for a specific field path."""
        ts = recorded_at or (datetime.utcnow().isoformat() + "Z")
        record = FactProvenance(
            entity_id=entity_id,
            scope=scope,
            field_path=field_path,
            value=value,
            context_version=version,
            source=source,
            recorded_at=ts,
        )
        self._index[(entity_id, field_path)] = record
        self._entity_fields.setdefault(entity_id, set()).add(field_path)
        return record

    def index_payload(
        self,
        scope: str,
        entity_id: str,
        version: int,
        payload: Dict[str, Any],
        source: str = "context_push",
        recorded_at: Optional[str] = None,
    ) -> List[FactProvenance]:
        """Flatten a payload dictionary and record provenance for all nested scalar/list leaves."""
        recorded = []

        def _walk(obj: Any, prefix: str):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_prefix = f"{prefix}.{k}" if prefix else str(k)
                    _walk(v, new_prefix)
            elif isinstance(obj, list):
                # Also index the list itself as a collection
                rec = self.record_fact(entity_id, scope, prefix, obj, version, source, recorded_at)
                recorded.append(rec)
                for idx, item in enumerate(obj):
                    new_prefix = f"{prefix}.{idx}"
                    _walk(item, new_prefix)
            else:
                rec = self.record_fact(entity_id, scope, prefix, obj, version, source, recorded_at)
                recorded.append(rec)

        _walk(payload, "")
        return recorded

    def get_provenance(self, entity_id: str, field_path: Optional[str] = None) -> List[FactProvenance]:
        """Retrieve provenance records for an entity or specific field."""
        if field_path is not None:
            rec = self._index.get((entity_id, field_path))
            return [rec] if rec else []

        fields = self._entity_fields.get(entity_id, set())
        return [self._index[(entity_id, fp)] for fp in sorted(fields) if (entity_id, fp) in self._index]

    def has_fact(self, entity_id: str, field_path: str) -> bool:
        """Check whether a specific fact is tracked."""
        return (entity_id, field_path) in self._index

    def search_value(self, query_val: Any) -> List[FactProvenance]:
        """Find facts across all entities matching a given value."""
        results = []
        for prov in self._index.values():
            if prov.value == query_val:
                results.append(prov)
        return results

    def clear(self):
        """Clear the provenance index."""
        self._index.clear()
        self._entity_fields.clear()
