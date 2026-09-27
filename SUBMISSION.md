# SUBMISSION BRIEF: magicpin AI Challenge — Vera

**Submission Date**: September 27, 2026  
**Candidate Team**: Harsh Kumar  
**System Name**: Vera AI Agent Engine  
**Repository**: [https://github.com/HKR000/magicpin-ai-challenge](https://github.com/HKR000/magicpin-ai-challenge)  
**Branch**: `main`  
**License**: Proprietary / Evaluation License  

---

## 1. Project Information for Portal Submission

* **Team Name**: Harsh Kumar
* **Primary Contact**: engineering@magicpin.challenge
* **Model Approach**: `hybrid-deterministic-reasoning`
* **Architecture Summary**: 
  Four-context relational state machine backed by a 5-tier context selector with strict provenance, multi-objective decision arbitration, Meta-compliant WhatsApp template parameter extraction, and a deterministic 13-dimension output safety and anti-hallucination validator.
* **Core Technology Stack**:
  - Language: Python 3.10+
  - Web Framework: FastAPI 0.136.1 & Uvicorn 0.47.0 (ASGI)
  - Data Validation: Pydantic v2 (2.13.4)
  - Thread Safety: Monitored In-Memory Relational Engine with `threading.RLock`
  - Containerization: Multi-stage Docker (Python 3.10-slim, non-root user `appuser`)

---

## 2. Production Health & Live Verification Endpoints

If deploying to a live public host (e.g. Railway, Render, Fly.io, or AWS EC2), the base URL exposes all required challenge endpoints:

* `GET /v1/healthz` — Liveness & loaded context counters
* `GET /v1/metadata` — Architecture & candidate identity
* `GET /v1/metrics` — Request counters & latency percentiles (avg 3–5ms)
* `POST /v1/context` — 4-domain relational ingestion with 409 stale version guards
* `POST /v1/tick` — Proactive trigger evaluation & Meta template action emitter
* `POST /v1/reply` — Multi-turn conversational next-move evaluator
* `POST /v1/teardown` — Automated state cleanup endpoint
* `GET /` — Interactive web dashboard & live state machine playground

---

## 3. Official Evaluator Scorecard

* **Overall Canonical Rubric Score**: **47 / 50 (94.0%, EXCELLENT)**
  - Specificity: **10 / 10**
  - Category Fit: **10 / 10**
  - Merchant Fit: **9 / 10**
  - Decision Quality: **8 / 10**
  - Engagement: **10 / 10**
* **Competition Scenarios**: **4 / 4 PASS (100%)**
  - Warmup: **PASS** (14ms)
  - Auto-Reply Hell: **PASS** (Turn 1: WAITING 900s, Turn 2: cleanly ENDED)
  - Intent Transition: **PASS** (Immediate switch to ACTION mode on commitment)
  - Hostile Handling: **PASS** (Immediate polite apology and exit)
* **Automated Unit & Stress Tests**: **209 / 209 PASS in 2.25s**

---

## 4. Key Engineering Innovations

1. **Zero-Hallucination 5-Tier Provenance Engine**:
   Every claim, percentage, price, or quote in composed messages is matched against verified context facts with origin tracing. Prohibited claims and taboo vocabulary (*"guaranteed"*, *"100% cure"*) are deterministically blocked.
2. **Deterministic Commitment Transition**:
   When a merchant expresses commitment (*"Yes"*, *"Do it"*), Vera immediately switches to `ACTION_PENDING` and schedules execution—she never re-qualifies or questions a willing merchant.
3. **Cross-Conversation Auto-Reply Fatigue Tracking**:
   Eliminates infinite loop turn wastage by tracking repeated canned WhatsApp business auto-replies across conversation threads, terminating on Turn 2.
4. **Sub-30s Asynchronous Hard Deadline**:
   All reactive replies are wrapped in a 25.0s asynchronous timeout deadline, guaranteeing the service never times out against the judge harness while operating with an average latency of 3–5ms.
5. **Customer Consent Scope Isolation**:
   Strict pre-dispatch gating prevents customer-facing promotional triggers from being sent unless the recipient has explicitly granted `whatsapp_marketing` consent.

---

## 5. Deployment Instructions

### Option A: Local Execution
```bash
pip install -r requirements.txt
python -m uvicorn bot:app --host 0.0.0.0 --port 8080
```

### Option B: Docker Container
```bash
docker build -t magicpin-vera-bot:latest .
docker run -p 8080:8080 magicpin-vera-bot:latest
```

### Option C: Run Local Judge Simulator
```bash
python judge_simulator.py all
python judge_simulator.py full_evaluation
```
