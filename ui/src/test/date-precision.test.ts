// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { formatDateTime } from './date-utils'

describe('Bud shows times to the second', () => {
  beforeEach(() => {
    localStorage.setItem('bud-timezone', 'UTC')
  })

  afterEach(() => {
    localStorage.removeItem('bud-timezone')
  })

  it('keeps the second', () => {
    expect(formatDateTime('2026-09-27T12:34:56Z')).toContain('12:34:56')
  })
})
