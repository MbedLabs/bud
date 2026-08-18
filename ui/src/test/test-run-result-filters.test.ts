import { describe, expect, it } from 'vitest'
import {
  EMPTY_OUTCOME_FILTERS,
  filterAssertionsForDisplay,
  shouldShowTestCase,
  toggleOutcomeFilter,
} from '../lib/testRunResultFilters'

describe('testRunResultFilters', () => {
  describe('shouldShowTestCase', () => {
    it('shows all cases when no outcome filter is active', () => {
      expect(shouldShowTestCase(0, EMPTY_OUTCOME_FILTERS)).toBe(true)
      expect(shouldShowTestCase(2, EMPTY_OUTCOME_FILTERS)).toBe(true)
    })

    it('shows only passed cases when passed filter is active', () => {
      const filters = { passed: true, failed: false, failedOnly: false }
      expect(shouldShowTestCase(0, filters)).toBe(true)
      expect(shouldShowTestCase(1, filters)).toBe(false)
    })

    it('shows failed cases for failed or failed-only filters', () => {
      expect(shouldShowTestCase(1, { passed: false, failed: true, failedOnly: false })).toBe(true)
      expect(shouldShowTestCase(0, { passed: false, failed: true, failedOnly: false })).toBe(false)
      expect(shouldShowTestCase(1, { passed: false, failed: false, failedOnly: true })).toBe(true)
      expect(shouldShowTestCase(0, { passed: false, failed: false, failedOnly: true })).toBe(false)
    })

    it('unions passed and failed selections', () => {
      const filters = { passed: true, failed: true, failedOnly: false }
      expect(shouldShowTestCase(0, filters)).toBe(true)
      expect(shouldShowTestCase(2, filters)).toBe(true)
    })
  })

  describe('toggleOutcomeFilter', () => {
    it('keeps failed and failed-only mutually exclusive', () => {
      const withFailed = toggleOutcomeFilter(EMPTY_OUTCOME_FILTERS, 'failed')
      expect(withFailed).toEqual({ passed: false, failed: true, failedOnly: false })

      const withFailedOnly = toggleOutcomeFilter(withFailed, 'failedOnly')
      expect(withFailedOnly).toEqual({ passed: false, failed: false, failedOnly: true })

      const backToFailed = toggleOutcomeFilter(withFailedOnly, 'failed')
      expect(backToFailed).toEqual({ passed: false, failed: true, failedOnly: false })
    })
  })

  describe('filterAssertionsForDisplay', () => {
    const assertions = [
      { passed: true, id: 'a' },
      { passed: false, id: 'b' },
      { passed: false, id: 'c' },
    ]

    it('returns all assertions unless failed-only is active on a failed case', () => {
      expect(filterAssertionsForDisplay(assertions, 2, EMPTY_OUTCOME_FILTERS)).toEqual(assertions)
      expect(
        filterAssertionsForDisplay(assertions, 2, { passed: false, failed: true, failedOnly: false }),
      ).toEqual(assertions)
      expect(filterAssertionsForDisplay(assertions, 0, { passed: false, failed: false, failedOnly: true })).toEqual(
        assertions,
      )
    })

    it('hides passing assertions inside failed cases when failed-only is active', () => {
      const filters = { passed: false, failed: false, failedOnly: true }
      expect(filterAssertionsForDisplay(assertions, 2, filters)).toEqual([
        { passed: false, id: 'b' },
        { passed: false, id: 'c' },
      ])
    })
  })
})
