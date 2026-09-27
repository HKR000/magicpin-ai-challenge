# MISSING FUNCTIONALITY REGISTER: magicpin AI Challenge (Vera)

**Audit Date**: September 27, 2026  
**Auditor**: Independent Principal Software Architect & AI Systems Auditor  
**Scope**: Strictly absent or insufficient capabilities verified through evidence  

---

## MF-01: Absence of `POST /v1/teardown` HTTP Endpoint

* **Missing Capability**: Endpoint to wipe in-memory context and active conversations upon judge test completion.
* **Challenge Requirement**:
  - `challenge-testing-brief.md` §11: *"Bots must not persist context data after the test ends. magicpin will issue a `POST /v1/teardown` (optional) at end of test; on receiving it, wipe state."*
  - `EVALUATION_SPEC.md` §6 item 2: *"Context Cleanup / Teardown Endpoint: Section 11 of challenge-testing-brief.md mentions that magicpin will issue an optional POST /v1/teardown at the conclusion of testing... our system should handle both empty bodies and `{"wipe": true}` gracefully."*
* **Evidence that it is Missing**:
  - Inspection of `bot.py` routes confirms handlers exist for `/v1/healthz`, `/v1/metrics`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`, `/v1/conversation/{id}`, `/v1/conversations`, and `/`. No route `@app.post("/v1/teardown")` exists.
  - Making an HTTP POST to `http://127.0.0.1:8080/v1/teardown` yields `404 Not Found`.
* **Why it Matters**:
  - If the judge harness issues `/v1/teardown` between test batches or at the end of the test window, an unhandled HTTP 404 error is logged, risking operational deduction or test suite interruption.
* **Affected Component**: `bot.py` (FastAPI route layer) and `vera/context/engine.py` (ContextEngine state clear method).
* **Severity**: **HIGH**.
* **Recommended Implementation**:
  ```python
  @app.post("/v1/teardown")
  async def teardown(request: Request):
      """Wipe all in-memory context and active conversations upon test completion."""
      engine.clear()
      return {"accepted": True, "wiped": True, "timestamp": datetime.utcnow().isoformat() + "Z"}
  ```
* **Verification Method**: Execute HTTP POST `/v1/teardown` and assert HTTP 200 response with `contexts_loaded` counts returning to zero.

---

## MF-02: Enforcement of `CustomerContext.consent.scope` Pre-Dispatch

* **Missing Capability**: Pre-send regulatory verification comparing `trigger.kind` against `CustomerContext.consent.scope`.
* **Challenge Requirement**:
  - `CHALLENGE_SPEC.md` §2.4: Specifies `CustomerContext.consent.scope` (`list[str]`, e.g., `["whatsapp_marketing", "reminders"]`).
  - `EVALUATION_SPEC.md` §2.2: Stresses compliance-accurate outreach adhering to medical and advertising regulations.
* **Evidence that it is Missing**:
  - In `vera/trigger/engine.py` (`TriggerEngine.evaluate_candidate`) and `vera/orchestrator.py`, the system checks trigger expiration (`expires_at`), suppression keys, and customer existence, but does NOT check if `trigger.kind` matches the customer's granted consent scope.
  - If a trigger of kind `festival_upcoming` or `promo_offer` targets a customer who only granted consent for `["reminders"]`, the engine dispatches the message anyway.
* **Why it Matters**:
  - Sending unsolicited marketing campaigns to consumers without marketing consent violates WhatsApp Business messaging policies and consumer protection guidelines.
* **Affected Component**: `vera/trigger/engine.py`, `vera/trigger/decision.py`.
* **Severity**: **MEDIUM**.
* **Recommended Implementation**:
  - Introduce a consent-gate check in `TriggerEngine.evaluate_candidate`: If `trigger.scope == "customer"`, map trigger kind to required scope (e.g. `promo` -> `whatsapp_marketing`, `recall_due` -> `reminders`), and suppress action if the required permission is absent from `customer.consent.scope`.
* **Verification Method**: Unit test ingesting customer with `consent.scope = ["reminders"]` and submitting a marketing trigger; verify trigger is suppressed with reason `consent_scope_mismatch`.

---

## MF-03: Incorporation of `MerchantContext.review_themes` in Copy Generation

* **Missing Capability**: Utilization of aggregated customer review sentiment clusters in decision making and copy composition.
* **Challenge Requirement**:
  - `CHALLENGE_SPEC.md` §2.2: Specifies `MerchantContext.review_themes` (`list[object]` containing `theme`, `sentiment`, `occurrences_30d`, `common_quote`).
* **Evidence that it is Missing**:
  - `vera/models/merchant.py` parses `review_themes`, but `vera/context/selector.py` never references or selects `review_themes` into `SelectionBundle`.
  - `vera/composer/engine.py` does not utilize `review_themes` in any communication objective.
* **Why it Matters**:
  - Positive customer review themes ("staff friendliness", "hygiene", "great coffee") provide authentic social-proof hooks that could improve merchant engagement conversion.
* **Affected Component**: `vera/context/selector.py`, `vera/composer/engine.py`.
* **Severity**: **LOW**.
* **Recommended Implementation**:
  - Select prominent positive review themes in `ContextSelector` under `SUPPORTING` tier, and allow `MessageComposer` to cite them in `curious_ask_due` or `milestone_reached` objectives.
* **Verification Method**: Unit test verifying that positive review theme appears in selection bundle and message copy.
