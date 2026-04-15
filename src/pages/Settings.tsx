import { useState, useEffect } from 'react'
import { Sun, Moon, Monitor, Key, Info, ExternalLink } from 'lucide-react'

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('bud-theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('bud-theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, setDark] as const
}

export default function Settings() {
  const [dark, setDark] = useDarkMode()
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('bud-api-key') || '')
  const [saved, setSaved] = useState(false)

  const handleSaveKey = () => {
    localStorage.setItem('bud-api-key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl space-y-6 animate-fade-in">
      {/* Appearance */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Monitor className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Appearance</h3>
        </div>
        <div className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Theme</p>
              <p className="text-xs text-muted-foreground mt-0.5">Toggle between light and dark mode</p>
            </div>
            <button
              onClick={() => setDark(!dark)}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors duration-200 ${
                dark ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200 ${
                dark ? 'translate-x-6' : 'translate-x-1'
              }`}>
                {dark ? <Moon className="h-3 w-3 text-primary" /> : <Sun className="h-3 w-3 text-amber-500" />}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* API Configuration */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Key className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">API Configuration</h3>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
              API URL
            </label>
            <div className="px-3 py-2 bg-muted rounded-md text-sm text-muted-foreground font-mono">
              {window.location.origin}/api
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
              API Key
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key..."
                className="flex-1 px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              />
              <button
                onClick={handleSaveKey}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                {saved ? 'Saved!' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Info className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">About</h3>
        </div>
        <div className="p-5">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-teal-700 flex items-center justify-center">
              <span className="text-white font-bold text-sm">B</span>
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Bud Test Platform</p>
              <p className="text-xs text-muted-foreground">Version 0.1.0</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>by</span>
            <a
              href="https://embedlabs.de"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-medium"
            >
              EmbedLabs
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
