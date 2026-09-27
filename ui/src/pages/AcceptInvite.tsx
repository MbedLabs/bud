import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useOneTimeToken } from '../hooks/useOneTimeToken'
import { InviteInfoResponse, authApi, extractApiErrorMessage } from '../api/client'
import AuthPageShell from '../components/AuthPageShell'
import { newPasswordProblem } from '../lib/passwordRules'

export default function AcceptInvite() {
  const token = useOneTimeToken()

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
    const passwordProblem = newPasswordProblem(password, confirmPassword)
    if (passwordProblem) {
      setSubmitError(passwordProblem)
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
    <AuthPageShell>
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
              minLength={12}
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
              minLength={12}
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="Repeat your password"
            />
          </div>

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full py-2.5 px-4 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
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

    </AuthPageShell>
  )
}
