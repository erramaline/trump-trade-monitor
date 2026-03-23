// ═══════════════════════════════════════════════════════
//  Shared types
// ═══════════════════════════════════════════════════════

export interface BotStatus {
  running: boolean
  posts_analyzed: number
  trades_executed: number
  open_positions_count: number
  total_pnl: number
  alpaca_connected: boolean
  uptime_seconds: number
  last_post_time: string | null
  last_poll_time: string | null
}

export interface Post {
  id: string
  content: string
  published: string
  url: string
  score: number
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | 'MIXED'
  category: string
  tickers: string[]
  reasoning: string
  trade_triggered: boolean
  trade_detail?: {
    side: string
    ticker: string
    shares: number
    entry: number
  }
  timestamp: string
}

export interface Position {
  ticker: string
  side: string
  entry: number
  shares: number
  stop: number
  target_1: number
  target_2: number
  t1_filled: boolean
  time: string
  post_id: string
  score: number
  order_id: string | null
  placed: boolean
}

export interface Trade {
  action: 'OPEN' | 'CLOSE'
  ticker: string
  side?: string
  entry?: number
  price?: number
  shares: number
  stop?: number
  target_1?: number
  target_2?: number
  time: string
  post_id?: string
  score?: number
  reason?: string
  pnl?: number
  total_pnl?: number
  post?: string
  analysis?: Record<string, unknown>
}

// ═══════════════════════════════════════════════════════
//  Base URL
// ═══════════════════════════════════════════════════════

const BASE = ''  // uses Vite proxy in dev, same origin in prod

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}

// ═══════════════════════════════════════════════════════
//  API functions
// ═══════════════════════════════════════════════════════

export const fetchStatus = () => req<BotStatus>('/api/status')
export const fetchPosts = () => req<Post[]>('/api/posts')
export const fetchTrades = () => req<Trade[]>('/api/trades')
export const fetchPositions = () => req<Record<string, Position>>('/api/positions')

export const startBot = () => req<{ ok: boolean }>('/api/start', { method: 'POST' })
export const stopBot = () => req<{ ok: boolean }>('/api/stop', { method: 'POST' })

export interface ConnectPayload {
  alpaca_api_key?: string
  alpaca_api_secret?: string
  anthropic_api_key?: string
  telegram_bot_token?: string
  telegram_chat_id?: string
}

export const postConnect = (payload: ConnectPayload) =>
  req<{ ok: boolean }>('/api/connect', { method: 'POST', body: JSON.stringify(payload) })

export interface ConfigPayload {
  min_impact_score?: number
  min_score_alert?: number
  poll_interval_sec?: number
  max_open_positions?: number
}

export const postConfig = (payload: ConfigPayload) =>
  req<{ ok: boolean; config: Record<string, unknown> }>('/api/config', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
