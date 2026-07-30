import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import App from '../App'
import { testRunsApi } from '../api/client'

const loginMock = vi.hoisted(() => vi.fn())

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
    login: loginMock,
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
        has_bloom_token: false,
        bloom_token_prefix: null,
        bloom_token_rotated_at: null,
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
  localStorage.clear()
})

describe('route smoke (Bud)', () => {
  it('shows public auth screens without redirect loops', async () => {
    renderAt('/login')
    expect(screen.getByRole('heading', { name: /Welcome to Bud/i })).toBeInTheDocument()
    const attribution = screen.getByRole('link', { name: 'Powered by EmbedLabs' })
    expect(attribution).toHaveAttribute(
      'href',
      'https://www.embedlabs.net',
    )
    expect(attribution).toHaveClass('text-lime-200/60')
    expect(attribution).not.toHaveClass('fixed', 'bottom-3', 'left-3')
    expect(screen.queryByRole('link', { name: 'by EmbedLabs' })).not.toBeInTheDocument()
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

  it('shows the API detail when login fails', async () => {
    loginMock.mockRejectedValueOnce(Object.assign(
      new Error('Request failed with status code 401'),
      {
        isAxiosError: true,
        response: { data: { detail: 'Incorrect email or password' } },
      },
    ))

    renderAt('/login')
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument()
  })

  it('shows Settings PLM Integration at /settings', async () => {
    renderAt('/settings')
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Appearance$/ })).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /^PLM Integration \(Bloom\)$/ })).toBeInTheDocument()
  })

  it('moves collapsed attribution to a dedicated footer below main content', () => {
    const { container } = renderAt('/')

    const sidebar = document.querySelector('aside')
    const main = document.querySelector('main')
    const layout = container.firstElementChild
    expect(sidebar).not.toBeNull()
    expect(main).not.toBeNull()
    expect(layout).toHaveClass('h-screen', 'overflow-hidden')
    expect(main).toHaveClass('min-h-0', 'overflow-auto')
    expect(sidebar).toHaveClass('overflow-x-hidden')
    expect(
      screen.getByRole('link', { name: 'Powered by EmbedLabs' }).closest('aside'),
    ).toBe(sidebar)
    expect(screen.getByText('v1.0.0')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }))

    const collapsedAttribution = screen.getByRole('link', {
      name: 'Powered by EmbedLabs © 2026',
    })
    expect(collapsedAttribution.closest('aside')).toBeNull()
    expect(collapsedAttribution.closest('main')).toBeNull()
    const footer = collapsedAttribution.closest('footer')
    expect(footer).not.toBeNull()
    expect(footer).toHaveClass('shrink-0', 'justify-center')
    expect(main?.nextElementSibling).toBe(footer)
    expect(collapsedAttribution).toHaveClass('whitespace-nowrap')
    expect(collapsedAttribution).not.toHaveClass('fixed', 'absolute')
    expect(collapsedAttribution).toHaveTextContent('Powered by EmbedLabs © 2026')
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

  it('does not show a Bloom link when Bud is standalone', async () => {
    renderAt('/runs')
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search test runs/i)).toBeInTheDocument()
    })

    expect(screen.queryByRole('link', { name: /Bloom PLM/i })).not.toBeInTheDocument()
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
