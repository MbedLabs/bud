// @vitest-environment jsdom
/**
 * Staying signed in, and being shut out.
 *
 * The access token lives in session storage, which a reload keeps but a new tab
 * does not; the refresh token lives in an httpOnly cookie the page cannot read.
 * So on mount the provider has to decide between three states - a stored token,
 * no token but a live cookie, and nothing at all - and `ProtectedRoute` has to
 * hold the screen until that decision is made. Nothing covered any of it, and
 * getting it wrong either logs everyone out on reload or flashes protected
 * content at someone who is not signed in.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { user } from './apiFixtures'

const authApi = {
  login: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  getMe: vi.fn(),
}

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, authApi }
})

const { AuthProvider, useAuth } = await import('../contexts/AuthContext')
const ProtectedRoute = (await import('../components/ProtectedRoute')).default
const { getAuthToken, setAuthToken } = await import('../lib/tokenStorage')

/** Shows which of the three states the provider settled on. */
function Probe() {
  const { user: current, isLoading, isAuthenticated, login, logout } = useAuth()
  return (
    <div>
      <output data-testid="state">
        {isLoading ? 'loading' : isAuthenticated ? `signed in as ${current?.email}` : 'signed out'}
      </output>
      <button onClick={() => login('ada@example.com', 'pw')}>sign in</button>
      {/* `logout` re-raises after clearing locally; a real caller handles that,
          and swallowing it here keeps the failure out of the test output. */}
      <button onClick={() => void logout().catch(() => {})}>sign out</button>
    </div>
  )
}

function state(): string {
  return screen.getByTestId('state').textContent ?? ''
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  authApi.getMe.mockResolvedValue(user)
  authApi.refresh.mockResolvedValue({ access_token: 'from-cookie', token_type: 'bearer', user })
  authApi.login.mockResolvedValue({ access_token: 'from-login', token_type: 'bearer', user })
  authApi.logout.mockResolvedValue(undefined)
})

afterEach(cleanup)

describe('restoring a session on load', () => {
  it('uses the stored token and asks who it belongs to', async () => {
    setAuthToken('stored-token')
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(state()).toBe(`signed in as ${user.email}`))
    expect(authApi.getMe).toHaveBeenCalled()
    // The cookie path is for when there is no token; it must not run here.
    expect(authApi.refresh).not.toHaveBeenCalled()
  })

  it('falls back to the refresh cookie when the tab has no token', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(state()).toBe(`signed in as ${user.email}`))
    expect(authApi.refresh).toHaveBeenCalled()
    // The recovered token is kept, so the next request carries it.
    expect(getAuthToken()).toBe('from-cookie')
  })

  it('settles on signed out when there is neither', async () => {
    authApi.refresh.mockRejectedValue(new Error('no cookie'))
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(state()).toBe('signed out'))
    expect(getAuthToken()).toBeNull()
  })

  it('discards a token the server no longer recognises', async () => {
    setAuthToken('revoked-token')
    authApi.getMe.mockRejectedValue(new Error('401'))
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(state()).toBe('signed out'))
    // Leaving it behind would send a token known to be dead with every request.
    expect(getAuthToken()).toBeNull()
  })
})

describe('signing in and out', () => {
  it('keeps the token the login returned', async () => {
    authApi.refresh.mockRejectedValue(new Error('no cookie'))
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(state()).toBe('signed out'))

    screen.getByRole('button', { name: 'sign in' }).click()

    await waitFor(() => expect(state()).toBe(`signed in as ${user.email}`))
    expect(getAuthToken()).toBe('from-login')
  })

  it('signs out locally even when the server call fails', async () => {
    setAuthToken('stored-token')
    authApi.logout.mockRejectedValue(new Error('network down'))
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(state()).toBe(`signed in as ${user.email}`))

    screen.getByRole('button', { name: 'sign out' }).click()

    // A failed revoke must not leave the browser believing it is signed in.
    await waitFor(() => expect(state()).toBe('signed out'))
    expect(getAuthToken()).toBeNull()
  })

  it('revokes the refresh token server-side on a normal sign out', async () => {
    setAuthToken('stored-token')
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(state()).toBe(`signed in as ${user.email}`))

    screen.getByRole('button', { name: 'sign out' }).click()

    await waitFor(() => expect(authApi.logout).toHaveBeenCalled())
    expect(getAuthToken()).toBeNull()
  })
})

describe('the protected-route guard', () => {
  function renderGuarded() {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <p>the dashboard</p>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<p>the login screen</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    )
  }

  it('holds the screen while the session is still being decided', () => {
    setAuthToken('stored-token')
    renderGuarded()
    // Synchronously, before getMe resolves: neither outcome has been committed.
    expect(screen.getByText('Loading...')).toBeTruthy()
    expect(screen.queryByText('the dashboard')).toBeNull()
    expect(screen.queryByText('the login screen')).toBeNull()
  })

  it('shows the page once the session is confirmed', async () => {
    setAuthToken('stored-token')
    renderGuarded()
    expect(await screen.findByText('the dashboard')).toBeTruthy()
  })

  it('redirects to login when there is no session', async () => {
    authApi.refresh.mockRejectedValue(new Error('no cookie'))
    renderGuarded()
    expect(await screen.findByText('the login screen')).toBeTruthy()
    expect(screen.queryByText('the dashboard')).toBeNull()
  })
})

describe('using the context outside its provider', () => {
  it('fails loudly rather than handing back undefined', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow(/within an AuthProvider/)
    consoleError.mockRestore()
  })
})
