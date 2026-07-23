import { useEffect, useState } from 'react'

/**
 * Reads a one-time token (invite / verify / reset / email-change) from the URL
 * fragment, which browsers never send to the server — so the token stays out of
 * request targets, proxy logs, and the Referer header. Falls back to the query
 * string for links generated before the switch to fragments. The token is read
 * once, then stripped from the address bar via history.replaceState so it is not
 * kept in history or leaked on subsequent navigations.
 */
export function useOneTimeToken(): string {
  const [token] = useState(() => {
    const loc = typeof window !== 'undefined' ? window.location : undefined
    if (!loc) return ''
    const fromHash = new URLSearchParams((loc.hash || '').replace(/^#/, '')).get('token')
    const fromQuery = new URLSearchParams(loc.search || '').get('token')
    return fromHash || fromQuery || ''
  })

  useEffect(() => {
    const loc = typeof window !== 'undefined' ? window.location : undefined
    if (loc && (loc.hash || (loc.search || '').includes('token='))) {
      window.history.replaceState(null, '', loc.pathname)
    }
  }, [])

  return token
}
