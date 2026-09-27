# INCORRECT IMPLEMENTATIONS REGISTER: magicpin AI Challenge (Vera)

**Audit Date**: September 27, 2026  
**Auditor**: Independent Principal Software Architect & AI Systems Auditor  
**Scope**: Existing implementations that exhibit incorrect, conflicting, or non-compliant behavior  

---

## II-01: Auto-Reply State Machine Loop (Failure to Terminate on Repeated Canned Replies)

* **Requirement**:
  - `CHALLENGE_SPEC.md` §4.3: *"Turn 2+: If identical canned pattern repeats (or repeats >= 2 times), emit action: 'end' or action: 'wait'. Never burn turns talking in circles."*
  - `EVALUATION_SPEC.md` §4.4 (Replay Stress Test 1: Auto-Reply Hell): *"Judge plays a merchant account sending an identical canned WhatsApp business message 4 turns in a row. Success Criterion: Bot must detect repetition and emit `action: 'end'` by turn 2 or 3."*
* **Current Behavior**:
  - The bot emits `action: "wait"` with `wait_seconds: 900` across all turns: Turn 1, Turn 2, Turn 3, and Turn 4.
  - It never transitions to terminal state `action: "end"`.
* **Evidence**:
  - Direct execution output of `python judge_simulator.py auto_reply`:
    ```text
    --- AUTO-REPLY DETECTION ---
    [INFO] Turn 1: Sending auto-reply...
    [PASS] Turn 1: Bot WAITING 900s
    [INFO] Turn 2: Sending auto-reply...
    [PASS] Turn 2: Bot WAITING 900s
    [INFO] Turn 3: Sending auto-reply...
    [PASS] Turn 3: Bot WAITING 900s
    [INFO] Turn 4: Sending auto-reply...
    [PASS] Turn 4: Bot WAITING 900s
    [WARN] Bot never ended after 4 auto-replies
    ```
* **Root Cause**:
  - In `vera/conversation/machine.py` (lines 165–175), the transition handler increments `auto_reply_count` but unconditionally returns `action: "wait"` for every occurrence without an upper bound threshold check to trigger `ConversationState.ENDED` and `action: "end"`.
* **Severity**: **HIGH**.
* **Correction Required**:
  - Modify `vera/conversation/machine.py` so that:
    - If `conv.auto_reply_count == 1`: Return `action: "wait"`, `wait_seconds: 900`.
    - If `conv.auto_reply_count >= 2`: Transition `to_state = ConversationState.ENDED`, `action = "end"`, `rationale = "Repeated canned auto-reply detected (>=2 turns); terminating dialogue to prevent turn wastage"`.
* **Test Required**:
  - Multi-turn unit test verifying that turn 1 returns `wait`, turn 2 returns `end`, and conversation state is marked `is_active = False`.

---

## II-02: Missing Template Parameter Extraction on Select Proactive Objectives

* **Requirement**:
  - `CHALLENGE_SPEC.md` §3.3 & `challenge-testing-brief.md` §2.2:
    *"First Outbound Turn: Must provide template parameters (`template_name`, `template_params`) representing Meta-approved template format (`{{1}}`, `{{2}}`), along with the rendered `body`."*
* **Current Behavior**:
  - In `vera/composer/engine.py`, while `PITCH_RESEARCH_CAMPAIGN` populates `template_params = [owner_name, source, summary]`, other proactive objectives (such as `RE_ENGAGE_LAPSED_CUSTOMER`, `PREPARE_FESTIVAL_CAMPAIGN`, and `RECOVER_PERFORMANCE_DIP`) leave `template_params` as `None` or an empty list `[]`.
  - In `bot.py` line 367, the fallback `template_params: composed.template_params or []` sends an empty parameter array `[]` to `/v1/tick` consumers.
* **Evidence**:
  - Inspecting actions returned by `POST /v1/tick` for non-research triggers shows `"template_params": []` despite having a non-null `template_name`.
* **Root Cause**:
  - `MessageComposer.compose()` does not systematically extract positional template parameters for every branch of `CommunicationObjective`.
* **Severity**: **MEDIUM**.
* **Correction Required**:
  - In `MessageComposer`, ensure every proactive objective branch populates `ComposedMessage.template_params` with the exact 2 to 4 variable strings embedded in the message template (e.g. `[salutation, offer_name, metric_delta, cta_prompt]`).
* **Test Required**:
  - Unit test in `test_message_composer.py` asserting that `composed.template_params` is a non-empty list of strings for all proactive communication objectives.
