import { useState, useEffect } from 'react'
import { Sun, Moon, Monitor, Info, ExternalLink, Link as LinkIcon, Save, Loader2, Globe, HelpCircle, Mail } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { APP_VERSION, authApi, settingsApi, extractApiErrorMessage } from '../api/client'
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
  const { user, refreshUser } = useAuth()
  const isAdmin = user?.role === 'admin'
  const queryClient = useQueryClient()
  
  const [dark, setDark] = useDarkMode()
  const [newEmail, setNewEmail] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [emailMessage, setEmailMessage] = useState<string | null>(null)

  // Timezone state
  const [timezone, setTimezone] = useState(() => localStorage.getItem('bud-timezone') || 'auto')

  // PLM Integration local state
  const [bloomUrl, setBloomUrl] = useState('')
  const [bloomToken, setBloomToken] = useState('')
  const [hasBloomToken, setHasBloomToken] = useState(false)
  const [bloomTokenPrefix, setBloomTokenPrefix] = useState<string | null>(null)

  const { data: almSettings, isLoading: almLoading } = useQuery({
    queryKey: ['almSettings'],
    queryFn: settingsApi.getALM,
    enabled: isAdmin,
  })

  useEffect(() => {
    if (almSettings) {
      setBloomUrl(almSettings.bloom_url)
      setBloomToken('')
      setHasBloomToken(almSettings.has_bloom_token)
      setBloomTokenPrefix(almSettings.bloom_token_prefix)
    }
  }, [almSettings])

  const almMutation = useMutation({
    mutationFn: settingsApi.updateALM,
    onSuccess: (updated) => {
      setHasBloomToken(updated.has_bloom_token)
      setBloomTokenPrefix(updated.bloom_token_prefix)
      setBloomToken('')
      queryClient.invalidateQueries({ queryKey: ['almSettings'] })
      alert('PLM settings updated successfully')
    },
    onError: (error) => {
      alert(`Error updating PLM settings: ${extractApiErrorMessage(error)}`)
    },
  })

  const requestEmailMutation = useMutation({
    mutationFn: () => authApi.requestEmailChange(currentPassword, newEmail),
    onSuccess: async (response) => {
      setEmailMessage(response.message)
      setNewEmail('')
      setCurrentPassword('')
      await refreshUser()
    },
    onError: (error) => {
      setEmailMessage(extractApiErrorMessage(error, 'Failed to request email change'))
    },
  })

  const cancelEmailMutation = useMutation({
    mutationFn: authApi.cancelEmailChange,
    onSuccess: async (response) => {
      setEmailMessage(response.message)
      await refreshUser()
    },
    onError: (error) => {
      setEmailMessage(extractApiErrorMessage(error, 'Failed to cancel email change'))
    },
  })

  const handleSaveALM = () => {
    almMutation.mutate({
      bloom_url: bloomUrl,
      ...(bloomToken ? { bloom_token: bloomToken } : {}),
    })
  }

  const handleClearToken = () => {
    if (!window.confirm('Remove the Bloom result-sync credential from Bud?')) return
    almMutation.mutate({ bloom_url: bloomUrl, clear_bloom_token: true })
  }

  const handleTimezoneChange = (newTz: string) => {
    setTimezone(newTz)
    localStorage.setItem('bud-timezone', newTz)
    window.location.reload()
  }

  return (
    <div className="max-w-2xl space-y-6 animate-fade-in pb-20">
      {/* Account */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
          <Mail className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Account</h3>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label htmlFor="current-email" className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
              Current email
            </label>
            <input
              id="current-email"
              type="email"
              value={user?.email ?? ''}
              readOnly
              className="w-full px-3 py-2 bg-muted/50 border border-input rounded-md text-sm text-foreground"
            />
          </div>

          {user?.pending_email ? (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 space-y-3">
              <div>
                <p className="text-sm font-medium text-foreground">Requested email: {user.pending_email}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {user.email_change_status === 'requested'
                    ? 'Waiting for an administrator to approve or reject this request.'
                    : 'Approved. Use the confirmation link sent to the new address to finish the change.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => cancelEmailMutation.mutate()}
                disabled={cancelEmailMutation.isPending}
                className="text-sm font-medium text-destructive hover:underline disabled:opacity-50"
              >
                {cancelEmailMutation.isPending ? 'Cancelling…' : 'Cancel email change'}
              </button>
            </div>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                setEmailMessage(null)
                requestEmailMutation.mutate()
              }}
            >
              <p className="text-xs text-muted-foreground">
                Request a new login email. An administrator must approve it before Bud sends a confirmation link to the new address.
              </p>
              <div>
                <label htmlFor="new-email" className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                  New email
                </label>
                <input
                  id="new-email"
                  type="email"
                  value={newEmail}
                  onChange={(event) => setNewEmail(event.target.value)}
                  required
                  className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground"
                />
              </div>
              <div>
                <label htmlFor="current-password" className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                  Current password
                </label>
                <input
                  id="current-password"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                  className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground"
                />
              </div>
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={requestEmailMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                >
                  {requestEmailMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Request email change
                </button>
              </div>
            </form>
          )}

          {emailMessage && (
            <p className="text-sm text-muted-foreground" role="status">{emailMessage}</p>
          )}
        </div>
      </div>

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
          <Globe className="h-4 w-4 text-primary" />
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

      {/* PLM Integration (Admin Only) */}
      {isAdmin && (
        <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
            <LinkIcon className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">PLM Integration (Bloom)</h3>
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
                    placeholder="Your Bloom URL"
                    className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors font-mono"
                  />
                </div>
                <div>
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <label htmlFor="bloom-credential" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Bloom Result-Sync Credential
                    </label>
                    <span
                      role="img"
                      aria-label="About the Bloom result-sync credential"
                      title={hasBloomToken
                        ? `A Bloom credential (${bloomTokenPrefix ?? 'blm_sync_'}…) is configured. Enter a new one only to rotate it; Bud never displays the saved secret.`
                        : 'Create a scoped test-results:write credential in Bloom, then paste it here. It cannot access Bloom user, project, or admin APIs.'}
                      className="inline-flex cursor-help text-muted-foreground"
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </span>
                  </div>
                  <input
                    id="bloom-credential"
                    type="password"
                    value={bloomToken}
                    onChange={(e) => setBloomToken(e.target.value)}
                    placeholder="Enter Bloom credential..."
                    className="w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors font-mono"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {hasBloomToken ? 'Configured' : 'Not configured'}
                </p>
                <div className="flex justify-end">
                  {hasBloomToken && (
                    <button
                      type="button"
                      onClick={handleClearToken}
                      disabled={almMutation.isPending}
                      className="mr-3 px-4 py-2 text-sm font-medium text-destructive hover:underline disabled:opacity-50"
                    >
                      Clear Credential
                    </button>
                  )}
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
            <div className="w-10 h-10 rounded-lg overflow-hidden flex items-center justify-center bg-muted">
              <img src="/favicon-96x96.png" alt="Bud" className="w-full h-full object-contain" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Bud TMP</p>
              <p className="text-xs text-muted-foreground">v{APP_VERSION}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>by</span>
            <a
              href="https://www.embedlabs.net"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-medium"
            >
              EmbedLabs
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <div className="mt-3 flex items-center gap-3 text-xs">
            <a
              href="https://github.com/MbedLabs/bud"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-primary/80 transition-colors font-medium"
            >
              Source code
            </a>
            <a
              href="https://github.com/MbedLabs/bud/blob/main/LICENSE"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-primary/80 transition-colors font-medium"
            >
              Source-available license
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
