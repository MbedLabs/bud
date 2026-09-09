import { describe, expect, it } from 'vitest'

/**
 * Every custom bg-gradient-* class must exist in this app's tailwind config.
 *
 * Bud and Bloom define different gradient names, so a class copied from one repo
 * into the other produces no CSS at all — Tailwind silently emits nothing for a
 * name it does not know. The element then renders with no background and no
 * error: build, lint and tests all stay green. That is how the setup screen
 * shipped to Bloom with an invisible submit button.
 *
 * Reads the sources through import.meta.glob rather than node:fs, matching the
 * other source-scanning tests here — the UI tsconfig carries no Node types.
 */
const sources = import.meta.glob('../{pages,components}/**/*.tsx', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

const configs = import.meta.glob('../../tailwind.config.js', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

/** Built-in Tailwind gradient direction utilities, which need no definition. */
const BUILT_IN_DIRECTIONS = /^to-(t|tr|r|br|b|bl|l|tl)$/

describe('custom gradient classes', () => {
  it('are all defined in tailwind.config.js', () => {
    const config = Object.values(configs).join('\n')
    expect(config).not.toHaveLength(0)

    const defined = new Set(
      [...config.matchAll(/"gradient-([a-z0-9-]+)"\s*:/g)].map((m) => m[1])
    )

    const undefinedUses: string[] = []
    for (const [path, source] of Object.entries(sources)) {
      for (const match of source.matchAll(/\bbg-gradient-([a-z0-9-]+)/g)) {
        const name = match[1]
        if (BUILT_IN_DIRECTIONS.test(name)) continue
        if (!defined.has(name)) undefinedUses.push(`${path}: bg-gradient-${name}`)
      }
    }

    expect(undefinedUses).toEqual([])
  })
})
