import { useEffect, useState } from 'react'

/**
 * A value that only changes once it has stopped changing for `delay` ms.
 *
 * The test-run search box keeps every keystroke on screen so typing stays
 * responsive. The server does not need to hear about each one - typing a suite
 * name would otherwise be a query per character, most of them already stale by
 * the time they land.
 */
export function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return settled
}
