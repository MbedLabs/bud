// @vitest-environment jsdom
/**
 * User groups on the Users page: create a group, set its role, add and remove
 * members, grant and revoke products (one or all), and delete it.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const group = {
  id: 3,
  name: 'Gateway team',
  description: 'Bench A',
  role: 'viewer',
  members: [{ user_id: 7, email: 'val@example.com', full_name: 'Val Viewer' }],
  grants: [
    { id: 9, product_id: 1, product_name: 'Gateway' },
    { id: 10, product_id: null, product_name: null },
  ],
  created_at: '',
  updated_at: '',
}

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (error: { message?: string }, fallback: string) => error?.message || fallback,
  groupsApi: {
    list: vi.fn(),
    create: vi.fn().mockResolvedValue(group),
    update: vi.fn().mockResolvedValue(group),
    remove: vi.fn().mockResolvedValue(undefined),
    addMember: vi.fn().mockResolvedValue(group),
    removeMember: vi.fn().mockResolvedValue(group),
    addGrant: vi.fn().mockResolvedValue(group),
    removeGrant: vi.fn().mockResolvedValue(group),
  },
  usersApi: {
    list: vi.fn().mockResolvedValue([
      { id: 7, email: 'val@example.com', full_name: 'Val Viewer' },
      { id: 8, email: 'ada@example.com', full_name: 'Ada Admin' },
    ]),
  },
  productsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 1, name: 'Gateway', description: null },
      { id: 2, name: 'Sensor', description: null },
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
  vi.mocked(api.groupsApi.list).mockResolvedValue([group] as never)
})
afterEach(cleanup)

describe('User groups', () => {
  it('lists a group with its members and grants', async () => {
    renderIt()
    expect(await screen.findByText('Gateway team')).toBeTruthy()
    expect(screen.getByText('Bench A')).toBeTruthy()
    expect(screen.getByText('val@example.com')).toBeTruthy()
    expect(screen.getByText('All products')).toBeTruthy()
    expect(screen.getByText('Gateway', { selector: 'span' })).toBeTruthy()
  })

  it('creates a group with a role', async () => {
    renderIt()
    await screen.findByText('Gateway team')
    fireEvent.change(screen.getByLabelText('Group name'), { target: { value: 'Leads' } })
    fireEvent.change(screen.getByLabelText('Group role'), { target: { value: 'admin' } })
    fireEvent.click(screen.getByRole('button', { name: 'New group' }))
    await waitFor(() => expect(api.groupsApi.create).toHaveBeenCalledWith({ name: 'Leads', role: 'admin' }))
    await waitFor(() => expect((screen.getByLabelText('Group name') as HTMLInputElement).value).toBe(''))
  })

  it('changes the role, members and grants', async () => {
    renderIt()
    await screen.findByText('Gateway team')
    fireEvent.change(screen.getByLabelText('Role of Gateway team'), { target: { value: 'admin' } })
    await waitFor(() => expect(api.groupsApi.update).toHaveBeenCalledWith(3, { role: 'admin' }))

    fireEvent.change(screen.getByLabelText('Add a member to Gateway team'), { target: { value: '8' } })
    await waitFor(() => expect(api.groupsApi.addMember).toHaveBeenCalledWith(3, 8))
    fireEvent.click(screen.getByLabelText('Remove Val Viewer from Gateway team'))
    await waitFor(() => expect(api.groupsApi.removeMember).toHaveBeenCalledWith(3, 7))

    fireEvent.change(screen.getByLabelText('Grant a product to Gateway team'), { target: { value: '2' } })
    await waitFor(() => expect(api.groupsApi.addGrant).toHaveBeenCalledWith(3, 2))
    fireEvent.click(screen.getByLabelText('Revoke all products from Gateway team'))
    await waitFor(() => expect(api.groupsApi.removeGrant).toHaveBeenCalledWith(3, 10))
    fireEvent.click(screen.getByLabelText('Revoke Gateway from Gateway team'))
    await waitFor(() => expect(api.groupsApi.removeGrant).toHaveBeenCalledWith(3, 9))
  })

  it('offers all products only when not granted, and grants it', async () => {
    vi.mocked(api.groupsApi.list).mockResolvedValue([{ ...group, grants: [], members: [] }] as never)
    renderIt()
    expect(await screen.findByText('No products: members see none.')).toBeTruthy()
    expect(screen.getByText('No members.')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Grant a product to Gateway team'), { target: { value: 'all' } })
    await waitFor(() => expect(api.groupsApi.addGrant).toHaveBeenCalledWith(3, null))
  })

  it('deletes after confirming and shows a failure', async () => {
    window.confirm = () => false
    renderIt()
    await screen.findByText('Gateway team')
    fireEvent.click(screen.getByLabelText('Delete Gateway team'))
    expect(api.groupsApi.remove).not.toHaveBeenCalled()

    window.confirm = () => true
    vi.mocked(api.groupsApi.remove).mockRejectedValueOnce(new Error('Group not found'))
    fireEvent.click(screen.getByLabelText('Delete Gateway team'))
    expect(await screen.findByText('Group not found')).toBeTruthy()
  })

  it('says when there are no groups, and that admins see every product', async () => {
    vi.mocked(api.groupsApi.list).mockResolvedValue([])
    renderIt()
    expect(await screen.findByText('No groups yet.')).toBeTruthy()
    cleanup()
    vi.mocked(api.groupsApi.list).mockResolvedValue([{ ...group, role: 'admin', grants: [] }] as never)
    renderIt()
    expect(await screen.findByText('Admins see every product.')).toBeTruthy()
  })
})
