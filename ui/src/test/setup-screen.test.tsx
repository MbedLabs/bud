// @vitest-environment jsdom
/**
 * First-run setup screen.
 *
 * The screen is only reachable while the instance has no accounts, so the
 * behaviour worth pinning down is what it does at each edge of that window:
 * offer the form while setup is needed, get out of the way once it is not, and
 * never submit a password the backend would reject anyway.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'

import Setup from '../pages/Setup'
import { setupApi } from '../api/client'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    setupApi: {
      getStatus: vi.fn(),
      createFirstAdmin: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(setupApi)

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/setup']}>
      <Routes>
        <Route path="/setup" element={<Setup />} />
        <Route path="/login" element={<div>login screen</div>} />
      </Routes>
    </MemoryRouter>
  )
}

async function fillForm({ password = 'a-long-enough-password', confirm = 'a-long-enough-password' } = {}) {
  fireEvent.change(screen.getByPlaceholderText('Your name'), { target: { value: 'Instance Owner' } })
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
    target: { value: 'owner@example.com' },
  })
  fireEvent.change(screen.getByPlaceholderText('At least 12 characters'), {
    target: { value: password },
  })
  fireEvent.change(screen.getByPlaceholderText('Repeat your password'), {
    target: { value: confirm },
  })
}

describe('first-run setup screen', () => {
  beforeEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('offers the form while the instance has no accounts', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: true })
    renderSetup()

    expect(await screen.findByText('Welcome to Bud')).toBeTruthy()
    expect(screen.getByPlaceholderText('you@example.com')).toBeTruthy()
  })

  it('redirects to login once an account exists', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: false })
    renderSetup()

    expect(await screen.findByText('login screen')).toBeTruthy()
  })

  it('does not offer to claim an instance it cannot reach', async () => {
    // A backend that cannot answer must not be treated as unclaimed.
    mockedApi.getStatus.mockRejectedValue(new Error('network down'))
    renderSetup()

    expect(await screen.findByText('login screen')).toBeTruthy()
  })

  it('creates the administrator and hands off to login', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: true })
    mockedApi.createFirstAdmin.mockResolvedValue({ message: 'created' })
    renderSetup()
    await screen.findByText('Welcome to Bud')

    await fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Create Administrator' }))

    await waitFor(() =>
      expect(mockedApi.createFirstAdmin).toHaveBeenCalledWith(
        'owner@example.com',
        'a-long-enough-password',
        'Instance Owner'
      )
    )
    expect(await screen.findByText('login screen')).toBeTruthy()
  })

  it('rejects a mismatched confirmation without calling the backend', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: true })
    renderSetup()
    await screen.findByText('Welcome to Bud')

    await fillForm({ confirm: 'a-different-password' })
    fireEvent.click(screen.getByRole('button', { name: 'Create Administrator' }))

    expect(await screen.findByText('Passwords do not match')).toBeTruthy()
    expect(mockedApi.createFirstAdmin).not.toHaveBeenCalled()
  })

  it('rejects a password below the policy without calling the backend', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: true })
    renderSetup()
    await screen.findByText('Welcome to Bud')

    await fillForm({ password: 'short', confirm: 'short' })
    fireEvent.click(screen.getByRole('button', { name: 'Create Administrator' }))

    expect(await screen.findByText('Password must be at least 12 characters long')).toBeTruthy()
    expect(mockedApi.createFirstAdmin).not.toHaveBeenCalled()
  })

  it('surfaces a backend rejection instead of navigating away', async () => {
    mockedApi.getStatus.mockResolvedValue({ setup_required: true })
    mockedApi.createFirstAdmin.mockRejectedValue(new Error('boom'))
    renderSetup()
    await screen.findByText('Welcome to Bud')

    await fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Create Administrator' }))

    await waitFor(() => expect(mockedApi.createFirstAdmin).toHaveBeenCalled())
    expect(screen.queryByText('login screen')).toBeNull()
  })
})
