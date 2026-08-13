import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { clearAuthToken, getAuthToken, setAuthToken } from '../lib/tokenStorage'

import packageJson from '../../package.json'

const API_URL = import.meta.env.VITE_API_URL || '/api'

export const APP_VERSION = packageJson.version

export const api = axios.create({
  baseURL: API_URL,
  // Send the httpOnly refresh cookie on same-origin auth calls.
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

const PUBLIC_PATHS = ['/login', '/accept-invite', '/verify-email', '/forgot-password', '/reset-password']

function redirectToLogin() {
  clearAuthToken()
  if (!PUBLIC_PATHS.includes(window.location.pathname)) {
    window.location.href = '/login'
  }
}

// De-duplicate concurrent refreshes: when the short access token expires, many
// in-flight requests can 401 at once; they all await a single /auth/refresh.
let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  try {
    // Bare axios (no interceptors) so a 401 here cannot recurse into itself.
    const resp = await axios.post<{ access_token: string }>(
      `${API_URL}/auth/refresh`,
      {},
      { withCredentials: true },
    )
    setAuthToken(resp.data.access_token)
    return resp.data.access_token
  } catch {
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const url = original?.url ?? ''
    const isAuthCall =
      url.includes('/auth/refresh') || url.includes('/auth/login') || url.includes('/auth/logout')

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null
        })
      }
      const newToken = await refreshPromise
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      redirectToLogin()
    } else if (error.response?.status === 401 && !isAuthCall) {
      redirectToLogin()
    }
    return Promise.reject(error)
  },
)

export interface User {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'viewer'
  is_active: boolean
  invited_at?: string | null
  last_invite_sent_at?: string | null
  invite_accepted_at?: string | null
  password_set_at?: string | null
  email_verified_at?: string | null
  pending_email?: string | null
  email_change_status?: 'requested' | 'awaiting_confirmation' | null
  email_change_requested_at?: string | null
  created_at: string
  updated_at: string
}

