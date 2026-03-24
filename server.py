"""
FastAPI server for Trump Trade Monitor.
Wraps trump_monitor.py and exposes REST + WebSocket API.
Serves the built React frontend from ./frontend/dist/.

AI priority: Gemini (GIMINI_API_KEY) → Anthropic (ANTHROPIC_API_KEY, optional) → keyword fallback
"""

import asyncio
import datetime
import json
import logging
import os
import re
import threading
from collections import deque
from pathlib import Path
from typing import Any

import requests as _requests
import trump_monitor
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#  WEB SOCKET BRIDGE  (thread → async)
# ═══════════════════════════════════════════════════════

# Stores active WebSocket connections
_ws_clients: list[WebSocket] = []
_ws_lock = threading.Lock()

# Asyncio event loop reference (set in lifespan)
_event_loop: asyncio.AbstractEventLoop | None = None

# In-memory store of the last 50 analyzed posts
analyzed_posts: deque[dict] = deque(maxlen=50)

# Scanner thread reference
_scanner_thread: threading.Thread | None = None


def emit_event(event: dict) -> None:
    """
    Called from the scanner thread to push a WebSocket event to all clients.
    Thread-safe: uses call_soon_threadsafe to schedule in the asyncio loop.
    """
    if _event_loop is None or _event_loop.is_closed():
        return
    event.setdefault("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
    _event_loop.call_soon_threadsafe(_event_loop.create_task, _broadcast(event))


async def _broadcast(event: dict) -> None:
    """Send a JSON event to every connected WebSocket client."""
    payload = json.dumps(event)
    dead: list[WebSocket] = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ═══════════════════════════════════════════════════════
#  GEMINI AI ANALYZER  (primary — replaces Claude)
# ═══════════════════════════════════════════════════════

_GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
]

# Shared prompt template (same JSON schema as the original Claude prompt)
_ANALYSIS_PROMPT_TEMPLATE = """You are a professional financial analyst specializing in political risk and market impact analysis.

Analyze this Trump Truth Social post for its potential market impact:

POST: "{content}"
POSTED AT: {published}

Respond ONLY with a JSON object (no markdown, no explanation, just raw JSON):

{{
  "impact_score": <0-100, where 0=no market impact, 100=extreme market-moving event>,
  "direction": "<BULLISH | BEARISH | NEUTRAL | MIXED>",
  "confidence": <0-100>,
  "affected_tickers": [<list of specific stock tickers directly mentioned or obviously implied>],
  "affected_sectors": [<list of sectors affected, e.g. "technology", "defense", "energy", "finance", "retail", "crypto">],
  "broad_market": <true if this affects the whole market, false if company-specific>,
  "crypto_impact": <true if this affects crypto markets>,
  "trade_action": "<BUY | SELL | HOLD | NONE>",
  "urgency": "<IMMEDIATE | WAIT_FOR_OPEN | LOW>",
  "reasoning": "<1-2 sentence explanation of the market impact>",
  "post_category": "<TARIFF | TRADE_WAR | COMPANY_MENTION | ECONOMY | POLITICAL | CRYPTO | PERSONAL | OTHER>",
  "key_entities": [<companies, countries, or people mentioned that have market relevance>]
}}

Scoring guidelines:
- 90-100: Massive policy announcement (tariff pause, trade deal, rate comment)
- 70-89: Clear market signal (company threat, sector policy, economic comment)
- 50-69: Moderate signal (indirect company mention, general economic mood)
- 30-49: Weak signal (political comment with possible indirect impact)
- 0-29: No market impact (personal comment, media attacks, personal news)"""


def _build_prompt(post: dict) -> str:
    return _ANALYSIS_PROMPT_TEMPLATE.format(
        content=post.get("content", "").replace('"', '\\"'),
        published=post.get("published", ""),
    )


def _parse_analysis_json(raw: str, post: dict, analyzed_by: str) -> dict:
    """Strip markdown fences and parse JSON. Returns None on failure."""
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    result = json.loads(cleaned)
    result["analyzed_by"] = analyzed_by
    result["post_id"] = post.get("id", "")
    result["post_content"] = post.get("content", "")[:200]
    return result


