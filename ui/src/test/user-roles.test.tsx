import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UsersPage from '../pages/Users'
import { usersApi } from '../api/client'

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
      update: vi.fn().mockResolvedValue({}),
    },
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
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('user roles', () => {
  it('shows each role without a picker until Edit role is chosen', async () => {
    renderIt()
    await screen.findByText('Val')
    for (const [name, label] of [['Ada', 'Admin'], ['Val', 'Viewer'], ['Dev', 'Developer']]) {
      const row = screen.getByText(name).closest('tr') as HTMLElement
      expect(within(row).getByText(label)).toBeTruthy()
      expect(within(row).queryByRole('combobox')).toBeNull()
    }
  })

  it('offers Edit role on every user but the signed-in Admin', async () => {
    renderIt()
    await screen.findByText('Val')
    const editable = (name: string) => within(screen.getByText(name).closest('tr') as HTMLElement).queryByTitle('Edit role')
    expect(editable('Ada')).toBeNull()
    expect(editable('Val')).toBeTruthy()
    expect(editable('Dev')).toBeTruthy()
  })

  it('changes a Viewer to Developer from the role picker', async () => {
    renderIt()
    await screen.findByText('Val')
    const row = screen.getByText('Val').closest('tr') as HTMLElement
    fireEvent.click(within(row).getByTitle('Edit role'))
    fireEvent.click(within(row).getByRole('combobox'))
    expect(screen.getAllByRole('option').map((option) => option.getAttribute('data-value'))).toEqual(['developer', 'viewer'])
    fireEvent.click(screen.getByRole('option', { name: 'Developer' }))
    await waitFor(() => expect(usersApi.update).toHaveBeenCalledWith(2, { role: 'developer' }))
  })

  it('offers Viewer, Developer and Admin when inviting', async () => {
    renderIt()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Invite User' }))
    fireEvent.click(screen.getByRole('combobox', { name: 'Role' }))
    expect(screen.getAllByRole('option').map((option) => option.getAttribute('data-value'))).toEqual(['viewer', 'developer', 'admin'])
  })
})
