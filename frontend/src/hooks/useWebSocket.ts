import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import type { Post } from '../api/api'

interface WsEvent {
  type: 'POST_ANALYZED' | 'TRADE_SIGNAL' | 'POSITION_CLOSED' | 'HEARTBEAT' | 'STATUS_UPDATE'
  timestamp: string
  data: Record<string, unknown>
}

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live`

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelay = useRef(1000)

  const addPost = useStore((s) => s.addPost)
  const setPositions = useStore((s) => s.setPositions)
  const setWsConnected = useStore((s) => s.setWsConnected)
  const updateStatus = useStore((s) => s.updateStatus)

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      reconnectDelay.current = 1000
    }

    ws.onmessage = (ev) => {
      let event: WsEvent
      try {
        event = JSON.parse(ev.data) as WsEvent
      } catch {
        return
      }

      switch (event.type) {
        case 'POST_ANALYZED':
          addPost(event.data as unknown as Post)
          break

        case 'POSITION_CLOSED':
          // Refresh positions will be triggered by STATUS_UPDATE
          break

        case 'HEARTBEAT':
        case 'STATUS_UPDATE': {
          const d = event.data
          updateStatus({
            running: d.running as boolean,
            posts_analyzed: d.posts_analyzed as number,
            trades_executed: d.trades_executed as number,
            open_positions_count: d.open_positions_count as number,
            total_pnl: d.total_pnl as number,
            alpaca_connected: d.alpaca_connected as boolean,
            uptime_seconds: d.uptime_seconds as number,
          })
          break
        }
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
      wsRef.current = null
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
        connect()
      }, reconnectDelay.current)
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
