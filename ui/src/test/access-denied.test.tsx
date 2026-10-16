// @vitest-environment jsdom
/**
 * The access-denied page: it names the resource only by its address, asks the
 * administrators once, and says when a request is pending or the mail failed.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AccessRequestInfo } from '../api/client'

const pending: AccessRequestInfo = {
  id: 3, resource_type: 'test-run', resource_ref: '42',
  status: 'pending', created_at: '2026-09-24T10:00:00', decided_at: null,
  requester_name: null, requester_email: null, already_requested: true, mail_sent: null,
}

vi.mock('../api/client', () => ({
  accessRequestsApi: { mine: vi.fn(), create: vi.fn() },
  extractApiErrorMessage: () => 'failed',
}))

const api = await import('../api/client')
const AccessDenied = (await import('../components/AccessDenied')).default
const { isAccessDenied } = await import('../lib/accessDenied')

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccessDenied resourceType="test-run" resourceRef="42" />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('Access denied page', () => {
  it('names the resource and sends one request', async () => {
    vi.mocked(api.accessRequestsApi.mine).mockResolvedValue(null)
    vi.mocked(api.accessRequestsApi.create).mockResolvedValue({ ...pending, already_requested: false, mail_sent: true })
    renderPage()
    expect(screen.getByText("You don't have access to this resource")).toBeTruthy()
    expect(screen.getByText('Test run 42')).toBeTruthy()
    fireEvent.click(await screen.findByText('Request access'))
    expect(await screen.findByText('Access requested on 2026-09-24 10:00 UTC.')).toBeTruthy()
    expect(api.accessRequestsApi.create).toHaveBeenCalledWith({
      resource_type: 'test-run', resource_ref: '42',
    })
    expect(screen.queryByText('Request access')).toBeNull()
  })

  it('says a request is already pending', async () => {
    vi.mocked(api.accessRequestsApi.mine).mockResolvedValue(pending)
    renderPage()
    expect(await screen.findByText('A request is already pending since 2026-09-24 10:00 UTC.')).toBeTruthy()
    expect(screen.queryByText('Request access')).toBeNull()
  })

  it('reports a mail failure without losing the request', async () => {
    vi.mocked(api.accessRequestsApi.mine).mockResolvedValue(null)
    vi.mocked(api.accessRequestsApi.create).mockResolvedValue({ ...pending, already_requested: false, mail_sent: false })
    renderPage()
    fireEvent.click(await screen.findByText('Request access'))
    expect(await screen.findByText(/email to the administrators could not be sent/)).toBeTruthy()
  })

  it('treats 403 and 404 as access denied, nothing else', () => {
    const axiosError = (status: number) => ({ isAxiosError: true, response: { status } })
    expect(isAccessDenied(axiosError(403))).toBe(true)
    expect(isAccessDenied(axiosError(404))).toBe(true)
    expect(isAccessDenied(axiosError(500))).toBe(false)
    expect(isAccessDenied(new Error('x'))).toBe(false)
  })
})
