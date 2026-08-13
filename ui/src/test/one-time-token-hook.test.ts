// @vitest-environment jsdom
/**
 * Where a one-time token may be read from, and where it must not be.
 *
 * Invitations, verification links, password resets and email-change
 * confirmations all carry a single-use token in the URL *fragment*. Browsers
 * never send a fragment to the server, so the token stays out of request
 * targets, proxy and access logs, and the Referer header sent to any third
 * party the page later links to. A query-string token would appear in all of
 * them.
 *
 * The screen tests exercise the pages; this exercises the rule itself, because
 * the rule is a negative one - "never read ?token=" - and a page test that only
 * ever puts a token in the fragment cannot tell you whether the query string
 * would have been read had one been there.
 */
import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useOneTimeToken } from '../hooks/useOneTimeToken'

/** Put the browser at a URL, the way a link from an email would. */
function goTo(url: string) {
  window.history.replaceState(null, '', url)
}

beforeEach(() => goTo('/'))
afterEach(() => goTo('/'))

describe('reading a one-time token', () => {
  it('reads it from the fragment', () => {
    goTo('/accept-invite#token=abc123')

    const { result } = renderHook(() => useOneTimeToken())

    expect(result.current).toBe('abc123')
  })

  it('refuses a token in the query string', () => {
    goTo('/accept-invite?token=abc123')

    const { result } = renderHook(() => useOneTimeToken())

    // A query-string token reaches the server on every request, so it lands in
    // access logs and in the Referer header. There is no fallback to it.
    expect(result.current).toBe('')
  })

  it('takes the fragment even when a query token is also present', () => {
    goTo('/accept-invite?token=from-the-query#token=from-the-fragment')

    const { result } = renderHook(() => useOneTimeToken())

    expect(result.current).toBe('from-the-fragment')
  })

  it('ignores other fragment parameters', () => {
    goTo('/accept-invite#other=abc123')

    const { result } = renderHook(() => useOneTimeToken())

    expect(result.current).toBe('')
  })

  it('reads nothing from a bare URL', () => {
    goTo('/accept-invite')

    const { result } = renderHook(() => useOneTimeToken())

    expect(result.current).toBe('')
  })
})

describe('what is left in the address bar', () => {
  it('strips the token once it has been read', () => {
    goTo('/accept-invite#token=abc123')

    renderHook(() => useOneTimeToken())

    // Left in place it would sit in the address bar, in browser history, and
    // in the Referer of anything the page navigates to next.
    expect(window.location.hash).toBe('')
    expect(window.location.pathname).toBe('/accept-invite')
  })

  it('keeps the token it already read after clearing the URL', () => {
    goTo('/reset-password#token=abc123')

    const { result, rerender } = renderHook(() => useOneTimeToken())
    rerender()

    // The form still has to submit it, so it is held in state rather than
    // re-read from a URL that no longer has it.
    expect(result.current).toBe('abc123')
    expect(window.location.hash).toBe('')
  })

  it('leaves a URL with no fragment alone', () => {
    goTo('/reset-password?next=/dashboard')

    renderHook(() => useOneTimeToken())

    expect(window.location.search).toBe('?next=/dashboard')
  })
})
