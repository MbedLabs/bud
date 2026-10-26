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

/** Render the assignments in a fresh query client. */
function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccessUsers />
    </QueryClientProvider>,
  )
}

const OPERATORS = 2
const STATIONS = 3
const DEE = 8
const dee = { user_id: DEE, email: 'dee@example.com', full_name: 'Dee Developer', role: 'developer' }
const operators = {
  id: OPERATORS,
  name: 'Test Operators',
  description: null,
  is_default: true,
  system_key: 'test_operators',
  policies: [],
  permissions: ['bloom_publish.execute', 'custom_runs.create', 'evidence.view'],
  members: [dee],
  created_at: '',
  updated_at: '',
}
const stations = {
  ...operators,
  id: STATIONS,
  name: 'Station Managers',
  system_key: 'station_managers',
  permissions: ['evidence.view', 'stations.manage'],
  members: [] as (typeof dee)[],
}

/** Mock the group and people listings with these members in Station Managers. */
function listings(stationMembers: (typeof dee)[]) {
  const held = [{ id: OPERATORS, name: 'Test Operators' }, ...(stationMembers.length ? [{ id: STATIONS, name: 'Station Managers' }] : [])]
  vi.mocked(api.groupsApi.list).mockResolvedValue([operators, { ...stations, members: stationMembers }] as never)
  vi.mocked(api.accessApi.users).mockResolvedValue([
    { id: 1, email: 'admin@example.com', full_name: 'Admin', role: 'admin', is_active: true, groups: [], permissions: [] },
    { id: DEE, email: 'dee@example.com', full_name: 'Dee Developer', role: 'developer', is_active: true, groups: held, permissions: ['custom_runs.create', 'evidence.view'] },
  ] as never)
}

beforeEach(() => {
  vi.clearAllMocks()
  listings([])
})
afterEach(cleanup)

describe('A person in several groups', () => {
  it('can be added to a second group without touching the first', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Station Managers' })
    const roster = screen.getByRole('region', { name: 'Station Managers' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Select members' }))
    const choice = within(roster).getByLabelText('Select Dee Developer') as HTMLInputElement
    expect(choice.checked).toBe(false)
    fireEvent.click(choice)
    fireEvent.click(within(roster).getByRole('button', { name: 'Save selection' }))
    await waitFor(() => expect(api.groupsApi.addMember).toHaveBeenCalledTimes(1))
    expect(vi.mocked(api.groupsApi.addMember).mock.calls).toEqual([[STATIONS, DEE]])
    expect(api.groupsApi.removeMember).not.toHaveBeenCalled()
  })

  it('shows the person in both rosters with a removal action for each group', async () => {
    renderIt()
    await screen.findByRole('heading', { name: 'Station Managers' })
    vi.mocked(api.groupsApi.addMember).mockImplementationOnce(async () => {
      listings([dee])
      return {} as never
    })
    const roster = screen.getByRole('region', { name: 'Station Managers' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Select members' }))
    fireEvent.click(within(roster).getByLabelText('Select Dee Developer'))
    fireEvent.click(within(roster).getByRole('button', { name: 'Save selection' }))
    expect(await screen.findByLabelText('Remove Dee Developer from Station Managers')).toBeTruthy()
    expect(screen.getByLabelText('Remove Dee Developer from Test Operators')).toBeTruthy()
  })

  it('removes the person from one group and keeps them in the other', async () => {
    listings([dee])
    renderIt()
    const stationRoster = await screen.findByRole('region', { name: 'Station Managers' })
    vi.mocked(api.groupsApi.removeMember).mockImplementationOnce(async () => {
      listings([])
      return {} as never
    })
    fireEvent.click(await within(stationRoster).findByLabelText('Remove Dee Developer from Station Managers'))
    await waitFor(() => expect(api.groupsApi.removeMember).toHaveBeenCalledTimes(1))
    expect(vi.mocked(api.groupsApi.removeMember).mock.calls).toEqual([[STATIONS, DEE]])
    await waitFor(() => expect(within(stationRoster).queryByLabelText('Remove Dee Developer from Station Managers')).toBeNull())
    const operatorsRoster = screen.getByRole('region', { name: 'Test Operators' })
    expect(within(operatorsRoster).getByLabelText('Remove Dee Developer from Test Operators')).toBeTruthy()
    expect(within(stationRoster).getByText('No people assigned.')).toBeTruthy()
  })
})
