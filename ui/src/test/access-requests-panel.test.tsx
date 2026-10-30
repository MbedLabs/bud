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
      resource_label: 'Nightly smoke',
      resource_deleted: false,
    },
  ] as never)
})
afterEach(cleanup)

describe('Access requests', () => {
  it('grants Publish to Bloom by giving Test Operators unless another publishing group is chosen', async () => {
    renderIt()
    expect(await screen.findByText(/asks for Publish to Bloom \(from run Nightly smoke\)/)).toBeTruthy()
    expect(screen.queryByText(/42/)).toBeNull()
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

  it('names stored requests by their run or product and marks a deleted one', async () => {
    const base = {
      status: 'pending', created_at: '', decided_at: null, requester_name: 'Val Viewer',
      requester_email: 'val@example.com', already_requested: false, mail_sent: null,
    }
    vi.mocked(api.accessRequestsApi.list).mockResolvedValue([
      { ...base, id: 6, resource_type: 'test-run', resource_ref: '7', resource_label: 'Soak test', resource_deleted: false },
      { ...base, id: 7, resource_type: 'product', resource_ref: '3', resource_label: 'Gateway board', resource_deleted: false },
      { ...base, id: 8, resource_type: 'publish-to-bloom', resource_ref: '99', resource_label: null, resource_deleted: true },
      { ...base, id: 9, resource_type: 'test-run', resource_ref: '99999999999', resource_label: null, resource_deleted: false },
    ] as never)
    renderIt()
    expect(await screen.findByText(/asks for test run Soak test/)).toBeTruthy()
    expect(screen.getByText(/asks for product Gateway board/)).toBeTruthy()
    expect(screen.getByText(/asks for Publish to Bloom \(from run 99 \(deleted\)\)/)).toBeTruthy()
    expect(screen.getByText(/asks for test run$/)).toBeTruthy()
    expect(screen.queryByText(/99999999999/)).toBeNull()
  })
})
