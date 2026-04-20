import { useState, useEffect } from 'react'
import { Sun, Moon, Monitor, Info, ExternalLink, Link as LinkIcon, Save, Loader2, Globe } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { APP_VERSION, settingsApi, extractApiErrorMessage } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const COMMON_TIMEZONES = [
  { label: 'Auto (Browser)', value: 'auto' },
  { label: 'UTC+0', value: 'UTC' },
  { label: 'UTC+1', value: 'Etc/GMT-1' },
  { label: 'UTC+2', value: 'Etc/GMT-2' },
  { label: 'UTC+3', value: 'Etc/GMT-3' },
  { label: 'UTC+4', value: 'Etc/GMT-4' },
  { label: 'UTC+5', value: 'Etc/GMT-5' },
  { label: 'UTC+5.5', value: 'Asia/Kolkata' },
  { label: 'UTC+6', value: 'Etc/GMT-6' },
  { label: 'UTC+7', value: 'Etc/GMT-7' },
  { label: 'UTC+8', value: 'Etc/GMT-8' },
  { label: 'UTC+9', value: 'Etc/GMT-9' },
  { label: 'UTC+10', value: 'Etc/GMT-10' },
  { label: 'UTC+11', value: 'Etc/GMT-11' },
  { label: 'UTC+12', value: 'Etc/GMT-12' },
  { label: 'UTC-1', value: 'Etc/GMT+1' },
  { label: 'UTC-2', value: 'Etc/GMT+2' },
  { label: 'UTC-3', value: 'Etc/GMT+3' },
  { label: 'UTC-4', value: 'Etc/GMT+4' },
  { label: 'UTC-5', value: 'Etc/GMT+5' },
  { label: 'UTC-6', value: 'Etc/GMT+6' },
  { label: 'UTC-7', value: 'Etc/GMT+7' },
  { label: 'UTC-8', value: 'Etc/GMT+8' },
  { label: 'UTC-9', value: 'Etc/GMT+9' },
  { label: 'UTC-10', value: 'Etc/GMT+10' },
  { label: 'UTC-11', value: 'Etc/GMT+11' },
  { label: 'UTC-12', value: 'Etc/GMT+12' },
]

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
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const queryClient = useQueryClient()
  
  const [dark, setDark] = useDarkMode()

  // Timezone state
  const [timezone, setTimezone] = useState(() => localStorage.getItem('bud-timezone') || 'auto')

  // ALM Integration local state
  const [bloomUrl, setBloomUrl] = useState('')
  const [bloomToken, setBloomToken] = useState('')

  const { data: almSettings, isLoading: almLoading } = useQuery({
    queryKey: ['almSettings'],
    queryFn: settingsApi.getALM,
    enabled: isAdmin,
  })

  useEffect(() => {
    if (almSettings) {
      setBloomUrl(almSettings.bloom_url)
      setBloomToken(almSettings.bloom_token)
    }
  }, [almSettings])

  const almMutation = useMutation({
    mutationFn: settingsApi.updateALM,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['almSettings'] })
      alert('ALM settings updated successfully')
    },
    onError: (error) => {
      alert(`Error updating ALM settings: ${extractApiErrorMessage(error)}`)
    },
  })

  const handleSaveALM = () => {
    almMutation.mutate({
      bloom_url: bloomUrl,
      bloom_token: bloomToken
    })
  }

  const handleTimezoneChange = (newTz: string) => {
    setTimezone(newTz)
    localStorage.setItem('bud-timezone', newTz)
    window.location.reload()
  }

  return (
    <div className="max-w-2xl space-y-6 animate-fade-in pb-20">
      {/* Appearance */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
          <Monitor className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Appearance</h3>
        </div>
        <div className="p-5 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Theme Mode</p>
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

      {/* Regional Settings */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
          <Globe className="h-4 w-4 text-emerald-500" />
          <h3 className="text-sm font-semibold text-foreground">Regional Settings</h3>
        </div>
        <div className="p-5 space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Display Timezone</p>
            <div className="max-w-sm mt-3">
              <select
                value={timezone}
                onChange={(e) => handleTimezoneChange(e.target.value)}
                className="w-full bg-background border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground italic">
            * Page will reload to apply changes.
          </p>
        </div>
      </div>

      {/* ALM Integration (Admin Only) */}
      {isAdmin && (
        <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
            <LinkIcon className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">ALM Integration (Bloom)</h3>
          </div>
          <div className="p-5 space-y-4">
            {almLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                    Bloom URL
                  </label>
                  <input
                    type="url"
                    value={bloomUrl}
                    onChange={(e) => setBloomUrl(e.target.value)}
                    placeholder="https://bloom.embedlabs.de"
                    className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                    Bloom Access Token
                  </label>
                  <input
                    type="password"
                    value={bloomToken}
                    onChange={(e) => setBloomToken(e.target.value)}
                    placeholder="Enter Bloom API token..."
                    className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors font-mono"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveALM}
                    disabled={almMutation.isPending}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {almMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Integration
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* About */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
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
              <p className="text-xs text-muted-foreground">v{APP_VERSION}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>by</span>
            <a
              href="https://www.embedlabs.de/en"
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
