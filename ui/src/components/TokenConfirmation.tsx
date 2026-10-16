import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useOneTimeToken } from '../hooks/useOneTimeToken'
import { extractApiErrorMessage } from '../api/client'
import AuthPageShell from './AuthPageShell'

interface TokenConfirmationProps {
  title: string
  subtitle: string
  pendingText: string
  missingTokenText: string
  failureText: string
  confirm: (token: string) => Promise<{ message: string }>
}

/** A page that sends the one-time token from the link to the server and shows the answer. */
export default function TokenConfirmation({
  title,
  subtitle,
  pendingText,
  missingTokenText,
  failureText,
  confirm,
}: Readonly<TokenConfirmationProps>) {
  const token = useOneTimeToken()

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      if (!token) {
        setStatus('error')
        setMessage(missingTokenText)
        return
      }
      setStatus('loading')
      try {
        const response = await confirm(token)
        if (!cancelled) {
          setStatus('success')
          setMessage(response.message)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setStatus('error')
          setMessage(extractApiErrorMessage(err, failureText))
        }
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [token, confirm, missingTokenText, failureText])

  return (
    <AuthPageShell>
      <h1 className="text-2xl font-bold text-foreground mb-2">{title}</h1>
      <p className="text-sm text-muted-foreground mb-6">{subtitle}</p>

      {status === 'loading' && (
        <div className="mb-4 p-3 rounded-lg bg-muted text-muted-foreground text-sm">
          {pendingText}
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
    </AuthPageShell>
  )
}
