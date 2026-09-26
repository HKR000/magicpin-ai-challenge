# magicpin AI Challenge — Vera System & Challenge Specification
**Document ID**: `CHALLENGE_SPEC.md`  
**Status**: Authoritative Technical Specification  
**Source Artifacts**: `challenge-brief.md`, `challenge-testing-brief.md`, `engagement-design.md`, `engagement-research.md`, `dataset/`, `examples/`  

---

## 1. Business Objective

### 1.1 Core Mission
Vera is magicpin's AI-driven marketing and growth assistant for local retail merchants across India (~100,000 merchant partners in 50+ cities, including restaurants, salons, gyms, dentists, pharmacies, and specialty retailers). Vera communicates primarily over WhatsApp to help merchants:
- Grow their Google Business Profile (GBP) through audits, photo updates, posts, and review management.
- Run targeted, high-conversion marketing and promotional campaigns.
- Re-engage lapsed, churning, and active customers with timely offers and recall reminders.
- Answer customer inquiries and coordinate appointments on the merchant's behalf.

### 1.2 Quantitative Operating Scale
As of April 2026 production metrics:
- **Merchant engagement**: 6,000–10,000 active merchants/day with 23,000–47,000 total messages (~4.6–4.9 turns per engaged merchant).
- **Customer outreach**: ~700 customers/day across ~500 unique merchants (~5.2–6.9 messages per customer).

### 1.3 Key Failures in Legacy Vera (Outperformance Targets)
The challenge requires engineering an assistant that specifically overcomes four critical flaws:
1. **Auto-Reply Pollution**: 40%–70% of merchant inbound responses are automated WhatsApp Business greeting/away messages. Legacy Vera burns 2–3 turns trying to converse with auto-responders. *Target*: Detect auto-replies rapidly (<= 1-2 turns), prevent turn wastage, and exit gracefully or back off.
2. **Intent-Handoff Failures**: When a merchant provides an explicit commitment ("I want to join", "Yes please update", "Let's do it"), legacy Vera frequently falls back to redundant qualification questions. *Target*: Detect commitment signals deterministically and immediately transition to action execution.
3. **Generic Copy Trap**: Generic promotional discounts ("10% off", "Flat discount") exhibit poor conversion among Indian merchants. *Target*: High-specificity, category-accurate service+price anchors (e.g., "Dental Cleaning @ ₹299", "Haircut @ ₹99") grounded strictly in verified catalog context.
4. **Low Engagement Frequency**: Relying solely on broken-profile or renewal nudges limits touches to 1–2 times per month. *Target*: A diversified conversation portfolio featuring curiosity hooks, peer benchmarks, compliance/research digests, seasonal beats, and customer win-backs driving 3–5 interactions per week.

---

## 2. Context Layers (The 4-Context Framework)

Every decision and message composed by Vera is a function of four structured context layers:
$$\text{Vera}(\text{Category}, \text{Merchant}, \text{Trigger}, \text{Customer?}) \to \text{ComposedMessage}$$

```
┌──────────────────┐     ┌──────────────────┐
│  CategoryContext │     │  MerchantContext │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
     ┌─────────────────────────────────┐
     │      Decision & Message Engine   │ ◄─── TriggerContext
     └────────────────┬────────────────┘
                      ▲
                      │ (Optional)
             ┌────────┴─────────┐
             │  CustomerContext │
             └──────────────────┘
```

