"""Vera Bot - magicpin Merchant AI Assistant HTTP Service & Inspector Dashboard."""

from __future__ import annotations
import asyncio
import os
import re
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from vera.context import ContextEngine
from vera.models import (
    ActionType,
    ContextAck,
    ContextEnvelope,
    ContextScope,
    ConversationStage,
    IntentType,
    ProactiveAction,
    ReplyAction,
    Role,
    SendAsIdentity,
    State,
    TickResponse,
)
from vera.intent.classifier import IntentClassifier
from vera.orchestrator import Vera

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}'
)
logger = logging.getLogger("vera.service")

app = FastAPI(
    title="Vera Message Engine",
    description="magicpin Retailer AI Assistant Engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

START_TIME = time.time()
engine = ContextEngine()
intent_classifier = IntentClassifier()
vera = Vera(context_engine=engine, intent_classifier=intent_classifier)

# In-memory metrics & observability counters
METRICS_DATA = {
    "total_requests": 0,
    "status_2xx": 0,
    "status_4xx": 0,
    "status_5xx": 0,
    "latencies_ms": [],
}

@app.middleware("http")
async def observability_and_security_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()
    status_code = 500
    try:
        response: Response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as exc:
        logger.error(f"Unhandled server exception: req_id={req_id} path={request.url.path} error={str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": req_id},
            headers={"X-Request-ID": req_id}
        )
    finally:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        METRICS_DATA["total_requests"] += 1
        if 200 <= status_code < 300:
            METRICS_DATA["status_2xx"] += 1
        elif 400 <= status_code < 500:
            METRICS_DATA["status_4xx"] += 1
        else:
            METRICS_DATA["status_5xx"] += 1

        if len(METRICS_DATA["latencies_ms"]) < 1000:
            METRICS_DATA["latencies_ms"].append(latency_ms)
        else:
            METRICS_DATA["latencies_ms"][METRICS_DATA["total_requests"] % 1000] = latency_ms

        logger.info(
            f"HTTP req_id={req_id} method={request.method} path={request.url.path} "
            f"status={status_code} latency_ms={latency_ms}"
        )

