// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const stations = {
  id: 4,
  name: 'Stations',
  description: 'Manage Test Stations.',
  permissions: { stations: ['view', 'manage'] },
  is_default: true,
  system_key: 'stations',
  created_at: '',
  updated_at: '',
}
const keys = { ...stations, id: 11, name: 'Station keys', is_default: false, system_key: null, permissions: { stations: ['manage'] } }

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (error: { message?: string }, fallback: string) => error?.message || fallback,
  policiesApi: {
    list: vi.fn(),
    catalogue: vi.fn().mockResolvedValue([
      { resource: 'stations', actions: ['view', 'manage'] },
      { resource: 'audit', actions: ['view'] },
      { resource: 'reports', actions: ['export'] },
      { resource: 'custom_runs', actions: ['create'] },
      { resource: 'bloom_publish', actions: ['execute'] },
      { resource: 'settings', actions: ['view', 'edit'] },
      { resource: 'evidence', actions: ['view'] },
    ]),
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    duplicate: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
  },
}))

const api = await import('../api/client')
const AccessPolicies = (await import('../components/AccessPolicies')).default

function renderIt(canEdit = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccessPolicies canEdit={canEdit} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.policiesApi.list).mockResolvedValue([stations, keys] as never)
})
afterEach(cleanup)

describe('Policies', () => {
  it('shows Read and Write through the existing policy viewer and resource matrix', async () => {
    renderIt()
    await screen.findByText('Station keys')
    expect(screen.getAllByText('Write')).toHaveLength(2)
    fireEvent.click(screen.getByLabelText('View Stations'))
    const dialog = await screen.findByRole('dialog', { name: 'View policy' })
    expect((within(dialog).getByLabelText('Read Test Stations') as HTMLInputElement).checked).toBe(true)
    expect((within(dialog).getByLabelText('Write Test Stations') as HTMLInputElement).checked).toBe(true)
    expect(within(dialog).getByLabelText('Read Test Stations').hasAttribute('disabled')).toBe(true)
    expect(within(dialog).queryByRole('button', { name: 'Save policy' })).toBeNull()
  })

  it('keeps defaults read-only and lets an Admin duplicate one', async () => {
    renderIt()
    await screen.findByText('Station keys')
    expect(screen.queryByLabelText('Edit Stations')).toBeNull()
    fireEvent.click(screen.getByLabelText('Duplicate Stations'))
    await waitFor(() => expect(api.policiesApi.duplicate).toHaveBeenCalledWith(4))
  })

  it('creates a policy from the catalogue', async () => {
    renderIt()
    await screen.findByText('Station keys')
    fireEvent.click(screen.getByRole('button', { name: 'New policy' }))
    const dialog = await screen.findByRole('dialog', { name: 'New policy' })
    fireEvent.change(within(dialog).getByLabelText('Policy name'), { target: { value: 'Auditors' } })
    fireEvent.click(await within(dialog).findByLabelText('Read Audit log'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save policy' }))
    await waitFor(() =>
      expect(api.policiesApi.create).toHaveBeenCalledWith({
        name: 'Auditors',
        description: null,
        permissions: { audit: ['view'] },
      }),
    )
  })

  it('edits and deletes a custom policy', async () => {
    renderIt()
    await screen.findByText('Station keys')
    fireEvent.click(screen.getByLabelText('Edit Station keys'))
    const dialog = await screen.findByRole('dialog', { name: 'Edit policy' })
    fireEvent.click(await within(dialog).findByLabelText('Read Test Stations'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save policy' }))
    await waitFor(() =>
      expect(api.policiesApi.update).toHaveBeenCalledWith(11, {
        name: 'Station keys',
        description: 'Manage Test Stations.',
        permissions: { stations: ['manage', 'view'] },
      }),
    )
    fireEvent.click(screen.getByLabelText('Delete Station keys'))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Delete policy' })).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.policiesApi.remove).toHaveBeenCalledWith(11))
  })

  it('preserves a write-only stored grant when saving the editor', async () => {
    renderIt()
    await screen.findByText('Station keys')
    fireEvent.click(screen.getByLabelText('Edit Station keys'))
    const dialog = await screen.findByRole('dialog', { name: 'Edit policy' })
    expect((within(dialog).getByLabelText('Read Test Stations') as HTMLInputElement).checked).toBe(false)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save policy' }))
    await waitFor(() => expect(api.policiesApi.update).toHaveBeenCalledWith(11, { name: 'Station keys', description: 'Manage Test Stations.', permissions: { stations: ['manage'] } }))
  })

  it('maps Read and Write controls to the existing export and execution operations', async () => {
    renderIt()
    await screen.findByText('Station keys')
    fireEvent.click(screen.getByRole('button', { name: 'New policy' }))
    const dialog = await screen.findByRole('dialog', { name: 'New policy' })
    fireEvent.change(within(dialog).getByLabelText('Policy name'), { target: { value: 'Operations' } })
    for (const label of ['Read Reports', 'Write Custom runs', 'Write Publish to Bloom', 'Write Settings and integrations']) fireEvent.click(within(dialog).getByLabelText(label))
    expect((within(dialog).getByLabelText('Write Runs, results and artifacts') as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save policy' }))
    await waitFor(() => expect(api.policiesApi.create).toHaveBeenCalledWith({ name: 'Operations', description: null, permissions: { reports: ['export'], custom_runs: ['create'], bloom_publish: ['execute'], settings: ['edit'] } }))
  })

  it('offers no changes to someone who is not an Admin', async () => {
    renderIt(false)
    await screen.findByText('Station keys')
    expect(screen.queryByRole('button', { name: 'New policy' })).toBeNull()
    expect(screen.queryByLabelText('Duplicate Stations')).toBeNull()
  })
})
