import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
  assertions: any[] | null
  metadata: Record<string, any> | null
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
