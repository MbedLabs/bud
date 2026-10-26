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
  created_at: string
  consumed: boolean
  request_code: string
}

interface CliApproval {
  redirect_to?: string
  exchange_code?: string
  expires_at?: string
}

interface CliDenial {
  redirect_to?: string
}

type Denied = 'returning' | 'ended' | null

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]'])
const LOOPBACK_PREFIX = /^http:\/\/(?:127\.0\.0\.1|localhost|\[::1\]):\d+(?:[/?]|$)/i
const CODE_MODE_OFF = 'Code sign-in is turned off on this instance. Use callback mode.'
const WARNING = 'rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300'

/** Check that a target is an HTTP loopback URL on the stored callback's origin and path, without credentials. */
function onStoredCallback(target: URL, redirectTo: string, original: URL) {
  return target.protocol === 'http:' &&
    LOOPBACK_HOSTS.has(target.hostname) &&
    LOOPBACK_PREFIX.test(redirectTo) &&
    target.username === '' && target.password === '' && target.hash === '' &&
    target.origin === original.origin && target.pathname === original.pathname
}

/** Check that the browser follows only the approved HTTP loopback callback. */
function matchesCallback(redirectTo: string, redirectUri: string | null) {
  if (!redirectUri) return false
  try {
    const target = new URL(redirectTo)
    return onStoredCallback(target, redirectTo, new URL(redirectUri)) &&
      target.searchParams.getAll('code').length === 1 && target.searchParams.getAll('state').length === 1
  } catch {
    return false
  }
}

/** Check that a denial returns to the stored loopback callback with only access_denied and the state. */
function matchesDenial(redirectTo: string, redirectUri: string | null) {
  if (!redirectUri) return false
  try {
    const target = new URL(redirectTo)
    const errors = target.searchParams.getAll('error')
    return onStoredCallback(target, redirectTo, new URL(redirectUri)) &&
      !redirectTo.includes('#') &&
      errors.length === 1 && errors[0] === 'access_denied' &&
      target.searchParams.getAll('state').length === 1 &&
      !target.searchParams.has('code')
  } catch {
    return false
  }
}

/** Return whether a failed request was answered with 403 Forbidden. */
function isForbidden(reason: unknown) {
  return (reason as { response?: { status?: number } }).response?.status === 403
}

/** Format a UTC timestamp from the API in the browser's locale. */
function localTime(value: string) {
  return new Date(value).toLocaleString()
}

interface DenyButtonProps {
  busy: boolean
  onDeny: () => void
}

/** Render the Deny action that ends the request on the server. */
function DenyButton({ busy, onDeny }: Readonly<DenyButtonProps>) {
  return (
    <button type="button" disabled={busy} onClick={onDeny} className="rounded-lg border border-border px-4 py-2 disabled:opacity-50">Deny</button>
  )
}

interface PendingRequestProps {
  session: CliSession
  userName: string | undefined
  userEmail: string | undefined
  busy: boolean
  onApprove: () => void
  onDeny: () => void
}

/** Render the request code, client, account, times, warnings and the Approve and Deny actions. */
function PendingRequest({ session, userName, userEmail, busy, onApprove, onDeny }: Readonly<PendingRequestProps>) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">Request code</p>
      <p className="font-mono text-3xl font-bold tracking-widest">{session.request_code}</p>
      <p className="text-sm mb-4">It must match the code your client shows. If it does not, deny this request.</p>
      <p className="text-sm text-muted-foreground">Client name, as given by the requesting client (not verified)</p>
      <p className="font-semibold text-lg mb-3 break-all">{session.client_name}</p>
      <p className="mb-3">Approving signs this client in to Bud as {userName} ({userEmail}), with your full permissions.</p>
      <p className="text-sm text-muted-foreground mb-1">{session.mode === 'callback' ? 'Local loopback callback' : 'One-time exchange code'}</p>
      {session.redirect_uri && <p className="text-sm break-all mb-3">{session.redirect_uri}</p>}
      <p className="text-sm mb-3">Requested {localTime(session.created_at)}. Expires {localTime(session.expires_at)}.</p>
      <p className={`${WARNING} mb-3`}>Approve only a sign-in you started yourself, on your own computer, in the last few minutes.</p>
      {session.mode === 'code' && (
        <p className={`${WARNING} mb-3`}>Code sign-in: after you approve, this page shows a one-time code. Anyone who has that code can sign in to Bud as you until it expires.</p>
      )}
      <div className="flex gap-3 mt-5">
        <button type="button" disabled={busy} onClick={onApprove} className="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">{busy ? 'Working...' : 'Approve'}</button>
        <DenyButton busy={busy} onDeny={onDeny} />
      </div>
    </div>
  )
}

