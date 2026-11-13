// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import {
  productDeleteConfirmationMatches,
  productDeleteConfirmationPhrase,
} from '../lib/productDelete'

const auth = vi.hoisted(() => ({
  user: { role: 'admin', full_name: 'Admin', email: 'admin@example.com', permissions: [] as string[] },
}))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: auth.user }) }))
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    productsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  }
})

const { productsApi } = await import('../api/client')
const Products = (await import('../pages/Products')).default
const mockedApi = vi.mocked(productsApi)

const DEMO = {
  id: 5,
  name: 'Demo',
  description: 'Demo product',
  status: 'Active' as const,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
}
const RETIRED = { ...DEMO, id: 6, name: 'Retired', description: null, status: 'Archived' as const }

function apiError(detail: string) {
  return { isAxiosError: true, message: 'Request failed', response: { data: { detail }, headers: {} } }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Products />
    </QueryClientProvider>,
  )
}

describe('product delete phrase', () => {
  it('is Delete followed by the product name', () => {
    expect(productDeleteConfirmationPhrase(' Demo ')).toBe('Delete Demo')
  })

  it('matches only the exact phrase', () => {
    expect(productDeleteConfirmationMatches(' Delete Demo ', 'Delete Demo')).toBe(true)
    expect(productDeleteConfirmationMatches('Delete demo', 'Delete Demo')).toBe(false)
  })
})

describe('Products page', () => {
  beforeEach(() => {
    cleanup()
    vi.clearAllMocks()
    auth.user.role = 'admin'
    auth.user.permissions = []
    mockedApi.list.mockResolvedValue([DEMO, RETIRED])
    mockedApi.create.mockResolvedValue(DEMO)
    mockedApi.update.mockResolvedValue(DEMO)
    mockedApi.remove.mockResolvedValue(undefined)
  })

  it('lists each product with its description, status and ID', async () => {
    renderPage()

    const row = (await screen.findByText('Demo')).closest('tr')
    expect(row?.textContent).toContain('Demo product')
    expect(row?.textContent).toContain('Active')
    expect(row?.textContent).toContain('5')
    expect(screen.getByText('Retired').closest('tr')?.textContent).toContain('Archived')
  })

  it('says so when there is no product', async () => {
    mockedApi.list.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText('No products yet.')).toBeTruthy()
  })

  it('says so when the products cannot be loaded', async () => {
    mockedApi.list.mockRejectedValue(apiError('boom'))
    renderPage()

    expect(await screen.findByText('Could not load the products.')).toBeTruthy()
  })

  it('refuses a user without products view and loads nothing', () => {
    auth.user.role = 'viewer'
    renderPage()

    expect(screen.getByText("You don't have access to Products")).toBeTruthy()
    expect(mockedApi.list).not.toHaveBeenCalled()
  })

  it('shows a user with products view the table without any action', async () => {
    auth.user.role = 'viewer'
    auth.user.permissions = ['products.view']
    renderPage()

    await screen.findByText('Demo')
    expect(screen.queryByRole('button', { name: 'New product' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit Demo' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Archive Demo' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete Demo' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Copy the ID of Demo' })).toBeTruthy()
  })

  it('copies the ID of a product', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Copy the ID of Demo' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('5'))
  })

  it('adds a product with its name and description', async () => {
    renderPage()
    await screen.findByText('Demo')

    fireEvent.click(screen.getByRole('button', { name: 'New product' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: ' Gateway ' } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Main gateway' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApi.create).toHaveBeenCalledWith({ name: 'Gateway', description: 'Main gateway' }),
    )
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('keeps Save disabled while the name is empty', async () => {
    renderPage()
    await screen.findByText('Demo')

    fireEvent.click(screen.getByRole('button', { name: 'New product' }))

    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('edits a product and sends an empty description as none', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit Demo' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Demo 2' } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(mockedApi.update).toHaveBeenCalledWith(5, { name: 'Demo 2', description: null }),
    )
  })

  it('shows the refusal of a name in use and keeps the dialog open', async () => {
    mockedApi.update.mockRejectedValue(apiError('Product with this name already exists'))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit Demo' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Retired' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Product with this name already exists')).toBeTruthy()
    expect(screen.getByRole('dialog', { name: 'Edit product' })).toBeTruthy()
  })

  it('archives a product after the confirmation', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Archive Demo' }))
    expect(mockedApi.update).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Archive' }))

    await waitFor(() => expect(mockedApi.update).toHaveBeenCalledWith(5, { status: 'Archived' }))
  })

  it('restores an archived product', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Restore Retired' }))

    await waitFor(() => expect(mockedApi.update).toHaveBeenCalledWith(6, { status: 'Active' }))
  })

  it('deletes a product only after its phrase is typed', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Delete Demo' }))
    const confirm = screen.getByRole('button', { name: 'Delete' }) as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Delete confirmation'), { target: { value: 'Delete Retired' } })
    expect(confirm.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Delete confirmation'), { target: { value: 'Delete Demo' } })
    expect(confirm.disabled).toBe(false)
    fireEvent.click(confirm)

    await waitFor(() => expect(mockedApi.remove).toHaveBeenCalled())
    expect(mockedApi.remove.mock.calls[0][0]).toBe(5)
  })

  it('shows the refusal of a delete in its dialog', async () => {
    mockedApi.remove.mockRejectedValue(apiError('Insufficient permissions'))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Delete Demo' }))
    fireEvent.change(screen.getByLabelText('Delete confirmation'), { target: { value: 'Delete Demo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('Insufficient permissions')).toBeTruthy()
    expect(screen.getByRole('dialog', { name: 'Delete product' })).toBeTruthy()
  })

  it('closes the product dialog with Escape', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Edit Demo' }))
    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
