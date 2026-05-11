import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import App from '../App'

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
