"""Base model configuration for Vera data entities."""

from __future__ import annotations
from typing import Any, Dict, Type, TypeVar
from pydantic import BaseModel, ConfigDict, ValidationError

T = TypeVar("T", bound="VeraBaseModel")


class VeraBaseModel(BaseModel):
    """Base Pydantic model for all Vera entities with strict validation defaults."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Safely deserialize a dict into the model."""
        return cls.model_validate(data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model to a dictionary using alias fields where appropriate."""
        return self.model_dump(by_alias=True, exclude_none=False)

    @classmethod
    def from_json(cls: Type[T], json_data: str) -> T:
        """Deserialize JSON string into model."""
        return cls.model_validate_json(json_data)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize model to JSON string."""
        return self.model_dump_json(by_alias=True, indent=indent)