### 2.1 CategoryContext (`scope: "category"`)
- **Status**: Required for all compositions.
- **Refresh Cadence**: Slow-changing (weekly for digest, monthly for voice/catalog).
- **Semantics**: Vertical-wide domain intelligence shared by all merchants within a category (`dentists`, `salons`, `restaurants`, `gyms`, `pharmacies`).
- **Fields**:
  | Field | Type | Description & Semantics | Required |
  |---|---|---|---|
  | `slug` | `string` | Unique category identifier: `"dentists"`, `"salons"`, `"restaurants"`, `"gyms"`, `"pharmacies"`. | Yes |
  | `display_name` | `string` | Human-readable name of the vertical. | Optional |
  | `voice` | `object` | Contains `tone` (e.g., `"peer_clinical"`), `register`, `code_mix` (e.g., `"hindi_english_natural"`), `vocab_allowed` (whitelisted domain jargon), `vocab_taboo` (strictly prohibited claims: "guaranteed", "cure"), `salutation_examples`, and `tone_examples`. | Yes |
  | `offer_catalog` | `list[object]` | Canonical service+price patterns (fields: `id`, `title`, `value`, `audience`, `type` like `service_at_price`, `free_service`, `membership`). | Yes |
  | `peer_stats` | `object` | City/metro benchmarks: `avg_rating`, `avg_review_count`, `avg_views_30d`, `avg_calls_30d`, `avg_directions_30d`, `avg_ctr`, `avg_photos`, `avg_post_freq_days`, `retention_6mo_pct`. | Yes |
  | `digest` | `list[object]` | Weekly research, compliance, CDE, tech, and trend items. Fields: `id`, `kind` (`research`, `compliance`, `cde`, `trend`, `tech`), `title`, `source`, `summary`, `actionable`, optional `trial_n`, `patient_segment`, `date`, `credits`. | Yes |
  | `patient_content_library` | `list[object]` | Pre-drafted educational or informational assets merchant can share with customers. Fields: `id`, `title`, `channel`, `length_seconds`, `body`. | Yes |
  | `seasonal_beats` | `list[object]` | Recurring seasonal demand shifts (e.g., `month_range`: `"Nov-Feb"`, `note`: `"exam-stress bruxism spike"`). | Yes |
  | `trend_signals` | `list[object]` | Macro query trends (e.g., `query`: `"clear aligners delhi"`, `delta_yoy`: `0.62`, `segment_age`: `"28-45"`). | Yes |

### 2.2 MerchantContext (`scope: "merchant"`)
- **Status**: Required for all compositions.
- **Refresh Cadence**: Daily for metrics/signals, real-time for conversation history.
- **Semantics**: Specific business identity, operational metrics, subscription tier, offer catalog, and relationship state with magicpin/Vera.
- **Fields**:
  | Field | Type | Description & Semantics | Required |
  |---|---|---|---|
  | `merchant_id` | `string` | Primary key (e.g., `"m_001_drmeera_dentist_delhi"`). | Yes |
  | `category_slug` | `string` | Foreign key matching `CategoryContext.slug`. | Yes |
  | `identity` | `object` | Business name (`name`), `city`, `locality`, `place_id`, `verified` (`bool`), `languages` (`list[str]`), `owner_first_name`, `established_year`. | Yes |
  | `subscription` | `object` | Plan details: `status` (`"active"`, `"expiring"`, `"lapsed"`), `plan` (`"Pro"`, `"Basic"`), `days_remaining` (`int`), `renewed_at`. | Yes |
  | `performance` | `object` | 30-day window metrics: `views`, `calls`, `directions`, `ctr`, `leads`, plus `delta_7d` percentage shifts (`views_pct`, `calls_pct`, `ctr_pct`). | Yes |
  | `offers` | `list[object]` | Merchant's active and expired offers: `id`, `title`, `status` (`"active"`, `"expired"`, `"paused"`), `started`, `ended`. | Yes |
  | `conversation_history`| `list[object]` | Past turns between Vera and merchant: `ts`, `from` (`"vera"`, `"merchant"`), `body`, `engagement` tag (`"merchant_replied"`, `"intent_action"`, `"merchant_no_reply"`, etc.). | Yes |
  | `customer_aggregate` | `object` | High-level CRM metrics: `total_unique_ytd`, `lapsed_180d_plus`, `retention_6mo_pct`, cohort flags (e.g., `high_risk_adult_count`). | Yes |
  | `signals` | `list[str]` | Pre-computed diagnostic signals (e.g., `"stale_posts:22d"`, `"ctr_below_peer_median"`, `"perf_dip_severe"`, `"dormant_with_vera_14d"`). | Yes |
  | `review_themes` | `list[object]` | Aggregated sentiment clusters: `theme`, `sentiment` (`pos`/`neg`), `occurrences_30d`, `common_quote`. | Optional |

