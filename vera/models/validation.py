"""Validation audit and error reporting models."""

from __future__ import annotations
from enum import Enum
from typing import Any, List, Optional
from pydantic import Field, ValidationError
from vera.models.base import VeraBaseModel


class ValidationStatus(str, Enum):
    """Integrity state of an entity or message."""

    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class ValidationErrorDetail(VeraBaseModel):
    """Specific field-level validation failure."""

    field: str = Field(..., description="Field path that failed validation")
    message: str = Field(..., min_length=1, description="Validation failure explanation")
    invalid_value: Optional[Any] = Field(default=None, description="The erroneous value received")


class ValidationResult(VeraBaseModel):
    """Comprehensive validation outcome for a payload or generated output."""

    status: ValidationStatus = Field(..., description="Overall status: valid, invalid, or warning")
    entity_type: str = Field(..., min_length=1, description="Class name or schema type evaluated")
    errors: List[ValidationErrorDetail] = Field(default_factory=list, description="List of blocking validation errors")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking observations or quality notices")

    @property
    def is_valid(self) -> bool:
        """Returns True if validation succeeded with zero blocking errors."""
        return self.status == ValidationStatus.VALID and len(self.errors) == 0

    @classmethod
    def success(cls, entity_type: str, warnings: Optional[List[str]] = None) -> ValidationResult:
        """Factory for a successful validation outcome."""
        return cls(
            status=ValidationStatus.VALID,
            entity_type=entity_type,
            errors=[],
            warnings=warnings or [],
        )

    @classmethod
    def from_pydantic_error(cls, entity_type: str, exc: ValidationError) -> ValidationResult:
        """Construct ValidationResult from a Pydantic ValidationError."""
        details = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            details.append(
                ValidationErrorDetail(
                    field=loc or "root",
                    message=err.get("msg", "Unknown error"),
                    invalid_value=err.get("input"),
                )
            )
        return cls(
            status=ValidationStatus.INVALID,
            entity_type=entity_type,
            errors=details,
            warnings=[],
        )
