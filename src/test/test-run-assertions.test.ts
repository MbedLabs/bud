import { describe, expect, it } from 'vitest'
import type { TestResult } from '../api/client'
import { summarizeAssertions } from '../lib/testRunAssertions'

describe('summarizeAssertions', () => {
  it('returns zeros for empty results', () => {
    expect(summarizeAssertions([])).toEqual({ total: 0, passed: 0, failed: 0 })
  })

  it('counts assertions from nested arrays (passed when passed !== false)', () => {
    const rows: Partial<TestResult>[] = [
      {
        assertions: [
          { passed: true },
          { passed: false },
          {}, // omitted passed → treated as pass
        ],
      },
      {
        assertions: [{ passed: false }],
      },
    ]

    expect(summarizeAssertions(rows as TestResult[])).toEqual({ total: 4, passed: 2, failed: 2 })
  })
})
