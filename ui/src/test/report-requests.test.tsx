// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import Panel from '../components/ReportRequests'

const mock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), publish: vi.fn(), user: { id: 1, role: 'admin', permissions: [] as string[] } }))
vi.mock('../api/client', () => ({ api: mock, testRunsApi: { publishToBloom: mock.publish }, extractApiErrorMessage: (_error: unknown, fallback: string) => fallback }))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: mock.user }) }))
const row = { id: 4, run_id: 41, run_name: 'Nightly run', run_status: 'Completed', project_prefix: 'PRJ', requester_name: 'Reader', requester_email: 'reader@example.com' }
function show(runId?: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<MemoryRouter><QueryClientProvider client={client}><Panel runId={runId} /></QueryClientProvider></MemoryRouter>)
  return vi.spyOn(client, 'invalidateQueries')
}
beforeEach(() => { vi.clearAllMocks(); mock.user.role = 'admin'; mock.get.mockResolvedValue({ data: [row] }); mock.post.mockResolvedValue({}); mock.publish.mockResolvedValue({}) })
afterEach(cleanup)

it('shows the reader and links the run from the dashboard inbox', async () => {
  show()
  expect((await screen.findByRole('link', { name: 'Nightly run' })).getAttribute('href')).toBe('/runs/41')
  expect(screen.getByText(/reader@example.com/)).toBeTruthy()
})
it('filters the run panel and refreshes all request panels after publishing', async () => {
  const invalidate = show(41)
  fireEvent.click(await screen.findByRole('button', { name: 'Publish report' }))
  await waitFor(() => expect(mock.post).toHaveBeenCalledWith('/report-requests/4/publish', {}))
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['report-requests'] }))
  expect(mock.get).toHaveBeenCalledWith('/report-requests', { params: { run_id: 41 } })
})
it('requires a reason, supports cancel and submits a refusal', async () => {
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Refuse' }))
  expect((screen.getByRole('button', { name: 'Refuse request' }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: 'Refuse' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Refusal reason' }), { target: { value: 'Evidence incomplete' } })
  fireEvent.submit(screen.getByRole('textbox').closest('form')!)
  await waitFor(() => expect(mock.post).toHaveBeenCalledWith('/report-requests/4/refuse', { reason: 'Evidence incomplete' }))
})
it('keeps failed decisions visible and prevents publishing unfinished runs', async () => {
  mock.post.mockRejectedValueOnce(new Error('offline'))
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Publish report' }))
  expect((await screen.findByRole('alert')).textContent).toBe('Could not complete the request')
  cleanup()
  mock.get.mockResolvedValue({ data: [{ ...row, run_status: 'Running' }] })
  show()
  expect((await screen.findByRole('button', { name: 'Publish report' }) as HTMLButtonElement).disabled).toBe(true)
})
it('hides empty inboxes and denies nonpublishers without fetching identities', async () => {
  mock.get.mockResolvedValue({ data: [] })
  show()
  await waitFor(() => expect(mock.get).toHaveBeenCalledTimes(1))
  expect(screen.queryByText('Report requests')).toBeNull()
  cleanup()
  mock.get.mockClear()
  mock.user.role = 'viewer'
  show()
  expect(mock.get).not.toHaveBeenCalled()
})
it('shows an inbox load error', async () => {
  mock.get.mockRejectedValueOnce(new Error('offline'))
  show()
  expect((await screen.findByRole('alert')).textContent).toBe('Could not load report requests.')
})
