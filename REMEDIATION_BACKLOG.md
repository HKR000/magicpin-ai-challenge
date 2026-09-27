# REMEDIATION BACKLOG: magicpin AI Challenge (Vera)

**Document ID**: `REMEDIATION_BACKLOG.md`  
**Status**: Authoritative Remediation Backlog  
**Audit Reference**: `FINAL_COMPLIANCE_AUDIT.md`, `COMPLIANCE_MATRIX.md`  

---

## 1. Prioritization & Classification Standard

* **P0 (Challenge-Blocking)**: Issues preventing system startup, crashes, HTTP 500s, or hard failure of all evaluation scenarios. *(0 items identified)*
* **P1 (Major Compliance Gap)**: Formal challenge requirements that are missing or non-compliant under evaluation. *(2 items)*
* **P2 (Important Quality Gap)**: Important behavioral, regulatory, or architectural edge cases affecting robust execution. *(3 items)*
* **P3 (Minor Improvement)**: Non-blocking polish, underutilized optional dataset fields, or low-probability edge test cases. *(2 items)*

---

## 2. Remediation Backlog Table

| ID | Priority | Component | Problem | Root Cause | Required Change | Dependencies | Tests | Risk |
|---|---|---|---|---|---|---|---|---|
| **REM-01** | **P1** | **STATE / CONVERSATION** | Auto-reply handler emits `action: "wait"` repeatedly across turns 1–4 without terminating (`action: "end"`), causing the judge simulator to log `[WARN] Bot never ended after 4 auto-replies`. | 1. In `vera/conversation/machine.py`, `_handle_auto_reply_transition` lacks a hard threshold to transition to `STOPPED` / `end` when `auto_reply_count >= 2`.<br>2. In `judge_simulator.py:882`, each simulated auto-reply turn provides a new conversation ID (`conv_auto_{i}`) for the same merchant, bypassing conversation-scoped counters. | 1. Update `_handle_auto_reply_transition()` in `machine.py` so that `auto_reply_count >= 2` transitions to `State.STOPPED` with `action="end"`.<br>2. Add merchant-level consecutive auto-reply tracking in `ContextEngine` so auto-reply fatigue persists across conversation threads from the same merchant account. | None | `test_conversation_state_machine.py`, `judge_simulator.py auto_reply` | Low (Isolated to auto-reply intent handling) |
| **REM-02** | **P1** | **API** | `POST /v1/teardown` endpoint is missing from `bot.py`. Calls return HTTP 404 Not Found. | The route handler `@app.post("/v1/teardown")` was not wired up to the FastAPI application, even though `ContextEngine.clear()` is already fully implemented. | Expose `@app.post("/v1/teardown")` in `bot.py` that invokes `engine.clear()` and returns `{"accepted": True, "wiped": True}`. | None | `test_integrated_loop.py`, HTTP curl test against `/v1/teardown` | Low (Add-only route, zero impact on existing endpoints) |
| **REM-03** | **P2** | **TRIGGER / CUSTOMER** | `POST /v1/tick` in `bot.py` evaluates candidate triggers directly instead of delegating to `TriggerEngine.evaluate_candidates()`, bypassing customer consent scope verification (`consent.scope`). | In `bot.py:347`, `tick` iterates over `sorted_triggers` and calls `vera.handle_proactive_trigger()` directly without running `TriggerEngine._check_customer_consent()`. | Refactor `/v1/tick` in `bot.py` or `vera.handle_proactive_trigger()` to validate `trigger.scope == "customer"` against `CustomerContext.consent.scope` before dispatching. | None | `test_trigger_engine.py`, `test_customer_model.py` | Medium (Could suppress valid marketing triggers if scope string matching is overly strict) |
| **REM-04** | **P2** | **GENERATION** | WhatsApp `template_params` positional variable array is empty (`[]`) for several proactive communication objectives (`RE_ENGAGE_LAPSED_CUSTOMER`, `PREPARE_FESTIVAL_CAMPAIGN`, `RECOVER_PERFORMANCE_DIP`). | `MessageComposer.compose()` does not instantiate `template_name` and `template_params` on `ComposedMessage` in non-research branches, leaving them `None`. | In `MessageComposer.compose()`, systematically extract `[salutation, anchor_1, anchor_2, cta]` into `template_params` for all proactive objectives. | None | `test_message_composer.py`, `test_integrated_loop.py` | Low (Adds metadata array without modifying rendered text body) |
| **REM-05** | **P2** | **CONTEXT / TESTING** | Lack of concurrent multi-threaded ingestion stress testing. Under parallel streaming context pushes, potential race conditions in version checking are unverified. | The test suite is 100% synchronous and single-threaded. | Add `tests/test_concurrency.py` simulating 50 concurrent async context pushes with version conflicts to prove thread safety under `_lock`. | None | `test_concurrency.py` | Low (Testing-only change) |
| **REM-06** | **P3** | **MERCHANT / GENERATION** | `MerchantContext.review_themes` sentiment clusters are parsed but never selected into `SelectionBundle` or incorporated into copy synthesis. | `ContextSelector.select()` does not evaluate `merchant.review_themes`. | Extract top positive review theme in `ContextSelector` under `SUPPORTING` tier, and allow `MessageComposer` to optionally cite it in `curious_ask_due` or `milestone_reached`. | None | `test_context_selector.py`, `test_message_composer.py` | Low (Feature enhancement in copy) |
| **REM-07** | **P3** | **TESTING / RELIABILITY** | No automated unit test verifies graceful behavior when an upstream dependency hangs beyond the 30.0-second deadline. | System runs completely offline in <5ms; timeout edge case never synthetically exercised. | Add mock unit test simulating socket hang and asserting that `/v1/reply` returns fallback response before 30-second timeout. | None | `tests/test_reliability.py` | Low (Testing-only change) |
