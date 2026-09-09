// @vitest-environment jsdom
/**
 * Every lazily-imported route must actually resolve.
 *
 * `lazy(() => import('./pages/Foo'))` is not checked by the type system the way
 * a static import is: a renamed or mistyped module compiles, lints and builds
 * clean, then fails only when a user navigates to that route. This imports each
 * path App.tsx declares and asserts a component comes back.
 *
 * Reads App.tsx through import.meta.glob rather than node:fs, matching the other
 * source-scanning tests here — the UI tsconfig carries no Node types.
 */
import { describe, expect, it } from 'vitest'

const appSources = import.meta.glob('../App.tsx', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

const pageModules = import.meta.glob('../pages/*.tsx')

const declared = [
  ...Object.values(appSources)
    .join('\n')
    .matchAll(/lazy\(\(\) => import\('\.\/pages\/(\w+)'\)\)/g),
].map((m) => m[1])

describe('lazy routes', () => {
  it('declares some', () => {
    // Guards the regex itself: if App.tsx stops matching, the cases below would
    // silently pass by iterating nothing.
    expect(declared.length).toBeGreaterThan(0)
  })

  it.each(declared)('%s resolves to a component', async (name) => {
    const loader = pageModules[`../pages/${name}.tsx`]
    expect(loader, `App.tsx imports ./pages/${name}, which does not exist`).toBeTypeOf('function')

    const mod = (await loader()) as { default?: unknown }
    expect(mod.default, `./pages/${name} has no default export`).toBeTruthy()
  })
})
