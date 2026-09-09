// @vitest-environment jsdom
/**
 * Administrator management for Test Station enrolment keys.
 *
 * The secret is returned once and never again, so what matters is that it is
 * shown when it arrives, hidden until asked for, and that neither it nor a
 * revoked key survives on screen afterwards.
 */
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

const PINNED = {
  id: 1,
  label: 'bench-a',
  key_prefix: 'budrnr_aaaa',
  runner_account: 'bench-a-station',
  created_at: '2026-09-01T10:00:00Z',
  last_used_at: '2026-09-02T10:00:00Z',
}

const UNUSED = {
  id: 2,
  label: 'bench-b',
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

  it('says a station cannot enrol while no key exists', async () => {
    renderKeys()

    expect(
      await screen.findByText('No keys yet. A station cannot enrol until one exists.')
    ).toBeTruthy()
  })

  it('distinguishes a pinned key from one still waiting for its station', async () => {
    mockedApi.listApiKeys.mockResolvedValue([PINNED, UNUSED])
    renderKeys()

    expect(await screen.findByText('bench-a')).toBeTruthy()
    expect(screen.getByText(/bench-a-station/)).toBeTruthy()
    expect(screen.getByText(/unused/)).toBeTruthy()
  })

  it('will not mint a key without a label', async () => {
    renderKeys()

    const submit = await screen.findByRole('button', { name: /New key/ })
    expect((submit as HTMLButtonElement).disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('New key label'), { target: { value: '   ' } })
    expect((submit as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the minted secret masked, and reveals it only on request', async () => {
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_the-actual-secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New key label'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))

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

    const label = (await screen.findByLabelText('New key label')) as HTMLInputElement
    fireEvent.change(label, { target: { value: 'bench-b' } })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))

    await screen.findByLabelText('New Test Station API key')
    expect((screen.getByLabelText('New key label') as HTMLInputElement).value).toBe('')
  })

  it('takes the secret off screen when dismissed', async () => {
    mockedApi.createApiKey.mockResolvedValue({ ...UNUSED, api_key: 'budrnr_secret' })
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New key label'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))
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

    fireEvent.change(await screen.findByLabelText('New key label'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))
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

    fireEvent.change(await screen.findByLabelText('New key label'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))
    await screen.findByLabelText('New Test Station API key')

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Copied' })).toBeNull()
  })

  it('revokes a key and refreshes the list', async () => {
    mockedApi.listApiKeys.mockResolvedValueOnce([PINNED]).mockResolvedValue([])
    mockedApi.deleteApiKey.mockResolvedValue(undefined)
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Revoke key bench-a' }))

    await waitFor(() => expect(mockedApi.deleteApiKey.mock.calls.length).toBe(1))
    expect(mockedApi.deleteApiKey.mock.calls[0][0]).toBe(1)
    expect(
      await screen.findByText('No keys yet. A station cannot enrol until one exists.')
    ).toBeTruthy()
  })

  it('reports a failure to mint rather than leaving the form silent', async () => {
    mockedApi.createApiKey.mockRejectedValue(new Error('boom'))
    renderKeys()

    fireEvent.change(await screen.findByLabelText('New key label'), {
      target: { value: 'bench-b' },
    })
    fireEvent.click(screen.getByRole('button', { name: /New key/ }))

    expect(await screen.findByText('Could not create the key.')).toBeTruthy()
  })

  it('reports a failure to revoke', async () => {
    mockedApi.listApiKeys.mockResolvedValue([PINNED])
    mockedApi.deleteApiKey.mockRejectedValue(new Error('boom'))
    renderKeys()

    fireEvent.click(await screen.findByRole('button', { name: 'Revoke key bench-a' }))

    expect(await screen.findByText('Could not revoke the key.')).toBeTruthy()
  })
})
