import { selectValue } from './select-value'
// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const group = (id: number, name: string, key: string | null, permissions: string[]) => ({
  id,
  name,
  description: null,
  is_default: key !== null,
  system_key: key,
  policies: [],
  permissions,
  members: [],
  created_at: '',
  updated_at: '',
})

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (error: { message?: string }) => error?.message ?? 'failed',
  accessRequestsApi: { list: vi.fn(), decide: vi.fn().mockResolvedValue({}) },
  groupsApi: { list: vi.fn() },
}))

const api = await import('../api/client')
const Panel = (await import('../components/AccessRequestsPanel')).default

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Panel />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.groupsApi.list).mockResolvedValue([
    group(1, 'Results Viewers', 'results_viewers', ['evidence.view']),
    group(2, 'Test Operators', 'test_operators', ['bloom_publish.execute', 'evidence.view']),
    group(9, 'Publishers', null, ['bloom_publish.execute']),
  ] as never)
  vi.mocked(api.accessRequestsApi.list).mockResolvedValue([
    {
      id: 5,
      resource_type: 'publish-to-bloom',
      resource_ref: '42',
      status: 'pending',
      created_at: '',
      decided_at: null,
      requester_name: 'Val Viewer',
      requester_email: 'val@example.com',
      already_requested: false,
      mail_sent: null,
    },
  ] as never)
})
afterEach(cleanup)

describe('Access requests', () => {
  it('grants Publish to Bloom by giving Test Operators unless another publishing group is chosen', async () => {
    renderIt()
    expect(await screen.findByText(/asks for Publish to Bloom \(from run 42\)/)).toBeTruthy()
    const select = await screen.findByRole('combobox', { name: 'Group to give Val Viewer' })
    fireEvent.click(select)
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(['Test Operators', 'Publishers'])
    fireEvent.keyDown(select, { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Grant' }))
    await waitFor(() => expect(api.accessRequestsApi.decide).toHaveBeenCalledWith(5, 'granted', 2))
    selectValue(select, '9')
    fireEvent.click(screen.getByRole('button', { name: 'Grant' }))
    await waitFor(() => expect(api.accessRequestsApi.decide).toHaveBeenLastCalledWith(5, 'granted', 9))
  })

  it('refuses without a group and says when nothing is pending', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Refuse' }))
    await waitFor(() => expect(api.accessRequestsApi.decide).toHaveBeenCalledWith(5, 'refused', undefined))
    cleanup()
    vi.mocked(api.accessRequestsApi.list).mockResolvedValue([])
    renderIt()
    expect(await screen.findByText('No pending requests.')).toBeTruthy()
  })
})