### 2.3 TriggerContext (`scope: "trigger"`)
- **Status**: Required. Every message must have an initiating trigger context.
- **Refresh Cadence**: Event-driven (injected dynamically or pushed via simulated tick).
- **Semantics**: The immediate catalyst explaining *why* this message must be sent *now*.
- **Fields**:
  | Field | Type | Description & Semantics | Required |
  |---|---|---|---|
  | `id` | `string` | Primary key (e.g., `"trg_001_research_digest_dentists"`). | Yes |
  | `scope` | `string` | Target recipient audience: `"merchant"` or `"customer"`. | Yes |
  | `kind` | `string` | Trigger family classification (see §3.2). | Yes |
  | `source` | `string` | Origin: `"external"` (market, regulations, calendar) or `"internal"` (merchant perf, CRM event). | Yes |
  | `merchant_id` | `string` | Target merchant recipient or merchant sponsor. | Yes |
  | `customer_id` | `string \| null`| Target customer recipient when `scope == "customer"`, otherwise `null`. | Required if scope is customer |
  | `payload` | `object` | Specific parameters of the event (e.g., `top_item_id`, `metric`, `delta_pct`, `deadline_iso`, `available_slots`). | Yes |
  | `urgency` | `int` | Priority scale from 1 (lowest/informational) to 5 (critical/immediate). | Yes |
  | `suppression_key`| `string` | Idempotency and deduplication key to prevent repeated messaging. | Yes |
  | `expires_at` | `string` | ISO-8601 timestamp after which the trigger is void. | Yes |

### 2.4 CustomerContext (`scope: "customer"`)
- **Status**: Optional in merchant-facing messages; **Mandatory** when `trigger.scope == "customer"`.
- **Refresh Cadence**: Real-time / per-visit CRM sync.
- **Semantics**: Individual consumer record for messages composed on behalf of the merchant.
- **Fields**:
  | Field | Type | Description & Semantics | Required |
  |---|---|---|---|
  | `customer_id` | `string` | Primary key (e.g., `"c_001_priya_for_m001"`). | Yes |
  | `merchant_id` | `string` | Foreign key binding customer to specific merchant. | Yes |
  | `identity` | `object` | `name`, `phone_redacted`, `language_pref` (e.g., `"hi-en mix"`, `"english"`, `"te-en mix"`), `age_band`. | Yes |
  | `relationship` | `object` | `first_visit`, `last_visit`, `visits_total`, `services_received` (`list[str]`), `lifetime_value`, optional `favourite_dish`. | Yes |
  | `state` | `string` | Lifecycle stage: `"new"`, `"active"`, `"lapsed_soft"`, `"lapsed_hard"`, `"churned"`. | Yes |
  | `preferences` | `object` | `preferred_slots`, `channel`, `reminder_opt_in`, optional `preferred_stylist`, `wedding_date`. | Yes |
  | `consent` | `object` | Regulatory opt-in audit: `opted_in_at` (ISO date), `scope` (`list[str]`). | Yes |

---

## 3. Message Types & Formats

### 3.1 Recipient Identities (`send_as`)
1. **`"vera"` (Merchant-Facing)**:
   - Sent from Vera's magicpin profile to the merchant owner/manager.
   - Tone: Collegial, peer-to-peer, analytical, consultative, respectful of time.
   - Voice styling matches merchant's primary `identity.languages`.
2. **`"merchant_on_behalf"` (Customer-Facing)**:
   - Sent from the merchant's business WhatsApp account to their customer.
   - Drafted by Vera on behalf of the owner (e.g., "Dr. Meera's clinic here", "Lakshmi from Studio11 Kapra here").
   - Tone: Warm, customer-friendly, service-oriented; strictly adheres to medical/advertising legal taboos (no false guarantees).

### 3.2 Trigger Kinds & Message Families
- **External Families**:
  - `research_digest`: Cites reputable clinical/domain research; offers patient-education collateral.
  - `regulation_change`: Actionable compliance warning with deadline and specific equipment/SOP implications.
  - `festival_upcoming`: Pre-festival campaign preparation anchored on real calendar milestones.
  - `weather_heatwave` / `local_news_event`: Real-time contextual hooks relevant to customer footfall or delivery spikes.
  - `category_trend_movement`: Search spikes or demographic trend insights with listing enhancement advice.
