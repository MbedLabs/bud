/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { filenameFromResponse, saveBlob } from '../api/client'
import dashboardSource from '../pages/Dashboard.tsx?raw'
import runDetailSource from '../pages/TestRunDetail.tsx?raw'

/**
 * The PDF comes back from an authenticated endpoint, so it is fetched through
 * the axios instance and handed to the browser as a blob. A plain <a href>
 * would arrive without the Authorization header.
 */

describe('filenameFromResponse', () => {
  const withHeader = (value?: string) => ({
    headers: value ? { 'content-disposition': value } : {},
  })

  it('prefers the RFC 5987 encoded name', () => {
    const header =
      `attachment; filename="bud-run-7-smoke.pdf"; filename*=UTF-8''bud-run-7-sm%C3%B8ke.pdf`
    expect(filenameFromResponse(withHeader(header), 'x.pdf')).toBe('bud-run-7-smøke.pdf')
  })

  it('falls back to the plain filename', () => {
    expect(
      filenameFromResponse(withHeader('attachment; filename="bud-test-report.pdf"'), 'x.pdf'),
    ).toBe('bud-test-report.pdf')
  })

  it('accepts an unquoted filename', () => {
    expect(filenameFromResponse(withHeader('attachment; filename=report.pdf'), 'x.pdf')).toBe(
      'report.pdf',
    )
  })

  it('uses the fallback when the header is absent', () => {
    expect(filenameFromResponse(withHeader(), 'fallback.pdf')).toBe('fallback.pdf')
  })

  it('uses the fallback when the encoded name is malformed', () => {
    const header = `attachment; filename*=UTF-8''%E0%A4%A`
    expect(filenameFromResponse(withHeader(header), 'fallback.pdf')).toBe('fallback.pdf')
  })

  it('reads a Headers-style response too', () => {
    const response = {
      headers: { get: (name: string) => (name === 'content-disposition' ? 'attachment; filename="a.pdf"' : null) },
    }
    expect(filenameFromResponse(response, 'x.pdf')).toBe('a.pdf')
  })
})

describe('saveBlob', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('names the download and cleans up the object URL', () => {
    const createObjectURL = vi.fn(() => 'blob:fake')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    saveBlob(new Blob(['%PDF-']), 'bud-run-7.pdf')

    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake')
    // The temporary anchor must not be left in the document.
    expect(document.querySelectorAll('a[download]')).toHaveLength(0)
    vi.unstubAllGlobals()
  })
})

describe('report buttons', () => {
  it('the dashboard reports the filters it is displaying', () => {
    expect(dashboardSource).toContain('reportsApi.testRuns(filters)')
  })

  it('the run page reports that run', () => {
    expect(runDetailSource).toContain('reportsApi.testRun(runId)')
  })

  it.each([
    ['Dashboard', dashboardSource],
    ['TestRunDetail', runDetailSource],
  ])('%s reports a failed download instead of doing nothing', (_name, source) => {
    expect(source).toContain('setReportError(extractApiErrorMessage(error')
  })

  it.each([
    ['Dashboard', dashboardSource],
    ['TestRunDetail', runDetailSource],
  ])('%s re-enables the button after a failure', (_name, source) => {
    expect(source).toContain('finally {')
    expect(source).toContain('setReportPending(false)')
  })
})
