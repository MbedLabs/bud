// @vitest-environment jsdom
/**
 * What the client does around authentication, which is the part with real logic.
 *
 * A short-lived access token means a normal session 401s regularly, and the
 * response interceptor is what keeps that invisible: refresh once, retry the
 * original request, and send everyone waiting on the same refresh. Nothing
 * tested it, so a regression here would have logged users out mid-session.
 */
import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'

interface Recorded {
  url: string
  authorization: string | undefined
}

const requests: Recorded[] = []

/** `url -> queued responses`; a status >= 400 is thrown, as a real adapter does. */
let script: Record<string, Array<{ status: number; data?: unknown }>> = {}

function scriptedFor(url: string): { status: number; data?: unknown } {
  const queue = script[url]
  if (!queue || queue.length === 0) return { status: 200, data: {} }
  return queue.length === 1 ? queue[0] : (queue.shift() as { status: number; data?: unknown })
}

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  const url = config.url ?? ''
  requests.push({ url, authorization: config.headers?.Authorization as string | undefined })
  const scripted = scriptedFor(url)
  const response = {
    data: scripted.data ?? {},
    status: scripted.status,
    statusText: '',
    headers: {},
    config,
    request: {},
  }
  if (scripted.status >= 400) {
    throw new axios.AxiosError('Request failed', String(scripted.status), config, {}, response)
  }
  return response
}

const client = await import('../api/client')
const { clearAuthToken, getAuthToken, setAuthToken } = await import('../lib/tokenStorage')

/** jsdom refuses assignment to `location.href`; this records it instead. */
function stubLocation(pathname: string): { href: string } {
  const location = { pathname, href: '' }
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: location })
  return location
}

beforeEach(() => {
  requests.length = 0
  script = {}
  sessionStorage.clear()
  stubLocation('/test-runs')
})

describe('the access token travels with every request', () => {
  it('is attached when one is stored', async () => {
    setAuthToken('stored-token')
    await client.testRunsApi.list()
    expect(requests[0].authorization).toBe('Bearer stored-token')
  })

  it('is absent when there is none', async () => {
    await client.testRunsApi.list()
    expect(requests[0].authorization).toBeUndefined()
  })
})

describe('a 401 refreshes once and retries', () => {
  it('replays the original request with the new token', async () => {
    setAuthToken('expired-token')
    script = {
      '/test-runs': [{ status: 401 }, { status: 200, data: { runs: [{ id: 1 }], total: 1 } }],
      '/api/auth/refresh': [{ status: 200, data: { access_token: 'fresh-token' } }],
    }

    await expect(client.testRunsApi.list()).resolves.toEqual({ runs: [{ id: 1 }], total: 1 })

    expect(requests.map((r) => r.url)).toEqual(['/test-runs', '/api/auth/refresh', '/test-runs'])
    expect(requests[2].authorization).toBe('Bearer fresh-token')
    expect(getAuthToken()).toBe('fresh-token')
  })

  it('does not retry a second time if the replay also fails', async () => {
    setAuthToken('expired-token')
    script = {
      '/test-runs': [{ status: 401 }],
      '/api/auth/refresh': [{ status: 200, data: { access_token: 'fresh-token' } }],
    }

    await expect(client.testRunsApi.list()).rejects.toBeDefined()
    expect(requests.filter((r) => r.url === '/api/auth/refresh')).toHaveLength(1)
    expect(requests.filter((r) => r.url === '/test-runs')).toHaveLength(2)
  })

  it('shares one refresh between requests that expire together', async () => {
    setAuthToken('expired-token')
    let calls = 0
    script = { '/api/auth/refresh': [{ status: 200, data: { access_token: 'fresh-token' } }] }
    Object.defineProperty(script, '/test-runs', {
      enumerable: true,
      get: () => [{ status: calls++ < 3 ? 401 : 200, data: { runs: [], total: 0 } }],
    })

    await Promise.all([
      client.testRunsApi.list(),
      client.testRunsApi.list(),
      client.testRunsApi.list(),
    ])

    expect(requests.filter((r) => r.url === '/api/auth/refresh')).toHaveLength(1)
  })

  it('sends the user to the login screen when the refresh fails', async () => {
    setAuthToken('expired-token')
    const location = stubLocation('/test-runs')
    script = { '/test-runs': [{ status: 401 }], '/api/auth/refresh': [{ status: 401 }] }

    await expect(client.testRunsApi.list()).rejects.toBeDefined()
    expect(getAuthToken()).toBeNull()
    expect(location.href).toBe('/login')
  })

  it('stays put when the 401 arrives on a public screen', async () => {
    const location = stubLocation('/reset-password')
    script = { '/auth/reset-password': [{ status: 401 }] }

    await expect(client.authApi.resetPassword('tok', 'pw')).rejects.toBeDefined()
    expect(location.href).toBe('')
  })

  it('never refreshes in response to a failed login', async () => {
    script = { '/auth/login': [{ status: 401 }] }

    await expect(client.authApi.login('u@example.com', 'wrong')).rejects.toBeDefined()
    expect(requests.map((r) => r.url)).toEqual(['/auth/login'])
  })
})

describe('logging out', () => {
  it('clears the token even when the request fails', async () => {
    setAuthToken('a-token')
    script = { '/auth/logout': [{ status: 500 }] }

    await expect(client.authApi.logout()).rejects.toBeDefined()
    expect(getAuthToken()).toBeNull()
  })

  it('clears the token on success', async () => {
    setAuthToken('a-token')
    await client.authApi.logout()
    expect(getAuthToken()).toBeNull()
  })
})

describe('token storage', () => {
  it('round-trips through session storage', () => {
    expect(getAuthToken()).toBeNull()
    setAuthToken('t')
    expect(getAuthToken()).toBe('t')
    clearAuthToken()
    expect(getAuthToken()).toBeNull()
  })
})
