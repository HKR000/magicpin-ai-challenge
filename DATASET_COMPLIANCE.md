# DATASET COMPLIANCE REPORT: magicpin AI Challenge (Vera)

**Audit Date**: September 27, 2026  
**Auditor**: Independent Principal Software Architect & AI Systems Auditor  
**Standard**: Strict Evidentiary Verification (Priority 1: Challenge Spec, Priority 2: Challenge Datasets)  
**Status**: COMPLETE AUDIT  

---

## 1. Executive Summary: Dataset Compliance

| Dataset Domain | Source Location | Record Count (Seed) | Record Count (Expanded) | Schema Validation Status | Mapping Fidelity | Compliance Finding |
|---|---|---|---|---|---|---|
| **Categories** | `dataset/categories/*.json`, `expanded/categories/*.json` | 5 records | 5 records | **VERIFIED** (0 errors) | 90.9% active usage | **PARTIAL**: `regulatory_authorities` & `professional_journals` stored but ignored |
| **Merchants** | `dataset/merchants_seed.json`, `expanded/merchants/*.json` | 10 records | 50 records | **VERIFIED** (0 errors) | 90.0% active usage | **PARTIAL**: `review_themes` stored but unused in decision/composition |
| **Customers** | `dataset/customers_seed.json`, `expanded/customers/*.json` | 15 records | 200 records | **VERIFIED** (0 errors) | 85.7% active usage | **PARTIAL**: `consent.scope` validated but not enforced before dispatch |
| **Triggers** | `dataset/triggers_seed.json`, `expanded/triggers/*.json` | 25 records | 100 records | **VERIFIED** (0 errors) | 100% active usage | **VERIFIED**: Full relational and expiration mapping |

---

## 2. Dataset Inventory & Structural Verification

### 2.1 Category Datasets
- **Files Inspected**:
  - `dataset/categories/dentists.json` (7,303 bytes)
  - `dataset/categories/gyms.json` (7,186 bytes)
  - `dataset/categories/pharmacies.json` (7,529 bytes)
  - `dataset/categories/restaurants.json` (6,740 bytes)
  - `dataset/categories/salons.json` (6,959 bytes)
- **Top-Level Fields**: `slug`, `display_name`, `voice`, `offer_catalog`, `peer_stats`, `digest`, `patient_content_library`, `seasonal_beats`, `trend_signals`, `regulatory_authorities`, `professional_journals`.
- **Validation**: All 5 seed and 5 expanded category files validate against `vera.models.category.CategoryContext` without schema errors.

### 2.2 Merchant Datasets
- **Files Inspected**:
  - `dataset/merchants_seed.json`: 10 merchant records across 5 verticals (2 dentists, 2 salons, 2 restaurants, 2 gyms, 2 pharmacies).
  - `expanded/merchants/`: 50 merchant files (`m_001.json` through `m_050.json`).
- **Top-Level Fields**: `merchant_id`, `category_slug`, `identity`, `subscription`, `performance`, `offers`, `conversation_history`, `customer_aggregate`, `signals`, `review_themes`.
- **Validation**: All 10 seed and 50 expanded merchant files validate against `vera.models.merchant.MerchantContext` without schema errors.

### 2.3 Customer Datasets
- **Files Inspected**:
  - `dataset/customers_seed.json`: 15 customer records bound to seed merchants.
  - `expanded/customers/`: 200 customer files (`c_001.json` through `c_200.json`).
- **Top-Level Fields**: `customer_id`, `merchant_id`, `identity`, `relationship`, `state`, `preferences`, `consent`.
- **Validation**: All 15 seed and 200 expanded customer files validate against `vera.models.customer.CustomerContext` without schema errors.

### 2.4 Trigger Datasets
- **Files Inspected**:
  - `dataset/triggers_seed.json`: 25 trigger records across 15 trigger kinds.
  - `expanded/triggers/`: 100 trigger files (`trg_001.json` through `trg_100.json`).
- **Top-Level Fields**: `id`, `scope`, `kind`, `source`, `merchant_id`, `customer_id`, `payload`, `urgency`, `suppression_key`, `expires_at`.
- **Validation**: All 25 seed and 100 expanded trigger files validate against `vera.models.trigger.TriggerContext` without schema errors.

---

## 3. Relational & Referential Integrity Audit

| Relationship | Primary Key | Foreign Key | Seed Matches | Expanded Matches | Integrity Status |
|---|---|---|---|---|---|
| **Merchant -> Category** | `CategoryContext.slug` | `MerchantContext.category_slug` | 10 / 10 (100%) | 50 / 50 (100%) | **VERIFIED** |
| **Customer -> Merchant** | `MerchantContext.merchant_id` | `CustomerContext.merchant_id` | 15 / 15 (100%) | 200 / 200 (100%) | **VERIFIED** |
| **Trigger -> Merchant** | `MerchantContext.merchant_id` | `TriggerContext.merchant_id` | 25 / 25 (100%) | 100 / 100 (100%) | **VERIFIED** |
| **Trigger -> Customer** | `CustomerContext.customer_id` | `TriggerContext.customer_id` | 5 / 5 (100%) | 20 / 20 (100%) | **VERIFIED** |

