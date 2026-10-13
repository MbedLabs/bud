// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (error: { message?: string }, fallback: string) => error?.message || fallback,
  accessApi: { users: vi.fn() },
  groupsApi: {
    list: vi.fn(),
    addMember: vi.fn().mockResolvedValue({}),
    removeMember: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, role: 'admin' }, refreshUser: vi.fn().mockResolvedValue(undefined) }) }))

const api = await import('../api/client')
const AccessUsers = (await import('../components/AccessUsers')).default

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccessUsers />
    </QueryClientProvider>,
  )
}

const operators = {
  id: 2,
  name: 'Test Operators',
  description: null,
  is_default: true,
  system_key: 'test_operators',
  policies: [],
  permissions: ['bloom_publish.execute', 'custom_runs.create', 'evidence.view'],
  members: [{ user_id: 7, email: 'val@example.com', full_name: 'Val Viewer', role: 'viewer' }],
  created_at: '',
  updated_at: '',
}
const stations = { ...operators, id: 3, name: 'Station Managers', system_key: 'station_managers', members: [], permissions: ['evidence.view', 'stations.manage'] }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.groupsApi.list).mockResolvedValue([operators, stations] as never)
  vi.mocked(api.accessApi.users).mockResolvedValue([
    { id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin', is_active: true, groups: [], permissions: [] },
    {
      id: 7,
      email: 'val@example.com',
      full_name: 'Val Viewer',
      role: 'viewer',
      is_active: true,
      groups: [{ id: 2, name: 'Test Operators' }],
      permissions: ['bloom_publish.execute', 'custom_runs.create', 'evidence.view'],
    },
    {
      id: 8,
      email: 'dee@example.com',
      full_name: 'Dee Developer',
      role: 'developer',
      is_active: true,
      groups: [],
      permissions: ['bloom_publish.execute', 'custom_runs.create', 'evidence.view'],
    },
  ] as never)
})
afterEach(cleanup)

describe('Group assignments', () => {
  it('shows one unified chooser with existing members checked and Admin above Developer', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Test Operators' })
    const roster = screen.getByRole('region', { name: 'Test Operators' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Choose people' }))
    expect((within(roster).getByLabelText('Select Val Viewer') as HTMLInputElement).checked).toBe(true)
    fireEvent.change(within(roster).getByPlaceholderText('Search people...'), { target: { value: 'dee@' } })
    expect(within(roster).queryByLabelText('Select Val Viewer')).toBeNull()
    expect(within(roster).getByLabelText('Select Dee Developer')).toBeTruthy()
    const stationRoster = screen.getByRole('region', { name: 'Station Managers' })
    fireEvent.click(within(stationRoster).getByRole('button', { name: 'Choose people' }))
    expect(within(stationRoster).queryByLabelText('Select Val Viewer')).toBeNull()
    expect(within(stationRoster).getByLabelText('Select Admin')).toBeTruthy()
    expect(within(stationRoster).getByLabelText('Select Dee Developer')).toBeTruthy()
  })

  it('saves only membership differences for this group, preserving other groups', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Test Operators' })
    const roster = screen.getByRole('region', { name: 'Test Operators' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Choose people' }))
    fireEvent.click(within(roster).getByLabelText('Select Dee Developer'))
    fireEvent.click(within(roster).getByRole('button', { name: 'Save selection' }))
    await waitFor(() => expect(api.groupsApi.addMember).toHaveBeenCalledWith(2, 8))
    expect(api.groupsApi.removeMember).not.toHaveBeenCalled()
  })

  it('removes through the avatar action and shows a refusal', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Test Operators' })
    vi.mocked(api.groupsApi.removeMember).mockRejectedValueOnce(new Error('Could not remove assignment'))
    const remove = screen.getByLabelText('Remove Val Viewer from Test Operators')
    expect(remove.className).toContain('group-hover/image:opacity-100')
    fireEvent.click(remove)
    expect((await screen.findByRole('alert')).textContent).toContain('Could not remove assignment')
    expect(api.groupsApi.removeMember).toHaveBeenCalledWith(2, 7)
  })

  it('refreshes saved membership after a partial failure and keeps untouched members', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Test Operators' })
    const roster = screen.getByRole('region', { name: 'Test Operators' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Choose people' }))
    fireEvent.click(within(roster).getByLabelText('Select Admin'))
    fireEvent.click(within(roster).getByLabelText('Select Dee Developer'))
    fireEvent.click(within(roster).getByLabelText('Select Val Viewer'))
    vi.mocked(api.groupsApi.addMember).mockImplementationOnce(async () => {
      vi.mocked(api.groupsApi.list).mockResolvedValue([{ ...operators, members: [...operators.members, { user_id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin' }] }, stations] as never)
      return {} as never
    }).mockRejectedValueOnce(new Error('Could not assign Dee Developer'))
    fireEvent.click(within(roster).getByRole('button', { name: 'Save selection' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Could not assign Dee Developer')
    expect(api.groupsApi.removeMember).not.toHaveBeenCalled()
    await waitFor(() => expect(api.groupsApi.list).toHaveBeenCalledTimes(2))
    fireEvent.click(within(roster).getByRole('button', { name: 'Cancel selection' }))
    expect(within(roster).getByLabelText('Remove Admin from Test Operators')).toBeTruthy()
    expect(within(roster).getByLabelText('Remove Val Viewer from Test Operators')).toBeTruthy()
    expect(within(roster).queryByLabelText('Remove Dee Developer from Test Operators')).toBeNull()
  })
})