- **Internal Families**:
  - `perf_spike`: Celebrates positive performance deltas and suggests doubling down.
  - `perf_dip`: Diagnoses drop in views/calls/CTR and offers immediate corrective actions.
  - `milestone_reached`: Review count or milestone celebration.
  - `dormant_with_vera`: Low-friction re-engagement for dormant merchants.
  - `renewal_due`: Direct subscription renewal alerts with expiration days.
  - `recall_due`: Customer service recalls (e.g., 6-month dental cleaning, car service) with concrete date/time slot proposals.
  - `wedding_package_followup` / `bridal_followup`: Milestone countdown for high-value lifecycle packages.
  - `curious_ask_due`: Strategic questions asking the merchant for frontline observations ("What treatment was most requested this week?").

### 3.3 Message Format Constraints
- **WhatsApp 24-Hour Session Window**:
  - **First Outbound Turn**: Must provide template parameters (`template_name`, `template_params`) representing Meta-approved template format (`{{1}}`, `{{2}}`), along with the rendered `body`.
  - **Subsequent In-Session Turns**: Can use flexible, free-form markdown text.
- **Call to Action (CTA)**:
  - Must provide a single primary CTA.
  - Allowed types: `binary` (YES/STOP), `choice` (Slot 1 / Slot 2), `open_ended`, or `none` (informational).
  - Anti-pattern: Never combine multiple competing CTAs in one message.

---

## 4. Conversation Behavior & Lifecycle State Machine

```
              [POST /v1/tick]
                     │
         ┌───────────┴───────────┐
         │ Has compelling trigger│
         │ & passed suppression? │
         └─────┬───────────┬─────┘
           Yes │           │ No
               ▼           ▼
        [Send Action]   [Empty Actions []]
               │
               ▼
        [POST /v1/reply]
               │
     ┌─────────┼─────────────────────────┬─────────────────────────┐
     ▼         ▼                         ▼                         ▼
[Auto-Reply] [Hostile / Stop]       [Intent Action]          [Inquiry / Clarification]
     │         │                         │                         │
     ▼         ▼                         ▼                         ▼
(Count repeats)(Apologize / Exit)   (Transition to Exec)      (Answer grounded in context)
 action="end"   action="end"         action="send"             action="send"
 or "wait"                           (No re-qualifying!)
```

### 4.1 Proactive Behavior (`/v1/tick`)
- Executed periodically on simulated clock ticks.
- Evaluates candidate triggers from `available_triggers` against current merchant state and suppression rules.
- Limits outbound actions to high-signal situations: maximum 20 actions per tick; at most 1 action per `(merchant_id, conversation_id)` pair.
- When no trigger warrants messaging, the bot must return `actions: []` (restraint is rewarded; spam is penalized).

### 4.2 Reactive Behavior (`/v1/reply`)
- Receives inbound user response with `turn_number`, `from_role`, and `message`.
- Must respond synchronously within 30 seconds with one of three decisions:
  1. `action: "send"`: Bot sends follow-up `body`, `cta`, and `rationale`.
  2. `action: "wait"`: Bot backs off, specifying `wait_seconds` (e.g., merchant asked for time).
  3. `action: "end"`: Bot terminates conversation gracefully.

### 4.3 Automated Reply Handling (Auto-Reply Hell)
- **Problem**: Inbound messages matching canned WhatsApp business greetings (e.g., "Thank you for contacting us, we will respond shortly").
- **Behavior**:
  - Turn 1: If detected, attempt one polite pivot to see if human is present.
  - Turn 2+: If identical canned pattern repeats (or repeats >= 2 times), emit `action: "end"` or `action: "wait"`. Never burn turns talking in circles.

### 4.4 Intent Transition Handling
- **Problem**: When a merchant indicates commitment ("Yes", "Ok let's do it", "Please update profile", "Send the draft"), legacy bots repeat qualification questions.
- **Behavior**:
  - Immediately switch from *pitch/qualify mode* to *action/execution mode*.
  - Return confirmation of work initiated or completed with clear next steps.
  - Strictly avoid re-asking questions like "Would you like me to do X?" when the user just said "Yes, do X".

### 4.5 Hostility & Opt-Out Handling
- When merchant sends hostile, frustrated, or opt-out messages ("Stop messaging me", "Unsubscribe", "Spam", "Leave me alone"):
  - Do not debate or attempt to persuade.
  - Either apologize politely in one short sentence and exit (`action: "send"` followed by termination) or immediately terminate (`action: "end"`).

