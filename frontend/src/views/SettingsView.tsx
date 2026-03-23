import { useState } from 'react'
import { Save, Plug, Send } from 'lucide-react'
import { postConnect, postConfig } from '../api/api'
import { useStore } from '../store/useStore'

// ── Shared section wrapper ────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-4">
      <h3 className="text-base font-bold text-white border-b border-gray-700 pb-2">{title}</h3>
      {children}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-gray-400 font-medium">{label}</label>
      {children}
    </div>
  )
}

function MaskedInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="flex items-center gap-2">
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 font-mono"
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 bg-gray-700 rounded"
      >
        {show ? 'hide' : 'show'}
      </button>
    </div>
  )
}

function SaveButton({
  onClick,
  loading,
  saved,
  label = 'Save',
}: {
  onClick: () => void
  loading: boolean
  saved: boolean
  label?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
    >
      {loading ? (
        <span className="animate-spin">⏳</span>
      ) : saved ? (
        <span>✅</span>
      ) : (
        <Save className="w-4 h-4" />
      )}
      {saved ? 'Saved!' : label}
    </button>
  )
}

// ── Settings sections ─────────────────────────────────

function AlpacaSection() {
  const status = useStore((s) => s.status)
  const [key, setKey] = useState('')
  const [secret, setSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleConnect = async () => {
    setLoading(true)
    try {
      await postConnect({ alpaca_api_key: key, alpaca_api_secret: secret })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Section title="🏦 Alpaca Connection (Paper Trading)">
      <Field label="API Key ID">
        <MaskedInput value={key} onChange={setKey} placeholder="PK…" />
      </Field>
      <Field label="API Secret">
        <MaskedInput value={secret} onChange={setSecret} placeholder="…" />
      </Field>
      <div className="flex items-center justify-between">
        <SaveButton onClick={handleConnect} loading={loading} saved={saved} label="Connect" />
        {status?.alpaca_connected ? (
          <span className="text-xs text-green-400">✅ Connected</span>
        ) : (
          <span className="text-xs text-yellow-400">⚠ Not connected</span>
        )}
      </div>
      <p className="text-xs text-gray-500">
        Free paper trading account at{' '}
        <a
          href="https://alpaca.markets"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          alpaca.markets
        </a>
      </p>
    </Section>
  )
}

function GeminiSection() {
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setLoading(true)
    try {
      await postConnect({ gemini_api_key: apiKey } as Parameters<typeof postConnect>[0])
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Section title="🤖 AI Analysis — Google Gemini (Primary)">
      <Field label="Gemini API Key (GIMINI_API_KEY)">
        <MaskedInput value={apiKey} onChange={setApiKey} placeholder="AIza…" />
      </Field>
      <div className="flex items-center justify-between">
        <SaveButton onClick={handleSave} loading={loading} saved={saved} />
        <span className="text-xs text-gray-500">Model: gemini-1.5-flash</span>
      </div>
      <p className="text-xs text-gray-500">
        Get a free key at{' '}
        <a
          href="https://aistudio.google.com/app/apikey"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          aistudio.google.com
        </a>
      </p>
    </Section>
  )
}

function AnthropicSection() {
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setLoading(true)
    try {
      await postConnect({ anthropic_api_key: apiKey })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Section title="🔵 AI Analysis — Anthropic Claude (Optional Fallback)">
      <Field label="Anthropic API Key (optional)">
        <MaskedInput value={apiKey} onChange={setApiKey} placeholder="sk-ant-…" />
      </Field>
      <div className="flex items-center justify-between">
        <SaveButton onClick={handleSave} loading={loading} saved={saved} />
        <span className="text-xs text-gray-500">Model: claude-sonnet-4</span>
      </div>
      <p className="text-xs text-gray-500">
        Used only as fallback if Gemini fails. ~$0.003/post at{' '}
        <a
          href="https://console.anthropic.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          console.anthropic.com
        </a>
      </p>
    </Section>
  )
}

function TelegramSection() {
  const [token, setToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [loading, setLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setLoading(true)
    try {
      await postConnect({ telegram_bot_token: token, telegram_chat_id: chatId })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async () => {
    setTestLoading(true)
    try {
      const url = `https://api.telegram.org/bot${token}/sendMessage`
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text: '🤖 Trump Trade Monitor test alert!' }),
      })
    } catch (e) {
      console.error(e)
    } finally {
      setTestLoading(false)
    }
  }

  return (
    <Section title="📱 Telegram Alerts (Optional)">
      <Field label="Bot Token">
        <MaskedInput value={token} onChange={setToken} placeholder="123456:ABC…" />
      </Field>
      <Field label="Chat ID">
        <input
          type="text"
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          placeholder="-100123456789"
          className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
        />
      </Field>
      <div className="flex items-center gap-3">
        <SaveButton onClick={handleSave} loading={loading} saved={saved} />
        <button
          onClick={handleTest}
          disabled={testLoading || !token || !chatId}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white transition-colors"
        >
          <Send className="w-4 h-4" />
          {testLoading ? 'Sending…' : 'Test Alert'}
        </button>
      </div>
      <p className="text-xs text-gray-500">
        Create a bot via{' '}
        <a
          href="https://t.me/BotFather"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:underline"
        >
          @BotFather
        </a>{' '}
        on Telegram — free.
      </p>
    </Section>
  )
}

function BotParamsSection() {
  const [minScore, setMinScore] = useState(70)
  const [alertScore, setAlertScore] = useState(50)
  const [pollInterval, setPollInterval] = useState(60)
  const [maxPositions, setMaxPositions] = useState(3)
  const [marketHoursOnly, setMarketHoursOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setLoading(true)
    try {
      await postConfig({
        min_impact_score: minScore,
        min_score_alert: alertScore,
        poll_interval_sec: pollInterval,
        max_open_positions: maxPositions,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Section title="⚙️ Bot Parameters">
      <Field label={`Min Impact Score to Trade: ${minScore}`}>
        <input
          type="range"
          min={0}
          max={100}
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
        <div className="flex justify-between text-xs text-gray-600">
          <span>0 (trade everything)</span>
          <span>100 (only extreme events)</span>
        </div>
      </Field>

      <Field label={`Min Score for Alerts: ${alertScore}`}>
        <input
          type="range"
          min={0}
          max={100}
          value={alertScore}
          onChange={(e) => setAlertScore(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
      </Field>

      <Field label="Poll Interval (seconds)">
        <input
          type="number"
          min={5}
          max={3600}
          value={pollInterval}
          onChange={(e) => setPollInterval(Number(e.target.value))}
          className="w-32 bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        />
      </Field>

      <Field label={`Max Open Positions: ${maxPositions}`}>
        <input
          type="range"
          min={1}
          max={5}
          value={maxPositions}
          onChange={(e) => setMaxPositions(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
        <div className="flex justify-between text-xs text-gray-600">
          <span>1</span>
          <span>5</span>
        </div>
      </Field>

      <Field label="Market Hours Only (9:30–16:00 ET)">
        <button
          onClick={() => setMarketHoursOnly((v) => !v)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            marketHoursOnly ? 'bg-blue-600' : 'bg-gray-600'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              marketHoursOnly ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
        <span className="ml-2 text-xs text-gray-400">
          {marketHoursOnly ? 'ON — only trade during market hours' : 'OFF — trade 24/7'}
        </span>
      </Field>

      <SaveButton onClick={handleSave} loading={loading} saved={saved} />
    </Section>
  )
}

// ── Main view ────────────────────────────────────────

export function SettingsView() {
  return (
    <div className="max-w-2xl space-y-5">
      <AlpacaSection />
      <GeminiSection />
      <AnthropicSection />
      <TelegramSection />
      <BotParamsSection />

      <div className="text-center text-xs text-gray-600 pb-4">
        ⚠ Paper trading only — educational purposes — not financial advice
      </div>
    </div>
  )
}
