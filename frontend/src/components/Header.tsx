import { Activity, TrendingUp, Settings, Wifi, WifiOff } from 'lucide-react'
import { useStore } from '../store/useStore'

type View = 'feed' | 'trades' | 'settings'

interface HeaderProps {
  currentView: View
  onNavigate: (view: View) => void
}

export function Header({ currentView, onNavigate }: HeaderProps) {
  const wsConnected = useStore((s) => s.wsConnected)

  const navItem = (view: View, label: string, Icon: React.ComponentType<{ className?: string }>) => (
    <button
      onClick={() => onNavigate(view)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        currentView === view
          ? 'bg-blue-600 text-white'
          : 'text-gray-400 hover:text-white hover:bg-gray-700'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  )

  return (
    <header className="bg-gray-900 border-b border-gray-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <span className="text-xl">🇺🇸</span>
          <div>
            <div className="font-bold text-white text-sm leading-none">Trump Trade Monitor</div>
            <div className="text-xs text-gray-500 leading-none mt-0.5">AI-Powered Political Trading</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {navItem('feed', 'Live Feed', Activity)}
          {navItem('trades', 'Trades', TrendingUp)}
          {navItem('settings', 'Settings', Settings)}
        </nav>

        {/* WS Status */}
        <div className={`flex items-center gap-1.5 text-xs font-medium ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
          {wsConnected ? (
            <>
              <Wifi className="w-3.5 h-3.5" />
              <span>Live</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5" />
              <span>Offline</span>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
