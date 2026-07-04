import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import App from '../App'
import { testRunsApi } from '../api/client'

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'bud@example.com',
      full_name: 'Bud Tester',
      role: 'admin',
      is_active: true,
      created_at: '',
      updated_at: '',
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

vi.mock('../components/ProtectedRoute', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    testRunsApi: {
      ...actual.testRunsApi,
      list: vi.fn().mockResolvedValue({ runs: [], total: 0 }),
      get: vi.fn().mockRejectedValue(new Error('not-found')),
      getEvents: vi.fn().mockResolvedValue([]),
    },
    resultsApi: {
      ...actual.resultsApi,
      list: vi.fn().mockResolvedValue([]),
    },
    testStationsApi: {
      ...actual.testStationsApi,
      status: vi.fn().mockResolvedValue({ runners: [] }),
    },
    settingsApi: {
      ...actual.settingsApi,
      getALM: vi.fn().mockResolvedValue({
        bloom_url: '',
        bloom_token: '',
      }),
    },
  }
})

function renderAt(path: string) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('route smoke (Bud)', () => {
  it('shows public auth screens without redirect loops', async () => {
    renderAt('/login')
    expect(screen.getByRole('heading', { name: /Welcome to Bud/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Forgot password\?/i })).toHaveAttribute('href', '/forgot-password')

    cleanup()
    renderAt('/accept-invite')
    expect(screen.getByRole('heading', { name: /Accept Invitation/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Back to Login/i })).toHaveAttribute('href', '/login')

    cleanup()
    renderAt('/verify-email')
    expect(screen.getByRole('heading', { name: /Verify Email/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to Login/i })).toHaveAttribute('href', '/login')

    cleanup()
    renderAt('/forgot-password')
    expect(screen.getByRole('heading', { name: /Forgot Password/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Back to Login/i })).toHaveAttribute('href', '/login')

    cleanup()
    renderAt('/reset-password')
    expect(screen.getByRole('heading', { name: /Reset Password/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reset Password/i })).toBeDisabled()
  })

  it('shows Settings PLM Integration at /settings', async () => {
    renderAt('/settings')
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Appearance$/ })).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /^PLM Integration \(Bloom\)$/ })).toBeInTheDocument()
  })

  it('shows test runs placeholder copy at /runs', async () => {
    renderAt('/runs')
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search test runs/i)).toBeInTheDocument()
    })
    expect(testRunsApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ latest_per_suite: true }),
    )
  })

  it('shows not-found state with Back link for bogus run detail', async () => {
    renderAt('/runs/999999')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Test Run Not Found/i })).toBeInTheDocument()
    })
    const backLink = screen.getByRole('link', { name: /Back to Test Runs/i })
    expect(backLink).toHaveAttribute('href', '/runs')
  })
})
