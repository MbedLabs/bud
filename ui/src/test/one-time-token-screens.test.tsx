// @vitest-environment jsdom
/**
 * The screens reached from a link in an email.
 *
 * Each is handed a single-use token in the URL *fragment* - never the query
 * string, so it stays out of request targets, server logs and the Referer
 * header - and each has to behave when the token is missing, rejected or
 * already spent. Nothing covered them, though they are the only way a user
 * accepts an invitation, verifies an address, resets a password or confirms an
 * email change.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RESPONSES, user } from './apiFixtures'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const mocked: Record<string, unknown> = { ...actual }
  for (const [groupName, group] of Object.entries(actual)) {
    if (!groupName.endsWith('Api') || typeof group !== 'object' || group === null) continue
    const replacement: Record<string, unknown> = {}
    for (const [method, value] of Object.entries(group)) {
      if (typeof value !== 'function') {
        replacement[method] = value
        continue
      }
      const key = `${groupName}.${method}`
      replacement[method] = vi.fn(async () => {
        if (!(key in RESPONSES)) throw new Error(`no fixture for ${key}`)
        return RESPONSES[key]
      })
    }
    mocked[groupName] = replacement
  }
  return mocked
})

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

const client = await import('../api/client')
const AcceptInvite = (await import('../pages/AcceptInvite')).default
const VerifyEmail = (await import('../pages/VerifyEmail')).default
const ResetPassword = (await import('../pages/ResetPassword')).default
const ConfirmEmailChange = (await import('../pages/ConfirmEmailChange')).default
const ForgotPassword = (await import('../pages/ForgotPassword')).default

/** Mount a screen with the token where a real link puts it: the fragment. */
function renderWithToken(element: React.ReactElement, token?: string) {
  window.location.hash = token ? `#token=${token}` : ''
  return render(<MemoryRouter>{element}</MemoryRouter>)
}

/** An axios-shaped rejection carrying the server's message. */
function apiError(detail: string) {
  return Object.assign(new Error('Request failed'), {
    isAxiosError: true,
    response: { data: { detail } },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.location.hash = ''
})

afterEach(cleanup)

describe('accepting an invitation', () => {
  it('greets the invitee by the name on the invitation', async () => {
    renderWithToken(<AcceptInvite />, 'invite-token')
    expect(await screen.findByText(new RegExp(user.full_name))).toBeTruthy()
    expect(client.authApi.getInviteInfo).toHaveBeenCalledWith('invite-token')
  })

  it('reads the token from the fragment, never the query string', async () => {
    // A token only in the query string must not be picked up. Asserting that
    // `search` is empty proves nothing unless something was put there first.
    window.history.replaceState(null, '', '/accept-invite?token=from-the-query')
    render(
      <MemoryRouter>
        <AcceptInvite />
      </MemoryRouter>,
    )

    await waitFor(() => expect(document.body.textContent).toMatch(/invalid|missing|expired/i))
    expect(client.authApi.getInviteInfo).not.toHaveBeenCalled()
    window.history.replaceState(null, '', '/')
  })

  it('refuses to proceed without a token', async () => {
    renderWithToken(<AcceptInvite />)
    await waitFor(() => expect(document.body.textContent).toMatch(/invalid|missing|expired/i))
    expect(client.authApi.getInviteInfo).not.toHaveBeenCalled()
  })

  it('says so when the invitation has already been used', async () => {
    vi.mocked(client.authApi.getInviteInfo).mockRejectedValueOnce(
      apiError('This invitation has already been accepted'),
    )
    renderWithToken(<AcceptInvite />, 'spent-token')
    expect(await screen.findByText(/already been accepted/i)).toBeTruthy()
  })

  it('sets the password against the token from the link', async () => {
    renderWithToken(<AcceptInvite />, 'invite-token')
    await screen.findByText(new RegExp(user.full_name))

    fireEvent.change(screen.getByPlaceholderText('Choose a password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.change(screen.getByPlaceholderText('Repeat your password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Accept Invitation' }))

    await waitFor(() =>
      expect(client.authApi.acceptInvite).toHaveBeenCalledWith(
        'invite-token',
        'a-long-enough-password',
      ),
    )
  })
})

describe('verifying an email address', () => {
  it('verifies against the token in the link', async () => {
    renderWithToken(<VerifyEmail />, 'verify-token')
    await waitFor(() => expect(client.authApi.verifyEmail).toHaveBeenCalledWith('verify-token'))
  })

  it('reports the refusal from the server', async () => {
    vi.mocked(client.authApi.verifyEmail).mockRejectedValueOnce(
      apiError('This verification link has expired'),
    )
    renderWithToken(<VerifyEmail />, 'stale-token')
    expect(await screen.findByText(/has expired/i)).toBeTruthy()
  })

  it('does not call the server without a token', async () => {
    renderWithToken(<VerifyEmail />)
    await waitFor(() => expect(document.body.textContent).toMatch(/missing|invalid/i))
    expect(client.authApi.verifyEmail).not.toHaveBeenCalled()
  })
})

describe('confirming an email change', () => {
  it('confirms against the token in the link', async () => {
    renderWithToken(<ConfirmEmailChange />, 'change-token')
    await waitFor(() =>
      expect(client.authApi.confirmEmailChange).toHaveBeenCalledWith('change-token'),
    )
  })

  it('reports a token that no longer matches the pending address', async () => {
    vi.mocked(client.authApi.confirmEmailChange).mockRejectedValueOnce(
      apiError('This confirmation link no longer matches the requested address'),
    )
    renderWithToken(<ConfirmEmailChange />, 'stale-token')
    expect(await screen.findByText(/no longer matches/i)).toBeTruthy()
  })

  it('says the token is missing rather than calling the server', async () => {
    renderWithToken(<ConfirmEmailChange />)
    expect(await screen.findByText(/missing confirmation token/i)).toBeTruthy()
    expect(client.authApi.confirmEmailChange).not.toHaveBeenCalled()
  })
})

describe('resetting a password', () => {
  it('resets against the token in the link', async () => {
    renderWithToken(<ResetPassword />, 'reset-token')

    fireEvent.change(screen.getByPlaceholderText('Enter your new password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.change(screen.getByPlaceholderText('Repeat your new password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }))

    await waitFor(() =>
      expect(client.authApi.resetPassword).toHaveBeenCalledWith(
        'reset-token',
        'a-long-enough-password',
      ),
    )
  })

  it('reports a spent or expired link', async () => {
    vi.mocked(client.authApi.resetPassword).mockRejectedValueOnce(
      apiError('This reset link has already been used'),
    )
    renderWithToken(<ResetPassword />, 'spent-token')

    fireEvent.change(screen.getByPlaceholderText('Enter your new password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.change(screen.getByPlaceholderText('Repeat your new password'), {
      target: { value: 'a-long-enough-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }))

    expect(await screen.findByText(/already been used/i)).toBeTruthy()
  })
})

describe('asking for a password reset', () => {
  it('sends the address to the server', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
      target: { value: 'ada@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }))

    await waitFor(() =>
      expect(client.authApi.forgotPassword).toHaveBeenCalledWith('ada@example.com'),
    )
  })

  it('answers the same way whether or not the address exists', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
      target: { value: 'nobody@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }))

    // The server never confirms an address exists, and neither does the screen.
    await waitFor(() => expect(client.authApi.forgotPassword).toHaveBeenCalled())
    expect(document.body.textContent).not.toMatch(/no such|not found|unknown account/i)
  })
})
