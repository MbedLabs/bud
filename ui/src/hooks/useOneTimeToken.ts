import { useEffect, useState } from 'react'

/**
 * Reads a one-time token (invite / verify / reset / email-change) from the URL
 * fragment, which browsers never send to the server — so the token stays out of
 * request targets, proxy logs, and the Referer header. Only the fragment is
 * accepted; there is no `?token=` query fallback. The token is read once, then
 * stripped from the address bar via history.replaceState so it is not kept in
 * history or leaked on subsequent navigations.
 */
export function useOneTimeToken(): string {
  const [token] = useState(() => {
    const loc = typeof window !== 'undefined' ? window.location : undefined
    if (!loc) return ''
    return new URLSearchParams((loc.hash || '').replace(/^#/, '')).get('token') || ''
  })

  useEffect(() => {
    const loc = typeof window !== 'undefined' ? window.location : undefined
    if (loc && loc.hash) {
      window.history.replaceState(null, '', loc.pathname)
    }
  }, [])

  return token
}
