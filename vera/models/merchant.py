"""MerchantContext entity and associated operational models."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import ConfigDict, Field
from vera.models.base import VeraBaseModel


class MerchantIdentity(VeraBaseModel):
    """Business identity, location, and owner demographics."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Official trade or brand name of the merchant")
    city: str = Field(..., min_length=1, description="City of operation (e.g., Delhi, Mumbai)")
    locality: str = Field(..., min_length=1, description="Sub-locality / neighbourhood (e.g., Lajpat Nagar)")
    place_id: Optional[str] = Field(default=None, description="Google Maps Place ID if linked")
    verified: bool = Field(default=False, description="Whether Google Business Profile is verified")
    languages: List[str] = Field(default_factory=lambda: ["en"], description="Languages spoken / preferred")
    owner_first_name: Optional[str] = Field(default=None, description="First name of the decision maker / owner")
    established_year: Optional[int] = Field(default=None, ge=1800, le=2100, description="Year business was established")


class Subscription(VeraBaseModel):
    """magicpin platform subscription details."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    status: str = Field(..., description="Subscription status (active, expiring, expired, lapsed, trial, cancelled)")
    plan: str = Field(default="Pro", description="Tier name (e.g., Pro, Basic, Trial)")
    days_remaining: Optional[int] = Field(default=None, description="Days until renewal is required (for active/expiring/trial)")
    days_since_expiry: Optional[int] = Field(default=None, ge=0, description="Days passed since plan expired (for expired plans)")
    renewed_at: Optional[str] = Field(default=None, description="ISO timestamp of last renewal")


class PerformanceDelta(VeraBaseModel):
    """7-day shift in performance metrics."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    views_pct: float = Field(default=0.0, description="Week-over-week shift in GBP views (+0.18 = +18%)")
    calls_pct: float = Field(default=0.0, description="Week-over-week shift in call inquiries")
    ctr_pct: Optional[float] = Field(default=None, description="Week-over-week shift in CTR")


class PerformanceSnapshot(VeraBaseModel):
    """Historical GBP and magicpin performance snapshot."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    window_days: int = Field(default=30, ge=1, description="Analysis window in days (default 30)")
    views: int = Field(..., ge=0, description="Total views over the window")
    calls: int = Field(..., ge=0, description="Total call clicks over the window")
    directions: int = Field(..., ge=0, description="Total direction requests over the window")
    ctr: float = Field(..., ge=0.0, le=1.0, description="Click-through rate")
    leads: Optional[int] = Field(default=None, ge=0, description="Total lead submissions generated")
    delta_7d: Optional[PerformanceDelta] = Field(default=None, description="Short-term 7-day velocity deltas")


class MerchantOffer(VeraBaseModel):
    """Specific offer running on the merchant's listing."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str = Field(..., min_length=1, description="Unique offer identifier")
    title: str = Field(..., min_length=1, description="Offer display name with service+price anchor")
    status: str = Field(..., description="Status (active, expired, paused)")
    started: Optional[str] = Field(default=None, description="ISO timestamp or date offer began")
    ended: Optional[str] = Field(default=None, description="ISO timestamp or date offer ended")


class ConversationTurnRecord(VeraBaseModel):
    """Historical conversation exchange stored in merchant context."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    ts: str = Field(..., description="ISO timestamp when turn was sent")
    from_role: str = Field(..., alias="from", description="Speaker identity (vera or merchant)")
    body: str = Field(..., min_length=1, description="Message text")
    engagement: Optional[str] = Field(default=None, description="Categorization tag (e.g., merchant_replied, intent_action)")


class CustomerAggregate(VeraBaseModel):
    """Aggregated customer metrics for the merchant."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    total_unique_ytd: Optional[int] = Field(default=None, ge=0, description="Total unique patients/clients year-to-date")
    total_active_members: Optional[int] = Field(default=None, ge=0, description="Active gym or club members count")
    lapsed_180d_plus: Optional[int] = Field(default=None, ge=0, description="Count of customers not seen in >180 days")
    lapsed_90d_plus: Optional[int] = Field(default=None, ge=0, description="Count of customers not seen in >90 days")
    retention_6mo_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="6-month retention rate")
    retention_3mo_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="3-month retention rate")
    retention_30d_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="30-day retention rate")
    repeat_customer_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Repeat customer percentage")
    delivery_share_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Delivery share of total orders")
    monthly_churn_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Monthly member churn rate")
    trial_to_paid_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Trial to paid member conversion")
    chronic_rx_count: Optional[int] = Field(default=None, ge=0, description="Count of chronic prescription patients")
    delivery_orders_30d: Optional[int] = Field(default=None, ge=0, description="30-day delivery orders")
    dine_in_orders_30d: Optional[int] = Field(default=None, ge=0, description="30-day dine-in covers")


class ReviewTheme(VeraBaseModel):
    """Recurring sentiment or topical cluster from customer reviews."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    theme: str = Field(..., min_length=1, description="Topic tag (e.g., wait_time, doctor_manner)")
    sentiment: str = Field(..., description="Sentiment polarities: pos, neg, neutral")
    occurrences_30d: int = Field(..., ge=0, description="Number of mentions in past 30 days")
    common_quote: Optional[str] = Field(default=None, description="Exemplar verbatim snippet from review")


class MerchantContext(VeraBaseModel):
    """Full operational state of a specific merchant."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    merchant_id: str = Field(..., min_length=1, description="Unique merchant ID (e.g., m_001_drmeera_dentist_delhi)")
    category_slug: str = Field(..., min_length=1, description="Vertical slug binding merchant to category")
    identity: MerchantIdentity = Field(..., description="Business identity, name, location, and owner info")
    subscription: Subscription = Field(..., description="Platform subscription plan and status")
    performance: PerformanceSnapshot = Field(..., description="Listing metrics and recent velocity")
    offers: List[MerchantOffer] = Field(default_factory=list, description="Active and historical offers")
    conversation_history: List[ConversationTurnRecord] = Field(default_factory=list, description="Historical exchanges with Vera")
    customer_aggregate: CustomerAggregate = Field(..., description="CRM customer counts and cohort stats")
    signals: List[str] = Field(default_factory=list, description="Pre-computed operational signals")
    review_themes: List[ReviewTheme] = Field(default_factory=list, description="Aggregated customer review sentiments")
