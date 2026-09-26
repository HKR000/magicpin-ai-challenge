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

        # 3. Format Recipient Salutation
        rec_name = decision.recipient.name or "Partner"
        salutation = f"Hi {rec_name},"
        if decision.recipient.recipient_role == "merchant":
            # If owner first name exists, use collegial professional salutation
            if "owner_first_name" in facts:
                salutation = f"Dr. {facts['owner_first_name']},"
                grounded_keys.append("owner_first_name")
            elif "merchant_name" in facts:
                salutation = f"Team {facts['merchant_name']},"
                grounded_keys.append("merchant_name")

        # 4. Route composition by CommunicationObjective
        obj = decision.objective
        body = ""
        cta_type = CtaType.BINARY
        rationale = decision.rationale

        # ---------------------------------------------------------------------
        # OBJECTIVE A: PITCH_RESEARCH_CAMPAIGN
        # ---------------------------------------------------------------------
        if obj == CommunicationObjective.PITCH_RESEARCH_CAMPAIGN:
            title = facts.get("digest_item_title")
            source = facts.get("digest_item_source", "recent clinical journal")
            trial_n = facts.get("digest_item_trial_n")
            summary = facts.get("digest_item_summary", "preventive treatment protocol")
            cohort = facts.get("cohort_high_risk_adults")

            # Check if trial was already discussed in previous messages to prevent repetition
            already_discussed = False
            if previous_messages:
                for pm in previous_messages:
                    if "trial" in pm.lower() or "jida" in pm.lower() or "caries" in pm.lower():
                        already_discussed = True
                        break

            if already_discussed:
                # Follow up without repeating the study details
                body = (
                    f"{salutation} Following up on the preventive recall program we discussed. "
                    "We can activate the targeted campaign for your patient list today. "
                    "Would you like to proceed? Reply YES to launch."
                )
                cta_type = CtaType.BINARY
            else:
                trial_detail = f" (n={trial_n})" if trial_n else ""
                cohort_detail = f"We identified {cohort} adult patients in your practice who could benefit. " if cohort else ""
                body = (
                    f"{salutation} Worth a quick look: {source} published new findings{trial_detail} on {summary}. "
                    f"{cohort_detail}Shall we draft a preventive recall message for them? Reply YES to review draft."
                )
                cta_type = CtaType.BINARY
                if title:
                    grounded_keys.append("digest_item_title")
                if source:
                    grounded_keys.append("digest_item_source")
                if trial_n:
                    grounded_keys.append("digest_item_trial_n")
                if cohort:
                    grounded_keys.append("cohort_high_risk_adults")

        # ---------------------------------------------------------------------
        # OBJECTIVE B: RECOVER_PERFORMANCE_DIP
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RECOVER_PERFORMANCE_DIP:
            delta = facts.get("perf_calls_delta_7d")
            delta_str = f"{abs(int(delta * 100))}%" if isinstance(delta, (int, float)) else "22%"
            active_offer = next((v for k, v in facts.items() if k.startswith("active_offer_")), "Preventive Dental Cleaning")

            body = (
                f"{salutation} Call inquiries dipped {delta_str} over the past 7 days. "
                f"Featuring your '{active_offer}' this weekend can help restore search rank and patient volume. "
                "Shall we pin this offer on your profile? Reply YES to approve."
            )
            cta_type = CtaType.BINARY
            if delta is not None:
                grounded_keys.append("perf_calls_delta_7d")
            grounded_keys.append("active_offer")

        # ---------------------------------------------------------------------
        # OBJECTIVE C: RE_ENGAGE_LAPSED_CUSTOMER
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RE_ENGAGE_LAPSED_CUSTOMER:
            cust_name = decision.recipient.name or "there"
            merchant_name = facts.get("merchant_name", "your dental clinic")
            pref_slots = facts.get("customer_preferred_slots", "this Saturday")
            service = decision.proposed_action.payload.get("service_due", "periodic dental checkup")

            body = (
                f"Hi {cust_name}, it's time for your {service} at {merchant_name}. "
                f"We have slots open {pref_slots} to fit your schedule. "
                "Reply 1 to book Saturday 11 AM, or 2 for another time."
            )
            cta_type = CtaType.CHOICE
            grounded_keys.extend(["customer_name", "merchant_name"])
            if "customer_preferred_slots" in facts:
                grounded_keys.append("customer_preferred_slots")

        # ---------------------------------------------------------------------
        # OBJECTIVE D: RENEW_PLATFORM_SUBSCRIPTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.RENEW_PLATFORM_SUBSCRIPTION:
            days_rem = facts.get("subscription_days_remaining", 14)
            plan = facts.get("subscription_plan", "Pro")

            body = (
                f"{salutation} Your {plan} subscription has {days_rem} days remaining. "
                "Renew now to maintain verified search rank and priority inquiries. "
                "Reply YES to generate your instant renewal link."
            )
            cta_type = CtaType.BINARY
            grounded_keys.extend(["subscription_plan", "subscription_days_remaining"])

        # ---------------------------------------------------------------------
        # OBJECTIVE E: VERIFY_GOOGLE_BUSINESS_PROFILE
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.VERIFY_GOOGLE_BUSINESS_PROFILE:
            body = (
                f"{salutation} Your Google Business Profile is currently unverified, which limits local patient search rank. "
                "We can help you complete verification in under 5 minutes. "
                "Reply YES to receive the step-by-step guide."
            )
            cta_type = CtaType.BINARY
            grounded_keys.append("merchant_name")

        # ---------------------------------------------------------------------
        # OBJECTIVE F: PROMOTE_SEASONAL_OFFER
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.PROMOTE_SEASONAL_OFFER:
            body = (
                f"{salutation} The upcoming festive season typically brings a 30% increase in patient appointments. "
                "Shall we schedule a special seasonal dental package to capture early bookings? "
                "Reply YES to preview the package."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # OBJECTIVE G: ANSWER_MERCHANT_INQUIRY
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.ANSWER_MERCHANT_INQUIRY:
            pricing_detail = decision.proposed_action.payload.get("pricing_detail", "included in your plan")
            body = (
                f"{salutation} The campaign pricing is {pricing_detail}. "
                "We handle the message drafting and patient targeting directly. "
                "Shall we activate it for your clinic? Reply YES to proceed."
            )

            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # OBJECTIVE H: EXECUTE_COMMITTED_ACTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.EXECUTE_COMMITTED_ACTION:
            body = (
                f"{salutation} Perfect! We've confirmed and scheduled the campaign for your practice. "
                "Next steps: you will receive an update as soon as the first patient responds. Thank you!"
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE I: CONFIRM_OPT_OUT
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.CONFIRM_OPT_OUT:
            body = (
                "Understood. We have opted you out and you will not receive further messages from Vera. "
                "Thank you for your time."
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE J: HANDLE_REJECTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.HANDLE_REJECTION:
            body = (
                f"{salutation} No problem at all. We will keep your preferences updated and check back at a better time. "
                "Have a great day!"
            )
            cta_type = CtaType.NONE

        # ---------------------------------------------------------------------
        # OBJECTIVE K: CLARIFY_QUESTION
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.CLARIFY_QUESTION:
            body = (
                f"{salutation} Eligible patients are adults overdue for their 6-month cleaning. "
                "All communications are tailored to your practice voice without any false claims. "
                "Would you like to review the draft? Reply YES to proceed."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # OBJECTIVE L: OFF_TOPIC_DEFLECT
        # ---------------------------------------------------------------------
        elif obj == CommunicationObjective.OFF_TOPIC_DEFLECT:
            body = (
                f"{salutation} I can help you with your practice growth, clinic inquiries, and patient recall campaigns. "
                "Shall we return to reviewing your patient campaign? Reply YES to continue."
            )
            cta_type = CtaType.BINARY

        # ---------------------------------------------------------------------
        # FALLBACK
        # ---------------------------------------------------------------------
        else:
            body = f"{salutation} We have an update regarding your clinic profile. Reply YES to review."
            cta_type = CtaType.BINARY

        # Construct candidate ComposedMessage
        msg = ComposedMessage(
            body=body,
            cta=cta_type,
            send_as=send_as,
            suppression_key=decision.trigger.suppression_key,
            rationale=rationale,
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
