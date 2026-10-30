// @vitest-environment jsdom
/**
 * The admin audit log screen: it lists events newest first and filters them by
 * event group and outcome.
 */
import { selectValue } from './select-value'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const page = {
  total: 2,
  items: [
    {
      id: 2, occurred_at: '2026-09-24T10:00:00', actor_user_id: 1, actor_name: 'Ada Admin',
      actor_type: 'user', action: 'user.role_changed', target_type: 'user', target_id: '5',
      product_id: null, request_id: 'req-2', ip: '10.0.0.1', user_agent: 'x', outcome: 'success',
      details: { from: 'maintainer', to: 'external' }, target_label: 'Uma User', target_deleted: false,
    },
    {
      id: 1, occurred_at: '2026-09-24T09:00:00', actor_user_id: null, actor_name: null,
      actor_type: 'anonymous', action: 'auth.login', target_type: 'user', target_id: '5',
      product_id: null, request_id: 'req-1', ip: '10.0.0.2', user_agent: 'x', outcome: 'failure',
      details: null, target_label: 'Uma User', target_deleted: false,
    },
  ],
}

const apiCalls = {
  total: 6,
  items: [
    {
      id: 14, occurred_at: '2026-10-28T10:03:00', actor_user_id: 1, actor_name: 'Ada Admin',
      actor_type: 'user', action: 'api.request', target_type: null, target_id: null,
      product_id: 3, request_id: 'req-14', ip: '10.0.0.1', user_agent: 'bud-cli/1.3.0', outcome: 'success',
      details: { method: 'POST', route: '/api/test-runs', path: '/api/test-runs', status: 201, client: 'cli', created_id: 77 },
      created_label: 'Nightly smoke', created_deleted: false,
    },
    {
      id: 13, occurred_at: '2026-10-28T10:02:00', actor_user_id: null, actor_name: null,
      actor_type: 'runner', action: 'api.request', target_type: null, target_id: null,
      product_id: null, request_id: 'req-13', ip: '10.0.0.5', user_agent: 'bud-runner', outcome: 'success',
      details: { method: 'POST', route: '/api/results', path: '/api/results', status: 201, runner_id: 1, created_test_run_id: 78 },
      created_label: 'Soak test', created_deleted: false, station_name: 'station-01', station_deleted: false,
    },
    {
      id: 12, occurred_at: '2026-10-28T10:01:00', actor_user_id: null, actor_name: null,
      actor_type: 'runner', action: 'api.request', target_type: null, target_id: null,
      product_id: null, request_id: 'req-12', ip: '10.0.0.6', user_agent: 'bud-runner', outcome: 'success',
      details: { method: 'POST', route: '/api/runners/heartbeat', path: '/api/runners/heartbeat', status: 200, runner_id: 9 },
      station_name: null, station_deleted: true,
    },
    {
      id: 11, occurred_at: '2026-10-28T10:00:00', actor_user_id: null, actor_name: null,
      actor_type: 'anonymous', action: 'api.request', target_type: 'test_run', target_id: '5',
      product_id: null, request_id: 'req-11', ip: '203.0.113.9', user_agent: 'curl/8', outcome: 'denied',
      details: { method: 'GET', route: '/api/test-runs/{test_run_id}', path: '/api/test-runs/5', status: 401 },
      target_label: null, target_deleted: true,
    },
    {
      id: 10, occurred_at: '2026-10-28T09:59:00', actor_user_id: 4, actor_name: null,
      actor_type: 'user', action: 'group.member_added', target_type: 'group', target_id: '2',
      product_id: null, request_id: 'req-10', ip: '10.0.0.1', user_agent: 'x', outcome: 'success',
      details: { user_id: 5 }, target_label: 'Test Operators', target_deleted: false,
    },
    {
      id: 9, occurred_at: '2026-10-28T09:58:00', actor_user_id: 1, actor_name: 'Ada Admin',
      actor_type: 'user', action: 'report.refused', target_type: 'report_request', target_id: '12',
      product_id: null, request_id: 'req-9', ip: '10.0.0.1', user_agent: 'x', outcome: 'success',
      details: null, target_label: null, target_deleted: false,
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

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.auditApi.list).mockResolvedValue(page)
})
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
    expect(screen.getByText('Every API request and every refused attempt is recorded. Events cannot be changed or deleted here.')).toBeTruthy()
    expect(screen.getAllByText('User Uma User')).toHaveLength(2)
    expect(screen.queryByText('user 5')).toBeNull()
  })

  it('offers the API calls and refused attempts groups and asks for each', async () => {
    renderPage()
    await screen.findByText('Ada Admin')
    selectValue(screen.getByRole('combobox', { name: 'Events' }), 'api.')
    await waitFor(() =>
      expect(api.auditApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ action: 'api.', outcome: undefined, offset: 0 }),
      ),
    )
    selectValue(screen.getByRole('combobox', { name: 'Events' }), 'refused')
    await waitFor(() =>
      expect(api.auditApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ action: undefined, outcome: 'denied', offset: 0 }),
      ),
    )
    const outcome = screen.getByRole('combobox', { name: 'Outcome' }) as HTMLButtonElement
    expect(outcome.disabled).toBe(true)
    expect(outcome.textContent).toContain('Denied')
  })

  it('filters by actor, address and request id', async () => {
    renderPage()
    await screen.findByText('Ada Admin')
    selectValue(screen.getByRole('combobox', { name: 'Actor' }), 'runner')
    fireEvent.change(screen.getByLabelText('Address'), { target: { value: ' 203.0.113.9 ' } })
    fireEvent.change(screen.getByLabelText('Request id'), { target: { value: 'req-11' } })
    await waitFor(() =>
      expect(api.auditApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ actor_type: 'runner', ip: '203.0.113.9', request_id: 'req-11', offset: 0 }),
      ),
    )
  })

  it('shows method, route, status, target and created ids of API calls', async () => {
    vi.mocked(api.auditApi.list).mockResolvedValue(apiCalls)
    renderPage()
    const row = within((await screen.findByText('req-14')).closest('tr')!)
    expect(row.getByTitle('/api/test-runs').textContent).toBe('POST /api/test-runs')
    expect(row.getByText('201')).toBeTruthy()
    expect(row.getByText('created Nightly smoke')).toBeTruthy()
    const upload = within(screen.getByText('req-13').closest('tr')!)
    expect(upload.getByText('created run Soak test')).toBeTruthy()
    const refused = within(screen.getByText('req-11').closest('tr')!)
    expect(refused.getByText('401')).toBeTruthy()
    expect(refused.getByText('Test run 5 (deleted)')).toBeTruthy()
    expect(within(screen.getByText('req-10').closest('tr')!).getByText('Group Test Operators')).toBeTruthy()
    const unnamed = within(screen.getByText('req-9').closest('tr')!)
    expect(unnamed.getByText('Report request')).toBeTruthy()
    expect(unnamed.queryByText(/12/)).toBeNull()
    expect(refused.getByText('denied')).toBeTruthy()
    expect(refused.getByTitle('/api/test-runs/5').textContent).toBe('GET /api/test-runs/{test_run_id}')
  })

  it('names the station, the MCP or CLI client and anonymous callers in the Actor column', async () => {
    vi.mocked(api.auditApi.list).mockResolvedValue(apiCalls)
    renderPage()
    const client = await screen.findByText('MCP or CLI')
    expect(client.getAttribute('title')).toBe('bud-cli/1.3.0')
    expect(within(client.closest('tr')!).getByText('Ada Admin')).toBeTruthy()
    expect(await screen.findByText('station-01')).toBeTruthy()
    expect(within(screen.getByText('req-12').closest('tr')!).getByText('Station 9 (deleted)')).toBeTruthy()
    expect(within(screen.getByText('req-11').closest('tr')!).getByText('anonymous')).toBeTruthy()
    expect(within(screen.getByText('req-10').closest('tr')!).getByText('User 4 (deleted)')).toBeTruthy()
  })

  it('filters by event group and outcome from the first page', async () => {
    renderPage()
    await screen.findByText('Ada Admin')
    selectValue(screen.getByRole('combobox', { name: 'Events' }), 'auth.')
    selectValue(screen.getByRole('combobox', { name: 'Outcome' }), 'failure')
    await waitFor(() =>
      expect(api.auditApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ action: 'auth.', outcome: 'failure', offset: 0 }),
      ),
    )
  })
  it('keeps literal date bounds and resets pagination when a date is selected or cleared', async () => {
    vi.mocked(api.auditApi.list).mockResolvedValue({ ...page, total: 60 })
    renderPage()
    await screen.findByText('Ada Admin')
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2024-02-28' } })
    await waitFor(() => expect((screen.getByRole('button', { name: 'Older' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Older' }))
    await waitFor(() => expect(api.auditApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ since: '2024-02-28', offset: 50 })))
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    const dateLabel = new Intl.DateTimeFormat(navigator.language, { dateStyle: 'full', calendar: 'gregory' }).format(new Date(2024, 1, 29))
    fireEvent.click(screen.getByRole('button', { name: dateLabel }))
    await waitFor(() => expect(api.auditApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ since: '2024-02-29', offset: 0 })))
    fireEvent.change(screen.getByLabelText('Until'), { target: { value: '2024-03-01' } })
    await waitFor(() => expect(api.auditApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ since: '2024-02-29', until: '2024-03-01' })))
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    await waitFor(() => expect(api.auditApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ since: undefined, until: '2024-03-01', offset: 0 })))
  })

})
