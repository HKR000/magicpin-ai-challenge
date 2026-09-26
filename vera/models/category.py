"""CategoryContext entity and child domain representations."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import ConfigDict, Field
from vera.models.base import VeraBaseModel


class VoiceProfile(VeraBaseModel):
    """Voice, register, and tone configuration for a business vertical."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=(), str_strip_whitespace=True)

    tone: str = Field(..., description="Overall voice tone (e.g., peer_clinical, warm_inviting)")
    register_style: Optional[str] = Field(default=None, alias="register", description="Sociolinguistic register (e.g., respectful_collegial)")
    code_mix: Optional[str] = Field(default=None, description="Language mixing guidance (e.g., hindi_english_natural)")
    vocab_allowed: List[str] = Field(default_factory=list, description="Approved vertical vocabulary terms")
    vocab_taboo: List[str] = Field(default_factory=list, description="Strictly prohibited claim words (e.g., guaranteed, cure)")
    salutation_examples: List[str] = Field(default_factory=list, description="Recommended salutations")
    tone_examples: List[str] = Field(default_factory=list, description="Canonical examples of tone in action")


class OfferTemplate(VeraBaseModel):
    """Canonical service+price pattern for a category."""

    id: str = Field(..., min_length=1, description="Unique offer identifier")
    title: str = Field(..., min_length=1, description="Display title of the offer (e.g., 'Dental Cleaning @ ₹299')")
    value: str = Field(..., description="Monetary or discount value indicator (e.g., '299', 'BOGO', '30%')")
    audience: str = Field(..., description="Target segment (e.g., new_user, repeat_user, all)")
    type: str = Field(..., description="Offer structure type (e.g., service_at_price, free_service, bogo, percentage_discount)")


class PeerStats(VeraBaseModel):
    """City/metro benchmark metrics for a category."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    scope: Optional[str] = Field(default=None, description="Geographic and cohort scope of benchmarks")
    avg_rating: float = Field(..., ge=0.0, le=5.0, description="Average review rating (0.0 to 5.0)")
    avg_review_count: int = Field(..., ge=0, description="Average count of customer reviews")
    avg_views_30d: Optional[int] = Field(default=None, ge=0, description="Average 30-day GBP views")
    avg_calls_30d: Optional[int] = Field(default=None, ge=0, description="Average 30-day phone call inquiries")
    avg_directions_30d: Optional[int] = Field(default=None, ge=0, description="Average 30-day directions requested")
    avg_ctr: float = Field(..., ge=0.0, le=1.0, description="Average click-through rate (0.0 to 1.0)")
    avg_photos: Optional[int] = Field(default=None, ge=0, description="Average listing photo count")
    avg_post_freq_days: Optional[int] = Field(default=None, ge=0, description="Average days between GBP posts")
    retention_6mo_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="6-month customer retention")
    retention_30d_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="30-day customer retention")


class DigestItem(VeraBaseModel):
    """Weekly curated industry, research, compliance, or trend intelligence item."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str = Field(..., min_length=1, description="Unique digest item identifier")
    kind: str = Field(..., description="Classification (research, compliance, cde, trend, tech, seasonal, supply)")
    title: str = Field(..., min_length=1, description="Digest headline")
    source: str = Field(..., min_length=1, description="Publication, agency, or data source citation")
    summary: str = Field(..., min_length=1, description="Core informational summary")
    actionable: Optional[str] = Field(default=None, description="Concrete recommendation or operational takeaway")
    trial_n: Optional[int] = Field(default=None, ge=0, description="Clinical trial sample size if applicable")
    patient_segment: Optional[str] = Field(default=None, description="Specific patient/customer cohort examined")
    deadline_iso: Optional[str] = Field(default=None, description="Regulatory compliance deadline if applicable")
    date: Optional[str] = Field(default=None, description="Event or publication date")
    credits: Optional[int] = Field(default=None, ge=0, description="Continuing education credits if applicable")


class PatientContentItem(VeraBaseModel):
    """Ready-to-share educational or informational content for merchant customers."""

    id: str = Field(..., min_length=1, description="Unique content identifier")
    title: str = Field(..., min_length=1, description="Content title")
    channel: str = Field(default="whatsapp", description="Target delivery channel")
    length_seconds: Optional[int] = Field(default=None, ge=0, description="Estimated read/watch duration")
    body: str = Field(..., min_length=1, description="Full customer-facing text")


class SeasonalBeat(VeraBaseModel):
    """Recurring seasonal or calendar demand dynamic."""

    month_range: str = Field(..., min_length=1, description="Active months (e.g., 'Nov-Feb', 'May-June')")
    note: str = Field(..., min_length=1, description="Description of the demand shift")


class TrendSignal(VeraBaseModel):
    """Local or metro macro search and consumer trend signal."""

    query: str = Field(..., min_length=1, description="Search query or keyword cluster")
    delta_yoy: float = Field(..., description="Year-over-year search volume shift (+0.62 = +62%)")
    segment_age: Optional[str] = Field(default=None, description="Primary age demographic affected")
    skew: Optional[str] = Field(default=None, description="Demographic or gender skew (e.g., female, male, balanced)")


class CategoryContext(VeraBaseModel):
    """Vertical domain knowledge pack shared across all merchants in a category."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    slug: str = Field(..., min_length=1, description="Canonical category slug: dentists, salons, restaurants, gyms, pharmacies")
    display_name: Optional[str] = Field(default=None, description="Human readable category name")
    voice: VoiceProfile = Field(..., description="Tone, vocabulary, and taboo constraints")
    offer_catalog: List[OfferTemplate] = Field(default_factory=list, description="Standard service+price templates")
    peer_stats: PeerStats = Field(..., description="Vertical benchmarks for performance comparison")
    digest: List[DigestItem] = Field(default_factory=list, description="Weekly curated intelligence items")
    patient_content_library: List[PatientContentItem] = Field(default_factory=list, description="Patient education collateral")
    seasonal_beats: List[SeasonalBeat] = Field(default_factory=list, description="Annual seasonal demand patterns")
    trend_signals: List[TrendSignal] = Field(default_factory=list, description="Macro consumer search signals")
    regulatory_authorities: List[str] = Field(default_factory=list, description="Regulatory oversight bodies")
    professional_journals: List[str] = Field(default_factory=list, description="Leading vertical trade publications and journals")
