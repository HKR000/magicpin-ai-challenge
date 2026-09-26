# Vera Internal Data Model Specification
**Document ID**: `DATA_MODEL.md`  
**Status**: Authoritative Data Dictionary & Schema Specification  
**Component**: `vera.models`  
**Engine**: Pydantic V2  

---

## 1. Architectural Overview

The Vera data model provides strongly-typed, runtime-validated Python data structures corresponding to the four context layers, internal conversation state, decision arbitration, message actions, version control, and validation results.

```
┌────────────────────────────────────────────────────────┐
│                   Context Envelopes                    │
│   ContextEnvelope (category, merchant, customer, trg)  │
└──────────┬───────────────────┬───────────────────┬─────┘
           ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ CategoryContext  │ │ MerchantContext  │ │ CustomerContext  │
├──────────────────┤ ├──────────────────┤ ├──────────────────┤
│ VoiceProfile     │ │ MerchantIdentity │ │ CustomerIdentity │
│ OfferTemplate    │ │ Subscription     │ │ Relationship     │
│ PeerStats        │ │ Performance      │ │ CustomerState    │
│ DigestItem       │ │ MerchantOffer    │ │ Preferences      │
│ SeasonalBeat     │ │ TurnRecord       │ │ Consent          │
│ TrendSignal      │ │ CustomerAggregate│ └──────────────────┘
└──────────────────┘ └──────────────────┘
           │                   │                   │
           └───────────────┐   │   ┌───────────────┘
                           ▼   ▼   ▼
               ┌───────────────────────┐
               │    TriggerContext     │
               └───────────┬───────────┘
                           ▼
               ┌───────────────────────┐
               │   Decision Engine     │
               │   ProactiveDecision   │
               │   ReactiveDecision    │
               │   DetectedIntent      │
               └───────────┬───────────┘
                           ▼
               ┌───────────────────────┐
               │    Message Models     │
               │   ComposedMessage     │
               │   ProactiveAction     │
               │   ReplyAction         │
               └───────────────────────┘
```

---

## 2. Entity Dictionaries

### 2.1 CategoryContext (`vera.models.category`)
Shared domain intelligence for a vertical. Source: `dataset/categories/*.json`.

| Field Name | Type | Req/Opt | Validation | Meaning / Purpose | Source |
|---|---|---|---|---|---|
| `slug` | `str` | Required | `min_length=1` | Vertical slug (`dentists`, `salons`, etc.) | `categories/*.json` |
| `display_name` | `Optional[str]` | Optional | None | Human-readable category label | `categories/*.json` |
| `voice` | `VoiceProfile` | Required | Nested model | Tone, code-mix, vocabulary, taboos | `categories/*.json` |
| `offer_catalog` | `List[OfferTemplate]`| Required | List of models | Canonical service+price patterns | `categories/*.json` |
| `peer_stats` | `PeerStats` | Required | Nested model | Vertical benchmarks (CTR, reviews, rating) | `categories/*.json` |
| `digest` | `List[DigestItem]` | Required | List of models | Curated research, compliance, CDE items | `categories/*.json` |
| `patient_content_library` | `List[PatientContentItem]` | Required | List of models | Educational collateral for customer sharing | `categories/*.json` |
| `seasonal_beats` | `List[SeasonalBeat]` | Required | List of models | Annual demand cyclicality windows | `categories/*.json` |
| `trend_signals` | `List[TrendSignal]` | Required | List of models | Local search trends and demographics | `categories/*.json` |
| `regulatory_authorities` | `List[str]` | Optional | List of strings | Statutory oversight bodies | `categories/*.json` |
| `professional_journals` | `List[str]` | Optional | List of strings | Trade publications and journals | `categories/*.json` |

#### Nested Sub-Models:
- **`VoiceProfile`**:
  - `tone` (`str`, Req): Overall voice persona (e.g. `peer_clinical`).
  - `register` / `register_style` (`Optional[str]`, Opt): Sociolinguistic register.
  - `code_mix` (`Optional[str]`, Opt): Language mixing guidance (`hindi_english_natural`).
  - `vocab_allowed` (`List[str]`, Opt): Permitted domain terminology.
  - `vocab_taboo` (`List[str]`, Opt): Prohibited words ("guaranteed", "cure").
  - `salutation_examples` (`List[str]`, Opt): Preferred salutations.
  - `tone_examples` (`List[str]`, Opt): Reference tone snippets.
