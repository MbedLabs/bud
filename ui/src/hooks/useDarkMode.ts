import { useEffect, useState } from 'react'

/** Dark mode on or off: the stored choice, else the system preference; applied to the page and remembered. */
export function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('bud-theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('bud-theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, setDark] as const
}
