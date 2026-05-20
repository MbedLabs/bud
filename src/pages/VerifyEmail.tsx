import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { APP_VERSION, authApi, extractApiErrorMessage } from '../api/client'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const token = useMemo(() => searchParams.get('token') || '', [searchParams])

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      if (!token) {
        setStatus('error')
        setMessage('Missing verification token')
        return
      }
      setStatus('loading')
      try {
        const response = await authApi.verifyEmail(token)
        if (!cancelled) {
          setStatus('success')
          setMessage(response.message)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setStatus('error')
          setMessage(extractApiErrorMessage(err, 'Email verification failed'))
        }
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-900 via-teal-800 to-cyan-900 p-4">
      <div className="w-full max-w-md bg-card rounded-2xl shadow-2xl p-8 border border-border">
        <h1 className="text-2xl font-bold text-foreground mb-2">Verify Email</h1>
        <p className="text-sm text-muted-foreground mb-6">Confirming your email address for Bud.</p>

        {status === 'loading' && (
          <div className="mb-4 p-3 rounded-lg bg-muted text-muted-foreground text-sm">
            Verifying your email address...
          </div>
        )}

        {status === 'success' && (
          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-700 text-sm dark:text-green-400">
            {message}
          </div>
        )}

        {status === 'error' && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {message}
          </div>
        )}

        <div className="mt-6 text-center text-sm">
          <Link to="/login" className="text-primary hover:text-primary/80 font-medium transition-colors">
            Go to Login
          </Link>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm text-teal-200/60">Bud TMP</p>
          <p className="text-xs text-teal-300/50 mt-1">v{APP_VERSION}</p>
          <a
            href="https://www.embedlabs.net"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-teal-300/40 mt-1 inline-block hover:text-teal-200 transition-colors"
          >
            by EmbedLabs
          </a>
        </div>
      </div>
    </div>
  )
}
