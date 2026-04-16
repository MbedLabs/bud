import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

export const APP_VERSION = '0.1.0'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bud_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('bud_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export interface User {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
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
}

export const usersApi = {
  list: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/users')
    return response.data
  },
  create: async (data: { email: string; full_name: string; password: string }): Promise<User> => {
    const response = await api.post<User>('/users', data)
    return response.data
  },
  update: async (id: number, data: { full_name?: string; email?: string; role?: string; is_active?: boolean }): Promise<User> => {
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
  metadata: Record<string, unknown> | null
  work_package_id: number | null
  created_at: string
  test_run_id: number
  artifacts?: string[]
}

export interface TestStation {
  account: string
  is_online: boolean
  is_active: boolean
  last_heartbeat: string | null
  socket_port: number
  location: string | null
}

// API functions
export const testRunsApi = {
  list: async (params?: { status?: string; limit?: number; offset?: number }) => {
    const response = await api.get<{ runs: TestRun[]; total: number }>('/test-runs', { params })
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get<TestRun>(`/test-runs/${id}`)
    return response.data
  },

  getResults: async (id: number) => {
    const response = await api.get<TestResult[]>(`/results/${id}`)
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
}

export const healthApi = {
  check: async () => {
    const response = await api.get<{ status: string; version: string }>('/health')
    return response.data
  },
}
