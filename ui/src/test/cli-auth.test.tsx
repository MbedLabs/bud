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
const codeSession = { session_id: SESSION, client_name: 'Terminal client', mode: 'code', redirect_uri: null, created_at: '2099-01-01T00:00:00Z', expires_at: '2099-01-01T00:10:00Z', consumed: false }
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

/** Type the code the client shows and wait for the server to confirm it. */
async function enterMatchingCode() {
  fireEvent.change(await screen.findByLabelText('Request code'), { target: { value: 'BUUZ-WHVV' } })
  expect(await screen.findByText('The code matches.')).toBeTruthy()
}

/** Answer /auth/cli/check with one result and every other post with another. */
function answerCheck(check: () => Promise<unknown>, other: () => Promise<unknown> = () => Promise.resolve({ data: {} })) {
  mocks.post.mockImplementation((url: string) => url === '/auth/cli/check' ? check() : other())
}

/** The calls made to /auth/cli/check. */
function checkCalls() {
  return mocks.post.mock.calls.filter(([url]) => url === '/auth/cli/check')
}

/** A refused request with an HTTP status and detail. */
function refused(status: number, detail: string) {
  return { isAxiosError: true, message: detail, response: { status, data: { detail }, headers: {} } }
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

it('asks for the request code and shows the unverified client name, the account, the times and the warning', async () => {
  renderApproval()
  expect(await screen.findByText('Terminal client')).toBeTruthy()
  expect((screen.getByLabelText('Request code') as HTMLInputElement).value).toBe('')
  const text = document.body.textContent ?? ''
  expect(text).toMatch(/Type the code your terminal or AI client shows next to the link\./)
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
  expect(await screen.findByLabelText('Request code')).toBeTruthy()
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
  await enterMatchingCode()
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  expect(await screen.findByText('single-use-exchange-code')).toBeTruthy()
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/approve', { session_id: SESSION, request_code: 'BUUZ-WHVV' })
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
  answerCheck(() => Promise.resolve({}), () => Promise.reject({ isAxiosError: true, response: { data: { detail: 'Invalid or expired authorization session' } } }))
  renderApproval()
  await enterMatchingCode()
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(screen.queryByText('single-use-exchange-code')).toBeNull()
})

it.each(['4567', '80'])('redirects an approved callback to its validated loopback listener on port %s', async (port) => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: { ...callbackSession, redirect_uri: `http://127.0.0.1:${port}/callback` } })
  mocks.post.mockResolvedValue({ data: { redirect_to: `http://127.0.0.1:${port}/callback?code=once&state=original` } })
  renderApproval()
  await enterMatchingCode()
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith(`http://127.0.0.1:${port}/callback?code=once&state=original`))
  expect(screen.queryByText('single-use-exchange-code')).toBeNull()
})

it('does not follow an approval response outside the validated loopback target', async () => {
  const assign = vi.fn()
  Object.defineProperty(window, 'location', { configurable: true, writable: true, value: { assign } })
  mocks.get.mockResolvedValue({ data: callbackSession })
  mocks.post.mockResolvedValue({ data: { redirect_to: 'https://evil.test/callback?code=once&state=original' } })
  renderApproval()
  await enterMatchingCode()
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(assign).not.toHaveBeenCalled()
})

it('renders no request code from the session answer', async () => {
  mocks.get.mockResolvedValue({ data: { ...codeSession, request_code: 'BUUZ-WHVV' } })
  renderApproval()
  expect((await screen.findByLabelText('Request code') as HTMLInputElement).value).toBe('')
  expect(screen.queryByText('BUUZ-WHVV')).toBeNull()
})

it('formats a typed code and checks it once at eight characters', async () => {
  renderApproval()
  const field = await screen.findByLabelText('Request code') as HTMLInputElement
  for (const letter of 'buuzwhvv') fireEvent.change(field, { target: { value: `${field.value}${letter}` } })
  expect(field.value).toBe('BUUZ-WHVV')
  fireEvent.change(field, { target: { value: 'BUUZ-WHVVX' } })
  expect(field.value).toBe('BUUZ-WHVV')
  await screen.findByText('The code matches.')
  expect(checkCalls()).toEqual([['/auth/cli/check', { session_id: SESSION, request_code: 'BUUZ-WHVV' }]])
})

it('formats a pasted code with a space and checks it', async () => {
  renderApproval()
  const field = await screen.findByLabelText('Request code') as HTMLInputElement
  fireEvent.change(field, { target: { value: 'buuz whvv' } })
  expect(field.value).toBe('BUUZ-WHVV')
  await screen.findByText('The code matches.')
  expect(checkCalls()).toHaveLength(1)
})

