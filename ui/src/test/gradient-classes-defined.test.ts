/**
 * Every custom bg-gradient-* class must exist in this app's tailwind config.
 *
 * Bud and Bloom define different gradient names, so a class copied from one
 * repo into the other produces no CSS at all — Tailwind simply emits nothing
 * for a name it does not know. The element then renders with no background
 * and no error, anywhere: build passes, tests pass, lint passes. That is how
 * the Setup screen shipped to Bloom with an invisible button.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(__dirname, '..')
const TAILWIND_CONFIG = join(__dirname, '..', '..', 'tailwind.config.js')

/** Built-in Tailwind gradient direction utilities, which need no definition. */
const BUILT_IN_DIRECTIONS = /^to-(t|tr|r|br|b|bl|l|tl)$/

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return walk(full)
    return /\.(tsx|ts)$/.test(entry) ? [full] : []
  })
}

describe('custom gradient classes', () => {
  it('are all defined in tailwind.config.js', () => {
    const config = readFileSync(TAILWIND_CONFIG, 'utf8')
    const defined = new Set(
      [...config.matchAll(/"gradient-([a-z0-9-]+)"\s*:/g)].map((m) => m[1])
    )

    const undefinedUses: string[] = []
    for (const file of walk(SRC)) {
      const source = readFileSync(file, 'utf8')
      for (const match of source.matchAll(/\bbg-gradient-([a-z0-9-]+)/g)) {
        const name = match[1]
        if (BUILT_IN_DIRECTIONS.test(name)) continue
        if (!defined.has(name)) {
          undefinedUses.push(`${file.replace(SRC, 'src')}: bg-gradient-${name}`)
        }
      }
    }

    expect(undefinedUses).toEqual([])
  })
})
