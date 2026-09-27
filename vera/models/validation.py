"""Validation audit and error reporting models."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
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


class ValidationDimension(str, Enum):
    """13 mandatory validation criteria for Level 10 Output Validation."""

    FACTUALITY = "factuality"
    RELEVANCE = "relevance"
    SPECIFICITY = "specificity"
    CATEGORY_FIT = "category_fit"
    MERCHANT_FIT = "merchant_fit"
    TRIGGER_FIT = "trigger_fit"
    CUSTOMER_FIT = "customer_fit"
    LANGUAGE = "language"
    LENGTH = "length"
    CTA = "cta"
    REPETITION = "repetition"
    HALLUCINATION = "hallucination"
    FORMAT = "format"


class DimensionAudit(VeraBaseModel):
    """Detailed score and observations for a single validation criterion."""

    dimension: ValidationDimension
    passed: bool
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    observation: Optional[str] = None


class OutputValidationReport(VeraBaseModel):
    """Independent validation audit for generated WhatsApp communications."""

    is_valid: bool = Field(..., description="Whether output passed all 13 independent checks")
    dimensions: Dict[str, DimensionAudit] = Field(default_factory=dict, description="Detailed 13-dimension audit breakdown")
    failures: List[ValidationErrorDetail] = Field(default_factory=list, description="Specific failing criteria details")
    repaired: bool = Field(default=False, description="Whether output was successfully repaired after an initial failure")
    retry_count: int = Field(default=0, ge=0, description="Number of regeneration / repair attempts performed")
    used_fallback: bool = Field(default=False, description="Whether safe fallback was invoked due to exhausted retries")
    final_body: Optional[str] = Field(default=None, description="Final approved message text")
    template_name: Optional[str] = Field(default=None, description="Approved Meta WhatsApp template name")
    template_params: Optional[List[str]] = Field(default=None, description="Positional template substitutions")

