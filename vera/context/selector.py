"""Context Selection Engine for Vera - Determines relevant facts with strict provenance."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from vera.context.provenance import FactProvenance
from vera.models.category import CategoryContext, DigestItem, OfferTemplate
from vera.models.conversation import ConversationState
from vera.models.customer import CustomerContext
from vera.models.intent import DetectedIntent, IntentType
from vera.models.merchant import MerchantContext, MerchantOffer
from vera.models.selection import (
    FactTier,
    SelectedFact,
    SelectionBundle,
    UnavailableFact,
)
from vera.models.trigger import TriggerContext


class ContextSelector:
    """Intelligently filters, categorizes, and prioritizes facts for message composition."""

    def select(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: Optional[CustomerContext] = None,
        conversation: Optional[ConversationState] = None,
        intent: Optional[DetectedIntent | IntentType | str] = None,
        context_versions: Optional[Dict[str, int]] = None,
        current_time_iso: Optional[str] = None,
    ) -> SelectionBundle:
        """
        Extracts verified facts from context, categorizes them into 5 explicit tiers,
        and enforces strict provenance and relevance filtering.
        """
        versions = context_versions or {
            "category": 1,
            "merchant": 1,
            "trigger": 1,
            "customer": 1,
        }
        cat_ver = versions.get("category", 1)
        mer_ver = versions.get("merchant", 1)
        trg_ver = versions.get("trigger", 1)
        cus_ver = versions.get("customer", 1)

        mandatory: List[SelectedFact] = []
        high_value: List[SelectedFact] = []
        supporting: List[SelectedFact] = []
        irrelevant: List[SelectedFact] = []
        unavailable: List[UnavailableFact] = []

        total_considered = 0

        # Normalise intent string
        intent_str = ""
        if intent:
            if isinstance(intent, DetectedIntent):
                intent_str = intent.intent_type.value
            elif isinstance(intent, IntentType):
                intent_str = intent.value
            elif isinstance(intent, str):
                intent_str = intent.lower()

        # =====================================================================
        # 1. TRIGGER FACTS
        # =====================================================================
        # Trigger identity & kind are MANDATORY
        mandatory.append(
            SelectedFact(
                key="trigger_kind",
                value=trigger.kind.value if hasattr(trigger.kind, "value") else str(trigger.kind),
                tier=FactTier.MANDATORY,
                provenance=FactProvenance(
                    entity_id=trigger.id,
                    scope="trigger",
                    field_path="kind",
                    value=trigger.kind,
                    context_version=trg_ver,
                ),
                priority_score=1.0,
                relevance_reason="Immediate catalyst explaining why message is triggered",
            )
        )
        total_considered += 1

        mandatory.append(
            SelectedFact(
                key="trigger_urgency",
                value=trigger.urgency,
                tier=FactTier.MANDATORY,
                provenance=FactProvenance(
                    entity_id=trigger.id,
                    scope="trigger",
                    field_path="urgency",
                    value=trigger.urgency,
                    context_version=trg_ver,
                ),
                priority_score=0.95,
                relevance_reason="Arbitration urgency level",
            )
        )
        total_considered += 1

        # Check trigger payload attributes
        payload = trigger.payload or {}
        top_item_id = payload.get("top_item_id")
        metric = payload.get("metric")
        delta_pct = payload.get("delta_pct")
        deadline_iso = payload.get("deadline_iso")
        available_slots = payload.get("available_slots")
        service_due = payload.get("service_due")

        if delta_pct is not None:
            high_value.append(
                SelectedFact(
                    key="trigger_delta_pct",
                    value=delta_pct,
                    tier=FactTier.HIGH_VALUE,
                    provenance=FactProvenance(
                        entity_id=trigger.id,
                        scope="trigger",
                        field_path="payload.delta_pct",
                        value=delta_pct,
                        context_version=trg_ver,
                    ),
                    priority_score=0.92,
                    relevance_reason="Concrete numeric performance shift driving outreach",
                )
            )
            total_considered += 1

        if available_slots:
            high_value.append(
                SelectedFact(
                    key="trigger_available_slots",
                    value=available_slots,
                    tier=FactTier.HIGH_VALUE,
                    provenance=FactProvenance(
                        entity_id=trigger.id,
                        scope="trigger",
                        field_path="payload.available_slots",
                        value=available_slots,
                        context_version=trg_ver,
                    ),
                    priority_score=0.96,
                    relevance_reason="Concrete low-friction appointment slot proposals",
                )
            )
            total_considered += 1

        # =====================================================================
        # 2. MERCHANT FACTS
        # =====================================================================
        # Merchant Name & Owner First Name
        if merchant.identity:
            if merchant.identity.name:
                mandatory.append(
                    SelectedFact(
                        key="merchant_name",
                        value=merchant.identity.name,
                        tier=FactTier.MANDATORY,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="identity.name",
                            value=merchant.identity.name,
                            context_version=mer_ver,
                        ),
                        priority_score=0.98,
                        relevance_reason="Primary business identity anchor",
                    )
                )
                total_considered += 1
            else:
                unavailable.append(
                    UnavailableFact(
                        key="merchant_name",
                        expected_scope="merchant",
                        importance="critical",
                        reason="Merchant identity name is empty or missing",
                    )
                )

            if merchant.category_slug:
                mandatory.append(
                    SelectedFact(
                        key="category_slug",
                        value=merchant.category_slug,
                        tier=FactTier.MANDATORY,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="category_slug",
                            value=merchant.category_slug,
                            context_version=mer_ver,
                        ),
                        priority_score=0.98,
                        relevance_reason="Vertical business category alignment",
                    )
                )
                total_considered += 1

            if merchant.identity.owner_first_name:
                mandatory.append(
                    SelectedFact(
                        key="owner_first_name",
                        value=merchant.identity.owner_first_name,
                        tier=FactTier.MANDATORY,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="identity.owner_first_name",
                            value=merchant.identity.owner_first_name,
                            context_version=mer_ver,
                        ),
                        priority_score=0.95,
                        relevance_reason="Personalized owner salutation anchor",
                    )
                )
                total_considered += 1

            if merchant.identity.locality:
                supporting.append(
                    SelectedFact(
                        key="merchant_locality",
                        value=merchant.identity.locality,
                        tier=FactTier.SUPPORTING,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="identity.locality",
                            value=merchant.identity.locality,
                            context_version=mer_ver,
                        ),
                        priority_score=0.75,
                        relevance_reason="Locality geographic anchor",
                    )
                )
                total_considered += 1

            if merchant.identity.languages:
                mandatory.append(
                    SelectedFact(
                        key="merchant_languages",
                        value=merchant.identity.languages,
                        tier=FactTier.MANDATORY,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="identity.languages",
                            value=merchant.identity.languages,
                            context_version=mer_ver,
                        ),
                        priority_score=0.90,
                        relevance_reason="Language register and code-mix preference",
                    )
                )
                total_considered += 1

            # Verification status & place_id check
            if not merchant.identity.place_id and trigger.kind == "unverified_gbp":
                unavailable.append(
                    UnavailableFact(
                        key="merchant_place_id",
                        expected_scope="merchant",
                        importance="critical",
                        reason="Google Place ID missing for GBP verification trigger",
                    )
                )

        # Merchant Subscription
        if merchant.subscription:
            sub_status = getattr(merchant.subscription, "status", None)
            # If scope is merchant-facing, subscription days remaining is relevant for renewals
            if trigger.scope.value == "merchant" or trigger.kind in {"renewal_due", "perf_dip"}:
                tier = FactTier.HIGH_VALUE if trigger.kind == "renewal_due" else FactTier.SUPPORTING
                high_value.append(
                    SelectedFact(
                        key="subscription_plan",
                        value=getattr(merchant.subscription, "plan", "Pro"),
                        tier=tier,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="subscription.plan",
                            value=merchant.subscription.plan,
                            context_version=mer_ver,
                        ),
                        priority_score=0.85,
                        relevance_reason="Current subscription tier",
                    )
                )
                total_considered += 1

                days_rem = getattr(merchant.subscription, "days_remaining", None)
                if days_rem is not None:
                    high_value.append(
                        SelectedFact(
                            key="subscription_days_remaining",
                            value=days_rem,
                            tier=FactTier.HIGH_VALUE if trigger.kind == "renewal_due" else FactTier.SUPPORTING,
                            provenance=FactProvenance(
                                entity_id=merchant.merchant_id,
                                scope="merchant",
                                field_path="subscription.days_remaining",
                                value=days_rem,
                                context_version=mer_ver,
                            ),
                            priority_score=0.90 if trigger.kind == "renewal_due" else 0.60,
                            relevance_reason="Days until subscription expiration",
                        )
                    )
                    total_considered += 1
            else:
                # If message is customer-facing, merchant subscription is IRRELEVANT (leak prevention!)
                irrelevant.append(
                    SelectedFact(
                        key="merchant_subscription_internal",
                        value=sub_status,
                        tier=FactTier.IRRELEVANT,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="subscription",
                            value="[REDACTED_INTERNAL]",
                            context_version=mer_ver,
                        ),
                        priority_score=0.0,
                        relevance_reason="Internal merchant subscription data must not leak into customer-facing message",
                    )
                )
                total_considered += 1

        # Merchant Customer Aggregates (CRM Cohorts)
        if merchant.customer_aggregate:
            if trigger.scope.value == "merchant":
                high_risk = getattr(merchant.customer_aggregate, "high_risk_adult_count", None)
                if high_risk is not None and (not top_item_id or "fluoride" in str(top_item_id).lower() or trigger.kind in {"research_digest", "perf_dip"}):
                    high_value.append(
                        SelectedFact(
                            key="cohort_high_risk_adults",
                            value=high_risk,
                            tier=FactTier.HIGH_VALUE,
                            provenance=FactProvenance(
                                entity_id=merchant.merchant_id,
                                scope="merchant",
                                field_path="customer_aggregate.high_risk_adult_count",
                                value=high_risk,
                                context_version=mer_ver,
                            ),
                            priority_score=0.94,
                            relevance_reason="Direct matching patient cohort for JIDA fluoride trial",
                        )
                    )
                    total_considered += 1
            else:
                # Customer facing: CRM aggregate internals are IRRELEVANT
                irrelevant.append(
                    SelectedFact(
                        key="merchant_crm_aggregate",
                        value="crm_stats",
                        tier=FactTier.IRRELEVANT,
                        provenance=FactProvenance(
                            entity_id=merchant.merchant_id,
                            scope="merchant",
                            field_path="customer_aggregate",
                            value="[REDACTED_CRM]",
                            context_version=mer_ver,
                        ),
                        priority_score=0.0,
                        relevance_reason="Merchant aggregate CRM metrics are irrelevant and confidential to customers",
                    )
                )
                total_considered += 1

        # Merchant Performance
        if merchant.performance and trigger.scope.value == "merchant":
            if trigger.kind in {"perf_dip", "perf_spike"}:
                delta_7d = getattr(merchant.performance, "delta_7d", None)
                if delta_7d:
                    calls_pct = getattr(delta_7d, "calls_pct", None)
                    views_pct = getattr(delta_7d, "views_pct", None)
                    if calls_pct is not None and metric == "calls":
                        high_value.append(
                            SelectedFact(
                                key="perf_calls_delta_7d",
                                value=calls_pct,
                                tier=FactTier.HIGH_VALUE,
                                provenance=FactProvenance(
                                    entity_id=merchant.merchant_id,
                                    scope="merchant",
                                    field_path="performance.delta_7d.calls_pct",
                                    value=calls_pct,
                                    context_version=mer_ver,
                                ),
                                priority_score=0.95,
                                relevance_reason="7-day calls percentage shift matching trigger metric",
                            )
                        )
                        total_considered += 1
                    if views_pct is not None:
                        supporting.append(
                            SelectedFact(
                                key="perf_views_delta_7d",
                                value=views_pct,
                                tier=FactTier.SUPPORTING,
                                provenance=FactProvenance(
                                    entity_id=merchant.merchant_id,
                                    scope="merchant",
                                    field_path="performance.delta_7d.views_pct",
                                    value=views_pct,
                                    context_version=mer_ver,
                                ),
                                priority_score=0.70,
                                relevance_reason="7-day views trend secondary context",
                            )
                        )
                        total_considered += 1
        elif merchant.performance and trigger.scope.value == "customer":
            irrelevant.append(
                SelectedFact(
                    key="merchant_internal_views_calls",
                    value="views_calls",
                    tier=FactTier.IRRELEVANT,
                    provenance=FactProvenance(
                        entity_id=merchant.merchant_id,
                        scope="merchant",
                        field_path="performance",
                        value="[REDACTED_PERF]",
                        context_version=mer_ver,
                    ),
                    priority_score=0.0,
                    relevance_reason="Merchant views/calls metrics must never be displayed to consumer",
                )
            )
            total_considered += 1

        # Merchant Offers: Filter expired offers, select active offers
        if merchant.offers:
            for off in merchant.offers:
                off_status = getattr(off, "status", "active")
                if off_status == "active":
                    # Check if offer is relevant to trigger
                    high_value.append(
                        SelectedFact(
                            key=f"active_offer_{off.id}",
                            value=f"{off.title}",
                            tier=FactTier.HIGH_VALUE,
                            provenance=FactProvenance(
                                entity_id=merchant.merchant_id,
                                scope="merchant",
                                field_path=f"offers.{off.id}",
                                value=off.title,
                                context_version=mer_ver,
                            ),
                            priority_score=0.92,
                            relevance_reason="Active catalog service+price offer anchor",
                        )
                    )
                    total_considered += 1
                else:
                    # Expired / paused offer must be filtered to IRRELEVANT (prevent stale leak!)
                    irrelevant.append(
                        SelectedFact(
                            key=f"expired_offer_{off.id}",
                            value=f"{off.title} (status: {off_status})",
                            tier=FactTier.IRRELEVANT,
                            provenance=FactProvenance(
                                entity_id=merchant.merchant_id,
                                scope="merchant",
                                field_path=f"offers.{off.id}.status",
                                value=off_status,
                                context_version=mer_ver,
                            ),
                            priority_score=0.0,
                            relevance_reason=f"Stale offer with status '{off_status}'; filtered to prevent generation leakage",
                            is_stale=True,
                        )
                    )
                    total_considered += 1

        # =====================================================================
        # 3. CATEGORY FACTS
        # =====================================================================
        # Category Voice Constraints: Taboo words are MANDATORY guardrails
        if category.voice and category.voice.vocab_taboo:
            mandatory.append(
                SelectedFact(
                    key="category_vocab_taboo",
                    value=category.voice.vocab_taboo,
                    tier=FactTier.MANDATORY,
                    provenance=FactProvenance(
                        entity_id=category.slug,
                        scope="category",
                        field_path="voice.vocab_taboo",
                        value=category.voice.vocab_taboo,
                        context_version=cat_ver,
                    ),
                    priority_score=1.0,
                    relevance_reason="Mandatory compliance taboo vocabulary (no false guarantees / cures)",
                )
            )
            total_considered += 1

        if category.voice and category.voice.tone:
            mandatory.append(
                SelectedFact(
                    key="category_tone",
                    value=category.voice.tone,
                    tier=FactTier.MANDATORY,
                    provenance=FactProvenance(
                        entity_id=category.slug,
                        scope="category",
                        field_path="voice.tone",
                        value=category.voice.tone,
                        context_version=cat_ver,
                    ),
                    priority_score=0.90,
                    relevance_reason="Vertical domain voice tone profile",
                )
            )
            total_considered += 1

        # Category Digest Items: Pick ONLY the item referenced by top_item_id
        if category.digest:
            for item in category.digest:
                if top_item_id and item.id == top_item_id:
                    # MATCHING ITEM -> MANDATORY & HIGH VALUE
                    mandatory.append(
                        SelectedFact(
                            key="digest_item_title",
                            value=item.title,
                            tier=FactTier.MANDATORY,
                            provenance=FactProvenance(
                                entity_id=category.slug,
                                scope="category",
                                field_path=f"digest.{item.id}.title",
                                value=item.title,
                                context_version=cat_ver,
                            ),
                            priority_score=0.98,
                            relevance_reason="Directly cited research digest topic",
                        )
                    )
                    total_considered += 1

                    if item.source:
                        high_value.append(
                            SelectedFact(
                                key="digest_item_source",
                                value=item.source,
                                tier=FactTier.HIGH_VALUE,
                                provenance=FactProvenance(
                                    entity_id=category.slug,
                                    scope="category",
                                    field_path=f"digest.{item.id}.source",
                                    value=item.source,
                                    context_version=cat_ver,
                                ),
                                priority_score=0.96,
                                relevance_reason="Exact publication/clinical trial source citation",
                            )
                        )
                        total_considered += 1

                    if getattr(item, "trial_n", None) is not None:
                        high_value.append(
                            SelectedFact(
                                key="digest_item_trial_n",
                                value=item.trial_n,
                                tier=FactTier.HIGH_VALUE,
                                provenance=FactProvenance(
                                    entity_id=category.slug,
                                    scope="category",
                                    field_path=f"digest.{item.id}.trial_n",
                                    value=item.trial_n,
                                    context_version=cat_ver,
                                ),
                                priority_score=0.95,
                                relevance_reason="Exact trial participant count for high specificity",
                            )
                        )
                        total_considered += 1

                    if item.summary:
                        high_value.append(
                            SelectedFact(
                                key="digest_item_summary",
                                value=item.summary,
                                tier=FactTier.HIGH_VALUE,
                                provenance=FactProvenance(
                                    entity_id=category.slug,
                                    scope="category",
                                    field_path=f"digest.{item.id}.summary",
                                    value=item.summary,
                                    context_version=cat_ver,
                                ),
                                priority_score=0.90,
                                relevance_reason="Specific study findings and percentage reduction metrics",
                            )
                        )
                        total_considered += 1
                else:
                    # Non-matching digest item -> IRRELEVANT (filter out unrelated research)
                    irrelevant.append(
                        SelectedFact(
                            key=f"unrelated_digest_{item.id}",
                            value=item.title,
                            tier=FactTier.IRRELEVANT,
                            provenance=FactProvenance(
                                entity_id=category.slug,
                                scope="category",
                                field_path=f"digest.{item.id}",
                                value=item.title,
                                context_version=cat_ver,
                            ),
                            priority_score=0.0,
                            relevance_reason="Unrelated category research item not referenced by trigger",
                        )
                    )
                    total_considered += 1

        # Category Peer Stats
        if category.peer_stats and trigger.scope.value == "merchant" and trigger.kind == "perf_dip":
            supporting.append(
                SelectedFact(
                    key="peer_benchmark_ctr",
                    value=category.peer_stats.avg_ctr,
                    tier=FactTier.SUPPORTING,
                    provenance=FactProvenance(
                        entity_id=category.slug,
                        scope="category",
                        field_path="peer_stats.avg_ctr",
                        value=category.peer_stats.avg_ctr,
                        context_version=cat_ver,
                    ),
                    priority_score=0.72,
                    relevance_reason="Metro peer median benchmark to contextualize performance dip",
                )
            )
            total_considered += 1
        elif category.peer_stats and trigger.scope.value == "customer":
            irrelevant.append(
                SelectedFact(
                    key="category_peer_benchmarks",
                    value="peer_benchmarks",
                    tier=FactTier.IRRELEVANT,
                    provenance=FactProvenance(
                        entity_id=category.slug,
                        scope="category",
                        field_path="peer_stats",
                        value="[REDACTED_PEER]",
                        context_version=cat_ver,
                    ),
                    priority_score=0.0,
                    relevance_reason="B2B peer benchmarks are irrelevant to retail customer messages",
                )
            )
            total_considered += 1

        # =====================================================================
        # 4. CUSTOMER FACTS (When scope == customer)
        # =====================================================================
        if trigger.scope.value == "customer":
            if customer is not None:
                # Customer Name
                if customer.identity and customer.identity.name:
                    mandatory.append(
                        SelectedFact(
                            key="customer_name",
                            value=customer.identity.name,
                            tier=FactTier.MANDATORY,
                            provenance=FactProvenance(
                                entity_id=customer.customer_id,
                                scope="customer",
                                field_path="identity.name",
                                value=customer.identity.name,
                                context_version=cus_ver,
                            ),
                            priority_score=0.98,
                            relevance_reason="Direct recipient consumer identity",
                        )
                    )
                    total_considered += 1

                # Customer Language Preference
                if customer.identity and customer.identity.language_pref:
                    mandatory.append(
                        SelectedFact(
                            key="customer_language_pref",
                            value=customer.identity.language_pref,
                            tier=FactTier.MANDATORY,
                            provenance=FactProvenance(
                                entity_id=customer.customer_id,
                                scope="customer",
                                field_path="identity.language_pref",
                                value=customer.identity.language_pref,
                                context_version=cus_ver,
                            ),
                            priority_score=0.95,
                            relevance_reason="Customer-specific multilingual styling preference",
                        )
                    )
                    total_considered += 1

                # Relationship & History
                if customer.relationship:
                    if customer.relationship.last_visit:
                        high_value.append(
                            SelectedFact(
                                key="customer_last_visit",
                                value=customer.relationship.last_visit,
                                tier=FactTier.HIGH_VALUE,
                                provenance=FactProvenance(
                                    entity_id=customer.customer_id,
                                    scope="customer",
                                    field_path="relationship.last_visit",
                                    value=customer.relationship.last_visit,
                                    context_version=cus_ver,
                                ),
                                priority_score=0.90,
                                relevance_reason="Timestamp of last completed visit for recall calculation",
                            )
                        )
                        total_considered += 1

                # Preferences & Preferred Slots
                if customer.preferences and customer.preferences.preferred_slots:
                    high_value.append(
                        SelectedFact(
                            key="customer_preferred_slots",
                            value=customer.preferences.preferred_slots,
                            tier=FactTier.HIGH_VALUE,
                            provenance=FactProvenance(
                                entity_id=customer.customer_id,
                                scope="customer",
                                field_path="preferences.preferred_slots",
                                value=customer.preferences.preferred_slots,
                                context_version=cus_ver,
                            ),
                            priority_score=0.92,
                            relevance_reason="Customer day/time convenience preference",
                        )
                    )
                    total_considered += 1
                elif trigger.kind == "recall_due":
                    unavailable.append(
                        UnavailableFact(
                            key="customer_preferred_slots",
                            expected_scope="customer",
                            importance="standard",
                            reason="Customer preferences do not specify preferred appointment slots",
                        )
                    )
            else:
                unavailable.append(
                    UnavailableFact(
                        key="customer_context",
                        expected_scope="customer",
                        importance="critical",
                        reason="Trigger scope is 'customer' but CustomerContext is null",
                    )
                )
        elif customer is not None and trigger.scope.value == "merchant":
            # If trigger is merchant-facing, unrelated individual customer context is IRRELEVANT
            irrelevant.append(
                SelectedFact(
                    key="unrelated_customer_context",
                    value=customer.customer_id,
                    tier=FactTier.IRRELEVANT,
                    provenance=FactProvenance(
                        entity_id=customer.customer_id,
                        scope="customer",
                        field_path="customer_id",
                        value=customer.customer_id,
                        context_version=cus_ver,
                    ),
                    priority_score=0.0,
                    relevance_reason="Outreach is merchant-facing; specific retail customer record is irrelevant",
                )
            )
            total_considered += 1

        # =====================================================================
        # 5. CONVERSATIONAL RELEVANCE & INTENT BOOSTING
        # =====================================================================
        if intent_str == "inquiry" or intent_str == "question":
            # Inbound question: boost pricing and verification facts to HIGH_VALUE
            for fact in supporting:
                if "price" in fact.key or "offer" in fact.key or "locality" in fact.key:
                    fact.priority_score = min(1.0, fact.priority_score + 0.25)
        elif intent_str == "commitment":
            # Inbound commitment: action execution facts are boosted
            mandatory.append(
                SelectedFact(
                    key="execution_mode",
                    value="immediate_action_confirmed",
                    tier=FactTier.MANDATORY,
                    provenance=FactProvenance(
                        entity_id=merchant.merchant_id,
                        scope="conversation",
                        field_path="detected_intent.commitment",
                        value="commitment_action",
                        context_version=1,
                    ),
                    priority_score=1.0,
                    relevance_reason="User gave explicit go-ahead; immediate action execution mode",
                )
            )
            total_considered += 1

        # If previous turns already discussed research paper, avoid re-pitching
        if conversation and len(conversation.turns) > 1:
            for turn in conversation.turns:
                if "JIDA" in turn.message or "fluoride" in turn.message:
                    # Demote repeated research paper from mandatory to supporting
                    for fact in list(mandatory):
                        if fact.key == "digest_item_title":
                            fact.tier = FactTier.SUPPORTING
                            fact.relevance_reason = "Already pitched in earlier turn; demoted to supporting context"
                            supporting.append(fact)
                            mandatory.remove(fact)

        return SelectionBundle(
            mandatory_facts=mandatory,
            high_value_facts=high_value,
            supporting_facts=supporting,
            irrelevant_facts=irrelevant,
            unavailable_facts=unavailable,
            context_versions_used=versions,
            total_facts_considered=total_considered,
        )
