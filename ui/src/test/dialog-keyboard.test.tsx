import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ConfirmDialog from '../components/ConfirmDialog'
import UsersPage from '../pages/Users'

const getAuthUser = vi.hoisted(() => vi.fn())

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: getAuthUser() }),
}))

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const person = (id: number, name: string, role: 'admin' | 'viewer') => ({
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
      list: vi.fn().mockResolvedValue([person(1, 'Ada', 'admin'), person(2, 'Val', 'viewer')]),
    },
    groupsApi: { ...actual.groupsApi, list: vi.fn().mockResolvedValue([]) },
  }
})

function renderUsers() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UsersPage />
    </QueryClientProvider>,
  )
}

function renderConfirm(onCancel: () => void, onConfirm = vi.fn()) {
  return render(
    <ConfirmDialog
      title="Remove this station?"
      body="Its runs are kept."
      confirmLabel="Remove"
      pendingLabel="Removing..."
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  )
}

beforeEach(() => {
  getAuthUser.mockReturnValue({ id: 1, email: 'ada@bud.example', full_name: 'Ada', role: 'admin', is_active: true })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('confirmation dialog', () => {
  it('cancels once when Escape is pressed, wherever focus is', () => {
    const onCancel = vi.fn()
    renderConfirm(onCancel)
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
    fireEvent.keyDown(screen.getByRole('button', { name: 'Cancel' }), { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(2)
  })

  it('stays open for other keys and for clicks inside it, and stops listening once closed', () => {
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    const { unmount } = renderConfirm(onCancel, onConfirm)
    fireEvent.keyDown(screen.getByRole('button', { name: 'Cancel' }), { key: 'Enter' })
    fireEvent.click(screen.getByText('Its runs are kept.'))
    fireEvent.click(screen.getByRole('dialog', { name: 'Remove this station?' }))
    unmount()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(onCancel).not.toHaveBeenCalled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('cancels once when the backdrop is clicked', () => {
    const onCancel = vi.fn()
    renderConfirm(onCancel)
    fireEvent.click(screen.getByRole('button', { name: 'Close Remove this station? backdrop' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

describe('user dialogs', () => {
  it('closes the invite dialog with Escape right after it opens', async () => {
    renderUsers()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Invite User' }))
    expect(screen.getByRole('dialog', { name: 'Invite User' })).toBeTruthy()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Invite User' })).toBeNull()
  })

  it('closes the invite dialog with Escape from its role field', async () => {
    renderUsers()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Invite User' }))
    const role = within(screen.getByRole('dialog', { name: 'Invite User' })).getByRole('combobox', { name: 'Role' })
    fireEvent.keyDown(role, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Invite User' })).toBeNull()
  })

  it('closes the invite dialog from its backdrop and keeps it open for clicks and other keys inside it', async () => {
    renderUsers()
    await screen.findByText('Val')
    fireEvent.click(screen.getByRole('button', { name: 'Invite User' }))
    const dialog = screen.getByRole('dialog', { name: 'Invite User' })
    fireEvent.click(dialog)
    fireEvent.keyDown(within(dialog).getByRole('button', { name: 'Send Invite' }), { key: 'Enter' })
    expect(screen.getByRole('dialog', { name: 'Invite User' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Close Invite User backdrop' }))
    expect(screen.queryByRole('dialog', { name: 'Invite User' })).toBeNull()
  })

  it('closes the email change dialog with Escape or its backdrop', async () => {
    renderUsers()
    await screen.findByText('Val')
    const valRow = screen.getByText('Val').closest('tr') as HTMLElement

    fireEvent.click(within(valRow).getByTitle('Change email'))
    fireEvent.keyDown(screen.getByLabelText('New email'), { key: 'Enter' })
    expect(screen.getByRole('dialog', { name: 'Change user email' })).toBeTruthy()
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Change user email' })).toBeNull()

    fireEvent.click(within(valRow).getByTitle('Change email'))
    fireEvent.click(screen.getByLabelText('New email'))
    expect(screen.getByRole('dialog', { name: 'Change user email' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Close Change user email backdrop' }))
    expect(screen.queryByRole('dialog', { name: 'Change user email' })).toBeNull()
  })
})
