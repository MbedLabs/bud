export type OutcomeFilters = {
  passed: boolean
  failed: boolean
  failedOnly: boolean
}

export const EMPTY_OUTCOME_FILTERS: OutcomeFilters = {
  passed: false,
  failed: false,
  failedOnly: false,
}

export function hasActiveOutcomeFilters(filters: OutcomeFilters): boolean {
  return filters.passed || filters.failed || filters.failedOnly
}

/** Whether a test case failed: it has a failed assertion or a failed result. */
export function isFailedTestCase(failedAssertions: number, failedMethods = 0): boolean {
  return failedAssertions > 0 || failedMethods > 0
}

/** Whether a grouped test case row should appear for the current outcome toggles. */
export function shouldShowTestCase(
  failedAssertions: number,
  filters: OutcomeFilters,
  failedMethods = 0,
): boolean {
  if (!hasActiveOutcomeFilters(filters)) return true

  const isFailedCase = isFailedTestCase(failedAssertions, failedMethods)
  const isPassedCase = !isFailedCase

  if (filters.passed && isPassedCase) return true
  if ((filters.failed || filters.failedOnly) && isFailedCase) return true
  return false
}

/** Assertions visible when a failed test case is expanded. */
export function filterAssertionsForDisplay<T extends { passed?: boolean }>(
  assertions: T[],
  failedAssertions: number,
  filters: OutcomeFilters,
): T[] {
  if (filters.failedOnly && failedAssertions > 0) {
    return assertions.filter((assertion) => assertion.passed === false)
  }
  return assertions
}

export function toggleOutcomeFilter(
  filters: OutcomeFilters,
  key: keyof OutcomeFilters,
): OutcomeFilters {
  const next = { ...filters, [key]: !filters[key] }
  if (key === 'failedOnly' && next.failedOnly) {
    next.failed = false
  }
  if (key === 'failed' && next.failed) {
    next.failedOnly = false
  }
  return next
}

export type SummaryOutcome = 'total' | 'passed' | 'failed'

/** The outcome filters each run summary card sets on the results list. */
export const SUMMARY_OUTCOME_FILTERS: Record<SummaryOutcome, OutcomeFilters> = {
  total: EMPTY_OUTCOME_FILTERS,
  passed: { passed: true, failed: false, failedOnly: false },
  failed: { passed: false, failed: true, failedOnly: false },
}

/** The run summary card that matches the current outcome filters, or null when none does. */
export function selectedSummaryOutcome(filters: OutcomeFilters): SummaryOutcome | null {
  if (!hasActiveOutcomeFilters(filters)) return 'total'
  if (filters.passed && !filters.failed && !filters.failedOnly) return 'passed'
  if (!filters.passed && (filters.failed || filters.failedOnly)) return 'failed'
  return null
}
