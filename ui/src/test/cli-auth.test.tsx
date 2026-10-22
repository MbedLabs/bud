// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  login: vi.fn(),
  auth: { isLoading: false, isAuthenticated: true, user: { full_name: 'Viewer', email: 'viewer@example.com' } },
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
const CALLBACK = 'http://127.0.0.1:4567/callback'
const CODE_MODE_OFF = 'Code sign-in is turned off on this instance. Use callback mode.'
const originalLocation = window.location
const codeSession = { session_id: SESSION, client_name: 'Terminal client', mode: 'code', redirect_uri: null, created_at: '2099-01-01T00:00:00Z', expires_at: '2099-01-01T00:10:00Z', consumed: false, request_code: 'BUUZ-WHVV' }
const callbackSession = { ...codeSession, mode: 'callback', redirect_uri: CALLBACK }

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
  mocks.auth = { isLoading: false, isAuthenticated: true, user: { full_name: 'Viewer', email: 'viewer@example.com' } }
  mocks.get.mockResolvedValue({ data: codeSession })
  mocks.post.mockResolvedValue({ data: { exchange_code: 'single-use-exchange-code', expires_at: '2099-01-01T00:00:00' } })
})
afterEach(() => {
  cleanup()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: originalLocation })
})

it('shows the request code, the unverified client name, the account, the times and the warning', async () => {
  renderApproval()
  expect(await screen.findByText('Terminal client')).toBeTruthy()
  expect(screen.getByText('BUUZ-WHVV')).toBeTruthy()
  const text = document.body.textContent ?? ''
  expect(text).toMatch(/It must match the code your client shows/)
  expect(text).toMatch(/as given by the requesting client \(not verified\)/)
  expect(text).toMatch(/to Bud as Viewer \(viewer@example\.com\), with your full permissions/)
  expect(text).toContain(`Requested ${new Date('2099-01-01T00:00:00Z').toLocaleString()}`)
  expect(text).toContain(`Expires ${new Date('2099-01-01T00:10:00Z').toLocaleString()}`)
  expect(text).toMatch(/Approve only a sign-in you started yourself, on your own computer, in the last few minutes\./)
  expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Deny' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull()
  expect(mocks.get).toHaveBeenCalledWith(`/auth/cli/sessions/${SESSION}`)
})

it('warns before Approve in code mode only', async () => {
  renderApproval()
  expect(await screen.findByText(/Code sign-in: after you approve, this page shows a one-time code/)).toBeTruthy()
  cleanup()
  mocks.get.mockResolvedValue({ data: callbackSession })
  renderApproval()
  expect(await screen.findByText('BUUZ-WHVV')).toBeTruthy()
  expect(screen.queryByText(/Code sign-in: after you approve/)).toBeNull()
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
  expect(screen.getByText('Paste this code only into the client where you started this sign-in. Never send it to anyone.')).toBeTruthy()
})

it('denies a code-mode request on the server without approving it', async () => {
  mocks.post.mockResolvedValue({ data: {} })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
  expect(await screen.findByText(/denied\. This link no longer works/)).toBeTruthy()
  expect(mocks.post).toHaveBeenCalledTimes(1)
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/deny', { session_id: SESSION })
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
})

it('returns a denied callback request to its validated loopback listener', async () => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: callbackSession })
  mocks.post.mockResolvedValue({ data: { redirect_to: `${CALLBACK}?error=access_denied&state=original` } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(`${CALLBACK}?error=access_denied&state=original`))
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/deny', { session_id: SESSION })
  expect(screen.getByText(/denied\. Returning to your client/)).toBeTruthy()
})

it.each([
  'https://127.0.0.1:4567/callback?error=access_denied&state=s',
  'http://evil.test:4567/callback?error=access_denied&state=s',
  'http://127.0.0.1:4568/callback?error=access_denied&state=s',
  'http://127.0.0.1:4567/other?error=access_denied&state=s',
  'http://user:secret@127.0.0.1:4567/callback?error=access_denied&state=s',
  'http://127.0.0.1:4567/callback?error=access_denied&state=s#fragment',
  'http://127.0.0.1:4567/callback?error=access_denied&state=s#',
  'http://127.0.0.1:4567/callback?error=server_error&state=s',
  'http://127.0.0.1:4567/callback?error=access_denied&error=access_denied&state=s',
  'http://127.0.0.1:4567/callback?state=s',
  'http://127.0.0.1:4567/callback?error=access_denied',
  'http://127.0.0.1:4567/callback?error=access_denied&state=a&state=b',
  'http://127.0.0.1:4567/callback?error=access_denied&state=s&code=once',
  'http://127.0.0.1:4567/callback?code=once&state=s',
  'not a url',
])('does not follow a denial target outside the validated loopback callback: %s', async (target) => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: callbackSession })
  mocks.post.mockResolvedValue({ data: { redirect_to: target } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
  expect(await screen.findByText(/denied\. This link no longer works/)).toBeTruthy()
  expect(assign).not.toHaveBeenCalled()
})

it('reports a refused denial', async () => {
  mocks.post.mockRejectedValue({ isAxiosError: true, response: { status: 400, data: { detail: 'Invalid or expired authorization session' } } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(document.body.textContent).toMatch(/Invalid or expired authorization session/)
})

it('shows the code sign-in message with Deny and no Approve when the instance refuses the request', async () => {
  mocks.get.mockRejectedValue({ isAxiosError: true, response: { status: 403, data: { detail: CODE_MODE_OFF } } })
  mocks.post.mockResolvedValue({ data: {} })
  renderApproval()
  expect(await screen.findByText(CODE_MODE_OFF)).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Deny' }))
  expect(await screen.findByText(/denied\. This link no longer works/)).toBeTruthy()
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/deny', { session_id: SESSION })
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
  mocks.get.mockResolvedValue({ data: { ...callbackSession, redirect_uri: `http://127.0.0.1:${port}/callback` } })
  mocks.post.mockResolvedValue({ data: { redirect_to: `http://127.0.0.1:${port}/callback?code=once&state=original` } })
  renderApproval()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(`http://127.0.0.1:${port}/callback?code=once&state=original`))
  expect(screen.queryByText('single-use-exchange-code')).toBeNull()
})

it('does not follow an approval response outside the validated loopback target', async () => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: callbackSession })
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
