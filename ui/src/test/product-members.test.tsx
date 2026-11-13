// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const auth = vi.hoisted(() => ({
  user: { role: 'admin', full_name: 'Admin', email: 'admin@example.com', permissions: [] as string[] },
}))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: auth.user }) }))
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    accessApi: { users: vi.fn() },
    groupsApi: { list: vi.fn() },
    productsApi: { members: vi.fn(), setGroupMembers: vi.fn() },
  }
})

const { accessApi, groupsApi, productsApi } = await import('../api/client')
const ProductMembers = (await import('../components/ProductMembers')).default

const GROUP = { id: 2, name: 'Results Viewers', description: null, is_default: true, system_key: 'results_viewers', policies: [], permissions: ['evidence.view', 'reports.export'], members: [], created_at: '', updated_at: '' }
const APP_ONLY = { ...GROUP, id: 3, name: 'Station Managers', system_key: 'station_managers', permissions: ['stations.view', 'stations.manage'] }
const RITA = { id: 7, email: 'rita@example.com', full_name: 'Rita Reader', role: 'viewer', is_active: true, groups: [], permissions: [] }
const KAI = { id: 8, email: 'kai@example.com', full_name: 'Kai Keeper', role: 'viewer', is_active: true, groups: [], permissions: [] }
const MEMBER = { user_id: 7, email: 'rita@example.com', full_name: 'Rita Reader', role: 'viewer', profile_picture_url: null, group_id: 2, group_name: 'Results Viewers' }

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ProductMembers productId={5} /></QueryClientProvider>)
}

describe('Product members', () => {
  beforeEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.mocked(accessApi.users).mockResolvedValue([RITA, KAI] as never)
    vi.mocked(groupsApi.list).mockResolvedValue([GROUP, APP_ONLY] as never)
    vi.mocked(productsApi.members).mockResolvedValue([MEMBER] as never)
    vi.mocked(productsApi.setGroupMembers).mockResolvedValue([] as never)
  })

  it('shows one roster per group that gives access per product, with its people', async () => {
    renderIt()
    const roster = await screen.findByRole('region', { name: 'Results Viewers' })
    expect(within(roster).getByText('Rita Reader')).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Station Managers' })).toBeNull()
    expect(productsApi.members).toHaveBeenCalledWith(5)
  })

  it('saves the selected people for the group on this product', async () => {
    renderIt()
    const roster = await screen.findByRole('region', { name: 'Results Viewers' })
    fireEvent.click(within(roster).getByRole('button', { name: 'Select members' }))
    fireEvent.click(within(roster).getByLabelText('Select Kai Keeper'))
    fireEvent.click(within(roster).getByRole('button', { name: 'Save selection' }))
    await waitFor(() => expect(productsApi.setGroupMembers).toHaveBeenCalledWith(5, 2, [7, 8]))
  })

  it('removes one person and keeps the others', async () => {
    vi.mocked(productsApi.members).mockResolvedValue([MEMBER, { ...MEMBER, user_id: 8, email: 'kai@example.com', full_name: 'Kai Keeper' }] as never)
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Remove Rita Reader from Results Viewers' }))
    await waitFor(() => expect(productsApi.setGroupMembers).toHaveBeenCalledWith(5, 2, [8]))
  })

  it('shows the refusal of a save', async () => {
    vi.mocked(productsApi.setGroupMembers).mockRejectedValue({ isAxiosError: true, message: 'x', response: { data: { detail: 'You can only give access that you hold yourself' }, headers: {} } })
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Remove Rita Reader from Results Viewers' }))
    expect(await screen.findByText('You can only give access that you hold yourself')).toBeTruthy()
  })

  it('offers no change to a user who does not hold the group', async () => {
    auth.user = { ...auth.user, role: 'viewer', permissions: ['access.manage'] }
    renderIt()
    const roster = await screen.findByRole('region', { name: 'Results Viewers' })
    expect(within(roster).queryByRole('button', { name: 'Select members' })).toBeNull()
    expect(within(roster).queryByRole('button', { name: 'Remove Rita Reader from Results Viewers' })).toBeNull()
    auth.user = { ...auth.user, role: 'admin', permissions: [] }
  })
})
