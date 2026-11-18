import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UsersPage from '../pages/Users'
import { policiesApi, usersApi } from '../api/client'

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
      list: vi.fn().mockResolvedValue([person(1, 'Ada', 'admin'), person(2, 'Dev', 'developer')]),
      applicationPolicies: vi.fn(),
      setApplicationPolicies: vi.fn(),
    },
    policiesApi: { ...actual.policiesApi, list: vi.fn() },
  }
})

const policy = (id: number, name: string, permissions: Record<string, string[]>) => ({
  id,
  name,
  description: `${name} description`,
  permissions,
  is_default: true,
  system_key: null,
  created_at: '',
  updated_at: '',
})

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
  vi.mocked(policiesApi.list).mockResolvedValue([
    policy(3, 'Stations', { stations: ['view', 'manage'] }),
    policy(4, 'Custom runs', { custom_runs: ['create'] }),
    policy(5, 'Access management', { access: ['manage'] }),
  ])
  vi.mocked(usersApi.applicationPolicies).mockResolvedValue({ policy_ids: [3] })
  vi.mocked(usersApi.setApplicationPolicies).mockResolvedValue({ policy_ids: [3, 5] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('application policies on Users', () => {
  it('offers the shield on a user who is not an Admin only', async () => {
    renderIt()
    await screen.findByText('Dev')
    expect(within(rowOf('Ada')).queryByTitle('Application policies')).toBeNull()
    expect(within(rowOf('Dev')).getByTitle('Application policies')).toBeTruthy()
  })

  it('lists only the application policies with the held ones checked', async () => {
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(within(rowOf('Dev')).getByTitle('Application policies'))
    const dialog = await screen.findByRole('dialog', { name: 'Application policies' })
    expect((await within(dialog).findByLabelText('App policy Stations') as HTMLInputElement).checked).toBe(true)
    expect((within(dialog).getByLabelText('App policy Access management') as HTMLInputElement).checked).toBe(false)
    expect(within(dialog).queryByLabelText('App policy Custom runs')).toBeNull()
    expect(usersApi.applicationPolicies).toHaveBeenCalledWith(2)
  })

  it('saves the selection and closes the dialog', async () => {
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(within(rowOf('Dev')).getByTitle('Application policies'))
    const dialog = await screen.findByRole('dialog', { name: 'Application policies' })
    fireEvent.click(await within(dialog).findByLabelText('App policy Access management'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save application policies' }))
    await waitFor(() => expect(usersApi.setApplicationPolicies).toHaveBeenCalledWith(2, [3, 5]))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Application policies' })).toBeNull())
  })

  it('shows a refusal and keeps the dialog open', async () => {
    vi.mocked(usersApi.setApplicationPolicies).mockRejectedValueOnce({
      isAxiosError: true,
      message: 'Request failed',
      response: { data: { detail: 'Station management requires an Admin or Developer base role' }, headers: {} },
    })
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(within(rowOf('Dev')).getByTitle('Application policies'))
    const dialog = await screen.findByRole('dialog', { name: 'Application policies' })
    fireEvent.click(await within(dialog).findByRole('button', { name: 'Save application policies' }))
    expect((await within(dialog).findByRole('alert')).textContent).toContain('Station management requires')
  })
})
