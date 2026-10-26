// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  accessApi: { users: vi.fn() },
}))

const api = await import('../api/client')
const AccessPeople = (await import('../components/AccessPeople')).default

/** Render the people view in a fresh query client. */
function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccessPeople />
    </QueryClientProvider>,
  )
}

const PEOPLE = [
  { id: 1, email: 'boss@example.com', full_name: 'Bo Boss', role: 'admin', is_active: true, groups: [], permissions: ['access.manage', 'audit.view'] },
  {
    id: 2,
    email: 'dee@example.com',
    full_name: 'Dee Developer',
    role: 'developer',
    is_active: true,
    groups: [{ id: 3, name: 'Access Managers' }, { id: 4, name: 'Station Managers' }],
    permissions: ['access.manage', 'bloom_publish.execute', 'custom_runs.create', 'evidence.view', 'products.view', 'reports.export', 'stations.manage', 'stations.view'],
  },
  { id: 3, email: 'val@example.com', full_name: 'Val Viewer', role: 'viewer', is_active: true, groups: [], permissions: ['evidence.view', 'products.view', 'reports.export', 'stations.view'] },
  { id: 4, email: 'gone@example.com', full_name: 'Gus Gone', role: 'viewer', is_active: false, groups: [], permissions: [] },
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.accessApi.users).mockResolvedValue(PEOPLE as never)
})
afterEach(cleanup)

describe('Per-person access view', () => {
  it('shows the base role, every group and the combined access of a person in two groups', async () => {
    renderIt()
    const dee = await screen.findByRole('region', { name: 'Dee Developer' })
    expect(within(dee).getByText('dee@example.com')).toBeTruthy()
    expect(within(dee).getByText('Developer')).toBeTruthy()
    expect(within(dee).getByText('Access Managers')).toBeTruthy()
    expect(within(dee).getByText('Station Managers')).toBeTruthy()
    const lines = within(dee).getAllByRole('listitem').map((item) => item.textContent)
    expect(lines).toEqual([
      'Access Managers',
      'Station Managers',
      'Runs, results and artifacts: Read',
      'Reports: Read',
      'Products: Read',
      'Test Stations: Read, Write',
      'Custom runs: Write',
      'Reports publishing: Write',
      'Access: Write',
    ])
  })

  it('shows every permission for an Admin and the base role lines for a person without groups', async () => {
    renderIt()
    const boss = await screen.findByRole('region', { name: 'Bo Boss' })
    expect(within(boss).getByText('Admin')).toBeTruthy()
    expect(within(boss).getByText('Every permission')).toBeTruthy()
    expect(within(boss).getByText('No groups')).toBeTruthy()
    const val = screen.getByRole('region', { name: 'Val Viewer' })
    expect(within(val).getByText('Viewer')).toBeTruthy()
    expect(within(val).getByText('No groups')).toBeTruthy()
    expect(within(val).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Runs, results and artifacts: Read',
      'Reports: Read',
      'Products: Read',
      'Test Stations: Read',
    ])
  })

  it('marks an inactive person and shows an empty access as no permissions', async () => {
    renderIt()
    const gus = await screen.findByRole('region', { name: 'Gus Gone' })
    expect(within(gus).getByText('Inactive')).toBeTruthy()
    expect(within(gus).getByText('No permissions')).toBeTruthy()
    expect(within(screen.getByRole('region', { name: 'Val Viewer' })).queryByText('Inactive')).toBeNull()
  })

  it('narrows the people by name and by email and says when nobody matches', async () => {
    renderIt()
    await screen.findByRole('region', { name: 'Dee Developer' })
    const search = screen.getByLabelText('Search people')
    fireEvent.change(search, { target: { value: 'DEE' } })
    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Dee Developer'])
    fireEvent.change(search, { target: { value: 'val@' } })
    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Val Viewer'])
    fireEvent.change(search, { target: { value: 'nobody' } })
    expect(screen.getByText('No matching people.')).toBeTruthy()
    expect(screen.queryAllByRole('region')).toHaveLength(0)
  })

  it('reports a load failure and reloads on Retry', async () => {
    vi.mocked(api.accessApi.users).mockRejectedValueOnce(new Error('down'))
    renderIt()
    expect((await screen.findByRole('alert')).textContent).toContain('Could not load people.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('region', { name: 'Dee Developer' })).toBeTruthy()
    await waitFor(() => expect(api.accessApi.users).toHaveBeenCalledTimes(2))
  })
})
