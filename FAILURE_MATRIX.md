# FAILURE MATRIX & SYSTEMIC ERROR CLASSIFICATION

**Level**: LEVEL 12 — OFFICIAL EVALUATOR INTEGRATION  
**Purpose**: Rigorous classification of all failure modes, edge-case bottlenecks, and friction points across the 12 canonical failure categories prior to targeted optimization.  
**Baseline Score**: **82.56% (41.28 / 50.00) — EXCELLENT TIER**  
**Total Failures / Friction Points Classified**: 24 items across 12 domains.

---

## 1. Classification Matrix by Category

| Category | Issue ID | Observed Failure / Friction Point | Root Cause Analysis | Severity |
| :--- | :--- | :--- | :--- | :---: |
| **DATA** | `DAT-01` | Non-uniform merchant owner naming schema (`owner_name` vs `owner_first_name` vs `name`) | Dataset merchants have varying property names across JSON payloads. | Medium |
| **DATA** | `DAT-02` | Unpopulated customer communication preferences (`preferred_channel` missing in some records) | Customer dataset models did not enforce default fallback channel before ingestion. | Low |
| **CONTEXT** | `CTX-01` | Re-pushed identical context versions without incrementing `version` field | Context repository raised validation or overwrite conflicts when re-ingesting identical keys. | Medium |
| **CONTEXT** | `CTX-02` | Redundant fact retention across repeated tick evaluations | Multi-tenant context store did not flush temporary per-tick provenance facts between batches. | Medium |
| **TRIGGER** | `TRG-01` | Broadcast triggers missing `merchant_id` returning zero actions | Global/category triggers (e.g. DCI compliance) lacked explicit target merchant binding. | High |
| **TRIGGER** | `TRG-02` | Invalid or unrecognized trigger ID in tick batch | If an unrecognized trigger ID is passed, strict dictionary lookup could raise `KeyError`. | Medium |
| **INTENT** | `INT-01` | Mixed intent in merchant replies (e.g., "Sounds good, what is the cost?") | Dual intent (Acceptance + Inquiry) classified ambiguously without hierarchical priority. | High |
| **INTENT** | `INT-02` | High-frequency auto-replies across disparate conversation IDs | Simulated test created new conversation IDs per auto-reply turn (`conv_auto_1`, `conv_auto_2`). | Medium |
| **STATE** | `STA-01` | Non-monotonic turn numbers when reusing conversation IDs in test loops | Prior conversation states preserved in memory caused out-of-order turn counter conflicts. | High |
| **STATE** | `STA-02` | Intermediate qualification lag after commitment | State engine did not transition immediately from `PITCHED` to `ACTION_PENDING`. | High |
| **DECISION** | `DEC-01` | Over-eager proposal generation on weak / low-confidence triggers | Decision engine defaulted to `PROPOSE_SOLUTION` instead of `WAIT` or `NONE`. | High |
| **DECISION** | `DEC-02` | Action payload mismatch on committed state | Decision engine emitted exploratory questions rather than action execution instructions. | High |
| **PROMPT** | `PRM-01` | Soft qualifying language ("Would you like to...", "Can we...") post-commitment | Prompt templates favored polite consultative questions rather than assertive next steps. | High |
| **PROMPT** | `PRM-02` | Generic merchant salutation when owner name missing | Reverted to generic "Valued Partner" rather than business entity name. | Low |
| **GENERATION** | `GEN-01` | Specificity score bottleneck (5.4 / 10 average) | Generated copy relied on qualitative statements rather than exact rupees / percentages. | High |
| **GENERATION** | `GEN-02` | Lead-in conversational filler ("Certainly! We noticed...") | Generative output occasionally prefixed pleasantries violating brevity constraints. | Medium |
| **VALIDATION** | `VAL-01` | Validation error exception on repeated test messages | When identical messages drafted, `MessageComposer` raised error without fallback recovery. | Critical |
| **VALIDATION** | `VAL-02` | Overly strict repetition threshold on multi-tenant single-merchant campaigns | Repeating seasonal slogans flagged as cross-turn repetition. | Medium |
| **STOPPING** | `STP-01` | Potential infinite auto-reply ping-pong loop | Lack of automated auto-responder signature detection would cause endless conversational turns. | Critical |
| **STOPPING** | `STP-02` | Soft decline vs hard opt-out confusion | Failure to cleanly distinguish "Not this month" (pause) from "Stop messaging me" (opt-out). | High |
| **API** | `API-01` | Missing `accepted: true` boolean in `/v1/context` response | Judge client specifically checks `data.get("accepted")` rather than HTTP status code alone. | High |
| **API** | `API-02` | Action response structure mismatch in `/v1/reply` | Returned dict lacked `action` or `wait_seconds` fields expected by automated judge harness. | High |
| **INFRASTRUCTURE**| `INF-01` | Windows console `UnicodeEncodeError` in ASCII terminal | Judge printed UTF-8 block characters (`\u2588`, `\u2591`) failing on Windows `cp1252`. | High |
| **INFRASTRUCTURE**| `INF-02` | IPv6 localhost lookup latency (`::1` vs `127.0.0.1`) | Default `localhost` resolution under Windows caused 2000ms delay on socket connect. | Medium |

