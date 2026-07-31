import { describe, expect, it } from 'vitest'
import type { TestResult } from '../api/client'
import { summarizeAssertions, summarizeTestCases } from '../lib/testRunAssertions'

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

describe('summarizeTestCases', () => {
  const run = { total_tests: 3, passed_tests: 2, failed_tests: 1, skipped_tests: 0 }

  it('reports the run statistics, not the assertion count', () => {
    // Two test cases carrying four assertions between them must still count as two.
    const rows: Partial<TestResult>[] = [
      { passed: true, assertions: [{ passed: true }, { passed: true }] },
      { passed: false, assertions: [{ passed: true }, { passed: false }] },
    ]

    expect(summarizeTestCases(run, rows as TestResult[])).toEqual({
      total: 3,
      passed: 2,
      failed: 1,
      skipped: 0,
    })
  })

  it('falls back to result rows when the run carries no counters', () => {
    const rows: Partial<TestResult>[] = [
      { passed: true, assertions: [{ passed: true }, { passed: true }] },
      { passed: false, assertions: [{ passed: false }] },
      { passed: true, assertions: [] },
    ]
    const emptyRun = { total_tests: 0, passed_tests: 0, failed_tests: 0, skipped_tests: 0 }

    expect(summarizeTestCases(emptyRun, rows as TestResult[])).toEqual({
      total: 3,
      passed: 2,
      failed: 1,
      skipped: 0,
    })
  })

  it('returns zeros when there is nothing to summarise', () => {
    const emptyRun = { total_tests: 0, passed_tests: 0, failed_tests: 0, skipped_tests: 0 }
    expect(summarizeTestCases(emptyRun, [])).toEqual({
      total: 0,
      passed: 0,
      failed: 0,
      skipped: 0,
    })
  })
})