# Auto-load seed dataset on startup if available
def auto_load_seeds():
    dataset_dir = Path(__file__).parent / "dataset"
    if not dataset_dir.exists():
        return

    # Categories
    cat_dir = dataset_dir / "categories"
    if cat_dir.exists():
        import json
        for cat_file in cat_dir.glob("*.json"):
            try:
                with open(cat_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                engine.ingest(
                    scope=ContextScope.CATEGORY,
                    context_id=data.get("slug", cat_file.stem),
                    version=1,
                    payload=data,
                    source="seed_autoload",
                )
            except Exception as e:
                print(f"[Autoload] Failed category {cat_file.name}: {e}")

    # Merchants seed
    m_seed = dataset_dir / "merchants_seed.json"
    if m_seed.exists():
        import json
        try:
            with open(m_seed, "r", encoding="utf-8") as f:
                merchants = json.load(f).get("merchants", [])
            for m in merchants:
                engine.ingest(
                    scope=ContextScope.MERCHANT,
                    context_id=m["merchant_id"],
                    version=1,
                    payload=m,
                    source="seed_autoload",
                )
        except Exception as e:
            print(f"[Autoload] Failed merchants seed: {e}")

    # Customers seed
    c_seed = dataset_dir / "customers_seed.json"
    if c_seed.exists():
        import json
        try:
            with open(c_seed, "r", encoding="utf-8") as f:
                customers = json.load(f).get("customers", [])
            for c in customers:
                engine.ingest(
                    scope=ContextScope.CUSTOMER,
                    context_id=c["customer_id"],
                    version=1,
                    payload=c,
                    source="seed_autoload",
                )
        except Exception as e:
            print(f"[Autoload] Failed customers seed: {e}")

    # Triggers seed
    t_seed = dataset_dir / "triggers_seed.json"
    if t_seed.exists():
        import json
        try:
            with open(t_seed, "r", encoding="utf-8") as f:
                triggers = json.load(f).get("triggers", [])
            for t in triggers:
                engine.ingest(
                    scope=ContextScope.TRIGGER,
                    context_id=t["id"],
                    version=1,
                    payload=t,
                    source="seed_autoload",
                )
        except Exception as e:
            print(f"[Autoload] Failed triggers seed: {e}")


auto_load_seeds()


# =============================================================================
# CHALLENGE API CONTRACT ENDPOINTS
# =============================================================================

def sanitize_payload_data(val: Any) -> Any:
    """Recursively strip script tags, dangerous HTML, and control chars from context payloads."""
    if isinstance(val, str):
        cleaned = re.sub(r"<script.*?>.*?</script>", "", val, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        return cleaned.strip()
    elif isinstance(val, dict):
        return {k: sanitize_payload_data(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_payload_data(v) for v in val]
    return val


@app.get("/v1/healthz")
async def healthz():
    """Liveness & health probe returning uptime, memory usage, and loaded context counts."""
    counts = engine.get_counts()
    uptime = int(time.time() - START_TIME)
    
    # Process memory stats if psutil available
    mem_info = {}
    try:
        import psutil
        proc = psutil.Process()
        mem_info = {
            "rss_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
            "vms_mb": round(proc.memory_info().vms / (1024 * 1024), 2),
        }
    except Exception:
        mem_info = {"status": "psutil_unavailable"}

    return {
        "status": "ok",
        "service": "vera-agent-engine",
        "uptime_seconds": uptime,
        "contexts_loaded": counts,
        "memory": mem_info,
        "conversations_active": len(engine._conversations),
    }


@app.get("/v1/metrics")
async def metrics():
    """Prometheus-style telemetry and latency percentiles."""
    lats = METRICS_DATA["latencies_ms"]
    p50 = round(float(sorted(lats)[len(lats) // 2]), 2) if lats else 0.0
    p95 = round(float(sorted(lats)[int(len(lats) * 0.95)]), 2) if lats else 0.0
    max_lat = round(float(max(lats)), 2) if lats else 0.0
    avg_lat = round(float(sum(lats) / len(lats)), 2) if lats else 0.0

    return {
        "total_requests": METRICS_DATA["total_requests"],
        "status_breakdown": {
            "2xx": METRICS_DATA["status_2xx"],
            "4xx": METRICS_DATA["status_4xx"],
            "5xx": METRICS_DATA["status_5xx"],
        },
        "latency_ms": {
            "avg": avg_lat,
            "p50": p50,
            "p95": p95,
            "max": max_lat,
        },
        "uptime_seconds": int(time.time() - START_TIME),
    }


@app.get("/v1/metadata")
async def metadata():
    """Bot identity and model architecture metadata."""
    return {
        "team_name": "Antigravity Engineers",
        "team_members": ["Production AI Team"],
        "model": "hybrid-deterministic-reasoning",
        "approach": "4-context stateful decision engine with verified provenance and strict zero-hallucination",
        "contact_email": "engineering@magicpin.challenge",
        "version": "1.0.0",
        "submitted_at": "2026-04-26T08:00:00Z",
    }


class ContextPushRequest(BaseModel):
    scope: str = Field(..., pattern="^(category|merchant|customer|trigger)$", description="Valid context domain")
    context_id: str = Field(..., min_length=1, max_length=128, description="Target entity identifier")
    version: int = Field(..., ge=1, description="Strict monotonically increasing integer version")
    payload: Dict[str, Any] = Field(..., description="Entity payload data")
    delivered_at: str = Field(..., description="ISO8601 delivery timestamp")


@app.post("/v1/context")
async def push_context(req: ContextPushRequest):
    """Receive atomic context pushes with version conflict handling and payload sanitization."""
    sanitized_payload = sanitize_payload_data(req.payload)
    outcome = engine.ingest(
        scope=req.scope,
        context_id=req.context_id,
        version=req.version,
        payload=sanitized_payload,
        delivered_at=req.delivered_at,
        source="POST /v1/context",
    )

    if not outcome.accepted:
        if outcome.reason == "stale_version":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "accepted": False,
                    "reason": "stale_version",
                    "current_version": outcome.current_version,
                },
            )
        elif outcome.reason == "invalid_scope":
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"accepted": False, "reason": "invalid_scope"},
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "accepted": False,
                    "reason": outcome.reason,
                    "details": [e.model_dump() for e in (outcome.validation.errors if outcome.validation else [])],
                },
            )

    return {
        "accepted": True,
        "ack_id": outcome.ack_id,
        "stored_at": outcome.stored_at,
    }


class TickRequest(BaseModel):
    now: str = Field(..., description="Simulation current timestamp")
    available_triggers: List[str] = Field(default_factory=list, description="Candidate trigger IDs")


@app.post("/v1/tick")
async def tick(req: TickRequest):
    """Periodic proactive simulation tick with priority ranking and merchant frequency-capping."""
    actions: List[Dict[str, Any]] = []

    # 1. Sort triggers by priority/urgency descending so critical perf_dip alerts precede low-urgency triggers
    def get_trigger_urgency(tid: str) -> int:
        trg = engine.get_trigger(tid)
        return trg.urgency if trg else 0

    sorted_triggers = sorted(req.available_triggers, key=get_trigger_urgency, reverse=True)

    # 2. Merchant frequency cap: Avoid spamming the same merchant multiple times in the same tick
    contacted_merchants = set()

    for trg_id in sorted_triggers:
        trigger = engine.get_trigger(trg_id)
        if not trigger:
            continue
        merchant_id = trigger.merchant_id or "unknown"
        if merchant_id != "unknown" and merchant_id in contacted_merchants:
            # Frequency capped for this tick
            continue

        # REM-03: Pre-filter customer-scoped triggers that lack customer opt-in or scope
        trg_scope = trigger.scope.value if hasattr(trigger.scope, "value") else str(trigger.scope)
        if trg_scope == "customer" or trigger.customer_id:
            if not trigger.customer_id:
                continue
            cust = engine.get_customer(trigger.customer_id)
            if not cust or not vera.trigger_engine._check_customer_consent(trigger, cust):
                continue

        conv_id = f"conv_{trg_id}"
        composed, decision, err = vera.handle_proactive_trigger(trg_id, conversation_id=conv_id)
        if composed:
            if merchant_id != "unknown":
                contacted_merchants.add(merchant_id)

            actions.append({
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": trigger.customer_id if trigger else None,
                "send_as": composed.send_as.value,
                "trigger_id": trg_id,
                "template_name": composed.template_name or f"vera_{trigger.kind if trigger else 'alert'}_v1",
                "template_params": composed.template_params if composed.template_params else [f"Team {merchant_id}", trigger.kind if trigger else "alert"],
                "body": composed.body,
                "cta": composed.cta.value,
                "suppression_key": composed.suppression_key,
                "rationale": composed.rationale,
            })

        if len(actions) >= 20:
            break

    return {"actions": actions[:20]}


class ReplyRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=128, description="Active conversation identifier")
    merchant_id: Optional[str] = Field(default=None, max_length=128, description="Merchant identifier")
    customer_id: Optional[str] = Field(default=None, max_length=128, description="Optional customer identifier")
    from_role: str = Field(default="merchant", description="'merchant' or 'customer'")
    message: str = Field(..., max_length=4000, description="Inbound text content")
    received_at: str = Field(..., description="Timestamp of inbound turn")
    turn_number: int = Field(default=1, ge=1, description="Sequence turn counter")

    @field_validator("message")
    @classmethod
    def validate_message_body(cls, v: str) -> str:
        trimmed = v.strip() if v is not None else ""
        if not trimmed:
            raise ValueError("Message body cannot be empty or pure whitespace")
        return trimmed


