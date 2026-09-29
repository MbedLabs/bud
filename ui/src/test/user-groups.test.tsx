// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const group = {
  id: 3,
  name: 'Gateway team',
  description: 'Bench A',
  role: 'viewer',
  members: [{ user_id: 7, email: 'val@example.com', full_name: 'Val Viewer' }],
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
  },
  usersApi: {
    list: vi.fn().mockResolvedValue([
      { id: 7, email: 'val@example.com', full_name: 'Val Viewer' },
      { id: 8, email: 'ada@example.com', full_name: 'Ada Admin' },
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
  it('lists a group with its members and no product controls', async () => {
    renderIt()
    expect(await screen.findByText('Gateway team')).toBeTruthy()
    expect(screen.getByText('Bench A')).toBeTruthy()
    expect(screen.getByText('val@example.com')).toBeTruthy()
    expect(screen.queryByText('Products')).toBeNull()
    expect(screen.queryByLabelText('Grant a product to Gateway team')).toBeNull()
  })

  it('offers only the Developer and Viewer roles', async () => {
    renderIt()
    await screen.findByText('Gateway team')
    for (const label of ['Group role', 'Role of Gateway team']) {
      const options = Array.from((screen.getByLabelText(label) as HTMLSelectElement).options).map((o) => o.value)
      expect(options).toEqual(['viewer', 'developer'])
    }
  })

  it('creates a developer group', async () => {
    renderIt()
    await screen.findByText('Gateway team')
    fireEvent.change(screen.getByLabelText('Group name'), { target: { value: 'Testers' } })
    fireEvent.change(screen.getByLabelText('Group role'), { target: { value: 'developer' } })
    fireEvent.click(screen.getByRole('button', { name: 'New group' }))
    await waitFor(() => expect(api.groupsApi.create).toHaveBeenCalledWith({ name: 'Testers', role: 'developer' }))
    await waitFor(() => expect((screen.getByLabelText('Group name') as HTMLInputElement).value).toBe(''))
  })

  it('changes the role and the members', async () => {
    renderIt()
    await screen.findByText('Gateway team')
    fireEvent.change(screen.getByLabelText('Role of Gateway team'), { target: { value: 'developer' } })
    await waitFor(() => expect(api.groupsApi.update).toHaveBeenCalledWith(3, { role: 'developer' }))

    fireEvent.change(screen.getByLabelText('Add a member to Gateway team'), { target: { value: '8' } })
    await waitFor(() => expect(api.groupsApi.addMember).toHaveBeenCalledWith(3, 8))
    fireEvent.click(screen.getByLabelText('Remove Val Viewer from Gateway team'))
    await waitFor(() => expect(api.groupsApi.removeMember).toHaveBeenCalledWith(3, 7))
  })

  it('says when a group has no members', async () => {
    vi.mocked(api.groupsApi.list).mockResolvedValue([{ ...group, members: [] }] as never)
    renderIt()
    expect(await screen.findByText('No members.')).toBeTruthy()
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

  it('says when there are no groups', async () => {
    vi.mocked(api.groupsApi.list).mockResolvedValue([])
    renderIt()
    expect(await screen.findByText('No groups yet.')).toBeTruthy()
  })
})