---

## 2. In-Depth Analysis by Category

### 2.1 DATA
* **Systemic Pattern**: **Schema Heterogeneity Across Upstream Sources.**  
  Merchant and customer records originating from different operational systems lack unified normalization. For example, some merchant objects use `name` while others use `business_name`, and owner names vary between full string, first name, or nested objects.
* **Failure Symptoms**: Fallback to generic salutations ("Hi there") which degrades the Merchant Fit dimension score.

### 2.2 CONTEXT
* **Systemic Pattern**: **Stateful Context Drift & Provenance Bleed.**  
  When high volumes of contextual payloads are pushed in rapid succession, facts from prior triggers remain active in memory if TTL or clear boundaries are not enforced.
* **Failure Symptoms**: Facts selected for generation can accidentally cite outdated metrics or irrelevant cross-category items.

### 2.3 TRIGGER
* **Systemic Pattern**: **Unbounded Scope in Broadcast Triggers.**  
  Triggers that apply category-wide (e.g. `trg_002_compliance_dci_radiograph`) lack pre-assigned merchant IDs.
* **Failure Symptoms**: If the bot tick engine only processes triggers with explicit `merchant_id`, broadcast triggers are silently dropped, yielding 0 actions and failing coverage.

### 2.4 INTENT
* **Systemic Pattern**: **Compound / Multi-Clause Intent Ambiguity.**  
  Real-world replies frequently combine an agreement clause with an objection or question ("Yes let's do it, but what will the commission be?").
* **Failure Symptoms**: If the classifier treats this solely as an `INQUIRY`, it fails to advance to `ACTION_PENDING`. If treated solely as `ACCEPTANCE`, it ignores the objection.

### 2.5 STATE
* **Systemic Pattern**: **Re-Entrant Conversation Idempotency.**  
  Test harnesses and external evaluators frequently restart test scenarios using the same `conversation_id` without clearing historical state.
* **Failure Symptoms**: The dialogue engine attempts to load prior completed turns, resulting in duplicate-turn errors or out-of-sequence turn counts.

### 2.6 DECISION
* **Systemic Pattern**: **Premature Actioning Without Factual Grounding.**  
  When incoming trigger confidence or context completeness is below 70%, the decision engine historically attempted to generate a proposal rather than deciding to `WAIT` or request clarification.
* **Failure Symptoms**: Results in generic, low-specificity outputs that score poorly (4/10 or 5/10) on Decision Quality.

### 2.7 PROMPT
* **Systemic Pattern**: **Polite Qualifier Drift.**  
  Conversational prompts trained or engineered for general customer service inherently inject polite qualifying questions ("Would you like us to proceed?").
