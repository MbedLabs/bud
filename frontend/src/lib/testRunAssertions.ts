import type { TestResult } from '../api/client'

interface AssertionShape {
  passed?: boolean
}

/** Aggregates flattened assertion rows from persisted test results (used by TestRunDetail summary tiles). */
export function summarizeAssertions(results: TestResult[]): {
  total: number
  passed: number
  failed: number
} {
  return results.reduce(
    (summary, result) => {
      const assertions = (result.assertions as AssertionShape[] | null) || []
      assertions.forEach((assertion) => {
        summary.total += 1
        if (assertion.passed !== false) summary.passed += 1
        else summary.failed += 1
      })
      return summary
    },
    { total: 0, passed: 0, failed: 0 },
  )
}
