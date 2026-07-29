import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useOneTimeToken } from '../hooks/useOneTimeToken'
import { APP_VERSION, authApi, extractApiErrorMessage } from '../api/client'
import { BUD_LOGO_DARK, BUD_LOGO_LIGHT } from '../brandAssets'

export default function ConfirmEmailChange() {
  const token = useOneTimeToken()

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      if (!token) {
        setStatus('error')
        setMessage('Missing confirmation token')
        return
      }
      setStatus('loading')
      try {
        const response = await authApi.confirmEmailChange(token)
        if (!cancelled) {
          setStatus('success')
          setMessage(response.message)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setStatus('error')
          setMessage(extractApiErrorMessage(err, 'Email change confirmation failed'))
        }
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [token])

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
        <h1 className="text-2xl font-bold text-foreground mb-2">Confirm Email Change</h1>
        <p className="text-sm text-muted-foreground mb-6">Confirming your new email address for Bud.</p>

        {status === 'loading' && (
          <div className="mb-4 p-3 rounded-lg bg-muted text-muted-foreground text-sm">
            Confirming your new email address...
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
          <p className="text-sm text-lime-100/70">Bud TMP</p>
          <p className="text-xs text-lime-200/50 mt-1">v{APP_VERSION}</p>
        </div>
      </div>
    </div>
  )
}
