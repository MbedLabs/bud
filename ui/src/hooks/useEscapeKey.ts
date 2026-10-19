import { useEffect, useRef } from 'react'

/** Calls `onEscape` when Escape is pressed anywhere on the page while `active` is true. */
export function useEscapeKey(onEscape: () => void, active = true) {
  const handler = useRef(onEscape)

  useEffect(() => {
    handler.current = onEscape
  }, [onEscape])

  useEffect(() => {
    if (!active) return
    const listener = (event: KeyboardEvent) => {
      if (event.key === 'Escape') handler.current()
    }
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [active])
}