- **`OfferTemplate`**:
  - `id` (`str`, Req): Unique template ID.
  - `title` (`str`, Req): Display title with service+price.
  - `value` (`str`, Req): Price or discount value.
  - `audience` (`str`, Req): `new_user`, `repeat_user`, `all`.
  - `type` (`str`, Req): Structure (`service_at_price`, `free_service`, `bogo`, `percentage_discount`).
- **`PeerStats`**:
  - `scope` (`Optional[str]`, Opt): Locality and cohort scope.
  - `avg_rating` (`float`, Req): 0.0 to 5.0.
  - `avg_review_count` (`int`, Req): >= 0.
  - `avg_views_30d` (`Optional[int]`, Opt): >= 0.
  - `avg_calls_30d` (`Optional[int]`, Opt): >= 0.
  - `avg_directions_30d` (`Optional[int]`, Opt): >= 0.
  - `avg_ctr` (`float`, Req): 0.0 to 1.0.
  - `retention_6mo_pct` (`Optional[float]`, Opt): 0.0 to 1.0.
  - `retention_30d_pct` (`Optional[float]`, Opt): 0.0 to 1.0.
- **`DigestItem`**:
  - `id` (`str`, Req): Unique digest ID.
  - `kind` (`str`, Req): `research`, `compliance`, `cde`, `trend`, `tech`, `seasonal`.
  - `title` (`str`, Req): Headline.
  - `source` (`str`, Req): Origin citation.
  - `summary` (`str`, Req): Intelligence summary.
  - `actionable` (`Optional[str]`, Opt): Operational suggestion.
  - `trial_n` (`Optional[int]`, Opt): Sample size if clinical trial.
  - `patient_segment` (`Optional[str]`, Opt): Target cohort.
- **`TrendSignal`**:
  - `query` (`str`, Req): Search query.
  - `delta_yoy` (`float`, Req): Year-over-year search delta (+0.62 = +62%).
  - `segment_age` (`Optional[str]`, Opt): Demographic age band.
  - `skew` (`Optional[str]`, Opt): Gender or demographic skew.

---

### 2.2 MerchantContext (`vera.models.merchant`)
Operational and performance profile of a specific business. Source: `dataset/merchants_seed.json` & `expanded/merchants/*.json`.

| Field Name | Type | Req/Opt | Validation | Meaning / Purpose | Source |
|---|---|---|---|---|---|
| `merchant_id` | `str` | Required | `min_length=1` | Primary merchant key (`m_001_drmeera...`) | `merchants/*.json` |
| `category_slug` | `str` | Required | `min_length=1` | Foreign key to `CategoryContext.slug` | `merchants/*.json` |
| `identity` | `MerchantIdentity` | Required | Nested model | Business name, location, languages, owner | `merchants/*.json` |
| `subscription` | `Subscription` | Required | Nested model | Status (`active`, `expired`), plan, days | `merchants/*.json` |
| `performance` | `PerformanceSnapshot` | Required | Nested model | Views, calls, directions, CTR, deltas | `merchants/*.json` |
| `offers` | `List[MerchantOffer]` | Required | List of models | Active and historical listing offers | `merchants/*.json` |
| `conversation_history`| `List[ConversationTurnRecord]`| Required | List of models | Previous WhatsApp exchanges with Vera | `merchants/*.json` |
| `customer_aggregate` | `CustomerAggregate`| Required | Nested model | CRM metrics (YTD unique, lapsed, retention) | `merchants/*.json` |
| `signals` | `List[str]` | Required | List of strings | Derived diagnostic flags | `merchants/*.json` |
| `review_themes` | `List[ReviewTheme]`| Optional | List of models | Sentiment clusters from reviews | `merchants/*.json` |

#### Nested Sub-Models:
- **`MerchantIdentity`**: `name` (Req), `city` (Req), `locality` (Req), `place_id` (Opt), `verified` (`bool`, Req), `languages` (`List[str]`, Req), `owner_first_name` (Opt), `established_year` (Opt, 1800..2100).
- **`Subscription`**: `status` (Req), `plan` (Req), `days_remaining` (`Optional[int]`), `days_since_expiry` (`Optional[int]`), `renewed_at` (Opt).
- **`PerformanceSnapshot`**: `window_days` (`int`, default 30), `views` (`int`, >= 0), `calls` (`int`, >= 0), `directions` (`int`, >= 0), `ctr` (`float`, 0.0..1.0), `leads` (`Optional[int]`), `delta_7d` (`Optional[PerformanceDelta]`: `views_pct`, `calls_pct`, `ctr_pct`).
- **`MerchantOffer`**: `id` (Req), `title` (Req), `status` (`active`, `expired`, `paused`), `started` (Opt), `ended` (Opt).
- **`ConversationTurnRecord`**: `ts` (Req), `from_role` (Req, alias `from`), `body` (Req), `engagement` (Opt).
- **`CustomerAggregate`**: Flexible CRM model supporting vertical metrics: `total_unique_ytd`, `total_active_members`, `lapsed_180d_plus`, `lapsed_90d_plus`, `retention_6mo_pct`, `retention_3mo_pct`, `retention_30d_pct`, `repeat_customer_pct`, `delivery_share_pct`, `chronic_rx_count`.
- **`ReviewTheme`**: `theme` (Req), `sentiment` (`pos`, `neg`, `neutral`), `occurrences_30d` (Req, >= 0), `common_quote` (Opt).

