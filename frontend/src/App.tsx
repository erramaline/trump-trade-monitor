import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { StatusBar } from './components/StatusBar'
import { FeedView } from './views/FeedView'
import { TradesView } from './views/TradesView'
import { SettingsView } from './views/SettingsView'
import { useWebSocket } from './hooks/useWebSocket'
import { fetchStatus, fetchPositions } from './api/api'
import { useStore } from './store/useStore'

type View = 'feed' | 'trades' | 'settings'

export default function App() {
  const [view, setView] = useState<View>('feed')
  const setStatus = useStore((s) => s.setStatus)
  const setPositions = useStore((s) => s.setPositions)

  // Connect WebSocket for live updates
  useWebSocket()

  // Bootstrap status on mount
  useEffect(() => {
    fetchStatus().then(setStatus).catch(console.error)
    fetchPositions().then(setPositions).catch(console.error)

    // Refresh status every 10s as fallback
    const id = setInterval(() => {
      fetchStatus().then(setStatus).catch(console.error)
      fetchPositions().then(setPositions).catch(console.error)
    }, 10_000)
    return () => clearInterval(id)
  }, [setStatus, setPositions])

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      <Header currentView={view} onNavigate={setView} />
      <StatusBar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-5">
        {view === 'feed' && <FeedView />}
        {view === 'trades' && <TradesView />}
        {view === 'settings' && <SettingsView />}
      </main>

      <footer className="text-center text-xs text-gray-700 py-3 border-t border-gray-800">
        Trump Trade Monitor — Paper trading only. Not financial advice.
      </footer>
    </div>
  )
}
