import { describe, expect, it } from 'vitest'

import layoutSource from '../components/Layout.tsx?raw'
import customRunSource from '../pages/CustomRun.tsx?raw'

const CONTAINERS: [string, string][] = [
  ['Layout', layoutSource],
  ['CustomRun', customRunSource],
]

describe.each(CONTAINERS)('%s', (_name, source) => {
  it('themes every scroll container it declares', () => {
    const scrollers = source.match(/className="[^"]*overflow-(?:y-)?auto[^"]*"/g) ?? []
    expect(scrollers.length).toBeGreaterThan(0)
    for (const scroller of scrollers) {
      expect(scroller).toMatch(/themed-scrollbar|sidebar-scrollbar/)
    }
  })
})

describe('main content area', () => {
  it('uses the same theme-aware scrollbar as Bloom', () => {
    expect(layoutSource).toMatch(/<main[^>]*overflow-auto themed-scrollbar/)
  })
})