@app.post("/v1/reply")
async def reply(req: ReplyRequest):
    """Handle reactive replies in multi-turn conversation with strict resilience and graceful fallback."""
    # Ensure conversation exists
    engine.create_or_get_conversation(
        conversation_id=req.conversation_id,
        merchant_id=req.merchant_id or "unknown",
        customer_id=req.customer_id,
    )

    try:
        composed, decision, trans = await asyncio.wait_for(
            asyncio.to_thread(
                vera.handle_reactive_message,
                conversation_id=req.conversation_id,
                message=req.message,
                from_role=req.from_role,
                received_at=req.received_at,
            ),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Reactive processing timed out for conv={req.conversation_id}; returning safe fallback")
        return {
            "action": "end",
            "rationale": "Graceful fallback: processing exceeded response deadline",
            "body": None,
            "cta": "none",
        }
    except Exception as exc:
        logger.error(f"Error processing reactive reply for conv={req.conversation_id}: {exc}")
        # Graceful fallback: do not crash with 500, end dialogue cleanly
        return {
            "action": "end",
            "rationale": f"Graceful fallback termination: {str(exc)}",
            "body": None,
            "cta": "none",
        }

    if not trans:
        return {
            "action": "end",
            "rationale": "State machine transition returned empty; defaulting to end",
            "body": None,
            "cta": "none",
        }

    if trans.action == "wait":
        return {
            "action": "wait",
            "wait_seconds": trans.wait_seconds or 1800,
            "rationale": trans.rationale,
        }
    elif trans.action == "end":
        return {
            "action": "end",
            "rationale": trans.rationale,
            "body": composed.body if composed else None,
            "cta": composed.cta.value if composed else "none",
        }
    else:
        return {
            "action": "send",
            "body": composed.body if composed else "Acknowledged.",
            "cta": composed.cta.value if composed else "binary",
            "rationale": composed.rationale if composed else trans.rationale,
        }


@app.post("/v1/teardown")
async def teardown(request: Request):
    """Wipe all loaded context and active conversations upon judge test completion."""
    engine.clear()
    logger.info("Teardown executed: all in-memory context and state wiped cleanly.")
    return {
        "accepted": True,
        "wiped": True,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# =============================================================================
# CONVERSATION INSPECTION ENDPOINTS
# =============================================================================

@app.get("/v1/conversation/{conversation_id}")
async def get_conversation_endpoint(conversation_id: str):
    """Retrieve full conversation state and history."""
    conv = engine.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.model_dump()


@app.get("/v1/conversations")
async def list_conversations_endpoint():
    """List all stored conversations with their current states."""
    convs = engine.conversation_store.list_all()
    return {
        "total": len(convs),
        "conversations": [
            {
                "conversation_id": c.conversation_id,
                "merchant_id": c.merchant_id,
                "current_state": c.current_state.value,
                "stage": c.stage.value,
                "turn_count": len(c.turns),
                "auto_reply_count": c.auto_reply_count,
                "is_active": c.is_active,
                "last_message_at": c.last_message_at,
            }
            for c in convs
        ],
    }


# =============================================================================
# VISUAL DASHBOARD & INTERACTIVE STATE MACHINE PLAYGROUND
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Interactive visual dashboard and live state machine playground."""
    counts = engine.get_counts()
    merchants = list(engine._merchants.keys())
    triggers = list(engine._triggers.keys())
    convs = engine.conversation_store.list_all()
    active_convs = engine.conversation_store.list_active()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vera AI Engine — Live State Machine & Dialogue Inspector</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #070d18;
            --bg-surface: #0e1626;
            --bg-card: rgba(17, 27, 45, 0.85);
            --border-color: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(0, 230, 153, 0.35);
            --accent-green: #00e699;
            --accent-cyan: #00b4d8;
            --accent-gold: #ffbe0b;
            --accent-purple: #a855f7;
            --accent-rose: #f43f5e;
            --accent-orange: #f97316;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-dim: #64748b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at 10% 10%, #0d1e38 0%, var(--bg-primary) 70%);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            padding: 24px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 28px;
        }}
        .logo-group {{ display: flex; align-items: center; gap: 14px; }}
        .badge-live {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 230, 153, 0.12);
            color: var(--accent-green);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid rgba(0, 230, 153, 0.3);
            letter-spacing: 0.5px;
        }}
        .pulse-dot {{
            width: 8px; height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse 1.6s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.7; }}
            50% {{ transform: scale(1.3); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.7; }}
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #ffffff 40%, var(--accent-cyan) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .stat-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px;
            transition: all 0.2s ease;
        }}
        .stat-card:hover {{
            border-color: var(--border-hover);
            transform: translateY(-2px);
        }}
        .stat-label {{
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .stat-val {{
            font-size: 32px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
        }}
        .stat-sub {{ font-size: 11px; color: var(--text-dim); margin-top: 4px; }}
        .main-layout {{
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 24px;
        }}
        @media(max-width: 1024px) {{
            .main-layout {{ grid-template-columns: 1fr; }}
        }}
        .panel {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .panel-title {{
            font-size: 17px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        /* Chat Simulator Styles */
        .chat-container {{
            background: #0b141f;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            display: flex;
            flex-direction: column;
            height: 480px;
            overflow: hidden;
        }}
        .chat-header {{
            background: #121f2f;
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .chat-conv-meta {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .chat-body {{
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: radial-gradient(circle at 50% 50%, #0d1825 0%, #070e17 100%);
        }}
        .msg-bubble {{
            max-width: 80%;
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 13.5px;
            line-height: 1.45;
            position: relative;
        }}
        .msg-vera {{
            align-self: flex-start;
            background: #17283c;
            border: 1px solid rgba(0, 180, 216, 0.25);
            color: #e2e8f0;
            border-bottom-left-radius: 3px;
        }}
        .msg-merchant {{
            align-self: flex-end;
            background: #005c4b;
            color: #ffffff;
            border-bottom-right-radius: 3px;
        }}
        .msg-meta {{
            font-size: 10px;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 4px;
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
        }}
        .chat-controls {{
            padding: 12px;
            background: #101c2b;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            gap: 8px;
        }}
        .chat-input {{
            flex: 1;
            background: #070e17;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 10px 14px;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            font-size: 13.5px;
            outline: none;
        }}
        .chat-input:focus {{ border-color: var(--accent-green); }}
        .btn-send {{
            background: var(--accent-green);
            color: #061118;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            padding: 0 18px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-send:hover {{ filter: brightness(1.1); }}
        /* State Pill Badges */
        .state-pill {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            font-family: 'JetBrains Mono', monospace;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .state-INITIAL {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid #94a3b8; }}
        .state-PITCHED {{ background: rgba(0, 180, 216, 0.15); color: #00b4d8; border: 1px solid #00b4d8; }}
        .state-WAITING {{ background: rgba(249, 115, 22, 0.15); color: #f97316; border: 1px solid #f97316; }}
        .state-INTERESTED {{ background: rgba(168, 85, 247, 0.15); color: #a855f7; border: 1px solid #a855f7; }}
        .state-QUESTION {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid #60a5fa; }}
        .state-ACTION_PENDING {{ background: rgba(0, 230, 153, 0.15); color: #00e699; border: 1px solid #00e699; }}
        .state-COMPLETED {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #4ade80; }}
        .state-REJECTED {{ background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid #f87171; }}
        .state-STOPPED {{ background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid #fb7185; }}
        /* State Machine Visual Map */
        .state-map {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            background: #09121d;
            padding: 14px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .state-node {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 10px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            text-align: center;
            color: var(--text-secondary);
            transition: all 0.25s ease;
        }}
        .state-node.active-node {{
            border-color: var(--accent-green);
            background: rgba(0, 230, 153, 0.1);
            color: var(--accent-green);
            font-weight: 700;
            box-shadow: 0 0 12px rgba(0, 230, 153, 0.2);
            transform: scale(1.02);
        }}
        .chips-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }}
        .quick-chip {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 14px;
            padding: 4px 10px;
            font-size: 11.5px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
        }}
        .quick-chip:hover {{
            background: rgba(0, 230, 153, 0.15);
            border-color: var(--accent-green);
            color: #ffffff;
        }}
        .btn-small {{
            background: rgba(0, 180, 216, 0.15);
            border: 1px solid rgba(0, 180, 216, 0.3);
            color: var(--accent-cyan);
            font-size: 11.5px;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            transition: all 0.2s;
        }}
        .btn-small:hover {{
            background: rgba(0, 180, 216, 0.3);
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-group">
                <h1>Vera AI Engine</h1>
                <span class="badge-live"><span class="pulse-dot"></span>LEVEL 6 STATEFUL ENGINE</span>
            </div>
            <div style="display: flex; gap: 8px;">
                <a href="/v1/healthz" target="_blank" class="btn-small">/v1/healthz</a>
                <a href="/v1/metadata" target="_blank" class="btn-small">/v1/metadata</a>
                <a href="/v1/conversations" target="_blank" class="btn-small">/v1/conversations</a>
            </div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Categories</div>
                <div class="stat-val" style="color: var(--accent-cyan);">{counts['category']}</div>
                <div class="stat-sub">Retail verticals</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Merchants</div>
                <div class="stat-val" style="color: var(--accent-green);">{counts['merchant']}</div>
                <div class="stat-sub">Store context records</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Triggers</div>
                <div class="stat-val" style="color: var(--accent-gold);">{counts['trigger']}</div>
                <div class="stat-sub">Catalog catalysts</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Customers</div>
                <div class="stat-val" style="color: var(--accent-purple);">{counts['customer']}</div>
                <div class="stat-sub">CRM profiles</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Active Threads</div>
                <div class="stat-val" style="color: #38bdf8;">{len(active_convs)}</div>
                <div class="stat-sub">{len(convs)} total persisted</div>
            </div>
        </div>

        <div class="main-layout">
            <!-- Left Panel: Live WhatsApp Chat Simulator -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <span>Live Multi-Turn State Machine Playground</span>
                    </div>
                    <div>
                        <span id="state-pill" class="state-pill state-INITIAL">INITIAL</span>
                    </div>
                </div>

                <div style="display: flex; gap: 10px; align-items: center; font-size: 13px;">
                    <label style="color: var(--text-secondary);">Target Merchant:</label>
                    <select id="merchant-select" style="background: #09121d; color: #ffffff; border: 1px solid rgba(255,255,255,0.12); padding: 5px 10px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                        {''.join(f'<option value="{m}">{m}</option>' for m in merchants[:15])}
                    </select>
                    <button onclick="startProactivePitch()" class="btn-small" style="margin-left: auto;">Dispatch Pitch (/v1/tick)</button>
                </div>

                <div class="chat-container">
                    <div class="chat-header">
                        <div class="chat-conv-meta">
                            Conversation ID: <span id="current-conv-id" style="color: var(--accent-cyan);">conv_live_demo</span>
                        </div>
                        <div class="chat-conv-meta">
                            Turns: <span id="turn-counter" style="color: #ffffff;">0</span> | Auto-Replies: <span id="autoreply-counter" style="color: var(--accent-orange);">0</span>
                        </div>
                    </div>

                    <div id="chat-messages" class="chat-body">
                        <div class="msg-bubble msg-vera">
                            <div><strong>Vera:</strong> Conversation initialized in <code>INITIAL</code> state. Click <em>"Dispatch Pitch"</em> or send a message below to test transitions.</div>
                            <div class="msg-meta">System</div>
                        </div>
                    </div>

                    <div class="chat-controls">
                        <input id="user-message-input" type="text" class="chat-input" placeholder="Type a reply as merchant..." onkeydown="if(event.key==='Enter') sendReply()">
                        <button onclick="sendReply()" class="btn-send">Send</button>
                    </div>
                </div>

                <div>
                    <div style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px;">1-Click Test Scenarios:</div>
                    <div class="chips-bar">
                        <span class="quick-chip" onclick="quickFill('Yes, please update our Google profile hours immediately')">Acceptance -> ACTION_PENDING</span>
                        <span class="quick-chip" onclick="quickFill('How much will this campaign cost?')">Question -> QUESTION</span>
                        <span class="quick-chip" onclick="quickFill('Sounds interesting, tell me more')">Interest -> INTERESTED</span>
                        <span class="quick-chip" onclick="quickFill('Thank you for contacting us! Our team will respond shortly.')">Auto-Reply (Turn 1 wait / Turn 2 loop break)</span>
                        <span class="quick-chip" onclick="quickFill('Stop messaging me! This is spam.')">Opt-Out -> STOPPED</span>
                        <span class="quick-chip" onclick="quickFill('hello?')">Spam Repetition (Send 3x -> STOPPED)</span>
                    </div>
                </div>
            </div>

            <!-- Right Panel: State Machine Architecture & Transition Map -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Finite State Architecture</div>
                    <span style="font-size: 12px; color: var(--text-dim);">9 Explicit States</span>
                </div>

                <div class="state-map">
                    <div id="node-INITIAL" class="state-node active-node">INITIAL</div>
                    <div id="node-PITCHED" class="state-node">PITCHED</div>
                    <div id="node-WAITING" class="state-node">WAITING</div>
                    <div id="node-INTERESTED" class="state-node">INTERESTED</div>
                    <div id="node-QUESTION" class="state-node">QUESTION</div>
                    <div id="node-ACTION_PENDING" class="state-node">ACTION_PENDING</div>
                    <div id="node-COMPLETED" class="state-node">COMPLETED</div>
                    <div id="node-REJECTED" class="state-node">REJECTED</div>
                    <div id="node-STOPPED" class="state-node">STOPPED</div>
                </div>

                <div style="background: #09121d; padding: 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); font-size: 12.5px;">
                    <div style="font-weight: 600; color: var(--accent-cyan); margin-bottom: 8px;">Last Transition Audit:</div>
                    <div id="audit-log" style="font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--text-secondary); line-height: 1.6;">
                        Awaiting interaction...
                    </div>
                </div>

                <div style="background: #09121d; padding: 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); font-size: 12px;">
                    <div style="font-weight: 600; color: var(--accent-gold); margin-bottom: 6px;">Level 6 Invariants Enforced:</div>
                    <ul style="padding-left: 18px; color: var(--text-secondary); line-height: 1.6;">
                        <li>Zero turn wastage on repeating auto-replies (exits on Turn 2).</li>
                        <li>Deterministic commitment to action (no redundant re-qualifying).</li>
                        <li>Terminal states strictly guarded against invalid transitions.</li>
                        <li>Thread-safe memory and disk persistence across calls.</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentConvId = "conv_live_" + Math.random().toString(36).substring(2, 7);
        let turnCounter = 0;
        let currentState = "INITIAL";
        document.getElementById("current-conv-id").innerText = currentConvId;

        function updateStateUI(stateName) {{
            currentState = stateName;
            const pill = document.getElementById("state-pill");
            pill.className = "state-pill state-" + stateName;
            pill.innerText = stateName;

            document.querySelectorAll(".state-node").forEach(node => {{
                node.classList.remove("active-node");
            }});
            const activeNode = document.getElementById("node-" + stateName);
            if (activeNode) activeNode.classList.add("active-node");
        }}

        function quickFill(text) {{
            const input = document.getElementById("user-message-input");
            input.value = text;
            input.focus();
        }}

        async function startProactivePitch() {{
            const merchantId = document.getElementById("merchant-select").value;
            const res = await fetch("/v1/tick", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    now: new Date().toISOString(),
                    available_triggers: ["trg_001_research_digest_dentists"]
                }})
            }});
            const data = await res.json();
            const action = (data.actions && data.actions[0]) ? data.actions[0] : null;
            if (action) {{
                currentConvId = action.conversation_id;
                document.getElementById("current-conv-id").innerText = currentConvId;
                turnCounter = 1;
                document.getElementById("turn-counter").innerText = turnCounter;
                updateStateUI("PITCHED");

                appendMessage("Vera", action.body, "action: send | cta: " + action.cta, "msg-vera");
                document.getElementById("audit-log").innerHTML = `<strong>Action:</strong> SEND<br><strong>Next State:</strong> PITCHED<br><strong>Rationale:</strong> ${{action.rationale}}`;
            }}
        }}

        async function sendReply() {{
            const input = document.getElementById("user-message-input");
            const text = input.value.trim();
            if (!text) return;
            input.value = "";

            turnCounter++;
            document.getElementById("turn-counter").innerText = turnCounter;
            appendMessage("Merchant", text, "Turn " + turnCounter, "msg-merchant");

            const merchantId = document.getElementById("merchant-select").value;
            const res = await fetch("/v1/reply", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    conversation_id: currentConvId,
                    merchant_id: merchantId,
                    from_role: "merchant",
                    message: text,
                    received_at: new Date().toISOString(),
                    turn_number: turnCounter
                }})
            }});
            const data = await res.json();

            // Refresh conversation state
            const convRes = await fetch("/v1/conversation/" + currentConvId);
            if (convRes.ok) {{
                const convData = await convRes.json();
                updateStateUI(convData.current_state);
                document.getElementById("autoreply-counter").innerText = convData.auto_reply_count;
            }}

            if (data.action === "send") {{
                appendMessage("Vera", data.body, "action: send | cta: " + (data.cta || "none"), "msg-vera");
            }} else if (data.action === "wait") {{
                appendMessage("Vera", `[WAITING: Paused dialogue for ${{data.wait_seconds || 900}}s]`, "action: wait", "msg-vera");
            }} else if (data.action === "end") {{
                appendMessage("Vera", `[TERMINATED: Conversation ended]`, "action: end", "msg-vera");
            }}

            document.getElementById("audit-log").innerHTML = `
                <strong>Action:</strong> ${{data.action.toUpperCase()}}<br>
                <strong>Current State:</strong> ${{currentState}}<br>
                <strong>Rationale:</strong> ${{data.rationale}}
            `;
        }}

        function appendMessage(sender, text, meta, cls) {{
            const box = document.getElementById("chat-messages");
            const div = document.createElement("div");
            div.className = "msg-bubble " + cls;
            div.innerHTML = `<div><strong>${{sender}}:</strong> ${{text}}</div><div class="msg-meta">${{meta}}</div>`;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=False)