def analyze_with_gemini(post: dict) -> dict | None:
    """
    Analyze a post using Google Gemini (gemini-1.5-flash).
    Returns parsed analysis dict or None on failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GIMINI_API_KEY", "")
    if not api_key:
        try:
            cfg = json.loads(Path("config.json").read_text())
            api_key = cfg.get("gemini_api_key", "")
        except Exception:
            pass

    if not api_key:
        return None

    prompt = _build_prompt(post)
    for model in _GEMINI_MODELS:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            resp = _requests.post(
                endpoint,
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.1,
                        "maxOutputTokens": 600,
                    },
                },
                timeout=20,
            )
            if resp.status_code == 404:
                log.warning(f"Gemini model not found: {model} — trying next model")
                continue
            if resp.status_code == 429:
                log.warning(f"Gemini API throttled (429) for model {model} — immediate fallback to keyword analysis")
                return None
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _parse_analysis_json(raw_text, post, f"gemini:{model}")
        except json.JSONDecodeError as e:
            log.warning(f"Gemini returned invalid JSON for {model}: {e}")
            continue
        except Exception as e:
            log.error(f"Gemini API error with model {model}: {e}")
            # Fallback immediately if 429 in error
            if hasattr(e, "response") and getattr(e.response, "status_code", None) == 429:
                log.warning(f"Gemini API throttled (429) for model {model} — immediate fallback to keyword analysis")
                return None
            if "429" in str(e):
                log.warning(f"Gemini API throttled (429) for model {model} — immediate fallback to keyword analysis")
                return None
            continue

    return None


def _patched_analyze_post_with_claude(post: dict) -> dict:
    """
    AI dispatch: Gemini first → Anthropic fallback → keyword fallback.
    Monkey-patches trump_monitor.analyze_post_with_claude.
    """
    # 1. Try Gemini (primary)
    result = analyze_with_gemini(post)
    if result:
        return result

    # 2. Try original Anthropic (optional — only if key present)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        try:
            cfg = json.loads(Path("config.json").read_text())
            anthropic_key = cfg.get("anthropic_api_key", "")
        except Exception:
            pass

    if anthropic_key:
        try:
            return _original_analyze_post_with_claude(post)
        except Exception as e:
            log.warning(f"Anthropic fallback failed: {e}")

    # 3. Keyword fallback
    return trump_monitor.keyword_fallback_analysis(post)


# Store original before patching
_original_analyze_post_with_claude = trump_monitor.analyze_post_with_claude
trump_monitor.analyze_post_with_claude = _patched_analyze_post_with_claude


# ═══════════════════════════════════════════════════════
#  MONKEY-PATCH trump_monitor TO EMIT EVENTS
# ═══════════════════════════════════════════════════════

_original_process_new_post = trump_monitor.process_new_post
_original_close_position = trump_monitor._close_position
_original_partial_sell = trump_monitor._partial_sell


def _patched_process_new_post(post: dict) -> None:
    """Wraps process_new_post to capture the analysis result and emit WS events."""
    prev_posts = trump_monitor.state["posts_analyzed"]
    prev_trades = trump_monitor.state["trades_executed"]

    _original_process_new_post(post)

    # Build a best-effort post record from the state changes
    posts_delta = trump_monitor.state["posts_analyzed"] - prev_posts
    trades_delta = trump_monitor.state["trades_executed"] - prev_trades

    if posts_delta > 0:
        # Grab the most recently added trade record for analysis details
        analysis_record: dict[str, Any] = {}
        if trump_monitor.state["trades_today"]:
            last = trump_monitor.state["trades_today"][-1]
            analysis_record = last.get("analysis", {})

        post_record = {
            "id": post.get("id", ""),
            "content": post.get("content", ""),
            "published": post.get("published", ""),
            "url": post.get("url", ""),
            "score": analysis_record.get("impact_score", 0),
            "direction": analysis_record.get("direction", "NEUTRAL"),
            "category": analysis_record.get("post_category", "OTHER"),
            "tickers": analysis_record.get("affected_tickers", []),
            "reasoning": analysis_record.get("reasoning", ""),
            "trade_triggered": trades_delta > 0,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        if trades_delta > 0 and trump_monitor.state["trades_today"]:
            last_trade = trump_monitor.state["trades_today"][-1]
            post_record["trade_detail"] = {
                "side": last_trade.get("side", ""),
                "ticker": last_trade.get("ticker", ""),
                "shares": last_trade.get("shares", 0),
                "entry": last_trade.get("entry", 0),
            }

        analyzed_posts.appendleft(post_record)

        emit_event({"type": "POST_ANALYZED", "data": post_record})

        if trades_delta > 0:
            emit_event({"type": "TRADE_SIGNAL", "data": post_record.get("trade_detail", {})})


def _patched_close_position(ticker: str, price: float, shares: int, reason: str, pnl: float) -> None:
    _original_close_position(ticker, price, shares, reason, pnl)
    emit_event({
        "type": "POSITION_CLOSED",
        "data": {
            "ticker": ticker,
            "price": price,
            "shares": shares,
            "reason": reason,
            "pnl": pnl,
        },
    })


trump_monitor.process_new_post = _patched_process_new_post
trump_monitor._close_position = _patched_close_position


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════

def _load_config_to_env() -> None:
    """Load config.json keys into environment variables if not already set."""
    config_path = Path("config.json")
    if not config_path.exists():
        return
    try:
        cfg: dict = json.loads(config_path.read_text())
    except Exception:
        return

    env_map = {
        "alpaca_api_key": "ALPACA_API_KEY",
        "alpaca_api_secret": "ALPACA_API_SECRET",
        "gemini_api_key": "GIMINI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "TELEGRAM_CHAT_ID",
    }
    for cfg_key, env_key in env_map.items():
        val = cfg.get(cfg_key, "")
        if val and not os.environ.get(env_key):
            os.environ[env_key] = str(val)

    # Update trump_monitor CONFIG
    if cfg.get("trump_min_impact_score"):
        trump_monitor.CONFIG["min_impact_score"] = int(cfg["trump_min_impact_score"])
    if cfg.get("trump_min_alert_score"):
        trump_monitor.CONFIG["min_score_alert"] = int(cfg["trump_min_alert_score"])
    if cfg.get("poll_interval_sec"):
        trump_monitor.CONFIG["poll_interval_sec"] = int(cfg["poll_interval_sec"])


def _start_scanner() -> None:
    """Start the scanner loop in a daemon thread (idempotent)."""
    global _scanner_thread
    if _scanner_thread and _scanner_thread.is_alive():
        return
    trump_monitor.state["running"] = True
    trump_monitor.state["seen_posts"] = trump_monitor.load_seen_posts()
    _scanner_thread = threading.Thread(
        target=trump_monitor.scanner_loop,
        daemon=True,
        name="trump-scanner",
    )
    _scanner_thread.start()


async def _heartbeat_task() -> None:
    """Sends a STATUS_UPDATE event every 2 seconds to all WS clients."""
    while True:
        await asyncio.sleep(2)
        if _ws_clients:
            s = trump_monitor.state
            uptime = (datetime.datetime.now() - s["start_time"]).total_seconds()
            await _broadcast({
                "type": "STATUS_UPDATE",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "data": {
                    "running": s["running"],
                    "posts_analyzed": s["posts_analyzed"],
                    "trades_executed": s["trades_executed"],
                    "open_positions_count": len(s["open_positions"]),
                    "total_pnl": s["total_pnl"],
                    "alpaca_connected": s["alpaca"] is not None,
                    "uptime_seconds": uptime,
                    "last_post_time": s["last_post_time"].isoformat() if s["last_post_time"] else None,
                    "last_poll_time": s["last_poll_time"].isoformat() if s["last_poll_time"] else None,
                },
            })


# ═══════════════════════════════════════════════════════
#  APP LIFESPAN
# ═══════════════════════════════════════════════════════

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _event_loop
    _event_loop = asyncio.get_event_loop()

    # Load config and set env vars
    _load_config_to_env()

    # Connect Alpaca
    trump_monitor.connect_alpaca()

    # Start heartbeat
    asyncio.create_task(_heartbeat_task())

    # Auto-start scanner in CI_MODE
    if os.environ.get("CI_MODE", "").lower() == "true":
        _start_scanner()

    yield
    # Graceful stop
    trump_monitor.state["running"] = False


# ═══════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════

app = FastAPI(title="Trump Trade Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════
#  REST ENDPOINTS
# ═══════════════════════════════════════════════════════

@app.get("/api/status")
async def get_status():
    s = trump_monitor.state
    uptime = (datetime.datetime.now() - s["start_time"]).total_seconds()
    return {
        "running": s["running"],
        "posts_analyzed": s["posts_analyzed"],
        "trades_executed": s["trades_executed"],
        "open_positions_count": len(s["open_positions"]),
        "total_pnl": s["total_pnl"],
        "alpaca_connected": s["alpaca"] is not None,
        "uptime_seconds": uptime,
        "last_post_time": s["last_post_time"].isoformat() if s["last_post_time"] else None,
        "last_poll_time": s["last_poll_time"].isoformat() if s["last_poll_time"] else None,
    }


@app.get("/api/posts")
async def get_posts():
    return list(analyzed_posts)


@app.get("/api/trades")
async def get_trades():
    path = Path(trump_monitor.CONFIG["trades_file"])
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


@app.get("/api/positions")
async def get_positions():
    return trump_monitor.state["open_positions"]


@app.post("/api/start")
async def start_bot():
    _start_scanner()
    return {"ok": True, "message": "Scanner started"}


@app.post("/api/stop")
async def stop_bot():
    trump_monitor.state["running"] = False
    return {"ok": True, "message": "Scanner stopping"}


@app.post("/api/connect")
async def connect(body: dict):
    """Save credentials to config.json and reconnect Alpaca."""
    # Sanitise — only accept known keys, no arbitrary writes
    allowed = {
        "alpaca_api_key", "alpaca_api_secret",
        "gemini_api_key",
        "anthropic_api_key",
        "telegram_bot_token", "telegram_chat_id",
    }
    try:
        existing: dict = {}
        if Path("config.json").exists():
            existing = json.loads(Path("config.json").read_text())
    except Exception:
        existing = {}

    for key in allowed:
        if key in body and isinstance(body[key], str):
            existing[key] = body[key]

    Path("config.json").write_text(json.dumps(existing, indent=2))
    _load_config_to_env()
    trump_monitor.connect_alpaca()
    return {"ok": True}


@app.post("/api/config")
async def update_config(body: dict):
    """Update runtime CONFIG parameters."""
    if "min_impact_score" in body:
        val = int(body["min_impact_score"])
        if 0 <= val <= 100:
            trump_monitor.CONFIG["min_impact_score"] = val
    if "poll_interval_sec" in body:
        val = int(body["poll_interval_sec"])
        if val >= 5:
            trump_monitor.CONFIG["poll_interval_sec"] = val
    if "min_score_alert" in body:
        val = int(body["min_score_alert"])
        if 0 <= val <= 100:
            trump_monitor.CONFIG["min_score_alert"] = val
    if "max_open_positions" in body:
        val = int(body["max_open_positions"])
        if 1 <= val <= 10:
            trump_monitor.CONFIG["max_open_positions"] = val
    return {"ok": True, "config": trump_monitor.CONFIG}


# ═══════════════════════════════════════════════════════
#  WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    # Send immediate status snapshot on connect
    s = trump_monitor.state
    uptime = (datetime.datetime.now() - s["start_time"]).total_seconds()
    await websocket.send_text(json.dumps({
        "type": "HEARTBEAT",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "data": {
            "running": s["running"],
            "posts_analyzed": s["posts_analyzed"],
            "trades_executed": s["trades_executed"],
            "open_positions_count": len(s["open_positions"]),
            "total_pnl": s["total_pnl"],
            "alpaca_connected": s["alpaca"] is not None,
            "uptime_seconds": uptime,
        },
    }))
    try:
        while True:
            # Keep connection alive — client never sends, but we need to detect disconnection
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ═══════════════════════════════════════════════════════
#  STATIC FRONTEND (SPA)
# ═══════════════════════════════════════════════════════

_DIST = Path(__file__).parent / "frontend" / "dist"


@app.get("/")
async def serve_index():
    index = _DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "Frontend not built. Run: cd frontend && npm run build"})


# Mount static assets (JS, CSS, images) — must come AFTER /api and /ws routes
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback: serve index.html for all non-API routes."""
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        static_file = _DIST / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(str(static_file))
        return FileResponse(str(_DIST / "index.html"))


# ═══════════════════════════════════════════════════════
#  ENTRY POINT (direct execution)
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
