// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const results = { id: 1, name: 'Results' }
const customRuns = { id: 2, name: 'Custom runs' }

const defaultGroup = {
  id: 2,
  name: 'Test Operators',
  description: 'See results, queue custom runs and publish to Bloom.',
  is_default: true,
  system_key: 'test_operators',
  policies: [results, customRuns],
  permissions: ['custom_runs.create', 'evidence.view'],
  members: [],
  created_at: '',
  updated_at: '',
}

const customGroup = {
  id: 9,
  name: 'Bench crew',
  description: 'Bench A',
  is_default: false,
  system_key: null,
  policies: [results],
  permissions: ['evidence.view'],
  members: [{ user_id: 7, email: 'val@example.com', full_name: 'Val Viewer', role: 'viewer' }],
  created_at: '',
  updated_at: '',
}

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (error: { message?: string }, fallback: string) => error?.message || fallback,
  groupsApi: {
    list: vi.fn(),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    duplicate: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
    addMember: vi.fn().mockResolvedValue({}),
    removeMember: vi.fn().mockResolvedValue({}),
  },
  policiesApi: {
    list: vi.fn().mockResolvedValue([
      { ...results, description: null, permissions: {}, is_default: true, system_key: 'results' },
      { ...customRuns, description: null, permissions: {}, is_default: true, system_key: 'custom_runs' },
    ]),
  },
  accessApi: {
    users: vi.fn().mockResolvedValue([
      { id: 7, email: 'val@example.com', full_name: 'Val Viewer', role: 'viewer', groups: [], permissions: [] },
      { id: 8, email: 'dee@example.com', full_name: 'Dee Developer', role: 'developer', groups: [], permissions: [] },
    ]),
  },
}))

const api = await import('../api/client')
const UserGroups = (await import('../components/UserGroups')).default

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <UserGroups />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.groupsApi.list).mockResolvedValue([defaultGroup, customGroup] as never)
})
afterEach(cleanup)

describe('Groups', () => {
  it('defines policy bundles without member controls', async () => {
    renderIt()
    expect(await screen.findByText('Bench crew')).toBeTruthy()
    expect(screen.queryByText('val@example.com')).toBeNull()
    expect(screen.getByText('Results, Custom runs')).toBeTruthy()
    expect(screen.queryByText('Select members')).toBeNull()
    expect(api.accessApi.users).not.toHaveBeenCalled()
    expect(screen.queryByText('Read')).toBeNull()
    expect(screen.queryByText('Write')).toBeNull()
  })

  it('keeps default groups read-only but lets them be duplicated', async () => {
    renderIt()
    await screen.findByText('Test Operators')
    expect(screen.getByText('Default')).toBeTruthy()
    expect(screen.queryByLabelText('Edit Test Operators')).toBeNull()
    expect(screen.queryByLabelText('Delete Test Operators')).toBeNull()
    fireEvent.click(screen.getByLabelText('Duplicate Test Operators'))
    await waitFor(() => expect(api.groupsApi.duplicate).toHaveBeenCalledWith(2))
  })

  it('creates a group from policies', async () => {
    renderIt()
    await screen.findByText('Bench crew')
    fireEvent.click(screen.getByRole('button', { name: 'New group' }))
    const dialog = await screen.findByRole('dialog', { name: 'New group' })
    fireEvent.change(within(dialog).getByLabelText('Group name'), { target: { value: 'Night shift' } })
    fireEvent.click(within(dialog).getByLabelText('Custom runs'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save group' }))
    await waitFor(() =>
      expect(api.groupsApi.create).toHaveBeenCalledWith({ name: 'Night shift', description: null, policy_ids: [2] }),
    )
  })

  it('edits a custom group policy bundle', async () => {
    renderIt()
    await screen.findByText('Bench crew')
    fireEvent.click(screen.getByLabelText('Edit Bench crew'))
    const dialog = await screen.findByRole('dialog', { name: 'Edit group' })
    fireEvent.click(within(dialog).getByLabelText('Custom runs'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save group' }))
    await waitFor(() =>
      expect(api.groupsApi.update).toHaveBeenCalledWith(9, {
        name: 'Bench crew',
        description: 'Bench A',
        policy_ids: [1, 2],
      }),
    )

    expect(api.groupsApi.addMember).not.toHaveBeenCalled()
    expect(api.groupsApi.removeMember).not.toHaveBeenCalled()
  })

  it('deletes through the confirmation dialog and shows a failure', async () => {
    renderIt()
    await screen.findByText('Bench crew')
    fireEvent.click(screen.getByLabelText('Delete Bench crew'))
    const dialog = await screen.findByRole('dialog', { name: 'Delete group' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(api.groupsApi.remove).not.toHaveBeenCalled()

    vi.mocked(api.groupsApi.remove).mockRejectedValueOnce(new Error('You can only give access that you hold yourself'))
    fireEvent.click(screen.getByLabelText('Delete Bench crew'))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Delete group' })).getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('You can only give access that you hold yourself')).toBeTruthy()
  })
})
