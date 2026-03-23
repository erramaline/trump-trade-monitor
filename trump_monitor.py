"""
╔══════════════════════════════════════════════════════════════════════╗
║   TRUMP TRUTH SOCIAL MONITOR — AI Trading Bot                       ║
║   Source: trumpstruth.org/feed (free RSS, no scraping)              ║
║   Analysis: Claude AI (claude-sonnet-4-20250514)                    ║
║   Execution: Alpaca Paper Trading                                    ║
║   Alerts: Telegram (optional)                                        ║
║                                                                      ║
║   PAPER TRADING ONLY — Educational purposes                         ║
╚══════════════════════════════════════════════════════════════════════╝

HOW IT WORKS:
  1. Polls Trump's Truth Social RSS feed every 60 seconds
  2. Detects new posts not seen before (deduplication)
  3. Claude AI analyzes each post for market impact (0–100 score)
  4. Detects affected tickers, sectors, direction (BUY/SELL/NEUTRAL)
  5. Executes paper trades on Alpaca if score >= threshold
  6. Sends Telegram alert with analysis summary
  7. Monitors open positions for exits (stop loss / target)
  8. Runs 24/7 (designed for GitHub Actions or Oracle Cloud)

SETUP:
  pip install requests alpaca-py anthropic feedparser python-telegram-bot

REQUIRED ENV VARS:
  ALPACA_API_KEY      — Alpaca paper trading key
  ALPACA_API_SECRET   — Alpaca paper trading secret
  ANTHROPIC_API_KEY   — Claude API key (for post analysis)

OPTIONAL ENV VARS:
  TELEGRAM_BOT_TOKEN  — Telegram bot token
  TELEGRAM_CHAT_ID    — Your Telegram chat ID
  MIN_IMPACT_SCORE    — Minimum score to trade (default: 70)
"""

import os
import json
import time
import datetime
import hashlib
import logging
import re
import threading
import requests
import feedparser
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

# ═══════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trump_bot.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════

CONFIG = {
    # ── RSS Sources (tried in order) ──────────────────
    "rss_feeds": [
        "https://trumpstruth.org/feed",
        "https://www.trumpstruth.org/feed",
        "https://truthsocial.com/@realDonaldTrump.rss",
    ],
    "poll_interval_sec":   60,       # Check for new posts every 60s
    "poll_market_hours":   30,       # Faster polling during market hours

    # ── Trade Thresholds ──────────────────────────────
    "min_impact_score":    70,       # Min score to execute a trade (0-100)
    "min_score_alert":     50,       # Min score to send Telegram alert
    "max_open_positions":  3,        # Max simultaneous Trump-signal positions
    "position_hold_min":   30,       # Hold position minimum 30 minutes
    "position_hold_max":   240,      # Exit after 240 minutes (4 hours) no matter what

    # ── Risk per trade ────────────────────────────────
    "risk_per_trade":      100.0,    # $ risk per trade (paper money)
    "stop_loss_pct":       0.05,     # 5% stop loss
    "target_1_pct":        0.08,     # 8% target (sell 50%)
    "target_2_pct":        0.15,     # 15% target (sell rest)
    "max_shares":          200,      # Max shares per trade

    # ── Score-based position sizing ───────────────────
    # Score 70-79 = 50% size, 80-89 = 75% size, 90+ = 100% size
    "score_size_tiers": {70: 0.5, 80: 0.75, 90: 1.0},

    # ── Files ─────────────────────────────────────────
    "seen_posts_file":     "trump_seen_posts.json",
    "trades_file":         "trump_trades.json",
    "state_file":          "trump_bot_state.json",

    # ── Market ETFs for broad signals ─────────────────
    # When Trump posts about broad economy/market/tariffs
    "broad_bull_ticker":   "SPY",    # Buy SPY on broad bullish posts
    "broad_bear_ticker":   "SH",     # Buy SH (inverse SPY) on bearish posts
    "crypto_ticker":       "COIN",   # Crypto signal proxy
}

# ═══════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════

state = {
    "running":         True,
    "alpaca":          None,
    "seen_posts":      set(),        # Post IDs already processed
    "open_positions":  {},           # {ticker: {entry, shares, stop, t1, t2, time, post_id}}
    "trades_today":    [],
    "total_pnl":       0.0,
    "posts_analyzed":  0,
    "trades_executed": 0,
    "last_post_time":  None,
    "last_poll_time":  None,
    "start_time":      datetime.datetime.now(),
}