---

### 2.3 TriggerContext (`vera.models.trigger`)
Catalyst prompting outreach. Source: `dataset/triggers_seed.json` & `expanded/triggers/*.json`.

| Field Name | Type | Req/Opt | Validation | Meaning / Purpose | Source |
|---|---|---|---|---|---|
| `id` | `str` | Required | `min_length=1` | Trigger ID (`trg_001_research_digest`) | `triggers/*.json` |
| `scope` | `TriggerScope` | Required | `merchant` or `customer` | Target audience partition | `triggers/*.json` |
| `kind` | `str` | Required | `min_length=1` | Trigger family (e.g. `research_digest`) | `triggers/*.json` |
| `source` | `TriggerSource` | Required | `external` or `internal` | Event origin | `triggers/*.json` |
| `merchant_id` | `str` | Required | `min_length=1` | Target or sponsor merchant | `triggers/*.json` |
| `customer_id` | `Optional[str]` | Optional* | Required if scope is customer | Target customer recipient | `triggers/*.json` |
| `payload` | `Dict[str, Any]` | Required | Dict | Event parameters (metrics, slots, items) | `triggers/*.json` |
| `urgency` | `int` | Required | `1 <= urgency <= 5` | Priority level (1=low, 5=critical) | `triggers/*.json` |
| `suppression_key` | `str` | Required | `min_length=1` | Rate limit and deduplication key | `triggers/*.json` |
| `expires_at` | `str` | Required | ISO-8601 string | Expiration timestamp | `triggers/*.json` |

---

### 2.4 CustomerContext (`vera.models.customer`)
CRM record for customer-facing outreach. Source: `dataset/customers_seed.json` & `expanded/customers/*.json`.

| Field Name | Type | Req/Opt | Validation | Meaning / Purpose | Source |
|---|---|---|---|---|---|
| `customer_id` | `str` | Required | `min_length=1` | Primary customer key (`c_001_priya...`) | `customers/*.json` |
| `merchant_id` | `str` | Required | `min_length=1` | Bound merchant ID | `customers/*.json` |
| `identity` | `CustomerIdentity` | Required | Nested model | Name, phone, language preference | `customers/*.json` |
| `relationship` | `CustomerRelationship`| Required | Nested model | Visits, spend, services received | `customers/*.json` |
| `state` | `CustomerState` | Required | `new`, `active`, `lapsed_soft`, `lapsed_hard`, `churned` | Lifecycle stage | `customers/*.json` |
| `preferences` | `CustomerPreferences` | Required | Nested model | Booking slot and channel preferences | `customers/*.json` |
| `consent` | `CustomerConsent` | Required | Nested model | Opt-in date and permission scopes | `customers/*.json` |

#### Nested Sub-Models:
- **`CustomerIdentity`**: `name` (Req), `phone_redacted` (Opt, `<phone>` or null), `language_pref` (Req, e.g. `hi-en mix`), `age_band` (Opt), `senior_citizen` (Opt).
- **`CustomerRelationship`**: `first_visit` (Req), `last_visit` (Req), `visits_total` (Req, >= 0), `services_received` (`List[str]`), `lifetime_value` (Opt, >= 0.0), `favourite_dish` (Opt), `chronic_conditions` (Opt).
- **`CustomerPreferences`**: `preferred_slots` (Opt), `channel` (default `whatsapp`), `reminder_opt_in` (Opt, `bool`), `preferred_stylist` (Opt), `wedding_date` (Opt).
- **`CustomerConsent`**: `opted_in_at` (Opt, ISO date or null), `scope` (`List[str]`).

---

### 2.5 Conversation & Turn Models (`vera.models.conversation`)
State tracking for active multi-turn dialogues. Source: `challenge-brief.md` §7.4, `challenge-testing-brief.md` §2.3.

