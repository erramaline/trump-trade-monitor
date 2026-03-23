import { useEffect } from 'react'
import { ExternalLink, Loader2 } from 'lucide-react'
import { useStore } from '../store/useStore'
import { fetchPosts } from '../api/api'
import type { Post } from '../api/api'

// ── Score badge ──────────────────────────────────────
function ScoreBadge({ score }: { score: number }) {
  if (score >= 90)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white">
        🔴 CRITICAL {score}
      </span>
    )
  if (score >= 70)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-orange-500 text-white">
        🟠 HIGH {score}
      </span>
    )
  if (score >= 50)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-yellow-500 text-black">
        🟡 MEDIUM {score}
      </span>
    )
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-gray-600 text-gray-300">
      ⚪ LOW {score}
    </span>
  )
}

// ── Direction badge ──────────────────────────────────
function DirectionBadge({ direction }: { direction: string }) {
  const map: Record<string, string> = {
    BULLISH: 'bg-green-600 text-white',
    BEARISH: 'bg-red-600 text-white',
    MIXED: 'bg-purple-600 text-white',
    NEUTRAL: 'bg-gray-600 text-gray-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${map[direction] ?? map.NEUTRAL}`}>
      {direction}
    </span>
  )
}

// ── Category badge ───────────────────────────────────
function CategoryBadge({ category }: { category: string }) {
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-700 text-gray-300 border border-gray-600">
      {category}
    </span>
  )
}

// ── Relative time ────────────────────────────────────
function RelativeTime({ iso }: { iso: string }) {
  const date = new Date(iso)
  const delta = Math.floor((Date.now() - date.getTime()) / 1000)
  let rel: string
  if (delta < 60) rel = `${delta}s ago`
  else if (delta < 3600) rel = `${Math.floor(delta / 60)}m ago`
  else if (delta < 86400) rel = `${Math.floor(delta / 3600)}h ago`
  else rel = `${Math.floor(delta / 86400)}d ago`

  return (
    <span
      title={date.toLocaleString()}
      className="text-xs text-gray-500 cursor-default"
    >
      {rel}
    </span>
  )
}

// ── Post card ────────────────────────────────────────
function PostCard({ post, isNew }: { post: Post; isNew: boolean }) {
  return (
    <div
      className={`bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3 ${
        isNew ? 'animate-slide-in' : ''
      }`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <ScoreBadge score={post.score} />
          <DirectionBadge direction={post.direction} />
          <CategoryBadge category={post.category} />
        </div>
        <div className="flex items-center gap-2">
          <RelativeTime iso={post.timestamp ?? post.published} />
          {post.url && (
            <a
              href={post.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-blue-400 transition-colors"
              title="View original post"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      </div>

      {/* Content */}
      <p className="text-gray-100 text-sm leading-relaxed whitespace-pre-wrap">
        {post.content}
      </p>

      {/* Tickers */}
      {post.tickers && post.tickers.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {post.tickers.map((t) => (
            <span
              key={t}
              className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-green-900 text-green-300 border border-green-700"
            >
              ${t}
            </span>
          ))}
        </div>
      )}

      {/* Reasoning */}
      {post.reasoning && (
        <p className="text-xs italic text-gray-500 leading-relaxed">
          🧠 {post.reasoning}
        </p>
      )}

      {/* Trade banner */}
      {post.trade_triggered && post.trade_detail && (
        <div className="bg-green-900/50 border border-green-600 rounded-lg px-3 py-2">
          <span className="text-green-300 font-bold text-sm">
            ✅ TRADE EXECUTED: {post.trade_detail.side} {post.trade_detail.shares}{' '}
            {post.trade_detail.ticker} @ ${post.trade_detail.entry?.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  )
}

// ── Main feed view ────────────────────────────────────
export function FeedView() {
  const posts = useStore((s) => s.posts)
  const setPosts = useStore((s) => s.setPosts)

  useEffect(() => {
    fetchPosts()
      .then(setPosts)
      .catch(console.error)
  }, [setPosts])

  if (posts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <p className="text-sm">Waiting for Trump to post…</p>
        <p className="text-xs text-gray-600">Bot polls every 60 seconds</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {posts.map((post, idx) => (
        <PostCard key={post.id || idx} post={post} isNew={idx === 0} />
      ))}
    </div>
  )
}
