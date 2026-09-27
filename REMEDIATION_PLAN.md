# PRIORITIZED REMEDIATION PLAN: magicpin AI Challenge (Vera)

**Audit Date**: September 27, 2026  
**Auditor**: Independent Principal Software Architect & AI Systems Auditor  
**Standard**: Objective Engineering Impact (P0 -> P1 -> P2 -> P3)  

---

## P0 — CRITICAL (Blocks Basic Challenge Compliance or Execution)

*There are currently **zero P0 blockers**. The engine boots cleanly, exposes all primary contract endpoints (`/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`), parses 100% of seed and expanded records, passes all 193 automated unit and adversarial tests, and scores 47/50 (94%, EXCELLENT) on the official canonical evaluation rubric.*

---

## P1 — HIGH (Major Required Capabilities Missing or Degraded)

### Item P1-1: Auto-Reply Hard Termination after >= 2 Canned Turns
* **Requirement**: `CHALLENGE_SPEC.md` §4.3 & `EVALUATION_SPEC.md` §4.4 (Auto-Reply Hell Stress Test).
* **Current State**: Emits `action: "wait"` with `wait_seconds: 900` across all turns (Turn 1 through Turn 4). Never transitions to terminal state.
* **Evidence**:
  ```text
  [PASS] Turn 1: Bot WAITING 900s
  [PASS] Turn 2: Bot WAITING 900s
  [PASS] Turn 3: Bot WAITING 900s
  [PASS] Turn 4: Bot WAITING 900s
  [WARN] Bot never ended after 4 auto-replies
  ```
* **Exact Missing Behavior**: When `conv.auto_reply_count >= 2`, the conversation state machine must emit `action: "end"` and mark `is_active = False`.
* **Implementation Required**:
  In `vera/conversation/machine.py`, update `_handle_auto_reply_transition()`:
  ```python
  if conv.auto_reply_count >= 2:
      conv.transition_to(ConversationState.ENDED)
      return StateTransition(
          from_state=ConversationState.AWAITING_REPLY,
          to_state=ConversationState.ENDED,
          action="end",
          rationale="Repeated canned auto-reply detected (>=2 turns); terminating dialogue to prevent turn wastage",
      )
  else:
      return StateTransition(
          from_state=ConversationState.AWAITING_REPLY,
          to_state=ConversationState.AWAITING_REPLY,
          action="wait",
          wait_seconds=900,
          rationale="Initial auto-reply detected; backing off 15 minutes",
      )
  ```
* **Verification Test**: Run `python judge_simulator.py auto_reply` and assert `[PASS] Turn 2: Bot correctly ENDED on repeated auto-reply`.

### Item P1-2: Implement `POST /v1/teardown` State Wipe Endpoint
* **Requirement**: `challenge-testing-brief.md` §11 & `EVALUATION_SPEC.md` §6 item 2.
* **Current State**: Endpoint does not exist in `bot.py`; calls return HTTP 404.
* **Evidence**: Route search in `bot.py` confirms absence of `/v1/teardown`.
* **Exact Missing Behavior**: An HTTP POST endpoint that wipes in-memory dictionaries and resets active conversation tracking.
* **Implementation Required**:
  Add in `bot.py`:
  ```python
  @app.post("/v1/teardown")
  async def teardown(request: Request):
      """Wipe all loaded contexts and conversation state upon test completion."""
      engine._categories.clear()
      engine._merchants.clear()
      engine._customers.clear()
      engine._triggers.clear()
      engine._contexts.clear()
      engine._conversations.clear()
      logger.info("Teardown executed: all in-memory context and state wiped cleanly.")
      return {"accepted": True, "wiped": True, "timestamp": datetime.utcnow().isoformat() + "Z"}
  ```
* **Verification Test**: Execute HTTP POST `/v1/teardown` and assert HTTP 200 response with `contexts_loaded` counts returning to zero.

---

## P2 — MEDIUM (Important Behavioral Degradation or Gaps)

