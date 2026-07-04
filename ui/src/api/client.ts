import axios from 'axios'
import { clearAuthToken, getAuthToken } from '../lib/tokenStorage'

import packageJson from '../../package.json'

const API_URL = import.meta.env.VITE_API_URL || '/api'

export const APP_VERSION = packageJson.version

export const api = axios.create({
  baseURL: API_URL,
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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthToken()
      const publicPaths = ['/login', '/accept-invite', '/verify-email', '/forgot-password', '/reset-password']
      if (!publicPaths.includes(window.location.pathname)) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
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
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me')
    return response.data
  },
  updateMe: async (data: { full_name?: string; email?: string }): Promise<User> => {
    const response = await api.put<User>('/auth/me', data)
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
    const response = await api.get<InviteInfoResponse>('/auth/invite-info', { params: { token } })
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
  update: async (id: number, data: { full_name?: string; email?: string; role?: 'admin' | 'viewer'; is_active?: boolean }): Promise<User> => {
    const response = await api.patch<User>(`/users/${id}`, data)
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
  traceback: string | null
  assertions: Record<string, unknown>[] | null
  test_metadata: Record<string, unknown> | null
  work_package_id: number | null
  created_at: string
  test_run_id: number | null
  artifacts?: string[]
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
export const testRunsApi = {
  list: async (params?: {
    status?: string
    limit?: number
    offset?: number
    /** Filter by Bud runner / Test Station account. */
    runner_account?: string
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

export const healthApi = {
  check: async () => {
    const response = await api.get<{ status: string; version: string }>('/health')
    return response.data
  },
}

export interface ALMIntegrationSettings {
  bloom_url: string
  bloom_token: string
}

export const settingsApi = {
  getALM: async () => {
    const response = await api.get<ALMIntegrationSettings>('/settings/integrations/PLM')
    return response.data
  },
  updateALM: async (data: ALMIntegrationSettings) => {
    const response = await api.post<ALMIntegrationSettings>('/settings/integrations/PLM', data)
    return response.data
  },
}
