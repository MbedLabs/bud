import type { TestResult } from '../api/client'

interface AssertionShape {
  passed?: boolean
}

interface TestCaseCountsSource {
  total_tests: number
  passed_tests: number
  failed_tests: number
  skipped_tests: number
}

/**
 * Aggregates test-case counts, which are distinct from assertion counts: one test
 * case usually carries several assertions. Prefers the run's stored statistics and
 * falls back to the loaded result rows for runs recorded without those counters.
 */
export function summarizeTestCases(
  run: TestCaseCountsSource,
  results: TestResult[],
): {
  total: number
  passed: number
  failed: number
  skipped: number
} {
  if (run.total_tests > 0) {
    return {
      total: run.total_tests,
      passed: run.passed_tests,
      failed: run.failed_tests,
      skipped: run.skipped_tests,
    }
  }

  const passed = results.filter((result) => result.passed).length
  return {
    total: results.length,
    passed,
    failed: results.length - passed,
    skipped: 0,
  }
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