export interface InviteUserResponse {
  message: string
  user: User
  invite_link?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface InviteInfoResponse {
  email: string
  full_name: string
  valid: boolean
  expired: boolean
}

export interface AcceptInviteResponse {
  requires_email_verification: boolean
  email: string
  message: string
}

export interface GenericMessageResponse {
  message: string
}

export function extractApiErrorMessage(error: unknown, fallback = 'Request failed'): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/auth/login', { email, password })
    return response.data
  },
  refresh: async (): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/auth/refresh')
    return response.data
  },
  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout')
    } finally {
      clearAuthToken()
    }
  },
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me')
    return response.data
  },
  updateMe: async (data: { full_name?: string }): Promise<User> => {
    const response = await api.put<User>('/auth/me', data)
    return response.data
  },
  requestEmailChange: async (
    currentPassword: string,
    newEmail: string,
  ): Promise<GenericMessageResponse> => {
    const response = await api.post<GenericMessageResponse>('/auth/me/email', {
      current_password: currentPassword,
      new_email: newEmail,
    })
    return response.data
  },
  cancelEmailChange: async (): Promise<GenericMessageResponse> => {
    const response = await api.delete<GenericMessageResponse>('/auth/me/email')
    return response.data
  },
  confirmEmailChange: async (token: string): Promise<GenericMessageResponse> => {
    const response = await api.post<GenericMessageResponse>('/auth/confirm-email-change', { token })
    return response.data
  },
  changePassword: async (currentPassword: string, newPassword: string): Promise<User> => {
    const response = await api.put<User>('/auth/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },
  getInviteInfo: async (token: string): Promise<InviteInfoResponse> => {
    const response = await api.post<InviteInfoResponse>('/auth/invite-info', { token })
    return response.data
  },
  acceptInvite: async (token: string, password: string): Promise<AcceptInviteResponse> => {
    const response = await api.post<AcceptInviteResponse>('/auth/accept-invite', { token, password })
    return response.data
  },
  verifyEmail: async (token: string): Promise<GenericMessageResponse> => {
    const response = await api.post<GenericMessageResponse>('/auth/verify-email', { token })
    return response.data
  },
  forgotPassword: async (email: string): Promise<GenericMessageResponse> => {
    const response = await api.post<GenericMessageResponse>('/auth/forgot-password', { email })
    return response.data
  },
  resetPassword: async (token: string, newPassword: string): Promise<GenericMessageResponse> => {
    const response = await api.post<GenericMessageResponse>('/auth/reset-password', { token, new_password: newPassword })
    return response.data
  },
}

export const usersApi = {
  list: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/users')
    return response.data
  },
  create: async (data: { email: string; full_name: string; password: string; role?: 'admin' | 'viewer' }): Promise<User> => {
    const response = await api.post<User>('/users', data)
    return response.data
  },
  invite: async (data: { email: string; full_name: string; role?: 'admin' | 'viewer' }): Promise<InviteUserResponse> => {
    const response = await api.post<InviteUserResponse>('/users/invite', data)
    return response.data
  },
  update: async (id: number, data: { full_name?: string; role?: 'admin' | 'viewer'; is_active?: boolean }): Promise<User> => {
    const response = await api.patch<User>(`/users/${id}`, data)
    return response.data
  },
  startEmailChange: async (id: number, newEmail: string): Promise<User> => {
    const response = await api.post<User>(`/users/${id}/email`, { new_email: newEmail })
    return response.data
  },
  approveEmailChange: async (id: number): Promise<User> => {
    const response = await api.post<User>(`/users/${id}/email/approve`)
    return response.data
  },
  rejectEmailChange: async (id: number): Promise<User> => {
    const response = await api.delete<User>(`/users/${id}/email`)
    return response.data
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/users/${id}`)
  },
}

// Types
export interface TestRun {
  id: number
  name: string
  test_case_list: string
  status: string
  url_test_software: string | null
  ref_test_software: string
  total_tests: number
  passed_tests: number
  failed_tests: number
  skipped_tests: number
  duration_seconds: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  product_id: number | null
  runner_id: number | null
  /** Bud runner (Test Station) account that executed this run, if any. */
  runner_account: string | null
  /**
   * The test cases a custom run was built from, as the importable paths the
   * station's loader takes. Absent on an ordinary run, whose `test_case_list`
   * names a list the station resolves in its own workspace.
   */
  selected_tests?: string[] | null
}

export interface TestRunStatsFilters {
  /** Only count runs created within the last N days. Omit for all time. */
  days?: number
  /** Only count runs executed by this Test Station account. */
  runner_account?: string
  /** Only count runs for this test suite name. */
  suite?: string
}

export interface TestRunStats {
  total_runs: number
  passed_runs: number
  failed_runs: number
  in_progress_runs: number
  run_pass_rate: number
  total_tests: number
  passed_tests: number
  failed_tests: number
  skipped_tests: number
  test_pass_rate: number
}

export interface TestRunFilterOptions {
  suites: string[]
  runner_accounts: string[]
}

export interface TestResult {
  id: number
  test_class: string
  test_method: string
  test_name?: string
  passed: boolean
  status?: string
  duration_seconds: number
  error_message: string | null
  /**
   * The method's own stack trace. Present when a single result is fetched;
   * absent from a run's listing, which does not render it - the trace shown
   * against a failure comes from inside that assertion, not from here.
   */
  traceback?: string | null
  assertions: Record<string, unknown>[] | null
  test_metadata: Record<string, unknown> | null
  work_package_id: number | null
  created_at: string
  test_run_id: number | null
}

export interface CatalogEntry {
  test_path: string
  test_class: string
  suite: string
  runner_accounts: string[]
  method_count: number
  last_run_at: string | null
  last_passed: boolean | null
  last_run_id: number | null
}

export interface UnassignedTest {
  test_path: string
  reason: string
}

export interface CustomRunResult {
  runs: TestRun[]
  unassigned: UnassignedTest[]
}

export interface Artifact {
  id: number
  filename: string
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string | null
  test_case: string | null
  created_at: string
  test_run_id: number | null
}

export interface TestRunEvent {
  id: number
  test_run_id: number
  sequence: number
  stage: string
  status: string
  title: string
  message: string | null
  event_metadata: Record<string, unknown> | null
  created_at: string
}

export interface TestStation {
  account: string
  is_online: boolean
  is_active: boolean
  last_heartbeat: string | null
  socket_port: number
  location: string | null
  current_run?: { id: number; name: string }
}

export interface Runner {
  id: number
  account: string
  socket_port: number
  location: string | null
  is_active: boolean
  last_heartbeat: string | null
  created_at: string
}

// API functions
export interface BloomPublishResult {
  document_id: number | null
  doc_id: string | null
  created: boolean
  published_files: string[]
}

export const testRunsApi = {
  publishToBloom: async (runId: number, projectPrefix: string) => {
    const response = await api.post<BloomPublishResult>(`/test-runs/${runId}/publish-to-bloom`, {
      project_prefix: projectPrefix,
    })
    return response.data
  },
  list: async (params?: {
    status?: string
    limit?: number
    offset?: number
    /** Filter by Bud runner / Test Station account. */
    runner_account?: string
    /** Filter by the location a runner sits at. A location holds several. */
    location?: string
    /** Match the run name, the test case list, or the runner account. */
    q?: string
    /** Return only the latest run for each test suite name. */
    latest_per_suite?: boolean
  }) => {
    const response = await api.get<{ runs: TestRun[]; total: number }>('/test-runs', { params })
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get<TestRun>(`/test-runs/${id}`)
    return response.data
  },

  getEvents: async (id: number) => {
    const response = await api.get<TestRunEvent[]>(`/test-runs/${id}/events`)
    return response.data
  },

  /** The files a run produced: screenshots, plots, traces, packet captures. */
  getArtifacts: async (id: number) => {
    const response = await api.get<Artifact[]>(`/test-runs/${id}/artifacts`)
    return response.data
  },

  /** Dashboard counters aggregated server-side over every matching run. */
  stats: async (params?: TestRunStatsFilters) => {
    const response = await api.get<TestRunStats>('/test-runs/stats', { params })
    return response.data
  },

  /** Suite names and Test Stations that actually appear in test runs. */
  filterOptions: async (params?: { days?: number }) => {
    const response = await api.get<TestRunFilterOptions>('/test-runs/filter-options', { params })
    return response.data
  },
}

export const resultsApi = {
  list: async (testRunId: number) => {
    const response = await api.get<TestResult[]>(`/results/${testRunId}`)
    return response.data
  },
}

export const testStationsApi = {
  status: async () => {
    const response = await api.get<{ runners: TestStation[] }>('/runners/status')
    return response.data
  },

  /**
   * Fetch a single runner (a.k.a. test station) by account name.
   * Used to resolve runner_id → account for display on test run detail pages.
   */
  getByAccount: async (account: string) => {
    const response = await api.get<Runner>(`/runners/${account}`)
    return response.data
  },
}

export interface ALMIntegrationSettings {
  bloom_url: string
  has_bloom_token: boolean
  bloom_token_prefix: string | null
  bloom_token_rotated_at: string | null
}

export interface ALMIntegrationSettingsUpdate {
  bloom_url: string
  bloom_token?: string
  clear_bloom_token?: boolean
}

export const settingsApi = {
  getALM: async () => {
    const response = await api.get<ALMIntegrationSettings>('/settings/integrations/PLM')
    return response.data
  },
  updateALM: async (data: ALMIntegrationSettingsUpdate) => {
    const response = await api.post<ALMIntegrationSettings>('/settings/integrations/PLM', data)
    return response.data
  },
}

/**
 * PDF reports.
 *
 * The download goes through the axios instance rather than a plain link so the
 * Authorization header (and the 401 refresh retry) still apply; a bare <a href>
 * would arrive unauthenticated.
 */
export const catalogApi = {
  /**
   * The test cases Bud has a record of, and the benches each has run on.
   *
   * Built from what has executed, not from a declared inventory - Bud never
   * reads a bench's workspace, so a case that has never run cannot appear and
   * cannot be selected.
   */
  list: async (params?: { runner_account?: string; suite?: string }) => {
    const response = await api.get<{ entries: CatalogEntry[]; total: number }>('/test-catalog', {
      params,
    })
    return response.data
  },
}

export const customRunsApi = {
  /**
   * Queue the selection. A selection spanning two benches comes back as two
   * runs, because a test case can only run where it has run before.
   */
  create: async (data: { test_paths: string[]; name?: string; runner_account?: string }) => {
    const response = await api.post<CustomRunResult>('/test-runs/custom', data)
    return response.data
  },
}

export const artifactsApi = {
  /**
   * Download one artifact.
   *
   * Through the API client rather than a bare `<a href>`, so the request
   * carries the Authorization header and the 401 refresh retry - artifacts are
   * not public, and a plain link would arrive unauthenticated.
   */
  download: async (artifactId: number, fallbackName: string) => {
    const response = await api.get(`/uploads/${artifactId}`, { responseType: 'blob' })
    return { blob: response.data as Blob, filename: filenameFromResponse(response, fallbackName) }
  },
}

export const reportsApi = {
  testRuns: async (params?: TestRunStatsFilters) => {
    const response = await api.get('/reports/test-runs.pdf', {
      params,
      responseType: 'blob',
    })
    return { blob: response.data as Blob, filename: filenameFromResponse(response, 'bud-test-report.pdf') }
  },

  testRun: async (runId: number) => {
    const response = await api.get(`/reports/test-runs/${runId}.pdf`, { responseType: 'blob' })
    return { blob: response.data as Blob, filename: filenameFromResponse(response, `bud-run-${runId}.pdf`) }
  },
}

/** Read the server's chosen filename, preferring the RFC 5987 form. */
export function filenameFromResponse(
  response: { headers: Record<string, unknown> | { get?: (name: string) => string | null } },
  fallback: string,
): string {
  const raw =
    typeof (response.headers as { get?: (n: string) => string | null }).get === 'function'
      ? (response.headers as { get: (n: string) => string | null }).get('content-disposition')
      : ((response.headers as Record<string, unknown>)['content-disposition'] as string | undefined)
  if (!raw) return fallback

  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(raw)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      // fall through to the plain form
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(raw)
  return plain ? plain[1] : fallback
}

/** Hand a generated file to the browser's downloader. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