* **Failure Symptoms**: Directly penalised by evaluation harnesses that test for decisive, low-friction execution once a merchant has committed.

### 2.8 GENERATION
* **Systemic Pattern**: **Quantitative Timidity.**  
  Composer models tend to produce conservative qualitative claims ("significantly increase your footfall") instead of injecting hard verified facts from the context ("fill 4 weekday cancellations", "recover 18 lapsed members").
* **Failure Symptoms**: Specificity scores plateau at 5–7 out of 10. This is the primary limiting factor preventing Vera from reaching 48+/50.

### 2.9 VALIDATION
* **Systemic Pattern**: **Brittle Exception Raising vs Graceful Healing.**  
  When validation rules (e.g. repetition, token length) fail, raising raw exceptions halts the execution pipeline and causes HTTP 500 crashes instead of engaging fallback repair loops.
* **Failure Symptoms**: Crashes the entire tick or reply endpoint during adversarial tests.

### 2.10 STOPPING
* **Systemic Pattern**: **Auto-Reply Echo Chambers & Zombie Dialogues.**  
  Automated email/SMS responders ("Out of office", "We will contact you shortly") mimic legitimate user inquiries.
* **Failure Symptoms**: Without pattern detection and turn ceilings, conversational bots burn messaging quotas and annoy recipients.

### 2.11 API
* **Systemic Pattern**: **Implicit Contract Misalignment.**  
  Evaluation harnesses enforce strict implicit contracts (e.g. `wait_seconds` integer in wait actions, `accepted` boolean in push responses) that exceed bare HTTP 200 specifications.
* **Failure Symptoms**: The bot operates functionally, but the judge simulator reports failure due to missing expected dictionary keys.

### 2.12 INFRASTRUCTURE
* **Systemic Pattern**: **Platform-Specific Runtime Friction.**  
  Development and evaluation environments on Windows encounter distinct encoding (`cp1252`) and networking (`localhost` resolving to IPv6 `::1`) behaviors not present on Linux CI runners.
* **Failure Symptoms**: Terminal rendering crashes (`UnicodeEncodeError`) and artificial 2-second socket connection delays.

---

## 3. Systemic Failure Patterns: Root Cause Clustering

Clustering all 24 failure items reveals **Three Core Systemic Themes**:

```
+-----------------------------------------------------------------------------------+
|                           CORE SYSTEMIC PATTERNS                                  |
+-----------------------------------------------------------------------------------+
|  1. GROUNDED SPECIFICITY DEFICIT (GEN-01, DEC-01, PRM-01)                        |
|     * Cause: Conservative copy synthesis avoiding numerical facts.               |
|     * Score Impact: Limits Specificity to 5.4/10; caps overall score at 82.5%.    |
|                                                                                   |
|  2. CONTRACT & SCHEMA RIGIDITY (API-01, API-02, VAL-01, DAT-01)                  |
|     * Cause: Unhandled exceptions on schema drift and missing validation healing. |
|     * Score Impact: Threatens zero-score crashes on unexpected payloads.          |
|                                                                                   |
|  3. ADVERSARIAL DIALOGUE CONTROL (STP-01, STP-02, INT-01, STA-01)                 |
|     * Cause: Non-deterministic conversational state machines.                     |
|     * Score Impact: Risk of looping in auto-replies or missing commitment cues.   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Baseline Establishment & Roadmap

* **Current Baseline**: **82.56% (41.28 / 50.00)** — Confirmed via `judge_simulator.py full_evaluation`.
* **Current Tier**: **EXCELLENT**
* **Next Optimization Focus (Level 13+)**:
  1. Inject verified numerical anchors into composer templates to elevate Specificity from 5.4/10 to 9.0+/10.
  2. Implement schema normalization middleware to resolve `DATA` heterogeneity.
  3. Formalize dual-intent resolution in the `INTENT` classifier.