interface ApprovalBodyProps {
  error: string
  blocked: string
  denied: Denied
  approval: CliApproval | null
  session: CliSession | null
  userName: string | undefined
  userEmail: string | undefined
  busy: boolean
  copyMessage: string
  onApprove: () => void
  onDeny: () => void
  onCopy: () => void
}

/** Render the error, denial, blocked request, one-time code, callback notice or approval request. */
function ApprovalBody({ error, blocked, denied, approval, session, userName, userEmail, busy, copyMessage, onApprove, onDeny, onCopy }: Readonly<ApprovalBodyProps>) {
  if (error) {
    return (
      <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive">
        <p>{error}</p>
        <p className="mt-2">Start again from your client to request a new authorization link.</p>
      </div>
    )
  }
  if (denied === 'returning') {
    return <output className="block">Sign-in request denied. Returning to your client.</output>
  }
  if (denied === 'ended') {
    return <output className="block">Sign-in request denied. This link no longer works. You can close this page.</output>
  }
  if (blocked) {
    return (
      <div>
        <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive mb-4">{blocked}</div>
        <p className="mb-4">You can still deny this request so that its link stops working.</p>
        <DenyButton busy={busy} onDeny={onDeny} />
      </div>
    )
  }
  if (approval?.exchange_code) {
    return (
      <div>
        <p>Paste this code only into the client where you started this sign-in. Never send it to anyone.</p>
        <code className="block my-4 break-all rounded-lg border border-border bg-background p-4 select-all">{approval.exchange_code}</code>
        <p className="text-sm text-muted-foreground mb-4">Expires {localTime(approval.expires_at ?? '')}.</p>
        <button type="button" onClick={onCopy} className="rounded-lg bg-primary px-4 py-2 text-primary-foreground">Copy code</button>
        {copyMessage && <output className="block mt-2 text-sm">{copyMessage}</output>}
      </div>
    )
  }
  if (approval?.redirect_to) {
    return <output className="block">Returning to your client. You can close this page when it connects.</output>
  }
  if (!session) return <p>Loading...</p>
  return <PendingRequest session={session} userName={userName} userEmail={userEmail} busy={busy} onApprove={onApprove} onDeny={onDeny} />
}

/** Confirm or deny a client request with the signed-in account's existing Bud permissions. */
export default function CliAuthApprovePage() {
  const { user, isAuthenticated, isLoading } = useAuth()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id') ?? ''
  const validSession = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId)
  const [session, setSession] = useState<CliSession | null>(null)
  const [approval, setApproval] = useState<CliApproval | null>(null)
  const [error, setError] = useState('')
  const [blocked, setBlocked] = useState('')
  const [busy, setBusy] = useState(false)
  const [denied, setDenied] = useState<Denied>(null)
  const [copyMessage, setCopyMessage] = useState('')

  useEffect(() => {
    if (isLoading || !isAuthenticated || !validSession) return
    let active = true
    setSession(null)
    setApproval(null)
    setError('')
    setBlocked('')
    setDenied(null)
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
        if (!active) return
        if (isForbidden(reason)) {
          setBlocked(extractApiErrorMessage(reason, CODE_MODE_OFF))
          return
        }
        setError(extractApiErrorMessage(reason, 'Unable to load this authorization session.'))
      })
    return () => { active = false }
  }, [isAuthenticated, isLoading, sessionId, validSession])

  const approve = async () => {
    if (!session || busy || denied) return
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

  const deny = async () => {
    if (busy || denied) return
    setBusy(true)
    try {
      const { data } = await api.post<CliDenial>('/auth/cli/deny', { session_id: sessionId })
      if (data.redirect_to && matchesDenial(data.redirect_to, session?.redirect_uri ?? null)) {
        setDenied('returning')
        window.location.assign(data.redirect_to)
      } else {
        setDenied('ended')
      }
    } catch (reason: unknown) {
      setError(extractApiErrorMessage(reason, 'Unable to deny this authorization session.'))
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
          blocked={blocked}
          denied={denied}
          approval={approval}
          session={session?.session_id === sessionId ? session : null}
          userName={user?.full_name}
          userEmail={user?.email}
          busy={busy}
          copyMessage={copyMessage}
          onApprove={() => void approve()}
          onDeny={() => void deny()}
          onCopy={() => void copyCode()}
        />
      </div>
    </main>
  )
}
