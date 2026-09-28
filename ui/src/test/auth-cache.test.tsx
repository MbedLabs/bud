// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { StrictMode } from 'react'
import { AxiosError } from 'axios'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '../api/client'
import { AuthProvider, useAuth } from '../contexts/AuthContext'
import { clearAuthToken, getAuthToken, getSessionUserId, setAuthToken, setSessionUserId } from '../lib/tokenStorage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      refresh: vi.fn(),
      getMe: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    },
  }
})

const reader = { id: 2, email: 'reader@example.com', full_name: 'Reader', role: 'viewer' }
const other = { id: 3, email: 'other@example.com', full_name: 'Other', role: 'viewer' }
const originalLocation = window.location
let location: { pathname: string; href: string; replace: (url: string) => void }

function Controls() {
  const { user, login, logout, refreshUser } = useAuth()
  return (
    <div>
      <span>{user?.email ?? 'Signed out'}</span>
      <button onClick={() => login('reader@example.com', 'secret')}>Sign in</button>
      <button onClick={() => void logout().catch(() => {})}>Sign out</button>
      <button onClick={() => refreshUser()}>Check session</button>
    </div>
  )
}

async function signedIn(client: QueryClient) {
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Controls />
      </AuthProvider>
    </QueryClientProvider>,
  )
  fireEvent.click(await screen.findByText('Sign in'))
  await screen.findByText('reader@example.com')
  client.setQueryData(['cached', 1], [{ id: 1 }])
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(authApi.refresh).mockRejectedValue(new Error('no session'))
  vi.mocked(authApi.login).mockResolvedValue({ access_token: 'token', user: reader } as never)
  vi.mocked(authApi.logout).mockResolvedValue(undefined)
  setSessionUserId(null)
  sessionStorage.clear()
  location = {
    pathname: '/',
    href: '',
    replace: (url: string) => {
      location.href = url
    },
  }
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: location })
})
afterEach(() => {
  cleanup()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: originalLocation })
})

describe('query cache and the signed-in user', () => {
  it('is emptied when a user signs in', async () => {
    const client = new QueryClient()
    client.setQueryData(['cached', 0], [{ id: 0 }])
    await signedIn(client)
    expect(client.getQueryData(['cached', 0])).toBeUndefined()
    expect(getSessionUserId()).toBe(2)
    expect(location.href).toBe('')
  })

  it('is emptied and the login page loaded when the user signs out', async () => {
    const client = new QueryClient()
    await signedIn(client)
    fireEvent.click(screen.getByText('Sign out'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
    expect(getSessionUserId()).toBeNull()
  })

  it('is emptied and the login page loaded when the server has ended the session', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.getMe).mockRejectedValueOnce(
      Object.assign(new AxiosError('Unauthorized'), { response: { status: 401 } }),
    )
    fireEvent.click(screen.getByText('Check session'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
  })

  it('is emptied and the login page loaded when the session check fails', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.getMe).mockRejectedValueOnce(new Error('offline'))
    fireEvent.click(screen.getByText('Check session'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
  })

  it('is kept when the session check confirms the same user', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.getMe).mockResolvedValueOnce(reader as never)
    fireEvent.click(screen.getByText('Check session'))
    await waitFor(() => expect(authApi.getMe).toHaveBeenCalled())
    expect(location.href).toBe('')
    expect(client.getQueryData(['cached', 1])).toEqual([{ id: 1 }])
  })

  it('is emptied without a reload when someone signs in as another user', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.login).mockResolvedValueOnce({ access_token: 'other-token', user: other } as never)
    fireEvent.click(screen.getByText('Sign in'))
    expect(await screen.findByText('other@example.com')).toBeInTheDocument()
    expect(location.href).toBe('')
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
    expect(getSessionUserId()).toBe(3)
  })

  it('is emptied and the login page loaded when the sign-out request cannot reach the server', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.logout).mockRejectedValueOnce(new Error('network down'))
    fireEvent.click(screen.getByText('Sign out'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
  })

  it('is emptied and the login page loaded when the server says the session is already over', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.logout).mockRejectedValueOnce(Object.assign(new AxiosError('Unauthorized'), { response: { status: 401 } }))
    fireEvent.click(screen.getByText('Sign out'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
  })

  it('is emptied and the login page loaded when the account is deactivated', async () => {
    const client = new QueryClient()
    await signedIn(client)
    vi.mocked(authApi.getMe).mockRejectedValueOnce(
      Object.assign(new AxiosError('Forbidden'), { response: { status: 403 } }),
    )
    fireEvent.click(screen.getByText('Check session'))
    await waitFor(() => expect(location.href).toBe('/login'))
  })

  it('drops a stored token, without a reload, when the first session check fails', async () => {
    setAuthToken('stored-token')
    vi.mocked(authApi.getMe).mockRejectedValueOnce(new Error('offline'))
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Controls />
        </AuthProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(authApi.getMe).toHaveBeenCalled())
    expect(await screen.findByText('Signed out')).toBeInTheDocument()
    expect(getAuthToken()).toBeNull()
    expect(location.href).toBe('')
  })

  it('asks again when the session is checked while the first check is still running', async () => {
    setAuthToken('stored-token')
    vi.mocked(authApi.getMe).mockReturnValueOnce(new Promise(() => {}) as never)
    vi.mocked(authApi.getMe).mockResolvedValueOnce(reader as never)
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Controls />
        </AuthProvider>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByText('Check session'))
    expect(await screen.findByText('reader@example.com')).toBeInTheDocument()
    expect(authApi.getMe).toHaveBeenCalledTimes(2)
  })

  it('restores a session with one refresh when the provider mounts twice', async () => {
    vi.mocked(authApi.refresh).mockResolvedValue({ access_token: 'cookie-token', user: reader } as never)
    render(
      <StrictMode>
        <QueryClientProvider client={new QueryClient()}>
          <AuthProvider>
            <Controls />
          </AuthProvider>
        </QueryClientProvider>
      </StrictMode>,
    )
    expect(await screen.findByText('reader@example.com')).toBeInTheDocument()
    expect(authApi.refresh).toHaveBeenCalledTimes(1)
    expect(location.href).toBe('')
  })

  it('is emptied and the login page loaded when the session now belongs to another user', async () => {
    const client = new QueryClient()
    await signedIn(client)
    clearAuthToken()
    vi.mocked(authApi.refresh).mockResolvedValueOnce({ access_token: 'other-token', user: other } as never)
    fireEvent.click(screen.getByText('Check session'))
    await waitFor(() => expect(location.href).toBe('/login'))
    expect(client.getQueryData(['cached', 1])).toBeUndefined()
    expect(screen.queryByText('other@example.com')).toBeNull()
  })
})
