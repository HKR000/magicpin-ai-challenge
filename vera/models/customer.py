"""CustomerContext entity and relationship models."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import ConfigDict, Field
from vera.models.base import VeraBaseModel


class CustomerState(str, Enum):
    """Lifecycle state of customer with this merchant."""

    NEW = "new"
    ACTIVE = "active"
    LAPSED_SOFT = "lapsed_soft"
    LAPSED_HARD = "lapsed_hard"
    CHURNED = "churned"


class CustomerIdentity(VeraBaseModel):
    """Individual customer demographic profile."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Customer given name or identifier")
    phone_redacted: Optional[str] = Field(default="<phone>", description="Redacted phone number string or null if unrecorded")
    language_pref: str = Field(default="english", description="Preferred language / code-mix (e.g., 'hi-en mix')")
    age_band: Optional[str] = Field(default=None, description="Age group (e.g., '25-35', 'child_under_12')")
    senior_citizen: Optional[bool] = Field(default=None, description="Flag indicating senior citizen cohort")


class CustomerRelationship(VeraBaseModel):
    """Historical visit frequency and services utilized."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    first_visit: str = Field(..., description="ISO date of first visit")
    last_visit: str = Field(..., description="ISO date of most recent visit")
    visits_total: int = Field(..., ge=0, description="Total completed visits/orders")
    services_received: List[str] = Field(default_factory=list, description="Historical list of services booked")
    lifetime_value: Optional[float] = Field(default=None, ge=0.0, description="Total spend in INR")
    favourite_dish: Optional[str] = Field(default=None, description="Preferred order item for restaurant context")
    chronic_conditions: Optional[List[str]] = Field(default=None, description="Diagnosed conditions for pharmacy context")


class CustomerPreferences(VeraBaseModel):
    """Booking slot and channel preferences."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    preferred_slots: Optional[str] = Field(default=None, description="Preferred booking slot (e.g., 'weekday_evening')")
    channel: str = Field(default="whatsapp", description="Preferred channel")
    reminder_opt_in: Optional[bool] = Field(default=True, description="Opt-in flag for automated reminders")
    preferred_stylist: Optional[str] = Field(default=None, description="Stylist preference for salon context")
    wedding_date: Optional[str] = Field(default=None, description="Wedding date for bridal/event workflows")


class CustomerConsent(VeraBaseModel):
    """Regulatory opt-in audit metadata."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    opted_in_at: Optional[str] = Field(default=None, description="ISO date of opt-in registration or null")
    scope: List[str] = Field(default_factory=list, description="Permitted communication scopes")


class CustomerContext(VeraBaseModel):
    """Individual client or patient record for customer-facing outreach."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    customer_id: str = Field(..., min_length=1, description="Unique customer ID (e.g., c_001_priya)")
    merchant_id: str = Field(..., min_length=1, description="Associated merchant ID")
    identity: CustomerIdentity = Field(..., description="Customer identity and language preferences")
    relationship: CustomerRelationship = Field(..., description="Visit history, spend, and services")
    state: CustomerState = Field(..., description="Lifecycle status (new, active, lapsed_soft, lapsed_hard, churned)")
    preferences: CustomerPreferences = Field(..., description="Scheduling and channel preferences")
    consent: CustomerConsent = Field(..., description="Opt-in record and allowed scopes")
