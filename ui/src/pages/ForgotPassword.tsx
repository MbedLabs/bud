import { useState } from 'react'
import { Link } from 'react-router'
import { authApi, extractApiErrorMessage } from '../api/client'
import AuthPageShell from '../components/AuthPageShell'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const response = await authApi.forgotPassword(email)
      setMessage(response.message)
    } catch (err: unknown) {
      setError(extractApiErrorMessage(err, 'Unable to process password reset request'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageShell>
      {!message && (
        <>
          <h1 className="text-2xl font-bold text-foreground mb-2">Forgot Password</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Enter your email and we will send a reset link if an account exists.
          </p>
        </>
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
            <label htmlFor="forgot-password-email" className="block text-sm font-medium text-foreground mb-1.5">Email</label>
            <input
              id="forgot-password-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2.5 bg-background border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              placeholder="you@company.com"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Sending reset email...' : 'Send Reset Link'}
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
