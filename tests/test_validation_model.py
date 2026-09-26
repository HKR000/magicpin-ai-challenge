"""Unit tests for ValidationResult and ValidationErrorDetail models."""

import unittest
from pydantic import BaseModel, Field, ValidationError
from vera.models.validation import (
    ValidationErrorDetail,
    ValidationResult,
    ValidationStatus,
)


class DummySample(BaseModel):
    name: str = Field(..., min_length=2)
    score: int = Field(..., ge=0, le=100)


class TestValidationModel(unittest.TestCase):
    """Test suite for Validation audit models."""

    def test_validation_success_factory(self):
        res = ValidationResult.success(entity_type="CategoryContext", warnings=["Minor notice"])
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, ValidationStatus.VALID)
        self.assertEqual(len(res.errors), 0)
        self.assertEqual(len(res.warnings), 1)

    def test_from_pydantic_error(self):
        try:
            DummySample.model_validate({"name": "A", "score": 150})
            self.fail("Should have raised ValidationError")
        except ValidationError as exc:
            res = ValidationResult.from_pydantic_error(entity_type="DummySample", exc=exc)
            self.assertFalse(res.is_valid)
            self.assertEqual(res.status, ValidationStatus.INVALID)
            self.assertGreaterEqual(len(res.errors), 2)
            fields = [e.field for e in res.errors]
            self.assertIn("name", fields)
            self.assertIn("score", fields)

    def test_serialization_roundtrip(self):
        detail = ValidationErrorDetail(
            field="peer_stats.avg_rating",
            message="Input should be less than or equal to 5.0",
            invalid_value=6.2,
        )
        res = ValidationResult(
            status=ValidationStatus.INVALID,
            entity_type="CategoryContext",
            errors=[detail],
            warnings=[],
        )
        json_data = res.to_json()
        deserialized = ValidationResult.from_json(json_data)
        self.assertEqual(deserialized.errors[0].field, "peer_stats.avg_rating")
        self.assertEqual(deserialized.errors[0].invalid_value, 6.2)


if __name__ == "__main__":
    unittest.main()