*Note*: For triggers where `scope == "merchant"`, `customer_id` is correctly `null`. For all triggers where `scope == "customer"`, `customer_id` strictly resolves to a valid, existing `CustomerContext`.

---

## 4. Field Utilization & Gap Analysis

### 4.1 Category Context Field Utilization
* **`slug`**: **VERIFIED** (Used as primary lookup key and routing logic).
* **`display_name`**: **VERIFIED** (Used in dashboard and metadata).
* **`voice.tone`**: **VERIFIED** (Enforced in composer salutations and tone routing).
* **`voice.vocab_taboo`**: **VERIFIED** (Extracted as `MANDATORY` fact in `ContextSelector`; verified by `OutputValidator.detect_taboo_violations`).
* **`offer_catalog`**: **VERIFIED** (Used when merchant active offers are absent).
* **`peer_stats`**: **VERIFIED** (Used in `RECOVER_PERFORMANCE_DIP` objective when comparing CTR/views to peer medians).
* **`digest`**: **VERIFIED** (Directly indexed by `top_item_id` in `PITCH_RESEARCH_CAMPAIGN` objective).
* **`patient_content_library`**: **PARTIAL** (Drafted collateral is referenced in decision rationale but body text is truncated or omitted in outbound turns).
* **`seasonal_beats`**: **VERIFIED** (Used in `PREPARE_FESTIVAL_CAMPAIGN`).
* **`trend_signals`**: **VERIFIED** (Used in search volume hooks).
* **`regulatory_authorities`**: **MISSING from execution** (Stored in database/Pydantic, but not selected by `ContextSelector` or used in composer).
* **`professional_journals`**: **MISSING from execution** (Digest `source` is used, but top-level category `professional_journals` list is not referenced).

### 4.2 Merchant Context Field Utilization
* **`merchant_id`**: **VERIFIED** (Primary routing key).
* **`category_slug`**: **VERIFIED** (Foreign key resolution).
* **`identity.owner_first_name`**: **VERIFIED** (Prioritized for salutations `Dr. {name}` or `Hi {name}`).
* **`identity.name`**: **VERIFIED** (Business name attribution).
* **`identity.locality` / `city`**: **VERIFIED** (Geographic grounding).
* **`identity.languages`**: **VERIFIED** (Language code-mix guidance).
* **`subscription.status` & `days_remaining`**: **VERIFIED** (Used in `renewal_due` triggers).
* **`performance.delta_7d`**: **VERIFIED** (Used in `RECOVER_PERFORMANCE_DIP`).
* **`offers`**: **VERIFIED** (Filtered by status; active offers selected, expired offers isolated to prevent leakage).
* **`conversation_history`**: **VERIFIED** (Inspected by composer to avoid verbatim repetition).
* **`customer_aggregate`**: **VERIFIED** (High-risk adult cohort count utilized in research pitches).
* **`signals`**: **VERIFIED** (Checked in proactive arbitration).
* **`review_themes`**: **MISSING from execution** (Aggregated sentiment clusters stored in data model but never surfaced in outreach copy).

### 4.3 Customer Context Field Utilization
* **`customer_id` & `merchant_id`**: **VERIFIED** (Identity binding).
* **`identity.name`**: **VERIFIED** (Customer salutation).
* **`identity.language_pref`**: **VERIFIED** (Tone and code-mix adjustment).
* **`relationship.services_received` & `last_visit`**: **VERIFIED** (Service recall anchoring).
* **`preferences.preferred_slots`**: **VERIFIED** (Proactive appointment proposal).
* **`consent.opted_in_at`**: **VERIFIED** (Present in record).
* **`consent.scope`**: **INCORRECT / PARTIAL** (The system ingests and stores consent scope e.g. `["whatsapp_marketing", "reminders"]`, but the proactive trigger arbiter does not assert that the customer's consent scope includes the trigger kind prior to generating an outbound action).

---

## 5. Potential Data Edge Cases & Vulnerabilities

1. **Missing Identifiers in Dynamic Context**:
   - If a trigger specifies `customer_id` but the corresponding customer has not been ingested yet, `ContextEngine.get_customer()` returns `None`. `ContextSelector` correctly marks `customer_identity` as `UNAVAILABLE` rather than crashing.
2. **Expired vs Active Offer Collisions**:
   - In merchants with both active and expired offers of identical names, `ContextSelector` filters strictly on `status == "active"`. Stale offers are marked `IRRELEVANT` with `is_stale=True`.
3. **HTML / Script Injection in Payload Strings**:
   - `bot.py` applies `sanitize_payload_data` recursively stripping `<script>` and HTML markup from inbound payloads.
