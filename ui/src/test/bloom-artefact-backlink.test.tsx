// @vitest-environment jsdom
/**
 * The Bloom artefact a run reached.
 *
 * The pairing is optional in both directions, so the whole surface has to
 * disappear cleanly when Bud is running with no Bloom - no empty row, no
 * placeholder, no warning - and be a working link when there is one.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { safeExternalUrl } from '../lib/externalLink'
import { RESPONSES, resetApiMocks, testRun, user } from './apiFixtures'

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
    user,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

const client = await import('../api/client')
const TestRuns = (await import('../pages/TestRuns')).default

const PAIRED = {
  bloom_artefact_id: 'FLT-CMP-003',
  bloom_artefact_name: 'Nightly regression',
  bloom_artefact_url: 'https://bloom.example.com/projects/FLT/campaigns/12',
}

function renderRuns() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TestRuns />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('the Bloom artefact a run reached', () => {
  beforeEach(() => {
    resetApiMocks(client as unknown as Record<string, unknown>, vi)
  })

  afterEach(() => {
    cleanup()
  })

  it('links a paired run to its campaign in Bloom', async () => {
    vi.mocked(client.testRunsApi.list).mockResolvedValue({
      runs: [{ ...testRun, ...PAIRED }],
      total: 1,
    })
    renderRuns()

    const link = (await screen.findByRole('link', {
      name: /FLT-CMP-003/,
    })) as HTMLAnchorElement
    expect(link.href).toBe('https://bloom.example.com/projects/FLT/campaigns/12')
    expect(link.target).toBe('_blank')
    expect(link.rel).toContain('noopener')
    expect(link.title).toBe('Nightly regression')
  })

  it('shows nothing at all when no Bloom is paired', async () => {
    vi.mocked(client.testRunsApi.list).mockResolvedValue({ runs: [testRun], total: 1 })
    renderRuns()

    await screen.findByText(testRun.name)
    expect(screen.queryByText(/CMP-/)).toBeNull()
    await waitFor(() => {
      expect(document.querySelector('a[href^="https://bloom"]')).toBeNull()
    })
  })

  it('will not render an address that would execute rather than navigate', async () => {
    vi.mocked(client.testRunsApi.list).mockResolvedValue({
      runs: [{ ...testRun, ...PAIRED, bloom_artefact_url: 'javascript:alert(1)' }],
      total: 1,
    })
    renderRuns()

    await screen.findByText(testRun.name)
    expect(screen.queryByRole('link', { name: /FLT-CMP-003/ })).toBeNull()
  })

  it('stays quiet when Bloom named an artefact but no address for it', async () => {
    vi.mocked(client.testRunsApi.list).mockResolvedValue({
      runs: [{ ...testRun, ...PAIRED, bloom_artefact_url: null }],
      total: 1,
    })
    renderRuns()

    await screen.findByText(testRun.name)
    expect(screen.queryByRole('link', { name: /FLT-CMP-003/ })).toBeNull()
  })
})

describe('safeExternalUrl', () => {
  it('passes an http or https address through unchanged', () => {
    expect(safeExternalUrl('https://bloom.example.com/projects/FLT/campaigns/12')).toBe(
      'https://bloom.example.com/projects/FLT/campaigns/12',
    )
    expect(safeExternalUrl('http://bloom.internal/projects/FLT/campaigns/12')).toBe(
      'http://bloom.internal/projects/FLT/campaigns/12',
    )
  })

  it('refuses a scheme that would execute rather than navigate', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(safeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeExternalUrl('vbscript:msgbox(1)')).toBeNull()
  })

  it('refuses anything that is not a URL at all', () => {
    expect(safeExternalUrl('/projects/FLT/campaigns/12')).toBeNull()
    expect(safeExternalUrl('')).toBeNull()
    expect(safeExternalUrl(null)).toBeNull()
    expect(safeExternalUrl(undefined)).toBeNull()
  })
})
