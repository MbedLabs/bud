// @vitest-environment jsdom
/**
 * Every endpoint the frontend can call, and the request it actually issues.
 *
 * `api/client.ts` is the whole surface between the app and the backend. Most
 * of its paths are built with a template literal, so a wrong variable name
 * silently produced `/test-runs/undefined` and only failed in the browser, on
 * the screen that happened to call it.
 *
 * The table below names every method, the arguments a caller passes and the
 * request that must come out. A completeness check walks the exported API
 * objects and fails if a method is missing from it, so a new endpoint cannot be
 * added without a row here.
 */
import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface Recorded {
  method: string
  url: string
  data: unknown
  params: unknown
  responseType: string | undefined
}

const requests: Recorded[] = []
let nextResponse: { status: number; data: unknown; headers: Record<string, string> } = {
  status: 200,
  data: {},
  headers: {},
}

// Installed before the client module is imported: `axios.create()` copies the
// adapter out of the defaults at creation time, so the instance the client
// builds picks this up and no request ever leaves the process.
axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  requests.push({
    method: (config.method ?? '').toLowerCase(),
    url: config.url ?? '',
    data: config.data,
    params: config.params,
    responseType: config.responseType,
  })
  return {
    data: nextResponse.data,
    status: nextResponse.status,
    statusText: 'OK',
    headers: nextResponse.headers,
    config,
    request: {},
  }
}

const client = await import('../api/client')

/** A body carrying every field the unwrapping methods reach into. */
const BODY = {
  id: 1,
  runs: [],
  total: 0,
  access_token: 'tok',
  user: { id: 1, email: 'u@example.com' },
}

const CALLS: Array<[string, unknown[], string, string]> = [
  ['authApi.login', ['u@example.com', 'pw'], 'post', '/auth/login'],
  ['authApi.refresh', [], 'post', '/auth/refresh'],
  ['authApi.logout', [], 'post', '/auth/logout'],
  ['authApi.getMe', [], 'get', '/auth/me'],
  ['authApi.updateMe', [{ full_name: 'New Name' }], 'put', '/auth/me'],
  ['authApi.requestEmailChange', ['pw', 'new@example.com'], 'post', '/auth/me/email'],
  ['authApi.cancelEmailChange', [], 'delete', '/auth/me/email'],
  ['authApi.confirmEmailChange', ['tok'], 'post', '/auth/confirm-email-change'],
  ['authApi.changePassword', ['old', 'new'], 'put', '/auth/me/password'],
  ['authApi.getInviteInfo', ['tok'], 'post', '/auth/invite-info'],
  ['authApi.acceptInvite', ['tok', 'pw'], 'post', '/auth/accept-invite'],
  ['authApi.verifyEmail', ['tok'], 'post', '/auth/verify-email'],
  ['authApi.forgotPassword', ['u@example.com'], 'post', '/auth/forgot-password'],
  ['authApi.resetPassword', ['tok', 'pw'], 'post', '/auth/reset-password'],

  ['usersApi.list', [], 'get', '/users'],
  [
    'usersApi.create',
    [{ email: 'u@example.com', full_name: 'U', password: 'pw' }],
    'post',
    '/users',
  ],
  ['usersApi.invite', [{ email: 'u@example.com', full_name: 'U' }], 'post', '/users/invite'],
  ['usersApi.update', [3, { full_name: 'U' }], 'patch', '/users/3'],
  ['usersApi.startEmailChange', [3, 'new@example.com'], 'post', '/users/3/email'],
  ['usersApi.approveEmailChange', [3], 'post', '/users/3/email/approve'],
  ['usersApi.rejectEmailChange', [3], 'delete', '/users/3/email'],
  ['usersApi.delete', [3], 'delete', '/users/3'],

  ['testRunsApi.publishToBloom', [7], 'post', '/test-runs/7/publish-to-bloom'],
  ['testRunsApi.list', [], 'get', '/test-runs'],
  ['testRunsApi.get', [42], 'get', '/test-runs/42'],
  ['testRunsApi.getEvents', [42], 'get', '/test-runs/42/events'],
  ['testRunsApi.getArtifacts', [42], 'get', '/test-runs/42/artifacts'],
  ['catalogApi.list', [], 'get', '/test-catalog'],
  ['customRunsApi.create', [{ test_paths: ['a.B'] }], 'post', '/test-runs/custom'],
  ['testRunsApi.stats', [], 'get', '/test-runs/stats'],
  ['testRunsApi.filterOptions', [], 'get', '/test-runs/filter-options'],

  ['resultsApi.list', [42], 'get', '/results/42'],

  ['testStationsApi.status', [], 'get', '/runners/status'],
  ['testStationsApi.getByAccount', ['bench-01'], 'get', '/runners/bench-01'],

  ['settingsApi.getALM', [], 'get', '/settings/integrations/PLM'],
  [
    'settingsApi.updateALM',
    [{ bloom_url: 'https://bloom.example.com' }],
    'post',
    '/settings/integrations/PLM',
  ],

  ['reportsApi.testRuns', [], 'get', '/reports/test-runs.pdf'],
  ['reportsApi.testRun', [42], 'get', '/reports/test-runs/42.pdf'],
  ['artifactsApi.download', [7, 'trace.pcap'], 'get', '/uploads/7'],
]

