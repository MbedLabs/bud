import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Settings from '../pages/Settings'
import UsersPage from '../pages/Users'

const requestEmailChange = vi.hoisted(() => vi.fn())
const approveEmailChange = vi.hoisted(() => vi.fn())
const refreshUser = vi.hoisted(() => vi.fn())
const getAuthUser = vi.hoisted(() => vi.fn())

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: getAuthUser(),
    refreshUser,
  }),
}))

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const pendingUser = {
    id: 2,
    email: 'old@bud.example',
    full_name: 'Bud User',
    role: 'viewer' as const,
    is_active: true,
    pending_email: 'new@bud.example',
    email_change_status: 'requested' as const,
    email_change_requested_at: '2026-07-29T12:00:00Z',
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-29T12:00:00Z',
  }
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      requestEmailChange,
      cancelEmailChange: vi.fn(),
    },
    settingsApi: {
      ...actual.settingsApi,
      getALM: vi.fn().mockResolvedValue({
        bloom_url: '',
        has_bloom_token: false,
        bloom_token_prefix: null,
        bloom_token_rotated_at: null,
      }),
    },
    usersApi: {
      ...actual.usersApi,
      list: vi.fn().mockResolvedValue([pendingUser]),
      approveEmailChange,
      rejectEmailChange: vi.fn(),
    },
  }
})

function renderWithQueryClient(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      {element}
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getAuthUser.mockReturnValue({
    id: 1,
    email: 'admin@bud.example',
    full_name: 'Bud Admin',
    role: 'admin',
    is_active: true,
    created_at: '',
    updated_at: '',
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('role-aware email changes', () => {
  it('tells an administrator that the current mailbox authorizes the change first', async () => {
    requestEmailChange.mockResolvedValue({
      message: 'Email change requested. An administrator must approve it.',
    })
    refreshUser.mockResolvedValue(undefined)
    renderWithQueryClient(<Settings />)

    expect(screen.getByRole('heading', { name: 'Bloom PLM Integration' })).toBeInTheDocument()
    expect(screen.queryByText(/administrator must approve/i)).not.toBeInTheDocument()
    expect(screen.getByText(/authorization link to your current email first/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('New email'), {
      target: { value: 'new@bud.example' },
    })
    fireEvent.change(screen.getByLabelText('Current password'), {
      target: { value: 'current-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send authorization email' }))

    await waitFor(() => {
      expect(requestEmailChange).toHaveBeenCalledWith(
        'current-password',
        'new@bud.example',
      )
    })
    expect(refreshUser).toHaveBeenCalled()
  })

  it('shows that an administrator must use the link sent to the current address', () => {
    getAuthUser.mockReturnValue({
      id: 1,
      email: 'admin@bud.example',
      full_name: 'Bud Admin',
      role: 'admin',
      is_active: true,
      pending_email: 'new@bud.example',
      email_change_status: 'awaiting_current_confirmation',
      created_at: '',
      updated_at: '',
    })

    renderWithQueryClient(<Settings />)

    expect(screen.getByText(/authorization link sent to your current address/i)).toBeInTheDocument()
  })

  it('shows a pending user request to administrators and approves it', async () => {
    approveEmailChange.mockResolvedValue({})
    renderWithQueryClient(<UsersPage />)

    expect(await screen.findByText('Requested: new@bud.example')).toBeInTheDocument()
    fireEvent.click(screen.getByTitle('Approve email change'))

    await waitFor(() => {
      expect(approveEmailChange).toHaveBeenCalledWith(2, expect.anything())
    })
  })
})
