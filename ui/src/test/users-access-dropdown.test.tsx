import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
      list: vi.fn().mockResolvedValue([person(1, 'Ada', 'admin'), person(2, 'Dev', 'developer'), person(3, 'Val', 'viewer')]),
      accessSummary: vi.fn(),
    },
  }
})

const summaries: Record<number, { every_product: boolean; products: { product_id: number; product_name: string }[] }> = {
  1: { every_product: true, products: [] },
  2: { every_product: false, products: [{ product_id: 4, product_name: 'Fleet Monitor' }, { product_id: 5, product_name: 'Gateway' }] },
  3: { every_product: false, products: [] },
}

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
  vi.mocked(usersApi.accessSummary).mockImplementation(async (id: number) => summaries[id])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('products under each user', () => {
  it('starts with every row closed and requests nothing', async () => {
    renderIt()
    await screen.findByText('Val')
    for (const name of ['Ada', 'Dev', 'Val']) {
      expect(screen.getByRole('button', { name: `Show access of ${name}` }).getAttribute('aria-expanded')).toBe('false')
    }
    expect(usersApi.accessSummary).not.toHaveBeenCalled()
  })

  it('lists the products of an opened user by name only and hides them again', async () => {
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(screen.getByRole('button', { name: 'Show access of Dev' }))
    expect(await screen.findByText('Fleet Monitor, Gateway')).toBeTruthy()
    expect(screen.getByText('Products:')).toBeTruthy()
    expect(screen.queryByText(/Groups/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hide access of Dev' }))
    expect(screen.queryByText('Fleet Monitor, Gateway')).toBeNull()
  })

  it('says No products for a user without products and Every product for an Admin', async () => {
    renderIt()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Show access of Val' }))
    expect(await screen.findByText('No products')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Show access of Ada' }))
    expect(await screen.findByText('Every product (Admin)')).toBeTruthy()
  })

  it('shows an alert when the access cannot load and retries', async () => {
    vi.mocked(usersApi.accessSummary).mockRejectedValueOnce(new Error('down'))
    renderIt()
    await screen.findByText('Dev')
    fireEvent.click(screen.getByRole('button', { name: 'Show access of Dev' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Could not load access.')
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Fleet Monitor, Gateway')).toBeTruthy()
  })
})

describe('the Users page', () => {
  it('shows no group block', async () => {
    renderIt()
    await screen.findByText('Val')
    expect(screen.queryByText('Application groups')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Select members' })).toBeNull()
  })
})
