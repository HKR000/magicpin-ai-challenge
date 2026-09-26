"""Payload diff and change detection for context updates."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field
from vera.models.base import VeraBaseModel


class ChangeType(str, Enum):
    """Classification of an entity delta."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class FieldChange(VeraBaseModel):
    """Specific field modification detected between context versions."""

    field_path: str = Field(..., min_length=1, description="Dotted path of field modified")
    change_type: ChangeType = Field(..., description="added, removed, or modified")
    old_value: Optional[Any] = Field(default=None, description="Previous value or None if added")
    new_value: Optional[Any] = Field(default=None, description="New value or None if removed")


def compute_payload_diff(
    old_obj: Any,
    new_obj: Any,
    prefix: str = "",
) -> List[FieldChange]:
    """Recursively computes field-level differences between two payloads."""
    changes: List[FieldChange] = []

    # Case 1: Both are dictionaries
    if isinstance(old_obj, dict) and isinstance(new_obj, dict):
        all_keys = set(old_obj.keys()).union(set(new_obj.keys()))
        for key in sorted(all_keys):
            curr_path = f"{prefix}.{key}" if prefix else str(key)
            if key not in old_obj:
                changes.append(
                    FieldChange(
                        field_path=curr_path,
                        change_type=ChangeType.ADDED,
                        old_value=None,
                        new_value=new_obj[key],
                    )
                )
            elif key not in new_obj:
                changes.append(
                    FieldChange(
                        field_path=curr_path,
                        change_type=ChangeType.REMOVED,
                        old_value=old_obj[key],
                        new_value=None,
                    )
                )
            else:
                changes.extend(compute_payload_diff(old_obj[key], new_obj[key], curr_path))

    # Case 2: Values are of different types or different values
    elif old_obj != new_obj:
        changes.append(
            FieldChange(
                field_path=prefix or "root",
                change_type=ChangeType.MODIFIED,
                old_value=old_obj,
                new_value=new_obj,
            )
        )

    return changes
