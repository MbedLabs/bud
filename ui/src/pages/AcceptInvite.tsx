import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { APP_VERSION, InviteInfoResponse, authApi, extractApiErrorMessage } from '../api/client'

export default function AcceptInvite() {
  const [searchParams] = useSearchParams()
  const token = useMemo(() => searchParams.get('token') || '', [searchParams])

  const [inviteInfo, setInviteInfo] = useState<InviteInfoResponse | null>(null)
  const [loadingInviteInfo, setLoadingInviteInfo] = useState(true)
  const [inviteInfoError, setInviteInfoError] = useState('')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitMessage, setSubmitMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false

    const loadInviteInfo = async () => {
      if (!token) {
        setInviteInfoError('Missing invitation token')
        setLoadingInviteInfo(false)
        return
      }
      try {
        const info = await authApi.getInviteInfo(token)
        if (!cancelled) {
          setInviteInfo(info)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setInviteInfoError(extractApiErrorMessage(err, 'Unable to load invitation details'))
        }
      } finally {
        if (!cancelled) {
          setLoadingInviteInfo(false)
        }
      }
    }

    loadInviteInfo()
    return () => {
      cancelled = true
    }
  }, [token])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError('')
    setSubmitMessage('')

    if (!token) {
      setSubmitError('Missing invitation token')
      return
    }
    if (password.length < 6) {
      setSubmitError('Password must be at least 6 characters long')
      return
    }
    if (password !== confirmPassword) {
      setSubmitError('Passwords do not match')
      return
    }

    setSubmitting(true)
    try {
      const response = await authApi.acceptInvite(token, password)
      setSubmitMessage(response.message)
      setPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      setSubmitError(extractApiErrorMessage(err, 'Unable to accept invitation'))
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = !!inviteInfo?.valid && !submitting

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0a1628] via-[#0c2a5c] to-[#e85d04] p-4">
      <div className="w-full max-w-md bg-card rounded-2xl shadow-2xl p-8 border border-border">
        {!submitMessage && (
          <>
            <h1 className="text-2xl font-bold text-foreground mb-2">Accept Invitation</h1>
            <p className="text-sm text-muted-foreground mb-6">Set your account password to activate Bud access.</p>
          </>
        )}

        {loadingInviteInfo && !submitMessage && (
          <div className="mb-4 p-3 rounded-lg bg-muted text-muted-foreground text-sm">
            Loading invitation details...
          </div>
        )}

        {inviteInfoError && !submitMessage && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {inviteInfoError}
          </div>
        )}

        {inviteInfo && !submitMessage && (
          <div className="mb-4 p-3 rounded-lg bg-muted/40 border border-border text-sm text-foreground">
            <p className="font-medium">{inviteInfo.full_name}</p>
            <p className="text-muted-foreground">{inviteInfo.email}</p>
            {!inviteInfo.valid && (
              <p className="mt-2 text-destructive">
                {inviteInfo.expired ? 'This invitation has expired.' : 'This invitation has already been used.'}
              </p>
            )}
          </div>
        )}

        {submitMessage && (
          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-700 text-sm dark:text-green-400">
            {submitMessage}
          </div>
        )}

        {submitError && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {submitError}
          </div>
        )}

        {!submitMessage && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">New Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
                placeholder="Choose a password"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
                placeholder="Repeat your password"
              />
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-primary to-[#e85d04] text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Accepting invitation...' : 'Accept Invitation'}
            </button>
          </form>
        )}

        <div className="mt-6 text-center text-sm">
          <Link to="/login" className="text-primary hover:text-primary/80 font-medium transition-colors">
            Back to Login
          </Link>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm text-blue-100/70">Bud TMP</p>
          <p className="text-xs text-blue-200/50 mt-1">v{APP_VERSION}</p>
          <a
            href="https://www.embedlabs.net"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-orange-200/50 mt-1 inline-block hover:text-orange-100 transition-colors"
          >
            by EmbedLabs
          </a>
        </div>
      </div>
    </div>
  )
}