### Item P2-1: Enforce Customer Consent Scope Prior to Outbound Dispatch
* **Requirement**: `CHALLENGE_SPEC.md` §2.4 (`CustomerContext.consent.scope`).
* **Current State**: Context store parses `consent.scope`, but `TriggerEngine.evaluate_candidate()` does not assert that the customer has granted permission for marketing outreach before generating a proactive action.
* **Evidence**: `vera/trigger/engine.py` checks only trigger expiration and suppression keys.
* **Exact Missing Behavior**: When `trigger.scope == "customer"`, check `customer.consent.scope`. If trigger kind is promotional and `whatsapp_marketing` is absent from `consent.scope`, suppress action.
* **Implementation Required**:
  Add validation hook in `TriggerEngine.evaluate_candidate()`:
  ```python
  if trigger.scope == ContextScope.CUSTOMER and customer:
      if trigger.kind in {"promo_offer", "festival_upcoming", "category_trend_movement"}:
          if "whatsapp_marketing" not in (customer.consent.scope or []):
              return None, "Customer has not consented to WhatsApp marketing"
  ```
* **Verification Test**: Create customer with `consent.scope = ["reminders"]` and verify promotional triggers are rejected.

### Item P2-2: Systematic WhatsApp Template Parameter Population
* **Requirement**: `CHALLENGE_SPEC.md` §3.3 & `challenge-testing-brief.md` §2.2.
* **Current State**: `template_params` is populated for research digest objectives but defaults to empty `[]` for festival and performance dip objectives.
* **Evidence**: Inspecting output actions from `POST /v1/tick` shows `"template_params": []` for certain proactive actions.
* **Exact Missing Behavior**: Systematically extract positional template variables `[salutation, anchor_1, anchor_2, cta_prompt]` across all proactive branches.
* **Implementation Required**:
  Update `MessageComposer.compose()` to populate `ComposedMessage.template_params` in all proactive branches.
* **Verification Test**: Unit test in `test_message_composer.py` asserting non-empty `template_params` across all 10 canonical case study scenarios.

### Item P2-3: Concurrent Ingestion & Thread-Safety Tests
* **Requirement**: `challenge-testing-brief.md` §1 (streaming concurrent ingestion).
* **Current State**: Single-threaded synchronous test execution only.
* **Evidence**: Zero asynchronous / multi-threaded race condition tests in `tests/`.
* **Exact Missing Behavior**: Concurrently pushing 100 context payloads in parallel tasks to verify lock safety and version conflict handling under contention.
* **Implementation Required**: Add `tests/test_concurrency.py` executing `asyncio.gather(*[client.post(...) for _ in range(50)])`.
* **Verification Test**: Test passes without deadlocks or corrupted context counts.

---

## P3 — LOW (Minor Optimizations or Quality of Life)

### Item P3-1: Surface `MerchantContext.review_themes` in Engagement Hooks
* **Requirement**: `CHALLENGE_SPEC.md` §2.2 (`review_themes`).
* **Current State**: `review_themes` parsed into Pydantic models but omitted from context selection and copy synthesis.
* **Evidence**: `vera/context/selector.py` does not extract review theme facts.
* **Exact Missing Behavior**: Incorporate positive review themes into merchant consultation copy.
* **Implementation Required**: Add `review_theme` extraction in `ContextSelector` and incorporate into `curious_ask_due` objective in `MessageComposer`.
* **Verification Test**: Unit test asserting review themes appear in selection bundle.

### Item P3-2: Synthetic Timeout Injection Guard Test
* **Requirement**: Strict 30.0-second SLA (`challenge-testing-brief.md` §2.3).
* **Current State**: Local reasoning executes in <5ms; no timeout test exists.
* **Evidence**: No test mocks an intentional 31-second hang.
* **Exact Missing Behavior**: Unit test verifying timeout middleware drops slow background tasks and returns fallback before the 30-second judge limit.
* **Implementation Required**: Add mock hanging route test.
* **Verification Test**: Request times out cleanly without server crash.