it('enables Approve only while the checked code matches', async () => {
  renderApproval()
  const field = await screen.findByLabelText('Request code')
  const approveButton = screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement
  expect(approveButton.disabled).toBe(true)
  fireEvent.change(field, { target: { value: 'BUUZ-WHV' } })
  expect(approveButton.disabled).toBe(true)
  await enterMatchingCode()
  expect(approveButton.disabled).toBe(false)
  fireEvent.change(field, { target: { value: 'BUUZ-WHV' } })
  expect(approveButton.disabled).toBe(true)
  expect(screen.queryByText('The code matches.')).toBeNull()
})

it('shows a mismatch without the server text and keeps Approve disabled while the request is pending', async () => {
  answerCheck(() => Promise.reject(refused(400, 'Invalid or expired authorization session')))
  renderApproval()
  fireEvent.change(await screen.findByLabelText('Request code'), { target: { value: 'AAAA-AAAA' } })
  expect(await screen.findByText('This code does not match. Check the code in your terminal, or deny this request.')).toBeTruthy()
  expect(screen.queryByText('Invalid or expired authorization session')).toBeNull()
  expect((screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true)
  expect(mocks.get).toHaveBeenCalledTimes(2)
})

it('shows the ended request when a refused check finds the request gone', async () => {
  answerCheck(() => Promise.reject(refused(400, 'Invalid or expired authorization session')))
  renderApproval()
  const field = await screen.findByLabelText('Request code')
  mocks.get.mockRejectedValue(refused(400, 'Invalid or expired authorization session'))
  fireEvent.change(field, { target: { value: 'AAAA-AAAA' } })
  expect((await screen.findByRole('alert')).textContent).toMatch(/expired or has already been used/)
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
})

it.each(['/auth/cli/check', '/auth/cli/approve'])('asks to wait after a 429 on %s', async (limited) => {
  mocks.post.mockImplementation((url: string) => url === limited ? Promise.reject(refused(429, 'Rate limit exceeded')) : Promise.resolve({}))
  renderApproval()
  fireEvent.change(await screen.findByLabelText('Request code'), { target: { value: 'BUUZ-WHVV' } })
  if (limited === '/auth/cli/approve') {
    await screen.findByText('The code matches.')
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  }
  expect(await screen.findByText('Too many attempts. Wait a minute and try again.')).toBeTruthy()
  expect((screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true)
})

it('shows a mismatch when approval answers 400 for a request that is still pending', async () => {
  answerCheck(() => Promise.resolve({}), () => Promise.reject(refused(400, 'Invalid or expired authorization session')))
  renderApproval()
  await enterMatchingCode()
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
  expect(await screen.findByText('This code does not match. Check the code in your terminal, or deny this request.')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
})

it('ignores a check answer for a code that was edited since', async () => {
  let answer: (value: unknown) => void = () => {}
  answerCheck(() => new Promise((resolve) => { answer = resolve }))
  renderApproval()
  const field = await screen.findByLabelText('Request code')
  fireEvent.change(field, { target: { value: 'BUUZ-WHVV' } })
  fireEvent.change(field, { target: { value: 'BUUZ-WHV' } })
  answer({})
  await waitFor(() => expect(checkCalls()).toHaveLength(1))
  expect(screen.queryByText('The code matches.')).toBeNull()
  expect((screen.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(true)
})

it('denies with an empty code field', async () => {
  mocks.post.mockResolvedValue({ data: {} })
  renderApproval()
  expect((await screen.findByLabelText('Request code') as HTMLInputElement).value).toBe('')
  fireEvent.click(screen.getByRole('button', { name: 'Deny' }))
  expect(await screen.findByText(/This link no longer works/)).toBeTruthy()
  expect(mocks.post).toHaveBeenCalledWith('/auth/cli/deny', { session_id: SESSION })
})

it.each([`/auth/cli?session_id=${SESSION}`, 'https://evil.test', '//evil.test', '/settings', '/auth/cli?session_id=invalid', `/auth/cli?session_id=${SESSION}&redirect=https://evil.test`])('only returns login to a validated approval path: %s', async (next) => {
  render(<MemoryRouter initialEntries={[`/login?next=${encodeURIComponent(next)}`]}><Routes><Route path="/login" element={<Login />} /><Route path="*" element={<p>Destination</p>} /></Routes><Location /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'viewer@example.com' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password-123' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await waitFor(() => expect(screen.getByLabelText('Location').textContent).toBe(next === APPROVAL_PATH ? APPROVAL_PATH : '/'))
})
