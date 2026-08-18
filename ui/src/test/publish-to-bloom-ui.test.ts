import { describe, expect, it } from 'vitest'

import detailSource from '../pages/TestRunDetail.tsx?raw'

describe('Publish to Bloom', () => {
  it('does not ask the reader to choose a project prefix', () => {
    expect(detailSource).not.toContain('Project prefix, e.g. VCU')
    expect(detailSource).not.toContain('aria-label="Bloom project prefix"')
  })

  it('lets a completed legacy run ask Bud to generate its missing reports', () => {
    expect(detailSource).not.toContain('Bud will generate the report before publishing')
    expect(detailSource).not.toContain('Bud derives the project from this run')
  })
})