| Field Name | Type | Req/Opt | Validation | Meaning / Purpose |
|---|---|---|---|---|
| `conversation_id` | `str` | Required | `min_length=1` | Unique conversation thread identifier |
| `merchant_id` | `str` | Required | `min_length=1` | Target merchant |
| `customer_id` | `Optional[str]` | Optional | None | Target customer if customer-facing |
| `trigger_id` | `Optional[str]` | Optional | None | Originating trigger |
| `stage` | `ConversationStage` | Required | `initiated`, `qualifying`, `action_committed`, `waiting`, `ended` | Dialogue lifecycle phase |
| `turns` | `List[ConversationTurn]`| Required | List of turns | Turn history |
| `auto_reply_count` | `int` | Required | `>= 0` | Consecutive auto-replies detected |
| `last_message_at` | `str` | Required | ISO string | Timestamp of last message |
| `is_active` | `bool` | Required | `bool` | Whether thread is still active |

---

### 2.6 Message & Action Models (`vera.models.message`)
Outbound and reactive message structures. Source: `challenge-testing-brief.md` §2.2, §2.3.

- **`ProactiveAction`** (`POST /v1/tick` response item):
  - `conversation_id` (`str`, Req): Thread ID.
  - `merchant_id` (`str`, Req): Target merchant.
  - `customer_id` (`Optional[str]`, Opt): Target customer.
  - `send_as` (`SendAsIdentity`, Req): `vera` or `merchant_on_behalf`.
  - `trigger_id` (`str`, Req): Initiating trigger.
  - `template_name` (`str`, Req): Meta template name for WhatsApp 24h compliance.
  - `template_params` (`List[str]`, Req): Parameter array (`{{1}}`, `{{2}}`).
  - `body` (`str`, Req): Complete rendered message body.
  - `cta` (`str`, Req): Primary Call to Action.
  - `suppression_key` (`str`, Req): Deduplication key.
  - `rationale` (`str`, Req): Judge-visible explanation of the decision.
- **`ReplyAction`** (`POST /v1/reply` response):
  - `action` (`ActionType`, Req): `send`, `wait`, or `end`.
  - `body` (`Optional[str]`): Required if `action == send`.
  - `cta` (`Optional[str]`): Required if `action == send`.
  - `wait_seconds` (`Optional[int]`): Required and must be > 0 if `action == wait`.
  - `rationale` (`str`, Req): Explanation of reactive move.

---

### 2.7 Intent Classification Models (`vera.models.intent`)
Inbound turn intent understanding. Source: `challenge-brief.md` §3, §12.

- **`DetectedIntent`**:
  - `intent_type` (`IntentType`, Req): `commitment`, `qualification`, `auto_reply`, `hostile_opt_out`, `inquiry`, `off_topic`, `unknown`.
  - `confidence` (`float`, Req): 0.0 to 1.0.
  - `raw_text` (`str`, Req): Inbound message text.
  - `signals_detected` (`List[str]`, Req): Pattern signatures detected.
  - `transition_recommended` (`Optional[str]`, Opt): Recommended next lifecycle stage.

---

### 2.8 Decision Models (`vera.models.decision`)
Audit trails for proactive and reactive arbitration.

- **`ProactiveDecision`**: `decision_type` (`proactive_send`, `proactive_skip`), `trigger_id`, `merchant_id`, `customer_id`, `selected_signal`, `selected_offer_id`, `rationale`, `suppression` (`SuppressionResult`).
- **`ReactiveDecision`**: `decision_type` (`reply_send`, `reply_wait`, `reply_end`), `conversation_id`, `intent_detected`, `rationale`, `wait_seconds`.

---

### 2.9 Context Versioning Models (`vera.models.context_version`)
Atomic ingestion and conflict control. Source: `challenge-testing-brief.md` §2.1.

- **`ContextEnvelope`** (`POST /v1/context` request): `scope` (`category`, `merchant`, `customer`, `trigger`), `context_id`, `version` (`>= 1`), `payload` (`dict`), `delivered_at`.
- **`ContextAck`** (`POST /v1/context` response): `accepted` (`bool`), `ack_id` (`Optional[str]`), `stored_at` (`Optional[str]`), `reason` (`Optional[str]`), `current_version` (`Optional[int]`).

---

### 2.10 Validation Models (`vera.models.validation`)
Audit results and error reporting.

- **`ValidationResult`**: `status` (`valid`, `invalid`, `warning`), `entity_type` (`str`), `errors` (`List[ValidationErrorDetail]`), `warnings` (`List[str]`), `is_valid` (`bool` property).
- **`ValidationErrorDetail`**: `field` (`str`), `message` (`str`), `invalid_value` (`Optional[Any]`).
