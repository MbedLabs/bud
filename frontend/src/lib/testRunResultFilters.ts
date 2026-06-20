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

/** Whether a grouped test case row should appear for the current outcome toggles. */
export function shouldShowTestCase(failedAssertions: number, filters: OutcomeFilters): boolean {
  if (!hasActiveOutcomeFilters(filters)) return true

  const isFailedCase = failedAssertions > 0
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
