"""Trigger intelligence and deterministic arbitration engine."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from vera.context.engine import ContextEngine
from vera.models.customer import CustomerContext
from vera.models.merchant import MerchantContext
from vera.models.trigger import TriggerContext, TriggerScope
from vera.trigger.decision import (
    CandidateEvaluation,
    ReasonCode,
    RejectionReason,
    TriggerDecision,
)
from vera.trigger.suppression import SuppressionStore


class TriggerIntelligenceEngine:
    """Evaluates candidate triggers deterministically to select the single best action catalyst."""

    def __init__(
        self,
        context_engine: ContextEngine,
        suppression_store: Optional[SuppressionStore] = None,
    ):
        self.context_engine = context_engine
        self.suppression_store = suppression_store or SuppressionStore()

    def evaluate_triggers(
        self,
        available_trigger_ids: List[str],
        now_iso: Optional[str] = None,
        auto_suppress: bool = True,
    ) -> TriggerDecision:
        """Arbitrates available triggers and selects the highest-priority, valid, relevant, unsuppressed trigger."""
        current_time = now_iso or (datetime.utcnow().isoformat() + "Z")

        # Step 0: Handle empty candidate list
        if not available_trigger_ids:
            return TriggerDecision(
                selected_trigger=None,
                reason_code=ReasonCode.NO_TRIGGERS_AVAILABLE,
                objective="No triggers available in simulated tick",
                priority=0,
                supporting_context={},
                suppressed_triggers=[],
                candidate_evaluations=[],
                decision_type="skip",
            )

        candidate_evaluations: List[CandidateEvaluation] = []
        valid_candidates: List[Tuple[TriggerContext, MerchantContext, Optional[CustomerContext], float, Dict[str, Any]]] = []
        suppressed_keys_found: List[str] = []

        seen_keys: set[str] = set()

        for tid in available_trigger_ids:
            trigger = self.context_engine.get_trigger(tid)

            # 1. Integrity check: Trigger must exist
            if not trigger:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind="unknown",
                        urgency=1,
                        is_valid=False,
                        is_relevant=False,
                        is_suppressed=False,
                        is_expired=False,
                        rank_score=0.0,
                        rejection_reason=RejectionReason.MERCHANT_NOT_FOUND,
                        rejection_details=f"Trigger '{tid}' not found in context engine",
                    )
                )
                continue

            # Deduplication check for identical triggers within the same tick
            dedup_key = f"{trigger.merchant_id}:{trigger.suppression_key}"
            if dedup_key in seen_keys:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind=trigger.kind,
                        urgency=trigger.urgency,
                        is_valid=True,
                        is_relevant=False,
                        is_suppressed=False,
                        is_expired=False,
                        rank_score=0.0,
                        rejection_reason=RejectionReason.DUPLICATE_CANDIDATE,
                        rejection_details="Duplicate candidate key in same tick",
                    )
                )
                continue
            seen_keys.add(dedup_key)

            # 2. Expiration check
            if trigger.expires_at and current_time >= trigger.expires_at:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind=trigger.kind,
                        urgency=trigger.urgency,
                        is_valid=True,
                        is_relevant=False,
                        is_suppressed=False,
                        is_expired=True,
                        rank_score=0.0,
                        rejection_reason=RejectionReason.EXPIRED,
                        rejection_details=f"Expired at {trigger.expires_at} (current: {current_time})",
                    )
                )
                continue

            # 3. Suppression check
            if self.suppression_store.is_suppressed(trigger.suppression_key, current_time):
                suppressed_keys_found.append(trigger.id)
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind=trigger.kind,
                        urgency=trigger.urgency,
                        is_valid=True,
                        is_relevant=True,
                        is_suppressed=True,
                        is_expired=False,
                        rank_score=0.0,
                        rejection_reason=RejectionReason.SUPPRESSED,
                        rejection_details=f"Suppressed by active key '{trigger.suppression_key}'",
                    )
                )
                continue

            # 4. Merchant entity check
            merchant = self.context_engine.get_merchant(trigger.merchant_id)
            if not merchant:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind=trigger.kind,
                        urgency=trigger.urgency,
                        is_valid=False,
                        is_relevant=False,
                        is_suppressed=False,
                        is_expired=False,
                        rank_score=0.0,
                        rejection_reason=RejectionReason.MERCHANT_NOT_FOUND,
                        rejection_details=f"Merchant '{trigger.merchant_id}' does not exist in store",
                    )
                )
                continue

            # 5. Customer entity & consent check (if customer-scoped)
            customer: Optional[CustomerContext] = None
            if trigger.scope == TriggerScope.CUSTOMER:
                if not trigger.customer_id:
                    candidate_evaluations.append(
                        CandidateEvaluation(
                            trigger_id=tid,
                            kind=trigger.kind,
                            urgency=trigger.urgency,
                            is_valid=False,
                            is_relevant=False,
                            is_suppressed=False,
                            is_expired=False,
                            rank_score=0.0,
                            rejection_reason=RejectionReason.CUSTOMER_NOT_FOUND,
                            rejection_details="Customer-scoped trigger missing customer_id",
                        )
                    )
                    continue

                customer = self.context_engine.get_customer(trigger.customer_id)
                if not customer:
                    candidate_evaluations.append(
                        CandidateEvaluation(
                            trigger_id=tid,
                            kind=trigger.kind,
                            urgency=trigger.urgency,
                            is_valid=False,
                            is_relevant=False,
                            is_suppressed=False,
                            is_expired=False,
                            rank_score=0.0,
                            rejection_reason=RejectionReason.CUSTOMER_NOT_FOUND,
                            rejection_details=f"Customer '{trigger.customer_id}' does not exist in store",
                        )
                    )
                    continue

                # Check customer consent scope
                if not self._check_customer_consent(trigger, customer):
                    candidate_evaluations.append(
                        CandidateEvaluation(
                            trigger_id=tid,
                            kind=trigger.kind,
                            urgency=trigger.urgency,
                            is_valid=True,
                            is_relevant=False,
                            is_suppressed=False,
                            is_expired=False,
                            rank_score=0.0,
                            rejection_reason=RejectionReason.CUSTOMER_CONSENT_MISSING,
                            rejection_details="Customer consent scope does not permit this outreach type",
                        )
                    )
                    continue

            # 6. Category & operational relevance check
            is_rel, rej_code, rel_reason = self._check_operational_relevance(trigger, merchant)
            if not is_rel:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        trigger_id=tid,
                        kind=trigger.kind,
                        urgency=trigger.urgency,
                        is_valid=True,
                        is_relevant=False,
                        is_suppressed=False,
                        is_expired=False,
                        rank_score=0.0,
                        rejection_reason=rej_code or RejectionReason.UNAPPLICABLE_STATUS,
                        rejection_details=rel_reason,
                    )
                )
                continue

            # 7. Compute multi-factor priority score
            score, supporting = self._calculate_rank_score(trigger, merchant, customer)
            valid_candidates.append((trigger, merchant, customer, score, supporting))
            candidate_evaluations.append(
                CandidateEvaluation(
                    trigger_id=tid,
                    kind=trigger.kind,
                    urgency=trigger.urgency,
                    is_valid=True,
                    is_relevant=True,
                    is_suppressed=False,
                    is_expired=False,
                    rank_score=score,
                    rejection_reason=None,
                    rejection_details=None,
                )
            )

        # Step 8: If no valid candidates survived, classify overall reason
        if not valid_candidates:
            reason = self._determine_overall_rejection_reason(candidate_evaluations)
            return TriggerDecision(
                selected_trigger=None,
                reason_code=reason,
                objective="No candidates met eligibility, relevance, or unsuppressed criteria",
                priority=0,
                supporting_context={},
                suppressed_triggers=suppressed_keys_found,
                candidate_evaluations=candidate_evaluations,
                decision_type="skip",
            )

        # Step 9: Rank candidates deterministically
        # Sort key: (-score, trigger.id) ensures deterministic tie-breaking
        valid_candidates.sort(key=lambda item: (-item[3], item[0].id))
        selected_trigger, selected_merchant, selected_customer, top_score, supporting = valid_candidates[0]

        # Step 10: Auto-suppress selected trigger if requested
        if auto_suppress:
            self.suppression_store.record_suppression(
                key=selected_trigger.suppression_key,
                trigger_id=selected_trigger.id,
                suppressed_at=current_time,
                expires_at=selected_trigger.expires_at,
            )

        return TriggerDecision(
            selected_trigger=selected_trigger,
            reason_code=ReasonCode.TRIGGER_SELECTED,
            objective=f"Outreach for {selected_trigger.kind} (priority score {top_score:.1f}) targeting {selected_merchant.identity.name}",
            priority=selected_trigger.urgency,
            supporting_context=supporting,
            suppressed_triggers=suppressed_keys_found,
            candidate_evaluations=candidate_evaluations,
            decision_type="send",
        )

    # =========================================================================
    # RELEVANCE & SCORING HELPERS
    # =========================================================================

    def _check_customer_consent(self, trigger: TriggerContext, customer: CustomerContext) -> bool:
        """Verifies customer opt-in scope covers this outreach."""
        # 1. Opt-in registration check
        if not customer.consent.opted_in_at:
            return False

        scope_list = [s.lower() for s in customer.consent.scope]
        if not scope_list:
            return False

        if "all" in scope_list:
            return True

        kind = trigger.kind.lower()

        # 2. Reminder / service triggers (recall, appointment, chronic refill)
        is_reminder_type = any(k in kind for k in ["recall", "appointment", "refill", "reminder"])
        if is_reminder_type:
            # Respect explicit reminder opt-out
            if customer.preferences.reminder_opt_in is False:
                return False

            allowed_scopes = {
                "recall_reminders",
                "appointment_reminders",
                "reminders",
                "recall_alerts",
                "refill_reminders",
                "delivery_notifications",
                "treatment_followup",
            }
            return any(s in allowed_scopes for s in scope_list)

        # 3. Promotional / Marketing / Winback / Lapsed triggers
        is_marketing_type = any(
            k in kind
            for k in [
                "promotional",
                "festival",
                "lapsed",
                "winback",
                "offer",
                "discount",
                "marketing",
                "specials",
            ]
        )
        if is_marketing_type:
            allowed_scopes = {
                "promotional_offers",
                "whatsapp_marketing",
                "marketing",
                "winback_offers",
                "renewal_reminders",
                "lunch_thali_updates",
                "match_night_specials",
            }
            return any(s in allowed_scopes for s in scope_list)

        # 4. Program / Trial followups
        if "trial" in kind or "program" in kind:
            allowed_scopes = {
                "kids_program_updates",
                "program_updates",
                "trial_followup",
                "appointment_reminders",
                "promotional_offers",
                "whatsapp_marketing",
            }
            return any(s in allowed_scopes for s in scope_list)

        # 5. Bridal / Event followups
        if "bridal" in kind or "wedding" in kind:
            allowed_scopes = {
                "bridal_package_followup",
                "appointment_reminders",
                "promotional_offers",
                "whatsapp_marketing",
                "stylist_specific",
            }
            return any(s in allowed_scopes for s in scope_list)

        # Default fallback: must have at least one general marketing or reminder scope
        return any(s in scope_list for s in ["promotional_offers", "whatsapp_marketing", "reminders"])

    def _check_operational_relevance(
        self, trigger: TriggerContext, merchant: MerchantContext
    ) -> Tuple[bool, Optional[RejectionReason], Optional[str]]:
        """Validates that the trigger aligns with merchant category and operational state."""
        # 1. Category alignment check
        payload_cat = trigger.payload.get("category")
        if payload_cat and payload_cat != merchant.category_slug:
            return False, RejectionReason.CATEGORY_MISMATCH, f"Category mismatch: trigger '{payload_cat}' != merchant '{merchant.category_slug}'"

        # 2. Renewal due relevance: only relevant if subscription is active/expiring and days_remaining <= 30
        if trigger.kind == "renewal_due":
            rem = merchant.subscription.days_remaining
            if rem is not None and rem > 30:
                return False, RejectionReason.UNAPPLICABLE_STATUS, f"Renewal not urgent: {rem} days remaining"

        # 3. Performance dip relevance
        if trigger.kind == "perf_dip":
            perf = merchant.performance
            has_dip = (
                (perf.delta_7d and (perf.delta_7d.calls_pct < 0 or perf.delta_7d.views_pct < 0))
                or any("perf_dip" in s for s in merchant.signals)
            )
            if not has_dip:
                return False, RejectionReason.UNAPPLICABLE_STATUS, "Merchant metrics show positive or neutral growth; perf_dip not applicable"

        return True, None, None

    def _calculate_rank_score(
        self,
        trigger: TriggerContext,
        merchant: MerchantContext,
        customer: Optional[CustomerContext],
    ) -> Tuple[float, Dict[str, Any]]:
        """Multi-factor deterministic ranking score combining urgency, cohort fit, and timing."""
        score = float(trigger.urgency * 100)
        supporting: Dict[str, Any] = {
            "merchant_id": merchant.merchant_id,
            "merchant_name": merchant.identity.name,
            "category": merchant.category_slug,
            "urgency": trigger.urgency,
            "kind": trigger.kind,
        }

        # Boost 1: Critical Regulatory Changes (Compliance deadlines)
        if trigger.kind == "regulation_change":
            score += 60.0
            supporting["compliance_deadline"] = trigger.payload.get("deadline_iso")

        # Boost 2: Research digest matching high-risk cohort
        if trigger.kind == "research_digest":
            top_id = trigger.payload.get("top_item_id")
            category = self.context_engine.get_category(merchant.category_slug)
            if category:
                for d in category.digest:
                    if d.id == top_id and d.patient_segment == "high_risk_adults":
                        if "high_risk_adult_cohort" in merchant.signals or (
                            merchant.customer_aggregate.model_extra
                            and merchant.customer_aggregate.model_extra.get("high_risk_adult_count", 0) > 0
                        ):
                            score += 50.0
                            supporting["cohort_match"] = "high_risk_adults"
                            supporting["citation"] = d.source

        # Boost 3: Severe performance drop
        if trigger.kind == "perf_dip":
            perf = merchant.performance
            if perf.delta_7d and perf.delta_7d.calls_pct <= -0.30:
                score += 45.0
                supporting["calls_drop_pct"] = perf.delta_7d.calls_pct

        # Boost 4: Recall due for lapsed customer
        if trigger.kind == "recall_due" and customer:
            if customer.state in ["lapsed_soft", "lapsed_hard"]:
                score += 45.0
                supporting["customer_name"] = customer.identity.name
                supporting["customer_state"] = customer.state.value

        # Boost 5: Active customer event countdown
        if trigger.kind in ["wedding_package_followup", "bridal_followup"]:
            days_to_event = trigger.payload.get("days_to_wedding")
            if days_to_event and days_to_event < 200:
                score += 35.0
                supporting["days_to_wedding"] = days_to_event

        return score, supporting

    def _determine_overall_rejection_reason(
        self, evals: List[CandidateEvaluation]
    ) -> ReasonCode:
        """Determines the most accurate reason code when zero candidates are selected."""
        reasons = [e.rejection_reason for e in evals if e.rejection_reason]
        if all(r == RejectionReason.SUPPRESSED for r in reasons):
            return ReasonCode.ALL_TRIGGERS_SUPPRESSED
        if all(r == RejectionReason.EXPIRED for r in reasons):
            return ReasonCode.ALL_TRIGGERS_EXPIRED
        if all(r in [RejectionReason.MERCHANT_NOT_FOUND, RejectionReason.CUSTOMER_NOT_FOUND] for r in reasons):
            return ReasonCode.ALL_TRIGGERS_INVALID
        return ReasonCode.ALL_TRIGGERS_IRRELEVANT
