import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { APP_VERSION, extractApiErrorMessage, setupApi } from '../api/client'
import { BUD_LOGO_DARK, BUD_LOGO_LIGHT } from '../brandAssets'

/**
 * First-run administrator creation.
 *
 * Reachable only while the instance has no users. A packaged install has no way
 * to ask for an email address at install time, so the first visitor supplies
 * their own here instead of hunting for a generated password on disk.
 */
export default function Setup() {
  const navigate = useNavigate()

  const [setupRequired, setSetupRequired] = useState<boolean | null>(null)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false

    setupApi
      .getStatus()
      .then((status) => {
        if (!cancelled) setSetupRequired(status.setup_required)
      })
      .catch(() => {
        // An instance that cannot answer is not one we should offer to claim.
        if (!cancelled) setSetupRequired(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError('')

    if (password.length < 12) {
      setSubmitError('Password must be at least 12 characters long')
      return
    }
    if (password !== confirmPassword) {
      setSubmitError('Passwords do not match')
      return
    }

    setSubmitting(true)
    try {
      await setupApi.createFirstAdmin(email, password, fullName)
      navigate('/login', { replace: true })
    } catch (err: unknown) {
      setSubmitError(extractApiErrorMessage(err, 'Unable to create the administrator account'))
    } finally {
      setSubmitting(false)
    }
  }

  if (setupRequired === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-auth">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!setupRequired) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-auth p-4">
      <div className="w-full max-w-md bg-card rounded-2xl shadow-2xl p-8 border border-border">
        <div className="flex flex-col items-center mb-6">
          <img
            src={BUD_LOGO_DARK}
            alt="Bud by EmbedLabs"
            className="h-16 w-auto max-w-full object-contain mb-3 hidden dark:block"
          />
          <img
            src={BUD_LOGO_LIGHT}
            alt="Bud by EmbedLabs"
            className="h-16 w-auto max-w-full object-contain mb-3 dark:hidden"
          />
        </div>

        <h1 className="text-2xl font-bold text-foreground mb-2">Welcome to Bud</h1>
        <p className="text-sm text-muted-foreground mb-6">
          This instance has no accounts yet. Create the administrator to get started.
        </p>

        {submitError && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {submitError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="Your name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={12}
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="At least 12 characters"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={12}
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="Repeat your password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 px-4 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Creating administrator...' : 'Create Administrator'}
          </button>
        </form>

        <div className="text-center mt-6">
          <p className="text-sm text-lime-100/70">Bud TMP</p>
          <p className="text-xs text-lime-200/50 mt-1">v{APP_VERSION}</p>
          <a
            href="https://www.embedlabs.net"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-lime-200/60 mt-1 inline-block hover:text-lime-100 transition-colors"
          >
            Powered by EmbedLabs
          </a>
        </div>
      </div>
    </div>
  )
}
