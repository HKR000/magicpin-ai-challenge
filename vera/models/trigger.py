"""TriggerContext entity and trigger classification models."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import Field, field_validator
from vera.models.base import VeraBaseModel


class TriggerScope(str, Enum):
    """Scope defining intended recipient audience."""

    MERCHANT = "merchant"
    CUSTOMER = "customer"


class TriggerSource(str, Enum):
    """Origin of the trigger event."""

    EXTERNAL = "external"
    INTERNAL = "internal"


class TriggerKind(str, Enum):
    """Common trigger event families from challenge specification."""

    RESEARCH_DIGEST = "research_digest"
    REGULATION_CHANGE = "regulation_change"
    RECALL_DUE = "recall_due"
    PERF_DIP = "perf_dip"
    PERF_SPIKE = "perf_spike"
    RENEWAL_DUE = "renewal_due"
    FESTIVAL_UPCOMING = "festival_upcoming"
    WEDDING_PACKAGE_FOLLOWUP = "wedding_package_followup"
    CURIOUS_ASK_DUE = "curious_ask_due"
    DORMANT_WITH_VERA = "dormant_with_vera"
    MILESTONE_REACHED = "milestone_reached"
    WEATHER_HEATWAVE = "weather_heatwave"
    LOCAL_NEWS_EVENT = "local_news_event"
    COMPETITOR_OPENED = "competitor_opened"
    CATEGORY_TREND_MOVEMENT = "category_trend_movement"
    SCHEDULED_RECURRING = "scheduled_recurring"
    OTHER = "other"


class TriggerContext(VeraBaseModel):
    """Event that prompts Vera to initiate outreach."""

    id: str = Field(..., min_length=1, description="Unique trigger identifier (e.g., trg_001_research_digest)")
    scope: TriggerScope = Field(..., description="Target audience scope: merchant or customer")
    kind: str = Field(..., min_length=1, description="Trigger classification family")
    source: TriggerSource = Field(..., description="Origin of event: external or internal")
    merchant_id: str = Field(..., min_length=1, description="Target merchant or merchant sponsor")
    customer_id: Optional[str] = Field(default=None, description="Target customer ID if scope == customer")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific parameters and metadata")
    urgency: int = Field(default=2, ge=1, le=5, description="Urgency rating from 1 (lowest) to 5 (critical)")
    suppression_key: str = Field(..., min_length=1, description="Deduplication key for rate-limiting and frequency capping")
    expires_at: str = Field(..., min_length=1, description="ISO timestamp after which trigger is void")

    @field_validator("customer_id")
    @classmethod
    def validate_customer_scope(cls, v: Optional[str], info) -> Optional[str]:
        scope = info.data.get("scope")
        if scope == TriggerScope.CUSTOMER and not v:
            raise ValueError("customer_id is required when trigger scope is 'customer'")
        return v
