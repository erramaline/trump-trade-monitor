import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, ChevronDown, ChevronRight } from 'lucide-react'
import { useStore } from '../store/useStore'
import { fetchTrades, fetchPositions } from '../api/api'
import type { Trade, Position } from '../api/api'

// ── Helpers ──────────────────────────────────────────

function pnlClass(pnl: number) {
  return pnl >= 0 ? 'text-green-400' : 'text-red-400'
}

function fmtPnl(pnl: number | undefined) {
  if (pnl === undefined) return '—'
  return `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`
}

function fmtPct(entry: number, exit: number, shares: number, side: string) {
  const pct = side === 'BUY' ? ((exit - entry) / entry) * 100 : ((entry - exit) / entry) * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
}

function useElapsed(isoTime: string) {
  const [elapsed, setElapsed] = useState('')
  useEffect(() => {
    const tick = () => {
      const delta = Math.floor((Date.now() - new Date(isoTime).getTime()) / 1000)
      const h = Math.floor(delta / 3600).toString().padStart(2, '0')
      const m = Math.floor((delta % 3600) / 60).toString().padStart(2, '0')
      const s = (delta % 60).toString().padStart(2, '0')
      setElapsed(`${h}:${m}:${s}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [isoTime])
  return elapsed
}

// ── Open position card ────────────────────────────────

function PositionCard({ ticker, pos }: { ticker: string; pos: Position }) {
  const elapsed = useElapsed(pos.time)
  // We don't have live market prices here, so show entry as current placeholder
  const pnl = 0 // live P&L would need price feed

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-white font-mono">{ticker}</span>
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-bold ${
              pos.side === 'BUY' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
            }`}
          >
            {pos.side}
          </span>
          <span className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded-full">
            Score: {pos.score}/100
          </span>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold font-mono text-gray-300">{elapsed}</div>
          <div className="text-xs text-gray-500">time in trade</div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div className="bg-gray-900 rounded-lg px-3 py-2">
          <div className="text-xs text-gray-500 mb-0.5">Entry</div>
          <div className="font-mono font-semibold text-white">${pos.entry.toFixed(2)}</div>
        </div>
        <div className="bg-gray-900 rounded-lg px-3 py-2">
          <div className="text-xs text-gray-500 mb-0.5">Shares</div>
          <div className="font-mono font-semibold text-white">{pos.shares}</div>
        </div>
        <div className="bg-gray-900 rounded-lg px-3 py-2">
          <div className="text-xs text-red-500 mb-0.5">Stop</div>
          <div className="font-mono font-semibold text-red-400">${pos.stop.toFixed(2)}</div>
        </div>
        <div className="bg-gray-900 rounded-lg px-3 py-2">
          <div className="text-xs text-green-500 mb-0.5">Target 1</div>
          <div className="font-mono font-semibold text-green-400">${pos.target_1.toFixed(2)}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Target 2: <span className="text-green-300 font-mono">${pos.target_2.toFixed(2)}</span></span>
        {pos.t1_filled && (
          <span className="text-green-400 font-medium">✅ T1 filled</span>
        )}
        <span className={pos.placed ? 'text-green-400' : 'text-yellow-400'}>
          {pos.placed ? '✅ Order placed' : '⚠ Alert only'}
        </span>
      </div>
    </div>
  )
}

// ── Trade history row ─────────────────────────────────

function TradeRow({ trade }: { trade: Trade }) {
  const [expanded, setExpanded] = useState(false)

  if (trade.action !== 'CLOSE') return null

  const entry = trade.entry ?? 0
  const exit = trade.price ?? 0
  const side = trade.side ?? 'BUY'
  const pnl = trade.pnl ?? 0
  const pct = entry > 0 ? fmtPct(entry, exit, trade.shares, side) : '—'
  const time = new Date(trade.time).toLocaleString()

  return (
    <>
      <tr
        className="border-b border-gray-700 hover:bg-gray-750 cursor-pointer transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-3 py-2 text-xs text-gray-400">{time}</td>
        <td className="px-3 py-2 font-mono font-bold text-white">{trade.ticker}</td>
        <td className={`px-3 py-2 text-xs font-semibold ${side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
          {side}
        </td>
        <td className="px-3 py-2 font-mono text-sm text-gray-300">${entry.toFixed(2)}</td>
        <td className="px-3 py-2 font-mono text-sm text-gray-300">${exit.toFixed(2)}</td>
        <td className="px-3 py-2 text-gray-300">{trade.shares}</td>
        <td className={`px-3 py-2 font-mono font-semibold ${pnlClass(pnl)}`}>
          {fmtPnl(pnl)}
        </td>
        <td className={`px-3 py-2 text-xs font-mono ${pnlClass(pnl)}`}>{pct}</td>
        <td className="px-3 py-2 text-xs text-gray-500">{trade.reason ?? '—'}</td>
        <td className="px-3 py-2 text-xs text-gray-500">{trade.score ?? '—'}</td>
        <td className="px-3 py-2 text-xs text-gray-500 max-w-xs truncate">{trade.post ?? '—'}</td>
        <td className="px-3 py-2">
          {expanded ? (
            <ChevronDown className="w-3 h-3 text-gray-500" />
          ) : (
            <ChevronRight className="w-3 h-3 text-gray-500" />
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-900 border-b border-gray-700">
          <td colSpan={12} className="px-4 py-3">
            <div className="space-y-2">
              <div className="text-xs text-gray-400 font-medium">Full post content:</div>
              <p className="text-sm text-gray-300 bg-gray-800 rounded p-2">{trade.post}</p>
              {trade.analysis && (
                <>
                  <div className="text-xs text-gray-400 font-medium mt-2">AI Analysis JSON:</div>
                  <pre className="text-xs text-green-300 bg-gray-800 rounded p-2 overflow-x-auto">
                    {JSON.stringify(trade.analysis, null, 2)}
                  </pre>
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Summary metrics ───────────────────────────────────

function SummaryMetrics({ trades }: { trades: Trade[] }) {
  const closed = trades.filter((t) => t.action === 'CLOSE' && t.pnl !== undefined)
  const totalPnl = closed.reduce((s, t) => s + (t.pnl ?? 0), 0)
  const wins = closed.filter((t) => (t.pnl ?? 0) > 0)
  const winRate = closed.length > 0 ? ((wins.length / closed.length) * 100).toFixed(0) : '—'
  const best = closed.length > 0 ? Math.max(...closed.map((t) => t.pnl ?? 0)) : undefined
  const worst = closed.length > 0 ? Math.min(...closed.map((t) => t.pnl ?? 0)) : undefined

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        { label: 'Total P&L', value: fmtPnl(totalPnl), color: pnlClass(totalPnl) },
        { label: 'Win Rate', value: closed.length > 0 ? `${winRate}%` : '—', color: 'text-blue-400' },
        { label: 'Best Trade', value: best !== undefined ? fmtPnl(best) : '—', color: 'text-green-400' },
        { label: 'Worst Trade', value: worst !== undefined ? fmtPnl(worst) : '—', color: 'text-red-400' },
      ].map(({ label, value, color }) => (
        <div key={label} className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-center">
          <div className="text-xs text-gray-500 mb-1">{label}</div>
          <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
        </div>
      ))}
    </div>
  )
}

// ── Main view ────────────────────────────────────────

export function TradesView() {
  const trades = useStore((s) => s.trades)
  const positions = useStore((s) => s.positions)
  const setTrades = useStore((s) => s.setTrades)
  const setPositions = useStore((s) => s.setPositions)

  useEffect(() => {
    fetchTrades().then(setTrades).catch(console.error)
    fetchPositions().then(setPositions).catch(console.error)
  }, [setTrades, setPositions])

  const openEntries = Object.entries(positions)
  const closedTrades = trades.filter((t) => t.action === 'CLOSE')

  return (
    <div className="space-y-8">
      {/* Summary */}
      <SummaryMetrics trades={trades} />

      {/* Open Positions */}
      <section>
        <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-green-400" />
          Open Positions
          <span className="text-sm font-normal text-gray-500">({openEntries.length})</span>
        </h2>
        {openEntries.length === 0 ? (
          <div className="text-center text-gray-600 py-8 bg-gray-800 rounded-xl border border-gray-700">
            No open positions
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {openEntries.map(([ticker, pos]) => (
              <PositionCard key={ticker} ticker={ticker} pos={pos} />
            ))}
          </div>
        )}
      </section>

      {/* Trade History */}
      <section>
        <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <TrendingDown className="w-5 h-5 text-blue-400" />
          Trade History
          <span className="text-sm font-normal text-gray-500">({closedTrades.length})</span>
        </h2>
        {closedTrades.length === 0 ? (
          <div className="text-center text-gray-600 py-8 bg-gray-800 rounded-xl border border-gray-700">
            No completed trades yet
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-gray-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 text-gray-400 text-xs uppercase">
                <tr>
                  {['Time', 'Ticker', 'Side', 'Entry', 'Exit', 'Shares', 'P&L$', 'P&L%', 'Reason', 'Score', 'Post', ''].map(
                    (h) => (
                      <th key={h} className="px-3 py-2 text-left font-medium">
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {[...closedTrades].reverse().map((t, i) => (
                  <TradeRow key={i} trade={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