type ApiGroup = Record<string, (...args: unknown[]) => Promise<unknown>>

function resolve(name: string): (...args: unknown[]) => Promise<unknown> {
  const [group, method] = name.split('.')
  const groups = client as unknown as Record<string, ApiGroup>
  return groups[group][method]
}

beforeEach(() => {
  requests.length = 0
  nextResponse = { status: 200, data: BODY, headers: {} }
  sessionStorage.clear()
})

describe('api client request contract', () => {
  it.each(CALLS)('%s issues the right request', async (name, args, method, url) => {
    await resolve(name)(...args)

    expect(requests).toHaveLength(1)
    expect(requests[0].method).toBe(method)
    expect(requests[0].url).toBe(url)
    // A template literal that names the wrong variable fails here rather than
    // in the browser.
    expect(requests[0].url).not.toMatch(/undefined|NaN|\[object Object\]/)
  })

  it('covers every exported endpoint', () => {
    const listed = new Set(CALLS.map(([name]) => name))
    const missing: string[] = []
    for (const [groupName, group] of Object.entries(client)) {
      if (!groupName.endsWith('Api') || typeof group !== 'object' || group === null) continue
      for (const [method, value] of Object.entries(group)) {
        if (typeof value !== 'function') continue
        if (!listed.has(`${groupName}.${method}`)) missing.push(`${groupName}.${method}`)
      }
    }
    expect(missing).toEqual([])
  })
})

describe('query parameters', () => {
  it('carries the run list filters', async () => {
    await client.testRunsApi.list({
      status: 'Completed',
      limit: 20,
      offset: 40,
      runner_account: 'bench-01',
      latest_per_suite: true,
    })
    expect(requests[0].params).toEqual({
      status: 'Completed',
      limit: 20,
      offset: 40,
      runner_account: 'bench-01',
      latest_per_suite: true,
    })
  })

  it('carries the dashboard stat filters', async () => {
    await client.testRunsApi.stats({ days: 30, runner_account: 'bench-01', suite: 'Nightly' })
    expect(requests[0].params).toEqual({ days: 30, runner_account: 'bench-01', suite: 'Nightly' })
  })

  it('asks for the filter options within a window', async () => {
    await client.testRunsApi.filterOptions({ days: 7 })
    expect(requests[0].params).toEqual({ days: 7 })
  })
})

describe('report downloads', () => {
  it('asks for a binary body so the PDF is not mangled into text', async () => {
    nextResponse = { status: 200, data: new Blob(['%PDF-']), headers: {} }
    await client.reportsApi.testRuns()
    expect(requests[0].responseType).toBe('blob')
  })

  it('passes the same filters the dashboard is showing', async () => {
    nextResponse = { status: 200, data: new Blob(['%PDF-']), headers: {} }
    await client.reportsApi.testRuns({ days: 30, suite: 'Nightly' })
    expect(requests[0].params).toEqual({ days: 30, suite: 'Nightly' })
  })

  it('names the per-run report after the run', async () => {
    nextResponse = {
      status: 200,
      data: new Blob(['%PDF-']),
      headers: { 'content-disposition': 'attachment; filename="bud-run-42-nightly.pdf"' },
    }
    const report = await client.reportsApi.testRun(42)
    expect(report.filename).toBe('bud-run-42-nightly.pdf')
  })

  it('falls back to a run-numbered name when the server does not say', async () => {
    nextResponse = { status: 200, data: new Blob(['%PDF-']), headers: {} }
    const report = await client.reportsApi.testRun(42)
    expect(report.filename).toBe('bud-run-42.pdf')
  })
})

describe('responses are unwrapped', () => {
  it('returns the body, not the axios envelope', async () => {
    nextResponse = { status: 200, data: { id: 42, name: 'Nightly' }, headers: {} }
    await expect(client.testRunsApi.get(42)).resolves.toEqual({ id: 42, name: 'Nightly' })
  })
})

describe('saveBlob', () => {
  it('hands the file to the browser and cleans up after itself', () => {
    const created: string[] = []
    const revoked: string[] = []
    vi.stubGlobal(
      'URL',
      Object.assign(URL, {
        createObjectURL: () => {
          created.push('blob:stub')
          return 'blob:stub'
        },
        revokeObjectURL: (url: string) => revoked.push(url),
      }),
    )
    const clicks: string[] = []
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(this.download)
      })

    client.saveBlob(new Blob(['%PDF-']), 'report.pdf')

    expect(created).toEqual(['blob:stub'])
    expect(clicks).toEqual(['report.pdf'])
    expect(revoked).toEqual(['blob:stub'])
    // The anchor is a means to an end and must not be left in the document.
    expect(document.querySelector('a[download]')).toBeNull()

    clickSpy.mockRestore()
    vi.unstubAllGlobals()
  })
})
