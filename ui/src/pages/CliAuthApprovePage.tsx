import { useEffect, useState } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { api, extractApiErrorMessage } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

interface CliSession {
  session_id: string
  client_name: string
  mode: 'callback' | 'code'
  redirect_uri: string | null
  expires_at: string
  consumed: boolean
}

interface CliApproval {
  redirect_to?: string
  exchange_code?: string
  expires_at?: string
}

/** Check that the browser follows only the approved HTTP loopback callback. */
function matchesCallback(redirectTo: string, redirectUri: string | null) {
  if (!redirectUri) return false
  try {
    const target = new URL(redirectTo)
    const original = new URL(redirectUri)
    return target.protocol === 'http:' &&
      ['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname) &&
      /^http:\/\/(?:127\.0\.0\.1|localhost|\[::1\]):\d+(?:[/?]|$)/i.test(redirectTo) &&
      target.username === '' && target.password === '' && target.hash === '' &&
      target.origin === original.origin && target.pathname === original.pathname &&
      target.searchParams.getAll('code').length === 1 && target.searchParams.getAll('state').length === 1
  } catch {
    return false
  }
}

interface ApprovalBodyProps {
  error: string
  cancelled: boolean
  approval: CliApproval | null
  session: CliSession | null
  userName: string | undefined
  busy: boolean
  copyMessage: string
  onApprove: () => void
  onCancel: () => void
  onCopy: () => void
}

/** Render the error, cancellation, one-time code, callback notice or approval request. */
function ApprovalBody({ error, cancelled, approval, session, userName, busy, copyMessage, onApprove, onCancel, onCopy }: Readonly<ApprovalBodyProps>) {
  if (error) {
    return (
      <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive">
        <p>{error}</p>
        <p className="mt-2">Start again from your client to request a new authorization link.</p>
      </div>
    )
  }
  if (cancelled) {
    return <output className="block">Authorization cancelled. You can close this page and return to your client.</output>
  }
  if (approval?.exchange_code) {
    return (
      <div>
        <p>Paste this one-time code into your client or terminal to finish connecting.</p>
        <code className="block my-4 break-all rounded-lg border border-border bg-background p-4 select-all">{approval.exchange_code}</code>
        <p className="text-sm text-muted-foreground mb-4">Expires {new Date(approval.expires_at ?? '').toLocaleString()}.</p>
        <button type="button" onClick={onCopy} className="rounded-lg bg-primary px-4 py-2 text-primary-foreground">Copy code</button>
        {copyMessage && <output className="block mt-2 text-sm">{copyMessage}</output>}
      </div>
    )
  }
  if (approval?.redirect_to) {
    return <output className="block">Returning to your client. You can close this page when it connects.</output>
  }
  if (!session) return <p>Loading...</p>
  return (
    <div>
      <p className="font-semibold text-lg mb-3">{session.client_name}</p>
      <p className="mb-3">This client is requesting access to Bud as {userName}, using your existing permissions.</p>
      <p className="text-sm text-muted-foreground mb-2">{session.mode === 'callback' ? 'Local loopback callback' : 'One-time exchange code'}</p>
      {session.redirect_uri && <p className="text-sm break-all mb-3">{session.redirect_uri}</p>}
      <p className="text-sm text-muted-foreground mb-5">Approve only if you started this request from a client you trust.</p>
      <div className="flex gap-3">
        <button type="button" disabled={busy} onClick={onApprove} className="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">{busy ? 'Approving...' : 'Approve'}</button>
        <button type="button" disabled={busy} onClick={onCancel} className="rounded-lg border border-border px-4 py-2 disabled:opacity-50">Cancel</button>
      </div>
    </div>
  )
}

/** Confirm a client request with the signed-in account's existing Bud permissions. */
export default function CliAuthApprovePage() {
  const { user, isAuthenticated, isLoading } = useAuth()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id') ?? ''
  const validSession = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId)
  const [session, setSession] = useState<CliSession | null>(null)
  const [approval, setApproval] = useState<CliApproval | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [copyMessage, setCopyMessage] = useState('')

  useEffect(() => {
    if (isLoading || !isAuthenticated || !validSession) return
    let active = true
    setSession(null)
    setApproval(null)
    setError('')
    setCancelled(false)
    api.get<CliSession>(`/auth/cli/sessions/${sessionId}`)
      .then(({ data }) => {
        if (!active) return
        if (data.consumed || new Date(data.expires_at).getTime() <= Date.now()) {
          setError('This authorization session has expired or has already been used.')
          return
        }
        setSession(data)
      })
      .catch((reason: unknown) => {
        if (active) setError(extractApiErrorMessage(reason, 'Unable to load this authorization session.'))
      })
    return () => { active = false }
  }, [isAuthenticated, isLoading, sessionId, validSession])

  const approve = async () => {
    if (!session || busy || cancelled) return
    setBusy(true)
    try {
      const { data } = await api.post<CliApproval>('/auth/cli/approve', { session_id: sessionId })
      if (session.mode === 'callback') {
        if (!data.redirect_to || !matchesCallback(data.redirect_to, session.redirect_uri)) {
          throw new Error('The authorization callback is invalid. Start again from your client.')
        }
        setApproval(data)
        window.location.assign(data.redirect_to)
      } else {
        if (!data.exchange_code || !data.expires_at) throw new Error('No authorization code was returned.')
        setApproval(data)
      }
    } catch (reason: unknown) {
      setError(extractApiErrorMessage(reason, 'Unable to approve this authorization session.'))
    } finally {
      setBusy(false)
    }
  }

  const copyCode = async () => {
    if (!approval?.exchange_code) return
    try {
      await navigator.clipboard.writeText(approval.exchange_code)
      setCopyMessage('Code copied.')
    } catch {
      setCopyMessage('Copy is unavailable. Select and copy the code below.')
    }
  }

  if (isLoading) return <p className="p-8 text-foreground">Loading...</p>
  if (validSession && !isAuthenticated) {
    const approvalPath = `/auth/cli?session_id=${sessionId}`
    return <Navigate to={`/login?next=${encodeURIComponent(approvalPath)}`} replace />
  }
  const displayedError = validSession ? error : 'This authorization link is invalid or missing its session.'

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-auth p-4">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-8 shadow-2xl text-foreground">
        <h1 className="text-2xl font-bold mb-4">Connect a client to Bud</h1>
        <ApprovalBody
          error={displayedError}
          cancelled={cancelled}
          approval={approval}
          session={session?.session_id === sessionId ? session : null}
          userName={user?.full_name}
          busy={busy}
          copyMessage={copyMessage}
          onApprove={() => void approve()}
          onCancel={() => setCancelled(true)}
          onCopy={() => void copyCode()}
        />
      </div>
    </main>
  )
}