# ═══════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════

def cprint(msg: str, color=Fore.WHITE, symbol="•"):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{Style.RESET_ALL} {color}{symbol} {msg}{Style.RESET_ALL}")

def load_seen_posts() -> set:
    path = CONFIG["seen_posts_file"]
    try:
        if Path(path).exists():
            data = json.loads(Path(path).read_text())
            return set(data.get("ids", []))
    except Exception:
        pass
    return set()

def save_seen_posts():
    try:
        Path(CONFIG["seen_posts_file"]).write_text(
            json.dumps({"ids": list(state["seen_posts"])[-500:]})  # Keep last 500
        )
    except Exception as e:
        log.warning(f"Could not save seen posts: {e}")

def save_trade_to_file(record: dict):
    path = CONFIG["trades_file"]
    try:
        existing = []
        if Path(path).exists():
            existing = json.loads(Path(path).read_text())
        existing.append(record)
        Path(path).write_text(json.dumps(existing, indent=2, default=str))
    except Exception as e:
        log.warning(f"Could not save trade: {e}")

def post_id(entry) -> str:
    """Generate stable ID for a post entry."""
    raw = entry.get("id") or entry.get("link") or entry.get("title") or ""
    return hashlib.md5(raw.encode()).hexdigest()

def is_market_hours() -> bool:
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # Weekend
        return False
    market_open  = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=16, minute=0,  second=0)
    return market_open <= now <= market_close

