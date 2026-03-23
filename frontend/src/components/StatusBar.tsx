import { useStore } from '../store/useStore'
import { startBot, stopBot } from '../api/api'
import { useState } from 'react'

function isMarketOpen(): boolean {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const et = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  }).format(now)
  const [h, m] = et.split(':').map(Number)
  const minutes = h * 60 + m
  return minutes >= 9 * 60 + 30 && minutes < 16 * 60
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const delta = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (delta < 60) return `${delta}s ago`
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`
  return `${Math.floor(delta / 3600)}h ago`
}

export function StatusBar() {
  const status = useStore((s) => s.status)
  const [loading, setLoading] = useState(false)

  const marketOpen = isMarketOpen()
  const pnl = status?.total_pnl ?? 0
  const pnlStr = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`

  const handleToggle = async () => {
    if (loading) return
    setLoading(true)
    try {
      if (status?.running) {
        await stopBot()
      } else {
        await startBot()
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  if (!status) return null

  return (
    <div className="bg-gray-800 border-b border-gray-700 px-4 py-2">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
        {/* Bot status */}
        <button
          onClick={handleToggle}
          className={`flex items-center gap-1.5 font-semibold ${
            status.running ? 'text-green-400 hover:text-red-400' : 'text-red-400 hover:text-green-400'
          } transition-colors`}
          title={status.running ? 'Click to stop' : 'Click to start'}
        >
          <span>{status.running ? '🟢' : '🔴'}</span>
          <span>{status.running ? 'Bot Active' : 'Bot Stopped'}</span>
        </button>

        <span className="text-gray-400">
          <span className="text-white font-medium">{status.posts_analyzed}</span> posts analyzed
        </span>

        <span className="text-gray-400">
          <span className="text-white font-medium">{status.trades_executed}</span> trades
        </span>

        <span className={`font-medium ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          P&amp;L: {pnlStr}
        </span>

        <span className="text-gray-400">
          Last post:{' '}
          <span className="text-white">{timeAgo(status.last_post_time)}</span>
        </span>

        <span className={`font-medium ${marketOpen ? 'text-green-400' : 'text-gray-500'}`}>
          Market: {marketOpen ? 'OPEN' : 'CLOSED'}
        </span>

        {!status.alpaca_connected && (
          <span className="text-yellow-400 text-xs">⚠ Alpaca not connected</span>
        )}
      </div>
    </div>
  )
}
