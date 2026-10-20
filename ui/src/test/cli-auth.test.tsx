// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  login: vi.fn(),
  auth: { isLoading: false, isAuthenticated: true, user: { full_name: 'Viewer' } },
}))

vi.mock('../api/client', async (original) => ({
  ...(await original<typeof import('../api/client')>()),
  api: { get: mocks.get, post: mocks.post },
  setupApi: { getStatus: vi.fn(async () => ({ setup_required: false })) },
}))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ ...mocks.auth, login: mocks.login }) }))
vi.mock('../components/Layout', () => ({ default: () => <p>Dashboard</p> }))

import App from '../App'
import Login from '../pages/Login'

const SESSION = 'b79c7405-4f63-4394-b653-59679590d642'
const APPROVAL_PATH = `/auth/cli?session_id=${SESSION}`
const originalLocation = window.location

/** Show the current client-side location for redirect assertions. */
function Location() {
  const location = useLocation()
  return <output aria-label="Location">{location.pathname}{location.search}</output>
}

/** Mount the application's public authorization route. */
function renderApproval() {
  return render(<MemoryRouter initialEntries={[APPROVAL_PATH]}><App /><Location /></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = { isLoading: false, isAuthenticated: true, user: { full_name: 'Viewer' } }
  mocks.get.mockResolvedValue({ data: { session_id: SESSION, client_name: 'Terminal client', mode: 'code', redirect_uri: null, expires_at: '2099-01-01T00:00:00', consumed: false } })
  mocks.post.mockResolvedValue({ data: { exchange_code: 'single-use-exchange-code', expires_at: '2099-01-01T00:00:00' } })
})
afterEach(() => {
  cleanup()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: originalLocation })
})

it('shows the requesting client and grants only the signed-in user permissions', async () => {
  renderApproval()
  expect(await screen.findByText('Terminal client')).toBeTruthy()
  expect(document.body.textContent).toMatch(/Bud/)
  expect(document.body.textContent).toMatch(/existing permissions/i)
  expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy()
  expect(mocks.get).toHaveBeenCalledWith(`/auth/cli/sessions/${SESSION}`)
})

it('waits for auth initialization before redirecting or loading metadata', () => {
  mocks.auth.isLoading = true
  mocks.auth.isAuthenticated = false
  renderApproval()
  expect(screen.getByText('Loading...')).toBeTruthy()
  expect(mocks.get).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Location').textContent).toBe(APPROVAL_PATH)
})

it('preserves the approval destination through login', async () => {
  mocks.auth.isAuthenticated = false
  renderApproval()
  await waitFor(() => expect(screen.getByLabelText('Location').textContent).toBe(`/login?next=${encodeURIComponent(APPROVAL_PATH)}`))
  expect(mocks.get).not.toHaveBeenCalled()
})

it('shows the one-time code and copies it only on the user action', async () => {
  const copy = vi.fn(async () => undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: copy } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  expect(await screen.findByText('single-use-exchange-code')).toBeTruthy()
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/approve', { session_id: SESSION })
  expect(copy).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Copy code' }))
  await waitFor(() => expect(copy).toHaveBeenCalledWith('single-use-exchange-code'))
  expect(document.body.textContent).toMatch(/paste.*client|paste.*terminal/i)
})

it('cancels without approving or issuing a code', async () => {
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(await screen.findByText(/authorization cancelled/i)).toBeTruthy()
  expect(mocks.post).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
})

it('shows an expired session error with a new-login instruction', async () => {
  mocks.get.mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'Invalid or expired authorization session' } } })
  renderApproval()
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(document.body.textContent).toMatch(/expired/)
  expect(document.body.textContent).toMatch(/start.*again|new.*link/i)
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
})

it('reports a rejected approval without displaying a code', async () => {
  mocks.post.mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'Invalid or expired authorization session' } } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(screen.queryByText('single-use-exchange-code')).toBeNull()
})

it.each(['4567', '80'])('redirects an approved callback to its validated loopback listener on port %s', async (port) => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: { session_id: SESSION, client_name: 'Terminal client', mode: 'callback', redirect_uri: `http://127.0.0.1:${port}/callback`, expires_at: '2099-01-01T00:00:00', consumed: false } })
  mocks.post.mockResolvedValue({ data: { redirect_to: `http://127.0.0.1:${port}/callback?code=once&state=original` } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(`http://127.0.0.1:${port}/callback?code=once&state=original`))
  expect(screen.queryByText('single-use-exchange-code')).toBeNull()
})

it('does not follow an approval response outside the validated loopback target', async () => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: { session_id: SESSION, client_name: 'Terminal client', mode: 'callback', redirect_uri: 'http://127.0.0.1:4567/callback', expires_at: '2099-01-01T00:00:00', consumed: false } })
  mocks.post.mockResolvedValue({ data: { redirect_to: 'https://evil.test/callback?code=once&state=original' } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(assign).not.toHaveBeenCalled()
})

it.each([`/auth/cli?session_id=${SESSION}`, 'https://evil.test', '//evil.test', '/settings', '/auth/cli?session_id=invalid', `/auth/cli?session_id=${SESSION}&redirect=https://evil.test`])('only returns login to a validated approval path: %s', async (next) => {
  render(<MemoryRouter initialEntries={[`/login?next=${encodeURIComponent(next)}`]}><Routes><Route path="/login" element={<Login />} /><Route path="*" element={<p>Destination</p>} /></Routes><Location /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'viewer@example.com' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password-123' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await waitFor(() => expect(screen.getByLabelText('Location').textContent).toBe(next === APPROVAL_PATH ? APPROVAL_PATH : '/'))
})
