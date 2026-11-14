// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const rules = [
  {
    id: 11,
    product_id: 5,
    channel_id: 4,
    channel_name: 'demo-runs',
    channel_format: 'discord',
    channel_enabled: true,
    run_filter: 'failures',
  },
]
const channels = [
  { id: 4, name: 'demo-runs', format: 'discord', enabled: true },
  { id: 6, name: 'lab', format: 'teams', enabled: true },
]

vi.mock('../api/client', () => ({
  extractApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  productsApi: {
    notificationRules: vi.fn(),
    notificationChannels: vi.fn(),
    createNotificationRule: vi.fn(),
    updateNotificationRule: vi.fn(),
    deleteNotificationRule: vi.fn(),
  },
}))

const api = await import('../api/client')
const ProductNotificationRules = (await import('../components/ProductNotificationRules')).default

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ProductNotificationRules productId={5} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.productsApi.notificationRules).mockResolvedValue(rules as never)
  vi.mocked(api.productsApi.notificationChannels).mockResolvedValue(channels as never)
  vi.mocked(api.productsApi.createNotificationRule).mockResolvedValue({ ...rules[0], id: 12, channel_id: 6, channel_name: 'lab' } as never)
  vi.mocked(api.productsApi.updateNotificationRule).mockResolvedValue(rules[0] as never)
  vi.mocked(api.productsApi.deleteNotificationRule).mockResolvedValue(undefined)
})
afterEach(cleanup)

describe('Product notification rules', () => {
  it('lists the rules with channel, format and filter', async () => {
    renderIt()
    expect(await screen.findByText('demo-runs')).toBeTruthy()
    expect(screen.getByText('Discord')).toBeTruthy()
    expect(screen.getByRole('combobox', { name: 'Post to demo-runs' }).textContent).toContain('Failures only')
  })

  it('offers only the channels without a rule and adds one', async () => {
    renderIt()
    await screen.findByText('demo-runs')
    fireEvent.click(await screen.findByRole('combobox', { name: 'Channel' }))
    expect(screen.queryByRole('option', { name: 'demo-runs (Discord)' })).toBeNull()
    fireEvent.click(screen.getByRole('option', { name: 'lab (Microsoft Teams)' }))
    fireEvent.click(screen.getByRole('combobox', { name: 'Post' }))
    fireEvent.click(screen.getByRole('option', { name: 'First failure after a green run' }))
    fireEvent.click(screen.getByText('Add rule'))
    await waitFor(() =>
      expect(api.productsApi.createNotificationRule).toHaveBeenCalledWith(5, { channel_id: 6, run_filter: 'first_failure' }),
    )
    expect(await screen.findByText('Runs are posted to lab.')).toBeTruthy()
  })

  it('changes a rule filter', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('combobox', { name: 'Post to demo-runs' }))
    fireEvent.click(screen.getByRole('option', { name: 'All finished runs' }))
    await waitFor(() =>
      expect(api.productsApi.updateNotificationRule).toHaveBeenCalledWith(5, 11, { run_filter: 'all' }),
    )
  })

  it('removes a rule', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Remove the rule for demo-runs' }))
    await waitFor(() => expect(api.productsApi.deleteNotificationRule).toHaveBeenCalledWith(5, 11))
  })

  it('shows no rule and no control without products management on the product', async () => {
    vi.mocked(api.productsApi.notificationRules).mockRejectedValue({ response: { status: 403 } })
    renderIt()
    expect(await screen.findByText(/Product management on this product is required/)).toBeTruthy()
    expect(screen.queryByText('demo-runs')).toBeNull()
    expect(screen.queryByText('Add rule')).toBeNull()
    expect(api.productsApi.notificationChannels).not.toHaveBeenCalled()
  })
})