def get_position_size(base_shares: int, score: int) -> int:
    """Scale position size by impact score."""
    for threshold in sorted(CONFIG["score_size_tiers"].keys(), reverse=True):
        if score >= threshold:
            multiplier = CONFIG["score_size_tiers"][threshold]
            return max(1, int(base_shares * multiplier))
    return max(1, base_shares // 2)


# ═══════════════════════════════════════════════════════
#  ALPACA CONNECTION
# ═══════════════════════════════════════════════════════

def connect_alpaca() -> object:
    """Connect to Alpaca paper trading."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        log.error("alpaca-py not installed. Run: pip install alpaca-py")
        return None

    api_key    = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")

    # Load from config.json if env vars not set
    if not api_key or not api_secret:
        try:
            cfg = json.loads(Path("config.json").read_text())
            api_key    = cfg.get("alpaca_api_key", "")
            api_secret = cfg.get("alpaca_api_secret", "")
        except Exception:
            pass

    if not api_key or not api_secret:
        log.warning("Alpaca keys not found — running ALERT ONLY mode")
        return None

    try:
        client  = TradingClient(api_key, api_secret, paper=True)
        account = client.get_account()
        equity  = float(account.equity)
        cash    = float(account.cash)
        cprint(f"Alpaca connected — Equity: ${equity:,.2f} | Cash: ${cash:,.2f}", Fore.GREEN, "✅")
        state["alpaca"] = client
        return client
    except Exception as e:
        log.error(f"Alpaca connection failed: {e}")
        return None


# ═══════════════════════════════════════════════════════
#  RSS FEED POLLING
# ═══════════════════════════════════════════════════════

def fetch_latest_posts(max_posts: int = 10) -> list:
    """
    Fetch latest Trump posts from RSS feeds.
    Tries multiple sources until one works.
    Returns list of dicts: {id, title, content, url, published}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    for feed_url in CONFIG["rss_feeds"]:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            feed = feedparser.parse(resp.content)
            if not feed.entries:
                continue

            posts = []
            for entry in feed.entries[:max_posts]:
                # Clean HTML from content
                content = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
                content = re.sub(r"<[^>]+>", " ", content).strip()
                content = re.sub(r"\s+", " ", content)

                posts.append({
                    "id":        post_id(entry),
                    "title":     entry.get("title", ""),
                    "content":   content,
                    "url":       entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "raw":       entry,
                })

            cprint(f"Fetched {len(posts)} posts from {feed_url}", Fore.CYAN, "📡")
            return posts

        except Exception as e:
            log.debug(f"Feed {feed_url} failed: {e}")
            continue

    log.warning("All RSS feeds failed")
    return []


# ═══════════════════════════════════════════════════════
#  CLAUDE AI ANALYSIS
# ═══════════════════════════════════════════════════════

def analyze_post_with_claude(post: dict) -> dict:
    """
    Send Trump post to Claude for market impact analysis.
    Returns structured trading signal.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            cfg = json.loads(Path("config.json").read_text())
            api_key = cfg.get("anthropic_api_key", "")
        except Exception:
            pass

    if not api_key:
        log.warning("No ANTHROPIC_API_KEY — using keyword fallback analysis")
        return keyword_fallback_analysis(post)

    prompt = f"""You are a professional financial analyst specializing in political risk and market impact analysis.

Analyze this Trump Truth Social post for its potential market impact:

POST: "{post['content']}"
POSTED AT: {post['published']}

Respond ONLY with a JSON object (no markdown, no explanation, just raw JSON):

{{
  "impact_score": <0-100, where 0=no market impact, 100=extreme market-moving event>,
  "direction": "<BULLISH | BEARISH | NEUTRAL | MIXED>",
  "confidence": <0-100, how confident are you in this analysis>,
  "affected_tickers": [<list of specific stock tickers directly mentioned or obviously implied, e.g. ["AAPL", "TSLA"]>],
  "affected_sectors": [<list of sectors affected, e.g. ["technology", "defense", "energy", "finance", "retail", "crypto"]>],
  "broad_market": <true if this affects the whole market (tariffs, Fed, economy), false if company-specific>,
  "crypto_impact": <true if this affects crypto markets>,
  "trade_action": "<BUY | SELL | HOLD | NONE>",
  "urgency": "<IMMEDIATE | WAIT_FOR_OPEN | LOW>",
  "reasoning": "<1-2 sentence explanation of the market impact>",
  "post_category": "<TARIFF | TRADE_WAR | COMPANY_MENTION | ECONOMY | POLITICAL | CRYPTO | PERSONAL | OTHER>",
  "key_entities": [<companies, countries, or people mentioned that have market relevance>]
}}

Scoring guidelines:
- 90-100: Massive policy announcement (tariff pause, trade deal, rate comment) — April 9 "GREAT TIME TO BUY" was 95
- 70-89: Clear market signal (company threat, sector policy, economic comment)
- 50-69: Moderate signal (indirect company mention, general economic mood)
- 30-49: Weak signal (political comment with possible indirect impact)
- 0-29: No market impact (personal comment, media attacks, personal news)"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_text = data["content"][0]["text"].strip()
        # Strip any markdown if present
        raw_text = re.sub(r"```json\s*|\s*```", "", raw_text).strip()

        analysis = json.loads(raw_text)
        analysis["analyzed_by"] = "claude"
        analysis["post_id"]     = post["id"]
        analysis["post_content"] = post["content"][:200]
        return analysis

    except json.JSONDecodeError as e:
        log.warning(f"Claude returned invalid JSON: {e} — using fallback")
        return keyword_fallback_analysis(post)
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return keyword_fallback_analysis(post)


def keyword_fallback_analysis(post: dict) -> dict:
    """
    Keyword-based fallback when Claude API is unavailable.
    Catches the most obvious high-impact signals.
    """
    content = post["content"].upper()

    # High-impact keywords
    BULL_KEYWORDS = [
        "GREAT TIME TO BUY", "DEAL REACHED", "TRADE DEAL", "TARIFF PAUSE",
        "TARIFF REDUCTION", "FREE TRADE", "ECONOMY GREAT", "STOCK MARKET",
        "CUT TAXES", "DEREGULATION", "REDUCE RATES", "RATE CUT",
    ]
    BEAR_KEYWORDS = [
        "TARIFF", "SANCTION", "BAN", "INVESTIGATE", "UNFAIR TRADE",
        "EMERGENCY", "CRISIS", "COLLAPSE", "DISASTER",
    ]
    CRYPTO_KEYWORDS = ["BITCOIN", "CRYPTO", "BTC", "ETHEREUM", "BLOCKCHAIN"]
    COMPANY_PATTERN = r'\b[A-Z]{2,5}\b'

    score = 0
    direction = "NEUTRAL"
    trade_action = "NONE"
    affected_tickers = []
    post_category = "OTHER"

    bull_hits = [kw for kw in BULL_KEYWORDS if kw in content]
    bear_hits = [kw for kw in BEAR_KEYWORDS if kw in content]
    crypto_hit = any(kw in content for kw in CRYPTO_KEYWORDS)

    if bull_hits:
        score = 75
        direction = "BULLISH"
        trade_action = "BUY"
        post_category = "ECONOMY"
    elif bear_hits:
        score = 65
        direction = "BEARISH"
        trade_action = "SELL"
        post_category = "TARIFF" if "TARIFF" in content else "TRADE_WAR"
    elif crypto_hit:
        score = 60
        direction = "BULLISH"
        trade_action = "BUY"
        post_category = "CRYPTO"
        affected_tickers = ["COIN", "MSTR"]

    # Try to find tickers mentioned
    words = re.findall(r'\b[A-Z]{2,5}\b', post["content"])
    # Filter common words
    ignore = {"I", "A", "THE", "FOR", "AND", "OR", "BUT", "IN", "ON", "AT",
              "TO", "OF", "IS", "IT", "BE", "AS", "BY", "WE", "MY", "SO",
              "DO", "UP", "AM", "AN", "NO", "US", "HE", "SHE", "HAS", "HAD"}
    potential_tickers = [w for w in words if w not in ignore and 2 <= len(w) <= 5]

    return {
        "impact_score":      score,
        "direction":         direction,
        "confidence":        40,
        "affected_tickers":  affected_tickers,
        "affected_sectors":  [],
        "broad_market":      len(affected_tickers) == 0 and score > 0,
        "crypto_impact":     crypto_hit,
        "trade_action":      trade_action,
        "urgency":           "WAIT_FOR_OPEN" if score >= 70 else "LOW",
        "reasoning":         f"Keyword match: {bull_hits or bear_hits or ['no strong signal']}",
        "post_category":     post_category,
        "key_entities":      potential_tickers[:5],
        "analyzed_by":       "keyword_fallback",
        "post_id":           post["id"],
        "post_content":      post["content"][:200],
    }


# ═══════════════════════════════════════════════════════
#  TICKER RESOLUTION
# ═══════════════════════════════════════════════════════

# Maps sectors/entities to tradeable ETFs on Alpaca paper
SECTOR_TO_ETF = {
    "technology":    "QQQ",
    "defense":       "ITA",
    "energy":        "XLE",
    "oil":           "XLE",
    "finance":       "XLF",
    "banking":       "XLF",
    "retail":        "XRT",
    "healthcare":    "XLV",
    "steel":         "SLX",
    "auto":          "CARZ",
    "china":         "FXI",
    "crypto":        "COIN",
    "bitcoin":       "MSTR",
    "gold":          "GLD",
    "agriculture":   "MOO",
    "airlines":      "JETS",
}

# Known company → ticker (common Trump mentions)
COMPANY_TO_TICKER = {
    "APPLE":         "AAPL",
    "AMAZON":        "AMZN",
    "GOOGLE":        "GOOGL",
    "TESLA":         "TSLA",
    "ELON":          "TSLA",
    "MICROSOFT":     "MSFT",
    "META":          "META",
    "FACEBOOK":      "META",
    "BOEING":        "BA",
    "LOCKHEED":      "LMT",
    "WALMART":       "WMT",
    "FORD":          "F",
    "GM":            "GM",
    "GOLDMAN":       "GS",
    "JPMORGAN":      "JPM",
    "HARLEY":        "HOG",
    "DISNEY":        "DIS",
    "TWITTER":       "TWTR",
    "TIKTOK":        "SNAP",  # Proxy
    "TRUTH SOCIAL":  "DJT",
    "TMTG":          "DJT",
}

def resolve_tickers(analysis: dict, post_content: str) -> list[str]:
    """
    Resolve the best tradeable tickers from analysis.
    Priority: explicit tickers > company name → ticker > sector → ETF > broad ETF
    """
    tickers = list(analysis.get("affected_tickers", []))

    # Check post content for company names
    content_upper = post_content.upper()
    for company, ticker in COMPANY_TO_TICKER.items():
        if company in content_upper and ticker not in tickers:
            tickers.append(ticker)

    # Map sectors to ETFs
    for sector in analysis.get("affected_sectors", []):
        sector_lower = sector.lower()
        for key, etf in SECTOR_TO_ETF.items():
            if key in sector_lower and etf not in tickers:
                tickers.append(etf)

    # Broad market fallback
    if not tickers:
        if analysis.get("broad_market"):
            if analysis["direction"] == "BULLISH":
                tickers = [CONFIG["broad_bull_ticker"]]
            elif analysis["direction"] == "BEARISH":
                tickers = [CONFIG["broad_bear_ticker"]]

    if analysis.get("crypto_impact") and "COIN" not in tickers:
        tickers.insert(0, "COIN")

    # Deduplicate, keep max 3
    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique[:3]


# ═══════════════════════════════════════════════════════
#  TRADE EXECUTION
# ═══════════════════════════════════════════════════════

def execute_signal(analysis: dict, tickers: list[str], post: dict):
    """
    Execute trades based on Claude's analysis.
    """
    score     = analysis.get("impact_score", 0)
    direction = analysis.get("direction", "NEUTRAL")
    action    = analysis.get("trade_action", "NONE")

    if score < CONFIG["min_impact_score"]:
        cprint(f"Score {score} below threshold {CONFIG['min_impact_score']} — no trade", Fore.YELLOW, "○")
        return

    if action == "NONE" or direction == "NEUTRAL":
        cprint("No actionable trade signal", Fore.YELLOW, "○")
        return

    if not is_market_hours() and analysis.get("urgency") != "IMMEDIATE":
        cprint("Market closed — trade queued for open", Fore.YELLOW, "⏳")
        return

    if len(state["open_positions"]) >= CONFIG["max_open_positions"]:
        cprint(f"Max positions ({CONFIG['max_open_positions']}) reached", Fore.YELLOW, "⚠")
        return

    for ticker in tickers:
        if ticker in state["open_positions"]:
            cprint(f"Already in {ticker} — skipping", Fore.YELLOW, "⚠")
            continue

        _place_trade(ticker, action, score, analysis, post)


def _place_trade(ticker: str, action: str, score: int,
                 analysis: dict, post: dict):
    """Place a single paper trade on Alpaca."""
    import yfinance as yf

    # Get current price
    try:
        info  = yf.Ticker(ticker).info
        price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
        if not price or price <= 0:
            log.warning(f"Could not get price for {ticker}")
            return
    except Exception as e:
        log.warning(f"Price fetch failed for {ticker}: {e}")
        return

    # Position sizing
    stop_dist  = price * CONFIG["stop_loss_pct"]
    base_shares = max(1, int(CONFIG["risk_per_trade"] / stop_dist))
    base_shares = min(base_shares, CONFIG["max_shares"])
    shares      = get_position_size(base_shares, score)

    stop_price = round(price * (1 - CONFIG["stop_loss_pct"]), 2)
    target_1   = round(price * (1 + CONFIG["target_1_pct"]), 2)
    target_2   = round(price * (1 + CONFIG["target_2_pct"]), 2)

    side_str = "BUY" if action in ("BUY", "BULLISH") else "SELL"

    cprint(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Fore.GREEN)
    cprint(f"🚀 TRUMP SIGNAL TRADE: {side_str} {shares} {ticker} @ ${price:.2f}", Fore.GREEN, "▲")
    cprint(f"   Score: {score}/100 | {analysis['direction']} | {analysis['post_category']}", Fore.GREEN)
    cprint(f"   Stop: ${stop_price} | T1: ${target_1} | T2: ${target_2}", Fore.GREEN)
    cprint(f"   Reason: {analysis.get('reasoning', '')[:80]}", Fore.CYAN)
    cprint(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Fore.GREEN)

    order_placed = False
    order_id     = None

    if state["alpaca"]:
        try:
            from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL

            buy_req = MarketOrderRequest(
                symbol=ticker,
                qty=shares,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            order = state["alpaca"].submit_order(buy_req)
            order_id = str(order.id)
            cprint(f"✅ Order submitted: {order_id}", Fore.GREEN, "✓")

            # Place stop loss
            time.sleep(1)
            stop_side = OrderSide.SELL if side_str == "BUY" else OrderSide.BUY
            stop_req = StopOrderRequest(
                symbol=ticker,
                qty=shares,
                side=stop_side,
                time_in_force=TimeInForce.DAY,
                stop_price=stop_price,
            )
            state["alpaca"].submit_order(stop_req)
            cprint(f"✅ Stop loss placed @ ${stop_price}", Fore.GREEN, "✓")
            order_placed = True

        except Exception as e:
            log.error(f"Alpaca order error: {e}")
    else:
        cprint("ALERT ONLY — no Alpaca connection", Fore.YELLOW, "⚠")

    # Track position
    position = {
        "ticker":     ticker,
        "side":       side_str,
        "entry":      price,
        "shares":     shares,
        "stop":       stop_price,
        "target_1":   target_1,
        "target_2":   target_2,
        "t1_filled":  False,
        "time":       datetime.datetime.now().isoformat(),
        "post_id":    post["id"],
        "score":      score,
        "order_id":   order_id,
        "placed":     order_placed,
    }
    state["open_positions"][ticker] = position
    state["trades_executed"] += 1

    record = {
        **position,
        "action":    "OPEN",
        "post":      post["content"][:200],
        "analysis":  analysis,
    }
    state["trades_today"].append(record)
    save_trade_to_file(record)


# ═══════════════════════════════════════════════════════
#  POSITION MONITORING
# ═══════════════════════════════════════════════════════

def monitor_positions():
    """Check open positions for stop loss / target hits / time exit."""
    if not state["open_positions"]:
        return

    import yfinance as yf

    for ticker, pos in list(state["open_positions"].items()):
        try:
            info  = yf.Ticker(ticker).info
            price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
            if not price:
                continue

            entry  = pos["entry"]
            stop   = pos["stop"]
            t1     = pos["target_1"]
            t2     = pos["target_2"]
            shares = pos["shares"]
            opened = datetime.datetime.fromisoformat(pos["time"])
            age_min = (datetime.datetime.now() - opened).total_seconds() / 60

            pnl = (price - entry) * shares if pos["side"] == "BUY" else (entry - price) * shares

            # ── STOP HIT ──
            if pos["side"] == "BUY" and price <= stop:
                cprint(f"🛑 STOP HIT {ticker} @ ${price:.2f} | P&L: ${pnl:.2f}", Fore.RED, "✗")
                _close_position(ticker, price, shares, "STOP_LOSS", pnl)

            elif pos["side"] == "SELL" and price >= stop:
                cprint(f"🛑 STOP HIT {ticker} @ ${price:.2f} | P&L: ${pnl:.2f}", Fore.RED, "✗")
                _close_position(ticker, price, shares, "STOP_LOSS", pnl)

            # ── TARGET 1 ──
            elif pos["side"] == "BUY" and price >= t1 and not pos["t1_filled"]:
                half   = shares // 2
                profit = (price - entry) * half
                cprint(f"🎯 TARGET 1 {ticker} @ ${price:.2f} | Profit: ${profit:.2f}", Fore.GREEN, "✓")
                state["open_positions"][ticker]["t1_filled"] = True
                state["open_positions"][ticker]["shares"]    = shares - half
                state["total_pnl"] += profit
                _partial_sell(ticker, price, half, "TARGET_1")

            # ── TARGET 2 ──
            elif pos["side"] == "BUY" and price >= t2 and pos["t1_filled"]:
                remaining = pos["shares"]
                profit    = (price - entry) * remaining
                cprint(f"🎯 TARGET 2 {ticker} @ ${price:.2f} | Profit: ${profit:.2f}", Fore.GREEN, "✓")
                _close_position(ticker, price, remaining, "TARGET_2", profit)

            # ── TIME EXIT ──
            elif age_min >= CONFIG["position_hold_max"]:
                cprint(f"⏱ TIME EXIT {ticker} @ ${price:.2f} | Age: {age_min:.0f}min | P&L: ${pnl:.2f}", Fore.YELLOW, "⏳")
                _close_position(ticker, price, pos["shares"], "TIME_EXIT", pnl)

        except Exception as e:
            log.error(f"Position monitor error for {ticker}: {e}")


def _close_position(ticker: str, price: float, shares: int, reason: str, pnl: float):
    """Close a position — market order + state cleanup."""
    if state["alpaca"]:
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            pos  = state["open_positions"].get(ticker, {})
            side = OrderSide.SELL if pos.get("side") == "BUY" else OrderSide.BUY
            req  = MarketOrderRequest(symbol=ticker, qty=shares, side=side,
                                      time_in_force=TimeInForce.DAY)
            state["alpaca"].submit_order(req)
        except Exception as e:
            log.error(f"Close order error: {e}")

    state["total_pnl"] += pnl
    save_trade_to_file({
        "action": "CLOSE", "ticker": ticker, "price": price,
        "shares": shares, "reason": reason, "pnl": pnl,
        "time": datetime.datetime.now().isoformat(),
        "total_pnl": state["total_pnl"],
    })
    del state["open_positions"][ticker]


def _partial_sell(ticker: str, price: float, shares: int, reason: str):
    """Sell partial position."""
    if state["alpaca"]:
        try:
            from alpaca.trading.requests import LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            req = LimitOrderRequest(
                symbol=ticker, qty=shares, side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(price * 0.998, 2),
            )
            state["alpaca"].submit_order(req)
        except Exception as e:
            log.error(f"Partial sell error: {e}")


# ═══════════════════════════════════════════════════════
#  TELEGRAM ALERTS
# ═══════════════════════════════════════════════════════

def send_telegram(message: str):
    """Send alert to Telegram (optional)."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }, timeout=10)
        if not resp.ok:
            log.debug(f"Telegram error: {resp.text}")
    except Exception as e:
        log.debug(f"Telegram failed: {e}")


def format_telegram_alert(post: dict, analysis: dict, tickers: list) -> str:
    """Format a clean Telegram message."""
    score     = analysis.get("impact_score", 0)
    direction = analysis.get("direction", "?")
    category  = analysis.get("post_category", "?")
    reasoning = analysis.get("reasoning", "")
    urgency   = analysis.get("urgency", "LOW")

    score_emoji = "🔴" if score >= 90 else "🟠" if score >= 70 else "🟡" if score >= 50 else "⚪"
    dir_emoji   = "📈" if direction == "BULLISH" else "📉" if direction == "BEARISH" else "➡️"

    tickers_str = " ".join([f"${t}" for t in tickers]) if tickers else "No specific tickers"

    return (
        f"🇺🇸 <b>TRUMP POST DETECTED</b>\n\n"
        f"{score_emoji} <b>Impact Score: {score}/100</b>\n"
        f"{dir_emoji} Direction: <b>{direction}</b>\n"
        f"📂 Category: {category}\n"
        f"⚡ Urgency: {urgency}\n\n"
        f"💬 <i>\"{post['content'][:280]}\"</i>\n\n"
        f"🎯 <b>Tickers: {tickers_str}</b>\n"
        f"🧠 AI Analysis: {reasoning}\n\n"
        f"🔗 {post.get('url', '')}"
    )


# ═══════════════════════════════════════════════════════
#  MAIN PROCESSING LOOP
# ═══════════════════════════════════════════════════════

def process_new_post(post: dict):
    """Full pipeline for a single new post."""
    cprint(f"New post: \"{post['content'][:80]}...\"", Fore.YELLOW, "📢")

    # Analyze with Claude
    analysis = analyze_post_with_claude(post)
    state["posts_analyzed"] += 1

    score     = analysis.get("impact_score", 0)
    direction = analysis.get("direction", "NEUTRAL")
    tickers   = resolve_tickers(analysis, post["content"])

    cprint(
        f"Analysis: score={score}/100 | {direction} | "
        f"tickers={tickers} | '{analysis.get('post_category', '?')}' | "
        f"by={analysis.get('analyzed_by', '?')}",
        Fore.CYAN if score >= 70 else Fore.WHITE,
        "🧠"
    )

    # Always log analysis
    log.info(f"POST ANALYZED | score={score} | direction={direction} | "
             f"category={analysis.get('post_category')} | "
             f"tickers={tickers} | "
             f"reasoning={analysis.get('reasoning', '')[:100]}")

    # Telegram alert if above threshold
    if score >= CONFIG["min_score_alert"]:
        msg = format_telegram_alert(post, analysis, tickers)
        send_telegram(msg)

    # Execute trade if above trading threshold
    if score >= CONFIG["min_impact_score"] and tickers:
        execute_signal(analysis, tickers, post)
    elif score >= CONFIG["min_impact_score"] and not tickers:
        cprint("High score but no tradeable tickers identified", Fore.YELLOW, "⚠")

    state["last_post_time"] = datetime.datetime.now()


def print_status():
    """Print current bot status."""
    runtime = datetime.datetime.now() - state["start_time"]
    hours   = int(runtime.total_seconds() / 3600)
    minutes = int((runtime.total_seconds() % 3600) / 60)

    pnl_color = Fore.GREEN if state["total_pnl"] >= 0 else Fore.RED
    pnl_sign  = "+" if state["total_pnl"] >= 0 else ""

    cprint(f"{'─'*55}", Fore.CYAN)
    cprint(f"TRUMP BOT STATUS | Runtime: {hours}h {minutes}m", Fore.CYAN, "📊")
    cprint(f"Posts analyzed:  {state['posts_analyzed']}", Fore.WHITE)
    cprint(f"Trades executed: {state['trades_executed']}", Fore.WHITE)
    cprint(f"Open positions:  {len(state['open_positions'])}", Fore.WHITE)
    cprint(f"Total P&L:       {pnl_color}{pnl_sign}${state['total_pnl']:.2f}{Style.RESET_ALL}", Fore.WHITE)
    cprint(f"Market hours:    {'YES' if is_market_hours() else 'NO'}", Fore.WHITE)

    if state["open_positions"]:
        cprint("Open positions:", Fore.CYAN)
        for ticker, pos in state["open_positions"].items():
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(pos["time"])).seconds // 60
            cprint(f"  {ticker}: {pos['shares']} shares @ ${pos['entry']:.2f} | {age}min | Stop ${pos['stop']}", Fore.WHITE)
    cprint(f"{'─'*55}", Fore.CYAN)


def scanner_loop():
    """Main 24/7 scanning loop."""
    cycle = 0
    cprint("Scanner started — monitoring Trump Truth Social 24/7", Fore.GREEN, "🚀")

    while state["running"]:
        try:
            cycle += 1

            # Check open positions every cycle
            monitor_positions()

            # Fetch posts
            posts = fetch_latest_posts(max_posts=5)
            state["last_poll_time"] = datetime.datetime.now()

            new_posts = [p for p in posts if p["id"] not in state["seen_posts"]]

            if new_posts:
                cprint(f"{len(new_posts)} new post(s) found!", Fore.GREEN, "🔔")
                for post in new_posts:
                    state["seen_posts"].add(post["id"])
                    process_new_post(post)
                save_seen_posts()
            else:
                log.debug(f"No new posts (cycle {cycle})")

            # Status every 10 cycles
            if cycle % 10 == 0:
                print_status()

            # Adaptive polling interval
            interval = CONFIG["poll_market_hours"] if is_market_hours() else CONFIG["poll_interval_sec"]
            time.sleep(interval)

        except KeyboardInterrupt:
            cprint("Stopped by user", Fore.YELLOW, "⚠")
            state["running"] = False
            break
        except Exception as e:
            log.error(f"Scanner loop error: {e}")
            time.sleep(30)  # Wait before retrying


# ═══════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════

def main():
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║   🇺🇸  TRUMP TRUTH SOCIAL MONITOR — AI Trading Bot        ║
║   Source:   trumpstruth.org RSS (free, no scraping)      ║
║   Analysis: Claude AI (Anthropic)                        ║
║   Broker:   Alpaca Paper Trading                         ║
║   {Fore.RED}PAPER TRADING ONLY — Educational use{Fore.CYAN}                   ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

    # Load previously seen posts (deduplication across restarts)
    state["seen_posts"] = load_seen_posts()
    cprint(f"Loaded {len(state['seen_posts'])} previously seen posts", Fore.CYAN, "📂")

    # Connect Alpaca
    connect_alpaca()

    # Check for Anthropic API key
    if os.environ.get("ANTHROPIC_API_KEY") or (
        Path("config.json").exists() and
        json.loads(Path("config.json").read_text()).get("anthropic_api_key")
    ):
        cprint("Claude AI analysis: ENABLED", Fore.GREEN, "✅")
    else:
        cprint("Claude AI not configured — using keyword fallback", Fore.YELLOW, "⚠")

    # Check for Telegram
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        cprint("Telegram alerts: ENABLED", Fore.GREEN, "✅")
    else:
        cprint("Telegram not configured — console only", Fore.YELLOW, "○")

    # Override config from env vars
    if os.environ.get("MIN_IMPACT_SCORE"):
        CONFIG["min_impact_score"] = int(os.environ["MIN_IMPACT_SCORE"])

    cprint(f"Trading threshold: {CONFIG['min_impact_score']}/100", Fore.CYAN)
    cprint(f"Poll interval: {CONFIG['poll_interval_sec']}s (market hours: {CONFIG['poll_market_hours']}s)", Fore.CYAN)

    # Start main loop
    scanner_loop()

    # Shutdown summary
    print_status()
    cprint("Bot stopped", Fore.YELLOW)


if __name__ == "__main__":
    main()
