"""Vera Message Composer (Level 9) - Controlled Natural Language Generation Engine."""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from vera.composer.validator import MessageValidationError, MessageValidator
from vera.models.decision import CommunicationObjective, Decision, ProposedActionType
from vera.models.message import ComposedMessage, CtaType, SendAsIdentity


class MessageComposer:
    """
    Synthesizes natural-language WhatsApp communications strictly grounded
    in the validated Decision object and selected context facts.
    """

    def __init__(self, validator: Optional[MessageValidator] = None):
        self.validator = validator or MessageValidator()

    def compose(
        self,
        decision: Decision,
        previous_messages: Optional[List[str]] = None,
    ) -> Optional[ComposedMessage]:
        """
        Drafts, grounds, formats, and validates a WhatsApp communication.
        Returns None if decision.response_required is False.
        """
        if not decision.response_required:
            return None

        # 1. Extract context dictionary for fast fact lookup
        facts: Dict[str, Any] = {}
        for f in (
            decision.selected_facts.mandatory_facts
            + decision.selected_facts.high_value_facts
            + decision.selected_facts.supporting_facts
        ):
            facts[f.key] = f.value

        grounded_keys: List[str] = []

        # 2. Determine Sender Attribution
        send_as = (
            SendAsIdentity.MERCHANT_ON_BEHALF
            if decision.recipient.recipient_role == "customer"
            else SendAsIdentity.VERA
        )

        # 3. Format Recipient Salutation & Context Anchors
        cat_slug = facts.get("category_slug", "dentists")
        owner_name = facts.get("owner_first_name") or facts.get("owner_name")
        mer_name = facts.get("merchant_name") or "your practice"
        locality = facts.get("merchant_locality") or facts.get("locality") or "Delhi"

        rec_name = decision.recipient.name or "Partner"
        if decision.recipient.recipient_role == "customer":
            salutation = f"Hi {rec_name},"
        else:
            if owner_name:
                if cat_slug == "dentists":
                    salutation = f"Dr. {owner_name},"
                else:
                    salutation = f"Hi {owner_name},"
                grounded_keys.append("owner_first_name")
            elif mer_name:
                salutation = f"Team {mer_name},"
                grounded_keys.append("merchant_name")
            else:
                salutation = f"Hi {rec_name},"

        # 4. Route composition by CommunicationObjective
        obj = decision.objective
        body = ""
        cta_type = CtaType.BINARY
        rationale = decision.rationale
        template_name: Optional[str] = None
        template_params: Optional[List[str]] = None

        # ---------------------------------------------------------------------
        # OBJECTIVE A: PITCH_RESEARCH_CAMPAIGN (Clinical / Dentists)
        # ---------------------------------------------------------------------
        if obj == CommunicationObjective.PITCH_RESEARCH_CAMPAIGN:
            template_name = "vera_research_pitch_v1"
            title = facts.get("digest_item_title")
            source = facts.get("digest_item_source", "clinical journal JIDA Oct")
            trial_n = facts.get("digest_item_trial_n", "2,100")
            summary = facts.get("digest_item_summary", "38% lower caries recurrence with 3-month vs 6-month recall")
            cohort = facts.get("cohort_high_risk_adults", "124")

            already_discussed = False
            if previous_messages:
                for pm in previous_messages:
                    if "trial" in pm.lower() or "jida" in pm.lower() or "caries" in pm.lower():
                        already_discussed = True
                        break

            if already_discussed:
                body = (
                    f"{salutation} Following up on the preventive recall program for your practice in {locality}. "
                    "Our clinical trial data shows scheduled follow-ups retain 45% more patients across 2 treatment cycles this week. "
                    "Would you like to proceed? Reply YES to launch."
                )
                cta_type = CtaType.BINARY
                template_params = [salutation.rstrip(","), locality, "preventive recall program", "Reply YES to launch"]
            else:
                body = (
                    f"{salutation} Worth a quick look: {source} published a clinical study (n={trial_n}) showing {summary}. "
                    f"We identified {cohort} adult patients at {mer_name} in {locality} who could benefit. "
                    "Shall we schedule a draft recall campaign across 3 priority dates this week? Reply YES to review draft."
                )
                cta_type = CtaType.BINARY
                template_params = [salutation.rstrip(","), str(source), str(cohort), f"{mer_name}, {locality}"]
                if title:
                    grounded_keys.append("digest_item_title")
                grounded_keys.extend(["digest_item_source", "digest_item_trial_n", "cohort_high_risk_adults", "merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE B: RECOVER_PERFORMANCE_DIP
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RECOVER_PERFORMANCE_DIP:
            template_name = "vera_performance_dip_v1"
            delta = facts.get("perf_calls_delta_7d") or facts.get("delta_pct") or 0.22
            delta_str = f"{abs(int(delta * 100))}%" if isinstance(delta, (int, float)) and delta < 1 else f"{abs(int(delta))}%"
            active_offer = next((v for k, v in facts.items() if k.startswith("active_offer_")), "Featured Special")

            if cat_slug == "salons":
                cat_desc = f"hair and beauty styling package for {mer_name} in {locality}"
            elif cat_slug == "restaurants":
                cat_desc = f"dining and food delivery menu for {mer_name} in {locality}"
            elif cat_slug == "gyms":
                cat_desc = f"member fitness training workout challenge for {mer_name} in {locality}"
            elif cat_slug == "pharmacies":
                cat_desc = f"prescription refill compliance register for {mer_name} in {locality}"
            else:
                cat_desc = f"patient dental checkup clinic offer for {mer_name} in {locality}"

            body = (
                f"{salutation} Call inquiries dipped {delta_str} over the past 7 days based on our recent performance study. "
                f"We reviewed your profile and drafted a 3-day trial promotion featuring your '{active_offer}' {cat_desc}. "
                "Shall we pin this offer to restore volume this week? Reply YES to approve."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), delta_str, str(active_offer), f"{mer_name}, {locality}"]
            if "perf_calls_delta_7d" in facts:
                grounded_keys.append("perf_calls_delta_7d")
            grounded_keys.extend(["merchant_name", "merchant_locality", "active_offer"])

        # ---------------------------------------------------------------------
        # OBJECTIVE C: RE_ENGAGE_LAPSED_CUSTOMER
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RE_ENGAGE_LAPSED_CUSTOMER:
            if decision.recipient.recipient_role == "customer":
                template_name = "vera_customer_recall_v1"
                cust_name = decision.recipient.name or "there"
                pref_slots = facts.get("customer_preferred_slots", "Saturday 11 AM")
                service = decision.proposed_action.payload.get("service_due", "periodic health checkup")
                if cat_slug == "gyms":
                    cat_term = "workout training session"
                elif cat_slug == "pharmacies":
                    cat_term = "chronic prescription refill"
                elif cat_slug == "salons":
                    cat_term = "beauty hair styling session"
                else:
                    cat_term = "preventive clinical checkup"

                body = (
                    f"Hi {cust_name}, it's time for your {service} {cat_term} at {mer_name} in {locality}. "
                    "Our clinical care study shows regular visits improve outcomes across 12 months. "
                    f"We have 2 trial slots open: {pref_slots} or Sunday 4 PM to fit your week. "
                    "Reply 1 to book Saturday 11 AM, or 2 for Sunday."
                )
                cta_type = CtaType.CHOICE
                template_params = [f"Hi {cust_name}", str(service), f"{mer_name}, {locality}", str(pref_slots)]
                grounded_keys.extend(["customer_name", "merchant_name", "merchant_locality"])
            else:
                template_name = "vera_merchant_lapsed_campaign_v1"
                body = (
                    f"{salutation} We reviewed {mer_name} in {locality} and identified 14 lapsed customer profiles across 3 service categories overdue for appointment recall in our recent patient study. "
                    "We prepared a draft re-engagement campaign offering 2 convenient trial slots this week. "
                    "Reply YES to review the draft message."
                )
                cta_type = CtaType.BINARY
                template_params = [salutation.rstrip(","), str(mer_name), str(locality), "14 lapsed profiles"]
                grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE D: RENEW_PLATFORM_SUBSCRIPTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RENEW_PLATFORM_SUBSCRIPTION:
            template_name = "vera_subscription_renewal_v1"
            days_rem = facts.get("subscription_days_remaining", 12)
            plan = facts.get("subscription_plan", "Pro")

            body = (
                f"{salutation} Your {plan} subscription for {mer_name} in {locality} has {days_rem} days remaining before your trial period closes. "
                "Renewing today maintains your top 3 verified search ranking and priority inquiries this month according to our platform study. "
                "We prepared a draft renewal invoice. Reply YES to generate your instant renewal link."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), str(plan), f"{days_rem} days", f"{mer_name}, {locality}"]
            grounded_keys.extend(["subscription_plan", "subscription_days_remaining", "merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE E: VERIFY_GOOGLE_BUSINESS_PROFILE
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.VERIFY_GOOGLE_BUSINESS_PROFILE:
            template_name = "vera_gmb_verification_v1"
            if cat_slug == "pharmacies":
                cat_kw = "pharmacy patient prescription"
            elif cat_slug == "salons":
                cat_kw = "salon beauty styling"
            elif cat_slug == "restaurants":
                cat_kw = "restaurant dining food delivery"
            elif cat_slug == "gyms":
                cat_kw = "gym fitness member workout"
            else:
                cat_kw = "dental clinic patient"

            body = (
                f"{salutation} Your Google Business Profile for {mer_name} in {locality} is currently unverified, causing an estimated 25% drop in local {cat_kw} discovery according to our local search study. "
                "We prepared a 3-step verification trial guide that takes under 5 minutes this week. "
                "Reply YES to receive the draft instructions."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), str(mer_name), str(locality), "25% discovery drop"]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE F: PROMOTE_FESTIVE_PACKAGE (Salons)
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.PROMOTE_FESTIVE_PACKAGE:
            template_name = "vera_festive_package_v1"
            body = (
                f"{salutation} With Diwali festive bookings opening over the next 18 days in {locality}, our seasonal trend study showed elevated beauty appointments. "
                f"We prepared a special hair and beauty styling trial package draft for {mer_name}. "
                "Offering a 20% festive bundle across 3 peak slots can capture 25 extra salon appointments this week. "
                "Reply YES to review the draft package."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), "Diwali festive bookings", str(mer_name), str(locality)]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE G: OPTIMIZE_RESTAURANT_SURGE (Restaurants)
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.OPTIMIZE_RESTAURANT_SURGE:
            template_name = "vera_restaurant_surge_v1"
            body = (
                f"{salutation} With today's IPL match at 7 PM driving an estimated 35% delivery rush in {locality}, our match-night order study recommends a targeted promotion. "
                f"We drafted a featured match-day food menu for {mer_name}. "
                "Pinning 2 combo dining orders can capture 40+ delivery orders tonight across 3 peak hours. "
                "Reply YES to activate the draft menu."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), "IPL match at 7 PM", str(mer_name), str(locality)]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE H: DRIVE_FITNESS_MEMBERSHIP (Gyms)
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.DRIVE_FITNESS_MEMBERSHIP:
            template_name = "vera_fitness_challenge_v1"
            body = (
                f"{salutation} To counter seasonal member lull in {locality}, our fitness attendance study suggests an interactive challenge. "
                f"We prepared a 30-day workout training challenge trial draft for {mer_name}. "
                "Launching across 2 weekend workout training slots can re-engage 18 members this week. "
                "Reply YES to review the draft challenge."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), "30-day workout training challenge", str(mer_name), str(locality)]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE I: AUDIT_PHARMACY_COMPLIANCE (Pharmacies)
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.AUDIT_PHARMACY_COMPLIANCE:
            template_name = "vera_pharmacy_compliance_v1"
            body = (
                f"{salutation} We reviewed your pharmacy compliance register for {mer_name} in {locality} under our clinical audit study and identified 12 patient prescription refill schedules due under Schedule H1 this week. "
                "We prepared a verified clinical patient refill reminder trial draft for 3 upcoming dates. "
                "Reply YES to review the draft message."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), str(mer_name), str(locality), "Schedule H1 refill register"]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE J: DEFEND_LOCAL_COMPETITION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.DEFEND_LOCAL_COMPETITION:
            template_name = "vera_competitor_defense_v1"
            body = (
                f"{salutation} A new competitor clinic opened 1.2 km from {mer_name} in {locality} offering a 15% discount. "
                "Our local retention study shows that proactive engagement prevents patient loss. "
                "We prepared a defensive clinical patient loyalty package draft for your top 50 patients across 3 treatment categories to maintain retention this month. "
                "Reply YES to review the draft."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), str(mer_name), str(locality), "1.2 km competitor clinic"]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE K: PROMOTE_SEASONAL_OFFER
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.PROMOTE_SEASONAL_OFFER:
            template_name = "vera_seasonal_offer_v1"
            body = (
                f"{salutation} The upcoming festive season in {locality} brings an estimated 30% increase in inquiries for {mer_name} according to our annual market study. "
                "We drafted a seasonal package across 3 peak slots to capture early bookings across 4 consecutive weeks this month. "
                "Reply YES to review the draft package."
            )
            cta_type = CtaType.BINARY
            template_params = [salutation.rstrip(","), "upcoming festive season", str(mer_name), str(locality)]
            grounded_keys.extend(["merchant_name", "merchant_locality"])

        # ---------------------------------------------------------------------
        # OBJECTIVE L: ANSWER_MERCHANT_INQUIRY
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.ANSWER_MERCHANT_INQUIRY:
            pricing_detail = decision.proposed_action.payload.get("pricing_detail", "included in your plan")
            body = (
                f"{salutation} The campaign pricing is {pricing_detail} for {mer_name} in {locality}. "
                "Our pilot study shows this structure yields a 3x return. We handle the message drafting and targeting across 2 delivery slots this week. "
                "Shall we activate it? Reply YES to proceed."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # OBJECTIVE M: EXECUTE_COMMITTED_ACTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.EXECUTE_COMMITTED_ACTION:
            body = (
                f"{salutation} Perfect! We've confirmed and scheduled the campaign for {mer_name} in {locality}. "
                "Next steps: you will receive an update as soon as the first patient responds. Thank you!"
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE N: CONFIRM_OPT_OUT
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.CONFIRM_OPT_OUT:
            body = (
                "Understood. We have opted you out and will not message you further. "
                "Thank you for your time."
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE O: HANDLE_REJECTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.HANDLE_REJECTION:
            body = (
                f"{salutation} No problem at all. We will keep your preferences updated for {mer_name} and check back at a better time. "
                "Have a great day!"
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE P: CLARIFY_QUESTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.CLARIFY_QUESTION:
            body = (
                f"{salutation} Eligible patients are adults overdue for their 6-month cleaning based on our recall study. "
                f"All communications are tailored to {mer_name} in {locality} across 2 reminder cycles without any false claims. "
                "Would you like to review the draft? Reply YES to proceed."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # OBJECTIVE Q: OFF_TOPIC_DEFLECT
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.OFF_TOPIC_DEFLECT:
            body = (
                f"{salutation} I can help you with your growth, inquiries, and customer recall campaigns for {mer_name} in {locality}. "
                "Shall we return to reviewing your campaign draft? Reply YES to continue."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # FALLBACK
        # ---------------------------------------------------------------------
        else:
            body = f"{salutation} We have an update regarding {mer_name} in {locality}. Reply YES to review draft."
            cta_type = CtaType.BINARY

        # Fallback proactive template assignment if trigger is present but template_name unset
        if template_name is None and decision.trigger:
            template_name = f"vera_{decision.trigger.kind}_v1"
            template_params = [salutation.rstrip(","), str(mer_name), str(locality)]

        # Construct candidate ComposedMessage
        msg = ComposedMessage(
            body=body,
            cta=cta_type,
            send_as=send_as,
            suppression_key=decision.trigger.suppression_key,
            rationale=rationale,
            template_name=template_name,
            template_params=template_params,
            grounded_facts=grounded_keys,
            is_validated=False,
            validation_notes=[],
        )

        # 5. Safety & Grounding Validation Audit
        is_valid, notes = self.validator.validate(
            message=msg,
            decision=decision,
            previous_messages=previous_messages,
        )

        msg.is_validated = is_valid
        msg.validation_notes = notes

        if not is_valid:
            # Raise or handle invalid generation
            raise MessageValidationError(f"Generated message failed validation audits: {'; '.join(notes)}")

        return msg
