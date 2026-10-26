import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UsersPage from '../pages/Users'
import { accessApi } from '../api/client'

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
      list: vi.fn().mockResolvedValue([person(1, 'Ada', 'admin'), person(2, 'Dev', 'developer'), person(3, 'Val', 'viewer')]),
    },
    accessApi: { ...actual.accessApi, users: vi.fn() },
  }
})

const accessUsers = [
  { id: 1, email: 'ada@bud.example', full_name: 'Ada', role: 'admin', is_active: true, groups: [], permissions: ['runs.read'] },
  {
    id: 2,
    email: 'dev@bud.example',
    full_name: 'Dev',
    role: 'developer',
    is_active: true,
    groups: [{ id: 4, name: 'Access Managers' }, { id: 5, name: 'Station Managers' }],
    permissions: ['access.manage', 'stations.manage'],
  },
  { id: 3, email: 'val@bud.example', full_name: 'Val', role: 'viewer', is_active: true, groups: [], permissions: [] },
]

function renderIt() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsersPage />
    </QueryClientProvider>,
  )
}

function rowOf(name: string) {
  return screen.getByText(name).closest('tr') as HTMLElement
}

beforeEach(() => {
  getAuthUser.mockReturnValue({ id: 1, email: 'ada@bud.example', full_name: 'Ada', role: 'admin', is_active: true })
  vi.mocked(accessApi.users).mockResolvedValue(accessUsers as never)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('groups under each user', () => {
  it('starts with every row closed and requests nothing', async () => {
    renderIt()
    await screen.findByText('Val')
    for (const name of ['Ada', 'Dev', 'Val']) {
      expect(screen.getByRole('button', { name: `Show groups of ${name}` }).getAttribute('aria-expanded')).toBe('false')
    }
    expect(screen.queryByText('Groups')).toBeNull()
    expect(accessApi.users).not.toHaveBeenCalled()
  })

  it('shows every group of an opened user without permissions and hides them again', async () => {
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(screen.getByRole('button', { name: 'Show groups of Dev' }))
    expect(await screen.findByText('Access Managers')).toBeTruthy()
    expect(screen.getByText('Station Managers')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Hide groups of Dev' }).getAttribute('aria-expanded')).toBe('true')
    expect(screen.queryByText(/access\.manage|stations\.manage|Read|Write/)).toBeNull()
    expect(within(rowOf('Ada')).queryByText('Access Managers')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hide groups of Dev' }))
    expect(screen.queryByText('Access Managers')).toBeNull()
  })

  it('says No groups for a user without groups', async () => {
    renderIt()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Show groups of Val' }))
    expect(await screen.findByText('No groups')).toBeTruthy()
    expect(accessApi.users).toHaveBeenCalledTimes(1)
  })

  it('shows an alert when the groups cannot load and retries', async () => {
    vi.mocked(accessApi.users).mockRejectedValueOnce(new Error('down'))
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(screen.getByRole('button', { name: 'Show groups of Dev' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Could not load groups.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Access Managers')).toBeTruthy()
    expect(accessApi.users).toHaveBeenCalledTimes(2)
  })
})
