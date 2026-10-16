import SelectField from '../components/SelectField'
import { useState, useEffect, useRef } from 'react'
import { Sun, Moon, Monitor, Info, ExternalLink, Link as LinkIcon, Save, Loader2, Globe, HelpCircle, Mail, Image as ImageIcon, X } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { APP_VERSION, authApi, settingsApi, companyLogoApi, extractApiErrorMessage, type User } from '../api/client'
import ProfilePicture from '../components/ProfilePicture'
import { useAuth } from '../contexts/AuthContext'
import { can } from '../lib/access'
import NotificationChannels from '../components/NotificationChannels'
import { useDarkMode } from '../hooks/useDarkMode'

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

export default function Settings() {
  const { user, refreshUser } = useAuth()
  const isAdmin = user?.role === 'admin'
  const canEditSettings = can(user, 'settings.edit')
  const [pictureFile, setPictureFile] = useState<File | null>(null)
  const pictureInput = useRef<HTMLInputElement>(null)
  const [pictureBusy, setPictureBusy] = useState(false)
  const [pictureMessage, setPictureMessage] = useState('')
  const [savedPictureUser, setSavedPictureUser] = useState<User | null>(null)
  const pictureUser = savedPictureUser?.id === user?.id ? savedPictureUser : user

  const handleRemovePicture = async () => {
    setPictureBusy(true)
    setPictureMessage('')
    try {
      setSavedPictureUser(await authApi.deleteProfilePicture())
      setPictureFile(null)
      await refreshUser()
      setPictureMessage('Profile picture removed.')
    } catch (error) {
      setPictureMessage(extractApiErrorMessage(error, 'Could not remove the picture.'))
    } finally {
      setPictureBusy(false)
    }
  }

  const handleUploadPicture = async () => {
    if (!pictureFile) return
    setPictureBusy(true)
    setPictureMessage('')
    try {
      setSavedPictureUser(await authApi.setProfilePicture(pictureFile))
      setPictureFile(null)
      await refreshUser()
      setPictureMessage('Profile picture updated.')
    } catch (error) {
      setPictureMessage(extractApiErrorMessage(error, 'Could not upload the picture.'))
    } finally {
      setPictureBusy(false)
    }
  }
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const logoInput = useRef<HTMLInputElement>(null)
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [logoBusy, setLogoBusy] = useState(false)
  const [logoMessage, setLogoMessage] = useState('')
  const logoPreviewRequest = useRef(0)

  const refreshLogoPreview = async () => {
    const request = ++logoPreviewRequest.current
    try {
      const blob = await companyLogoApi.fetchLogo()
      if (request !== logoPreviewRequest.current) return
      if (!blob) {
        setLogoUrl(null)
        return
      }
      const url = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => typeof reader.result === 'string'
          ? resolve(reader.result)
          : reject(new Error('Could not load the logo preview.'))
        reader.onerror = () => reject(new Error('Could not load the logo preview.'))
        reader.readAsDataURL(blob)
      })
      if (request === logoPreviewRequest.current) setLogoUrl(url)
    } catch {
      if (request === logoPreviewRequest.current) setLogoMessage('Could not load the logo preview.')
    }
  }

  useEffect(() => {
    if (!canEditSettings) return
    void refreshLogoPreview()
    return () => { logoPreviewRequest.current += 1 }
  }, [canEditSettings])

  const handleUploadLogo = async () => {
    if (!logoFile) return
    setLogoBusy(true)
    setLogoMessage('')
    try {
      await companyLogoApi.setLogo(logoFile)
      setLogoFile(null)
      setLogoMessage('Logo updated.')
      await refreshLogoPreview()
    } catch (err) {
      setLogoMessage(extractApiErrorMessage(err, 'Could not upload the logo.'))
    } finally {
      setLogoBusy(false)
    }
  }

  const handleRemoveLogo = async () => {
    setLogoBusy(true)
    setLogoMessage('')
    try {
      await companyLogoApi.deleteLogo()
      logoPreviewRequest.current += 1
      setLogoUrl(null)
      setLogoMessage('Logo removed.')
    } catch (err) {
      setLogoMessage(extractApiErrorMessage(err, 'Could not remove the logo.'))
    } finally {
      setLogoBusy(false)
    }
  }

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

  const { data: plmSettings, isLoading: plmLoading } = useQuery({
    queryKey: ['plmSettings'],
    queryFn: settingsApi.getPLM,
    enabled: canEditSettings,
  })

  useEffect(() => {
    if (plmSettings) {
      setBloomUrl(plmSettings.bloom_url)
      setBloomToken('')
      setHasBloomToken(plmSettings.has_bloom_token)
      setBloomTokenPrefix(plmSettings.bloom_token_prefix)
    }
  }, [plmSettings])

  const plmMutation = useMutation({
    mutationFn: settingsApi.updatePLM,
    onSuccess: (updated) => {
      setHasBloomToken(updated.has_bloom_token)
      setBloomTokenPrefix(updated.bloom_token_prefix)
      setBloomToken('')
      queryClient.invalidateQueries({ queryKey: ['plmSettings'] })
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

  const handleSavePLM = () => {
    plmMutation.mutate({
      bloom_url: bloomUrl,
      ...(bloomToken ? { bloom_token: bloomToken } : {}),
    })
  }

  const handleClearToken = () => {
    if (!window.confirm('Remove the Bloom result-sync credential from Bud?')) return
    plmMutation.mutate({ bloom_url: bloomUrl, clear_bloom_token: true })
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
          <div className="flex items-center gap-4">
            <div className="group/image relative shrink-0">
              <ProfilePicture own user={pictureUser} className="w-16 h-16" />
              {pictureUser?.has_profile_picture && (
                <button type="button" aria-label="Remove profile picture" title="Remove profile picture"
                  onClick={handleRemovePicture} disabled={pictureBusy}
                  className="absolute -right-2 -top-2 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card text-red-500 opacity-0 transition-opacity group-hover/image:opacity-100 group-focus-within/image:opacity-100 [@media(hover:none)]:opacity-100 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-wait disabled:text-muted-foreground">
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
            <div className="space-y-2 flex-1">
              <label htmlFor="profile-picture" className="block text-sm font-medium text-foreground">Profile picture</label>
              <p className="text-xs text-muted-foreground">PNG, JPEG or WebP, up to 2 MB.</p>
              <div className="flex min-w-0 flex-wrap items-center gap-3">
                <input ref={pictureInput} id="profile-picture" type="file" accept="image/png,image/jpeg,image/webp" disabled={pictureBusy}
                  onChange={event => {
                    setPictureFile(event.target.files?.[0] ?? null)
                    event.target.value = ''
                  }}
                  className="hidden" />
                <button type="button" onClick={() => pictureInput.current?.click()} disabled={pictureBusy}
                  className="shrink-0 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50">
                  Choose file
                </button>
                <span aria-live="polite" title={pictureFile?.name}
                  className="max-w-40 truncate text-xs text-muted-foreground">
                  {pictureFile?.name ?? 'No file selected'}
                </span>
                <button type="button" onClick={handleUploadPicture} disabled={!pictureFile || pictureBusy}
                  className="inline-flex shrink-0 items-center gap-2 px-3 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
                  {pictureBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Upload
                </button>
              </div>
              {pictureMessage && <output className="block text-sm text-muted-foreground">{pictureMessage}</output>}
            </div>
          </div>
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
                    : user.email_change_status === 'awaiting_current_confirmation'
                      ? 'Use the authorization link sent to your current address before Bud contacts the new address.'
                      : 'Current address authorized. Use the verification link sent to the new address to finish the change.'}
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
                {isAdmin
                  ? 'Enter a new login email. Bud sends an authorization link to your current email first, then verifies the new address.'
                  : 'Request a new login email. An administrator must approve it before Bud sends a confirmation link to the new address.'}
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
                  {requestEmailMutation.isPending
                    ? (isAdmin ? 'Sending…' : 'Requesting…')
                    : (isAdmin ? 'Send authorization email' : 'Request email change')}
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
              <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-xs transition-transform duration-200 ${
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
              <SelectField
                value={timezone}
                onChange={(e) => handleTimezoneChange(e.target.value)}
                className="w-full bg-background border border-input rounded-md px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
              >
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </SelectField>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground italic">
            * Page will reload to apply changes.
          </p>
        </div>
      </div>

      {canEditSettings && (
        <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
            <LinkIcon className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Bloom PLM Integration</h3>
          </div>
          <div className="p-5 space-y-4">
            {plmLoading ? (
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
                      disabled={plmMutation.isPending}
                      className="mr-3 px-4 py-2 text-sm font-medium text-destructive hover:underline disabled:opacity-50"
                    >
                      Clear Credential
                    </button>
                  )}
                  <button
                    onClick={handleSavePLM}
                    disabled={plmMutation.isPending}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {plmMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Integration
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {canEditSettings && <NotificationChannels />}

      {canEditSettings && (
        <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden border-primary/20">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-primary/5">
            <ImageIcon className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Company logo</h3>
          </div>
          <div className="p-5 space-y-4">
            <p className="text-xs text-muted-foreground">
              Upload your company logo (PNG, JPEG, GIF or WebP, up to 2 MB). It appears top-left on
              generated PDF reports, alongside the EmbedLabs tamper-evidence footer, which always
              stays.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              {logoUrl ? (
              <div className="group/image relative inline-block shrink-0">
                <img
                  src={logoUrl}
                  alt="Company logo"
                  className="h-16 w-auto max-w-[220px] object-contain rounded border border-border bg-muted/30 p-2"
                />
                <button type="button" aria-label="Remove company logo" title="Remove company logo"
                  onClick={handleRemoveLogo} disabled={logoBusy}
                  className="absolute -right-2 -top-2 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card text-red-500 opacity-0 transition-opacity group-hover/image:opacity-100 group-focus-within/image:opacity-100 [@media(hover:none)]:opacity-100 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-wait disabled:text-muted-foreground">
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            ) : (
              <p className="text-xs italic text-muted-foreground">No company logo set yet.</p>
              )}
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
              <input
                ref={logoInput}
                type="file"
                aria-label="Company logo file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                onChange={(e) => {
                  setLogoFile(e.target.files?.[0] ?? null)
                  e.target.value = ''
                }}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => logoInput.current?.click()}
                disabled={logoBusy}
                className="shrink-0 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
              >
                Choose file
              </button>
              <span aria-live="polite" title={logoFile?.name}
                className="max-w-40 truncate text-xs text-muted-foreground">
                {logoFile?.name ?? 'No file selected'}
              </span>
              <button
                type="button"
                onClick={handleUploadLogo}
                disabled={!logoFile || logoBusy}
                className="inline-flex shrink-0 items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {logoBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Upload
              </button>
              </div>
            </div>
            {logoMessage && (
              <output className="block text-sm text-muted-foreground">{logoMessage}</output>
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
          <div className="flex items-center text-xs text-muted-foreground">
            <a
              href="https://www.embedlabs.net"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-medium"
            >
              Powered by EmbedLabs
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
