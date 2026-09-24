// @vitest-environment jsdom
/**
 * The admin audit log screen: it lists events newest first and filters them by
 * event group and outcome.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const page = {
  total: 2,
  items: [
    {
      id: 2, occurred_at: '2026-09-24T10:00:00', actor_user_id: 1, actor_name: 'Ada Admin',
      actor_type: 'user', action: 'user.role_changed', target_type: 'user', target_id: '5',
      product_id: null, request_id: 'req-2', ip: '10.0.0.1', user_agent: 'x', outcome: 'success',
      details: { from: 'maintainer', to: 'external' },
    },
    {
      id: 1, occurred_at: '2026-09-24T09:00:00', actor_user_id: null, actor_name: null,
      actor_type: 'anonymous', action: 'auth.login', target_type: 'user', target_id: '5',
      product_id: null, request_id: 'req-1', ip: '10.0.0.2', user_agent: 'x', outcome: 'failure',
      details: null,
    },
  ],
}

vi.mock('../api/client', () => ({
  auditApi: { list: vi.fn().mockResolvedValue(page) },
}))

const api = await import('../api/client')
const AuditPage = (await import('../pages/Audit')).default

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuditPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('Audit log admin screen', () => {
  it('lists events with actor, event, target, outcome and request', async () => {
    renderPage()
    expect(await screen.findByText('Ada Admin')).toBeTruthy()
    expect(screen.getByText('user.role_changed')).toBeTruthy()
    expect(screen.getByText('anonymous')).toBeTruthy()
    expect(screen.getByText('failure')).toBeTruthy()
    expect(screen.getByText('req-1')).toBeTruthy()
    expect(screen.getByText('2 events')).toBeTruthy()
  })

  it('filters by event group and outcome from the first page', async () => {
    renderPage()
    await screen.findByText('Ada Admin')
    fireEvent.change(screen.getByLabelText('Events'), { target: { value: 'auth.' } })
    fireEvent.change(screen.getByLabelText('Outcome'), { target: { value: 'failure' } })
    await waitFor(() =>
      expect(api.auditApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ action: 'auth.', outcome: 'failure', offset: 0 }),
      ),
    )
  })
})
