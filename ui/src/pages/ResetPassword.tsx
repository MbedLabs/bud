import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useOneTimeToken } from '../hooks/useOneTimeToken'
import { APP_VERSION, authApi, extractApiErrorMessage } from '../api/client'
import { BUD_LOGO_DARK, BUD_LOGO_LIGHT } from '../brandAssets'

export default function ResetPassword() {
  const token = useOneTimeToken()

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!token) {
      setError('Missing password reset token')
      return
    }
    if (newPassword.length < 12) {
      setError('Password must be at least 12 characters long')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const response = await authApi.resetPassword(token, newPassword)
      setMessage(response.message)
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      setError(extractApiErrorMessage(err, 'Unable to reset password'))
    } finally {
      setLoading(false)
    }
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
        {!message && (
          <>
            <h1 className="text-2xl font-bold text-foreground mb-2">Reset Password</h1>
            <p className="text-sm text-muted-foreground mb-6">Set a new password for your Bud account.</p>
          </>
        )}

        {!token && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            This reset link is invalid because no token was provided.
          </div>
        )}

        {message && (
          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-700 text-sm dark:text-green-400">
            {message}
          </div>
        )}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {!message && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={12}
                className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
                placeholder="Enter your new password"
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
                placeholder="Repeat your new password"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !token}
              className="w-full py-2.5 px-4 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Resetting password...' : 'Reset Password'}
            </button>
          </form>
        )}

        <div className="mt-6 text-center text-sm">
          <Link to="/login" className="text-primary hover:text-primary/80 font-medium transition-colors">
            Back to Login
          </Link>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm text-lime-100/70">Bud TMP</p>
          <p className="text-xs text-lime-200/50 mt-1">v{APP_VERSION}</p>
          <a
            href="https://www.embedlabs.net"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-lime-200/60 mt-1 inline-block hover:text-lime-100 transition-colors"
          >
            by EmbedLabs
          </a>
        </div>
      </div>
    </div>
  )
}
