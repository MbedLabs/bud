// @vitest-environment jsdom
/** Administrator management for Test Station enrolment keys. */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import EnrolmentKeys from '../components/EnrolmentKeys'
import { testStationsApi } from '../api/client'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    testStationsApi: {
      listApiKeys: vi.fn(),
      createApiKey: vi.fn(),
      deleteApiKey: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(testStationsApi)

function apiError(detail?: string, requestId?: string) {
  return {
    isAxiosError: true,
    message: 'Request failed with status code 500',
    response: {
      data: detail ? { detail } : {},
      headers: requestId ? { 'x-request-id': requestId } : {},
    },
  }
}

const PINNED = {
  id: 1,
  label: 'bench-a',
  station_name: 'bench-a',
  key_prefix: 'budrnr_aaaa',
  runner_account: 'bench-a-station',
  created_at: '2026-09-01T10:00:00Z',
  last_used_at: '2026-09-02T10:00:00Z',
}

const UNUSED = {
  id: 2,
  label: 'bench-b',
  station_name: 'bench-b',
  key_prefix: 'budrnr_bbbb',
  runner_account: null,
  created_at: '2026-09-01T10:00:00Z',
  last_used_at: null,
}

function renderKeys() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <EnrolmentKeys />
    </QueryClientProvider>
  )
}

describe('enrolment keys', () => {
  beforeEach(() => {
    cleanup()
    vi.clearAllMocks()
    mockedApi.listApiKeys.mockResolvedValue([])
  })

  it('says so when no key is waiting for a station', async () => {
    renderKeys()

    expect(
      await screen.findByText('No key is waiting for a station. Name one above to enrol a new bench.')
    ).toBeTruthy()
  })

  it('lists only keys still waiting, so it is not a second station roster', async () => {
    mockedApi.listApiKeys.mockResolvedValue([PINNED, UNUSED])
    renderKeys()

    expect(await screen.findByText('bench-b')).toBeTruthy()
    expect(screen.getByText(/waiting for its station to register/)).toBeTruthy()
    expect(screen.queryByText('bench-a')).toBeNull()
    expect(screen.queryByText(/bench-a-station/)).toBeNull()
  })

  it('will not mint a key under a name that would break a URL', async () => {
    renderKeys()

    const submit = await screen.findByRole('button', { name: 'Add station' })
    const field = screen.getByLabelText('New station name')
    expect((submit as HTMLButtonElement).disabled).toBe(true)

    for (const bad of ['   ', 'ab', "Ada's bench", 'lab 2', 'bench/a', 'bench#3']) {
      fireEvent.change(field, { target: { value: bad } })
      expect((submit as HTMLButtonElement).disabled, bad).toBe(true)
    }

    fireEvent.change(field, { target: { value: 'bench-a' } })
    expect((submit as HTMLButtonElement).disabled).toBe(false)
  })

  it('shows the minted secret masked, and reveals it only on request', async () => {
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_the-actual-secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))

    const field = (await screen.findByLabelText(
      'New Test Station API key'
    )) as HTMLInputElement
    expect(mockedApi.createApiKey.mock.calls[0][0]).toBe('bench-b')
    expect(field.value).toBe('budrnr_the-actual-secret')
    expect(field.type).toBe('password')

    fireEvent.click(screen.getByRole('button', { name: 'Show key' }))
    await waitFor(() => {
      expect(
        (screen.getByLabelText('New Test Station API key') as HTMLInputElement).type
      ).toBe('text')
    })
  })

  it('clears the label once the key is minted, so it cannot be issued twice by accident', async () => {
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_secret' })
    renderKeys()

    const label = (await screen.findByLabelText('New station name')) as HTMLInputElement
    fireEvent.change(label, { target: { value: 'bench-b' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))

    await screen.findByLabelText('New Test Station API key')
    expect((screen.getByLabelText('New station name') as HTMLInputElement).value).toBe('')
  })

  it('takes the secret off screen when dismissed', async () => {
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))
    await screen.findByLabelText('New Test Station API key')

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    await waitFor(() => {
      expect(screen.queryByLabelText('New Test Station API key')).toBeNull()
    })
  })

  it('copies the secret to the clipboard and says so', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))
    await screen.findByLabelText('New Test Station API key')

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('budrnr_secret'))
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
  })

  it('stays quiet when the clipboard is refused', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))
    await screen.findByLabelText('New Test Station API key')

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Copied' })).toBeNull()
  })

  it('asks before revoking, and revokes nothing until asked again', async () => {
    mockedApi.listApiKeys.mockResolvedValue([UNUSED])
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Actions for bench-b' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Revoke' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog.textContent).toContain('has not been used yet')
    expect(mockedApi.deleteApiKey).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(mockedApi.deleteApiKey).not.toHaveBeenCalled()
  })

  it('revokes a key once confirmed, and refreshes the list', async () => {
    mockedApi.listApiKeys.mockResolvedValueOnce([UNUSED]).mockResolvedValue([])
    mockedApi.deleteApiKey.mockResolvedValue(undefined)
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Actions for bench-b' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Revoke' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Revoke' }))

    await waitFor(() => expect(mockedApi.deleteApiKey.mock.calls.length).toBe(1))
    expect(mockedApi.deleteApiKey.mock.calls[0][0]).toBe(2)
    expect(
      await screen.findByText('No key is waiting for a station. Name one above to enrol a new bench.')
    ).toBeTruthy()
  })

  it('says an unused key has not been used yet', async () => {
    mockedApi.listApiKeys.mockResolvedValue([UNUSED])
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Actions for bench-b' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Revoke' }))

    expect((await screen.findByRole('dialog')).textContent).toContain('has not been used yet')
  })

  it('shows what the server said rather than a generic failure', async () => {
    mockedApi.createApiKey.mockRejectedValue(apiError('That label is already in use.'))
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))

    expect(await screen.findByText('That label is already in use.')).toBeTruthy()
  })

  it('falls back to a reference the user can quote', async () => {
    mockedApi.createApiKey.mockRejectedValue(apiError(undefined, 'abc123'))
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New station name'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add station' }))

    expect(await screen.findByText(/Could not create the key. Quote reference abc123/)).toBeTruthy()
  })

  it('reports a failure to revoke inside the dialog, and keeps it open', async () => {
    mockedApi.listApiKeys.mockResolvedValue([UNUSED])
    mockedApi.deleteApiKey.mockRejectedValue(apiError('That key is still enrolling a station.'))
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Actions for bench-b' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Revoke' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Revoke' }))

    expect(await screen.findByText('That key is still enrolling a station.')).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeTruthy()
  })
})
