import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UsersPage from '../pages/Users'

const update = vi.hoisted(() => vi.fn())
const getAuthUser = vi.hoisted(() => vi.fn())

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: getAuthUser() }),
}))

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const person = (id: number, name: string, role: 'admin' | 'developer' | 'viewer') => ({
    id,
    email: `${name.toLowerCase()}@bud.example`,
    full_name: name,
    role,
    is_active: true,
    created_at: '2026-07-01T12:00:00Z',
    updated_at: '2026-07-01T12:00:00Z',
  })
  return {
    ...actual,
    usersApi: {
      ...actual.usersApi,
      list: vi.fn().mockResolvedValue([person(1, 'Ada', 'admin'), person(2, 'Val', 'viewer'), person(3, 'Dev', 'developer')]),
      update,
    },
    groupsApi: { ...actual.groupsApi, list: vi.fn().mockResolvedValue([]) },
  }
})

function renderIt() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsersPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getAuthUser.mockReturnValue({ id: 1, email: 'ada@bud.example', full_name: 'Ada', role: 'admin', is_active: true })
  update.mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('user roles', () => {
  it('lets an administrator make a viewer a developer', async () => {
    renderIt()
    const picker = (await screen.findByLabelText('Role of Val')) as HTMLSelectElement
    expect(Array.from(picker.options).map((o) => o.value)).toEqual(['viewer', 'developer'])
    fireEvent.change(picker, { target: { value: 'developer' } })
    await waitFor(() => expect(update).toHaveBeenCalledWith(2, { role: 'developer' }))
    expect((screen.getByLabelText('Role of Dev') as HTMLSelectElement).value).toBe('developer')
  })

  it("shows an administrator's role without offering a change", async () => {
    renderIt()
    await screen.findByLabelText('Role of Val')
    expect(screen.queryByLabelText('Role of Ada')).toBeNull()
    expect(screen.getByText('Admin')).toBeTruthy()
  })

  it('shows roles without pickers to someone who is not an administrator', async () => {
    getAuthUser.mockReturnValue({ id: 3, email: 'dev@bud.example', full_name: 'Dev', role: 'developer', is_active: true })
    renderIt()
    expect(await screen.findByText('Developer')).toBeTruthy()
    expect(screen.queryByLabelText('Role of Val')).toBeNull()
  })

  it('offers Viewer, Developer and Admin when inviting', async () => {
    renderIt()
    await screen.findByLabelText('Role of Val')
    fireEvent.click(screen.getByRole('button', { name: 'Invite User' }))
    const role = screen.getByTitle('Role') as HTMLSelectElement
    expect(Array.from(role.options).map((o) => o.value)).toEqual(['viewer', 'developer', 'admin'])
  })
})