### 4.6 Question & Objection Handling
- Answer questions directly using context facts (e.g., explaining why GBP verification takes 24–48 hours, explaining pricing details).
- Never hallucinate external facts, competitor names, or imaginary guarantees.

---

## 5. Technical Architecture & API Contract

The bot must expose 5 HTTP/JSON endpoints matching the specification in `challenge-testing-brief.md`:

### 5.1 `GET /v1/healthz`
- **Purpose**: Liveness probe polled every 60s.
- **Response (200)**:
  ```json
  {
    "status": "ok",
    "uptime_seconds": 3600,
    "contexts_loaded": {
      "category": 5,
      "merchant": 50,
      "customer": 200,
      "trigger": 100
    }
  }
  ```
- **Rule**: Must accurately report context counts in memory. 3 consecutive non-200 responses result in disqualification.

### 5.2 `GET /v1/metadata`
- **Purpose**: Identity and configuration inspection.
- **Response (200)**:
  ```json
  {
    "team_name": "string",
    "team_members": ["string"],
    "model": "string",
    "approach": "string",
    "contact_email": "string",
    "version": "string",
    "submitted_at": "string"
  }
  ```

### 5.3 `POST /v1/context`
- **Purpose**: Context ingestion and atomic updates.
- **Request**:
  ```json
  {
    "scope": "category" | "merchant" | "customer" | "trigger",
    "context_id": "string",
    "version": 1,
    "payload": { ... },
    "delivered_at": "ISO-8601 string"
  }
  ```
- **Behavior & Responses**:
  - **Idempotency**: Same `(context_id, version)` returns 200 without duplicate processing.
  - **Atomic Replacement**: Higher `version` for existing `context_id` atomically replaces existing payload.
  - **Conflict (409)**: If incoming `version <= current_version` when attempting an overwrite:
    `{"accepted": false, "reason": "stale_version", "current_version": int}`
  - **Success (200)**:
    `{"accepted": true, "ack_id": "string", "stored_at": "ISO-8601 string"}`
  - **Validation Error (400)**: Malformed scope or missing required fields.

### 5.4 `POST /v1/tick`
- **Purpose**: Periodic proactive simulation step.
- **Request**:
  ```json
  {
    "now": "ISO-8601 string",
    "available_triggers": ["trg_001", "trg_002"]
  }
  ```
- **Response (200)**:
  ```json
  {
    "actions": [
      {
        "conversation_id": "conv_unique_id",
        "merchant_id": "m_001",
        "customer_id": null,
        "send_as": "vera" | "merchant_on_behalf",
        "trigger_id": "trg_001",
        "template_name": "vera_template_v1",
        "template_params": ["param1", "param2"],
        "body": "Composed message body...",
        "cta": "binary" | "open_ended" | "choice" | "none",
        "suppression_key": "suppress:m_001:kind",
        "rationale": "Reason for send and expected outcome"
      }
    ]
  }
  ```

### 5.5 `POST /v1/reply`
- **Purpose**: Multi-turn reactive conversation handling.
- **Request**:
  ```json
  {
    "conversation_id": "conv_001",
    "merchant_id": "m_001",
    "customer_id": null,
    "from_role": "merchant" | "customer",
    "message": "User's reply text",
    "received_at": "ISO-8601 string",
    "turn_number": 2
  }
  ```
- **Response (200)**:
  ```json
  {
    "action": "send" | "wait" | "end",
    "body": "Optional response body (required if action == 'send')",
    "cta": "Optional CTA (if action == 'send')",
    "wait_seconds": 1800,
    "rationale": "Reason for action decision"
  }
  ```

---

## 6. Constraints & Invariants

1. **Deterministic Execution**: Given identical context inputs and simulator settings, the system must produce deterministic decisions and outputs.
2. **Response Latency**: Maximum 30 seconds per call. If `tick` or `reply` takes > 30s, the judge logs a timeout penalty.
3. **Payload Limit**: `/v1/context` payload cap is 500 KB.
4. **Action Budget**: Maximum 20 actions per `/v1/tick`.
5. **No Hallucination (Universal Invariant)**: All facts, numbers, dates, paper citations, discounts, and prices must strictly originate from the provided context layers.
6. **Data Privacy**: No payload data may be leaked outside approved LLM APIs or saved after test teardown.
7. **State Preservation**: Context and conversation states must persist across requests.
