# Trump Trade Monitor 🇺🇸

> AI-powered trading bot that monitors Trump's Truth Social posts 24/7 and automatically executes paper trades based on market impact analysis.

**PAPER TRADING ONLY — Educational purposes — Not financial advice.**

---

## What It Does

```
RSS Feed (60s poll) → Gemini AI analysis → Alpaca paper trade → Telegram alert
```

Every 60 seconds the bot polls Trump's Truth Social RSS feed. New posts are sent to **Google Gemini** for market impact scoring (0–100). Posts scoring above the threshold trigger automatic paper trades on **Alpaca**.

### Real example — April 9, 2025

On April 9, 2025 at 9:37 AM ET, Trump posted **"THIS IS A GREAT TIME TO BUY!!!"** on Truth Social. The S&P 500 surged **9.52%** that day — its largest single-day gain since 2008. This bot detects posts within 60 seconds and executes the trade automatically.

---

## Quick Start (3 steps)

```bash
# 1. Clone and configure
git clone https://github.com/erramaline/trump-trade-monitor
cd trump-trade-monitor
cp config.example.json config.json
# Edit config.json with your API keys

# 2. Install everything
bash setup.sh

# 3. Run
bash run.sh
# → Opens dashboard at http://localhost:8000
```

---

## Required API Keys

| Key | Where to get | Cost | Required? |
|-----|-------------|------|-----------|
| **Alpaca Paper API** | [alpaca.markets](https://alpaca.markets) → Paper Trading | Free | ✅ YES |
| **Google Gemini API** (`GIMINI_API_KEY`) | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Free tier available | ✅ YES |
| **Anthropic Claude** (`ANTHROPIC_API_KEY`) | [console.anthropic.com](https://console.anthropic.com) | ~$0.003/post | Optional fallback |
| **Telegram Bot** | [@BotFather](https://t.me/BotFather) | Free | Optional |

---

## config.json

```json
{
  "alpaca_api_key": "YOUR_ALPACA_KEY_ID",
  "alpaca_api_secret": "YOUR_ALPACA_SECRET",
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "anthropic_api_key": "",
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "trump_min_impact_score": 70,
  "trump_min_alert_score": 50,
  "poll_interval_sec": 60
}
```

---

## AI Analysis Priority

1. **Google Gemini** (`GIMINI_API_KEY`) — primary, fast, cheap
2. **Anthropic Claude** (`ANTHROPIC_API_KEY`) — optional fallback
3. **Keyword matching** — final fallback, no API key needed

---

## Dashboard

The web UI at `http://localhost:8000` has 3 views:

- **Live Feed** — Real-time Trump posts with AI scores, trade banners, and impact badges
- **Trades** — Open positions (live P&L) + trade history table
- **Settings** — Configure API keys, thresholds, and bot parameters

---

## GitHub Actions — 24/7 Cloud (Free)

The included workflow (`.github/workflows/trump-monitor.yml`) runs the bot every 5 hours automatically on GitHub's free tier.

### Add these repository secrets:

| Secret | Value |
|--------|-------|
| `ALPACA_API_KEY` | Your Alpaca key ID |
| `ALPACA_API_SECRET` | Your Alpaca secret |
| `GIMINI_API_KEY` | Your Google Gemini API key |
| `ANTHROPIC_API_KEY` | (Optional) Anthropic key |
| `TELEGRAM_BOT_TOKEN` | (Optional) Telegram bot token |
| `TELEGRAM_CHAT_ID` | (Optional) Your Telegram chat ID |

Go to **Settings → Secrets and variables → Actions → New repository secret**.

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Bot state (running, P&L, uptime…) |
| GET | `/api/posts` | Last 50 analyzed posts |
| GET | `/api/trades` | All trade history |
| GET | `/api/positions` | Current open positions |
| POST | `/api/start` | Start the scanner |
| POST | `/api/stop` | Stop the scanner |
| POST | `/api/connect` | Save credentials |
| POST | `/api/config` | Update runtime parameters |
| WS | `/ws/live` | Live event stream |

---

## Architecture

```
trump_monitor.py  ←  core bot (unchanged)
server.py         ←  FastAPI wrapper + WebSocket bridge
frontend/         ←  React + TypeScript + Tailwind dashboard
```

`server.py` monkey-patches `trump_monitor.analyze_post_with_claude` to route through Gemini first, keeping the core bot untouched.

---

## Disclaimer

This project is for **educational and research purposes only**. It uses paper trading (simulated money) exclusively. Nothing in this project constitutes financial advice. Past performance of any strategy is not indicative of future results. Use at your own risk.