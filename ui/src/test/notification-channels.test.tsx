// @vitest-environment jsdom
/**
 * Run notification channels in Settings: listing, adding, enabling, testing and deleting.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const channels = [
  {
    id: 4,
    name: 'qa-results',
    format: 'slack',
    url_prefix: 'https://hooks.slack.com/services/T000/B0...',
    run_filter: 'failures',
    enabled: true,
    has_secret: false,
    created_at: '',
  },
]

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  notificationsApi: {
    listChannels: vi.fn().mockResolvedValue(channels),
    createChannel: vi.fn().mockResolvedValue(channels[0]),
    updateChannel: vi.fn().mockResolvedValue(channels[0]),
    deleteChannel: vi.fn().mockResolvedValue(undefined),
    testChannel: vi.fn().mockResolvedValue({ delivered: true, attempts: 1, status_code: 200, error: null }),
  },
}))

const api = await import('../api/client')
const NotificationChannels = (await import('../components/NotificationChannels')).default

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <NotificationChannels />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('Run notifications settings', () => {
  it('lists channels without technical metadata or endpoint prefixes', async () => {
    renderIt()
    expect(await screen.findByText('qa-results')).toBeTruthy()
    expect(screen.getByText('Slack · Failures only')).toBeTruthy()
    expect(screen.queryByText(/hooks.slack.com|stored encrypted|Workflows or connector/)).toBeNull()
    expect(screen.getByLabelText('Webhook URL').getAttribute('autocomplete')).toBe('off')
    expect(screen.getByLabelText('Signing secret (optional)').getAttribute('autocomplete')).toBe('new-password')
  })

  it('adds a channel', async () => {
    renderIt()
    await screen.findByText('qa-results')
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'lab' } })
    fireEvent.click(screen.getByRole('combobox', { name: 'Format' }))
    fireEvent.click(screen.getByRole('option', { name: 'Microsoft Teams' }))
    fireEvent.change(screen.getByLabelText('Webhook URL'), { target: { value: 'https://example.com/hook' } })
    fireEvent.click(screen.getByRole('combobox', { name: 'Post' }))
    fireEvent.click(screen.getByRole('option', { name: 'First failure after a green run' }))
    fireEvent.click(screen.getByText('Add channel'))
    await waitFor(() =>
      expect(api.notificationsApi.createChannel).toHaveBeenCalledWith({
        name: 'lab',
        format: 'teams',
        url: 'https://example.com/hook',
        secret: undefined,
        run_filter: 'first_failure',
      }),
    )
    expect(await screen.findByText('Channel added.')).toBeTruthy()
  })

  it('sends a test message and reports delivery', async () => {
    renderIt()
    fireEvent.click(await screen.findByTitle('Send a test message to qa-results'))
    expect(await screen.findByText('Test message delivered to qa-results.')).toBeTruthy()
    expect(api.notificationsApi.testChannel).toHaveBeenCalledWith(4)
  })

  it('supports keyboard selection, cancellation and short format options', async () => {
    renderIt()
    await screen.findByText('qa-results')
    const picker = screen.getByRole('combobox', { name: 'Format' })
    fireEvent.click(picker)
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(['Microsoft Teams', 'Slack', 'Discord', 'JSON'])
    fireEvent.keyDown(picker, { key: 'End' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(picker.textContent).toContain('JSON')
    expect(screen.queryByRole('listbox')).toBeNull()
    fireEvent.keyDown(picker, { key: 'Home' })
    fireEvent.keyDown(picker, { key: 'Escape' })
    expect(picker.textContent).toContain('JSON')
    fireEvent.keyDown(picker, { key: 's' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(picker.textContent).toContain('Slack')
    fireEvent.keyDown(picker, { key: 'ArrowDown' })
    fireEvent.keyDown(picker, { key: 'ArrowUp' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(picker.textContent).toContain('Slack')
    fireEvent.click(picker)
    fireEvent.blur(picker, { relatedTarget: screen.getByLabelText('Name') })
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('reports a test message the channel refused', async () => {
    vi.mocked(api.notificationsApi.testChannel).mockResolvedValueOnce({
      delivered: false,
      attempts: 3,
      status_code: 404,
      error: 'no_service',
    })
    renderIt()
    fireEvent.click(await screen.findByTitle('Send a test message to qa-results'))
    expect(
      await screen.findByText('qa-results did not accept the test message after 3 attempt(s): no_service.'),
    ).toBeTruthy()
  })

  it('disables and deletes a channel', async () => {
    renderIt()
    fireEvent.click(await screen.findByLabelText('Enable qa-results'))
    await waitFor(() => expect(api.notificationsApi.updateChannel).toHaveBeenCalledWith(4, { enabled: false }))
    fireEvent.click(screen.getByTitle('Delete qa-results'))
    await waitFor(() => expect(api.notificationsApi.deleteChannel).toHaveBeenCalledWith(4))
  })

  it('shows the error when adding fails', async () => {
    vi.mocked(api.notificationsApi.createChannel).mockRejectedValueOnce(new Error('boom'))
    renderIt()
    await screen.findByText('qa-results')
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'lab' } })
    fireEvent.change(screen.getByLabelText('Webhook URL'), { target: { value: 'https://example.com/hook' } })
    fireEvent.click(screen.getByText('Add channel'))
    expect(await screen.findByText('Could not add the channel')).toBeTruthy()
  })
})
