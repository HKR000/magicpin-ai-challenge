"""Vera Bot - magicpin Merchant AI Assistant HTTP Service & Inspector Dashboard."""

from __future__ import annotations
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

@app.get("/v1/healthz")
async def healthz():
    """Liveness probe returning uptime and loaded context counts."""
    counts = engine.get_counts()
    uptime = int(time.time() - START_TIME)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "contexts_loaded": counts,
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
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str


@app.post("/v1/context")
async def push_context(req: ContextPushRequest):
    """Receive atomic context pushes with version conflict handling."""
    outcome = engine.ingest(
        scope=req.scope,
        context_id=req.context_id,
        version=req.version,
        payload=req.payload,
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
    now: str
    available_triggers: List[str] = Field(default_factory=list)


@app.post("/v1/tick")
async def tick(req: TickRequest):
    """Periodic proactive simulation tick."""
    # Context & arbitration layer (Message generation plugged in Level 4/5)
    actions: List[Dict[str, Any]] = []

    for trg_id in req.available_triggers:
        trigger = engine.get_trigger(trg_id)
        if not trigger:
            continue

        merchant = engine.get_merchant(trigger.merchant_id)
        if not merchant:
            continue

        category = engine.get_category(merchant.category_slug)
        if not category:
            continue

        conv_id = f"conv_{trigger.merchant_id}_{trg_id}"
        conv = engine.create_or_get_conversation(
            conversation_id=conv_id,
            merchant_id=trigger.merchant_id,
            customer_id=trigger.customer_id,
            trigger_id=trg_id,
        )
        engine.transition_conversation(
            conversation_id=conv_id,
            user_intent=IntentType.UNKNOWN,
            is_proactive_send=True,
        )

        # Proactive action placeholder adhering to contract
        actions.append({
            "conversation_id": conv_id,
            "merchant_id": trigger.merchant_id,
            "customer_id": trigger.customer_id,
            "send_as": trigger.scope.value if trigger.scope.value in ["vera", "merchant_on_behalf"] else "vera",
            "trigger_id": trg_id,
            "template_name": f"vera_{trigger.kind}_v1",
            "template_params": [merchant.identity.name, merchant.identity.locality],
            "body": f"Hello {merchant.identity.name}, regarding {trigger.kind} in {merchant.identity.locality}.",
            "cta": "binary",
            "suppression_key": trigger.suppression_key,
            "rationale": f"Trigger {trigger.kind} (urgency {trigger.urgency}) activated for {merchant.identity.name}",
        })

    return {"actions": actions[:20]}


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


@app.post("/v1/reply")
async def reply(req: ReplyRequest):
    """Handle reactive replies in multi-turn conversation via state machine."""
    conv = engine.create_or_get_conversation(
        conversation_id=req.conversation_id,
        merchant_id=req.merchant_id or "unknown",
        customer_id=req.customer_id,
    )

    detected = intent_classifier.classify(req.message)
    if detected.intent_type == IntentType.AUTO_REPLY:
        engine.increment_auto_reply_count(req.conversation_id)

    trans = engine.transition_conversation(
        conversation_id=req.conversation_id,
        user_intent=detected.intent_type,
        message=req.message,
    )

    engine.add_turn(
        conversation_id=req.conversation_id,
        from_role=req.from_role,
        message=req.message,
        timestamp=req.received_at,
        detected_intent=detected.intent_type.value,
        action_taken=trans.action,
    )

    if trans.action == "end":
        return {
            "action": "end",
            "rationale": trans.rationale,
        }
    elif trans.action == "wait":
        return {
            "action": "wait",
            "wait_seconds": trans.wait_seconds or 900,
            "rationale": trans.rationale,
        }
    else:
        if trans.to_state == State.ACTION_PENDING:
            body = "Done! Switched to action mode. Here is what has been initiated for you immediately."
            cta = "binary"
        elif trans.to_state == State.QUESTION:
            body = f"Understood your question regarding '{req.message[:50]}'. Here are the relevant details from your profile."
            cta = "binary"
        elif trans.to_state == State.INTERESTED:
            body = "Great to hear your interest! Here is the relevant breakdown for your business."
            cta = "binary"
        elif trans.to_state == State.COMPLETED:
            body = "Action verified and completed successfully. Let me know if you need anything else!"
            cta = "none"
        else:
            body = f"Acknowledged: '{req.message[:50]}'. Next step ready."
            cta = "binary"

        return {
            "action": "send",
            "body": body,
            "cta": cta,
            "rationale": trans.rationale,
        }


# =============================================================================
# VISUAL DASHBOARD & STATE INSPECTOR
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Interactive visual dashboard displaying real-time system state and context."""
    counts = engine.get_counts()
    categories = list(engine._categories.keys())
    merchants = list(engine._merchants.keys())
    triggers = list(engine._triggers.keys())
    customers = list(engine._customers.keys())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vera AI Engine — Live System Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0f18;
            --bg-surface: #121a29;
            --bg-card: rgba(22, 33, 51, 0.75);
            --border-color: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(0, 230, 153, 0.35);
            --accent-green: #00e699;
            --accent-cyan: #00b4d8;
            --accent-gold: #ffbe0b;
            --accent-purple: #9d4edd;
            --text-primary: #f0f4f8;
            --text-secondary: #94a3b8;
            --text-dim: #64748b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at 10% 20%, #0d1b2a 0%, var(--bg-primary) 90%);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1280px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .logo-group {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .badge-live {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 230, 153, 0.12);
            color: var(--accent-green);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid rgba(0, 230, 153, 0.3);
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 1.8s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.7; }}
            50% {{ transform: scale(1.3); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.7; }}
        }}
        h1 {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #ffffff 40%, var(--accent-cyan) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }}
        .stat-card:hover {{
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
        }}
        .stat-label {{
            font-size: 13px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .stat-val {{
            font-size: 38px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #ffffff;
        }}
        .stat-sub {{
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 6px;
        }}
        .main-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }}
        @media(max-width: 900px) {{
            .main-grid {{ grid-template-columns: 1fr; }}
        }}
        .panel {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }}
        .panel-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }}
        .endpoint-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .endpoint-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 18px;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }}
        .method {{
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
        }}
        .method-get {{ background: rgba(0, 180, 216, 0.15); color: var(--accent-cyan); }}
        .method-post {{ background: rgba(0, 230, 153, 0.15); color: var(--accent-green); }}
        .pill-tag {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-secondary);
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 12px;
            margin: 3px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .code-box {{
            background: #060a10;
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 16px;
            color: var(--accent-cyan);
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            overflow-x: auto;
            margin-top: 14px;
        }}
        .btn {{
            background: linear-gradient(135deg, var(--accent-green), #00b4d8);
            border: none;
            color: #05101a;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.2s;
        }}
        .btn:hover {{
            filter: brightness(1.15);
            transform: translateY(-1px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-group">
                <h1>Vera Engine Dashboard</h1>
                <span class="badge-live"><span class="pulse-dot"></span>ENGINE ONLINE</span>
            </div>
            <div>
                <a href="/v1/healthz" target="_blank" class="btn">View /v1/healthz</a>
            </div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Categories Loaded</div>
                <div class="stat-val" style="color: var(--accent-cyan);">{counts['category']}</div>
                <div class="stat-sub">Vertical domains active</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Merchants Loaded</div>
                <div class="stat-val" style="color: var(--accent-green);">{counts['merchant']}</div>
                <div class="stat-sub">Profiles in state store</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Triggers Indexed</div>
                <div class="stat-val" style="color: var(--accent-gold);">{counts['trigger']}</div>
                <div class="stat-sub">Outreach catalysts</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Customers Loaded</div>
                <div class="stat-val" style="color: var(--accent-purple);">{counts['customer']}</div>
                <div class="stat-sub">CRM client records</div>
            </div>
        </div>

        <div class="main-grid">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Active Context Explorer</div>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 12px; font-size: 14px;">
                    Entities ingested into Vera's thread-safe memory store with full fact provenance:
                </p>

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 13px; font-weight: 600; color: var(--accent-cyan); margin-bottom: 6px;">Categories:</div>
                    <div>
                        {''.join(f'<span class="pill-tag">{c}</span>' for c in categories)}
                    </div>
                </div>

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 13px; font-weight: 600; color: var(--accent-green); margin-bottom: 6px;">Sample Merchants (first 5):</div>
                    <div>
                        {''.join(f'<span class="pill-tag">{m}</span>' for m in merchants[:5])}
                    </div>
                </div>

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 13px; font-weight: 600; color: var(--accent-gold); margin-bottom: 6px;">Sample Triggers (first 5):</div>
                    <div>
                        {''.join(f'<span class="pill-tag">{t}</span>' for t in triggers[:5])}
                    </div>
                </div>

                <div class="code-box">
// Run judge simulator against this live instance:
export BOT_URL=http://localhost:8080
python judge_simulator.py
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Exposed API Endpoints</div>
                </div>
                <div class="endpoint-list">
                    <div class="endpoint-item">
                        <span><span class="method method-get">GET</span> /v1/healthz</span>
                        <a href="/v1/healthz" target="_blank" style="color: var(--accent-cyan);">Test</a>
                    </div>
                    <div class="endpoint-item">
                        <span><span class="method method-get">GET</span> /v1/metadata</span>
                        <a href="/v1/metadata" target="_blank" style="color: var(--accent-cyan);">Test</a>
                    </div>
                    <div class="endpoint-item">
                        <span><span class="method method-post">POST</span> /v1/context</span>
                        <span style="color: var(--text-dim);">Ingest</span>
                    </div>
                    <div class="endpoint-item">
                        <span><span class="method method-post">POST</span> /v1/tick</span>
                        <span style="color: var(--text-dim);">Proactive</span>
                    </div>
                    <div class="endpoint-item">
                        <span><span class="method method-post">POST</span> /v1/reply</span>
                        <span style="color: var(--text-dim);">Reactive</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=False)
