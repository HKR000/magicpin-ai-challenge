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

    trans = engine.transition_conversation(
        conversation_id=req.conversation_id,
        user_intent=detected.intent_type,
        message=req.message,
    )

    if detected.intent_type == IntentType.AUTO_REPLY:
        engine.increment_auto_reply_count(req.conversation_id)

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

