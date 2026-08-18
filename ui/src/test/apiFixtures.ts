/**
 * Canned API responses in the shapes the backend really returns.
 *
 * Page tests mount a route and let its queries resolve against these, so what
 * is asserted is the page rendering real-shaped data rather than a spinner. The
 * shapes are the exported interfaces in `api/client.ts`; a page that reads a
 * field nothing here supplies fails loudly instead of silently rendering blank.
 */

const NOW = '2026-03-01T10:00:00Z'

export const user = {
  id: 1,
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
  role: 'admin' as const,
  is_active: true,
  pending_email: null,
  email_change_status: null,
  email_change_requested_at: null,
  created_at: NOW,
  updated_at: NOW,
}

/** A second account, so tests can act on someone other than the signed-in user. */
export const otherUser = {
  id: 2,
  email: 'grace@example.com',
  full_name: 'Grace Hopper',
  role: 'viewer' as const,
  is_active: true,
  pending_email: null,
  email_change_status: null,
  email_change_requested_at: null,
  created_at: NOW,
  updated_at: NOW,
}

export const testRun = {
  id: 42,
  name: 'Gateway ECU - Nightly',
  test_case_list: 'SmokeTests, RegressionTests',
  status: 'Completed',
  url_test_software: null,
  ref_test_software: '1.4.2',
  total_tests: 3,
  passed_tests: 2,
  failed_tests: 1,
  skipped_tests: 0,
  duration_seconds: 12.5,
  created_at: NOW,
  started_at: NOW,
  completed_at: NOW,
  product_id: 1,
  runner_id: 1,
  runner_account: 'bench-01',
}

export const testResult = {
  id: 101,
  test_class: 'SmokeTests',
  test_method: 'test_boot',
  test_name: 'SmokeTests.test_boot',
  passed: true,
  status: 'Passed',
  duration_seconds: 1.5,
  error_message: null,
  traceback: null,
  assertions: [{ name: 'voltage', passed: true, actual: 3.3 }],
  test_metadata: { bench: 'lab-01' },
  work_package_id: null,
  created_at: NOW,
  test_run_id: 42,
  artifacts: [],
}

export const failedResult = {
  ...testResult,
  id: 102,
  test_method: 'test_shutdown',
  test_name: 'SmokeTests.test_shutdown',
  passed: false,
  status: 'Failed',
  error_message: 'expected 0V, measured 3.3V',
  traceback: 'Traceback (most recent call last): ...',
  assertions: [{ name: 'rail', passed: false, actual: 3.3, expected: 0 }],
}

export const testRunEvent = {
  id: 201,
  test_run_id: 42,
  sequence: 1,
  stage: 'upload',
  status: 'Completed',
  title: 'Results uploaded',
  message: '3 results',
  event_metadata: null,
  created_at: NOW,
}

export const testStation = {
  account: 'bench-01',
  is_online: true,
  is_active: true,
  last_heartbeat: NOW,
  socket_port: 9000,
  location: 'Lab A',
  current_run: { id: 42, name: testRun.name },
}

export const runner = {
  id: 1,
  account: 'bench-01',
  socket_port: 9000,
  location: 'Lab A',
  is_active: true,
  last_heartbeat: NOW,
  created_at: NOW,
}

export const stats = {
  total_runs: 5,
  passed_runs: 3,
  failed_runs: 2,
  in_progress_runs: 0,
  run_pass_rate: 60,
  total_tests: 30,
  passed_tests: 24,
  failed_tests: 5,
  skipped_tests: 1,
  test_pass_rate: 80,
}

export const filterOptions = {
  suites: ['Nightly', 'Regression'],
  runner_accounts: ['bench-01', 'bench-02'],
}

export const almSettings = {
  bloom_url: 'https://bloom.example.com',
  has_bloom_token: true,
  bloom_token_prefix: 'blm_sync_abcd',
  bloom_token_rotated_at: NOW,
}

/** `group.method -> response`, matching the client's declared return types. */
/** A packet capture attached to a run: the shape the artifacts panel lists. */
export const artifact = {
  id: 7,
  filename: '5f0c9c4e-2b3a-4f11-9a77-0f2c9a1b3c4d.pcap',
  original_filename: 'endurance-load.pcap',
  content_type: 'application/vnd.tcpdump.pcap',
  size_bytes: 4_718_592,
  sha256: 'a'.repeat(64),
  test_case: 'ThroughputTests',
  created_at: NOW,
  test_run_id: 42,
}

/**
 * Three test cases across two benches, chosen so placement is testable:
 * Voltage runs only on bench-01, Thermal only on bench-02, and Boot on both.
 */
export const catalogEntries = [
  {
    test_path: 'BigPack_voltage.VoltageTest',
    test_class: 'VoltageTest',
    suite: 'Nightly',
    runner_accounts: ['bench-01'],
    method_count: 2,
    last_run_at: NOW,
    last_passed: true,
    last_run_id: 42,
  },
  {
    test_path: 'boot_suite.BootTest',
    test_class: 'BootTest',
    suite: 'Nightly',
    runner_accounts: ['bench-01', 'bench-02'],
    method_count: 1,
    last_run_at: NOW,
    last_passed: false,
    last_run_id: 42,
  },
  {
    test_path: 'thermal.ThermalTest',
    test_class: 'ThermalTest',
    suite: 'Powertrain',
    runner_accounts: ['bench-02'],
    method_count: 1,
    last_run_at: NOW,
    last_passed: true,
    last_run_id: 43,
  },
]

export const RESPONSES: Record<string, unknown> = {
  'authApi.login': { access_token: 'tok', token_type: 'bearer', user },
  'authApi.refresh': { access_token: 'tok', token_type: 'bearer', user },
  'authApi.logout': undefined,
  'authApi.getMe': user,
  'authApi.updateMe': user,
  'authApi.requestEmailChange': { message: 'ok' },
  'authApi.cancelEmailChange': { message: 'ok' },
  'authApi.confirmEmailChange': { message: 'ok' },
  'authApi.changePassword': user,
  'authApi.getInviteInfo': {
    email: user.email,
    full_name: user.full_name,
    valid: true,
    expired: false,
  },
  'authApi.acceptInvite': {
    requires_email_verification: false,
    email: user.email,
    message: 'ok',
  },
  'authApi.verifyEmail': { message: 'ok' },
  'authApi.forgotPassword': { message: 'ok' },
  'authApi.resetPassword': { message: 'ok' },

  'usersApi.list': [user, otherUser],
  'usersApi.create': user,
  'usersApi.invite': { message: 'Invitation sent', user },
  'usersApi.update': user,
  'usersApi.startEmailChange': user,
  'usersApi.approveEmailChange': user,
  'usersApi.rejectEmailChange': user,
  'usersApi.delete': undefined,

  'testRunsApi.list': { runs: [testRun], total: 1 },
  'testRunsApi.get': testRun,
  'testRunsApi.getEvents': [testRunEvent],
  'testRunsApi.getArtifacts': [artifact],
  'catalogApi.list': { entries: catalogEntries, total: catalogEntries.length },
  'customRunsApi.create': {
    runs: [{ ...testRun, id: 90, name: 'Custom run - Nightly', status: 'Pending', selected_tests: ['BigPack_voltage.VoltageTest'] }],
    unassigned: [],
  },
  // The blob a download resolves to; `saveBlob` is stubbed in the page tests.
  'artifactsApi.download': { blob: new Blob(['pcap']), filename: 'endurance-load.pcap' },
  'testRunsApi.stats': stats,
  'testRunsApi.filterOptions': filterOptions,

  'resultsApi.list': [testResult, failedResult],

  'testStationsApi.status': { runners: [testStation] },
  'testStationsApi.getByAccount': runner,

  'settingsApi.getALM': almSettings,
  'settingsApi.updateALM': almSettings,

  'reportsApi.testRuns': { blob: new Blob(['%PDF-']), filename: 'bud-test-report.pdf' },
  'reportsApi.testRun': { blob: new Blob(['%PDF-']), filename: 'bud-run-42.pdf' },
}

/**
 * Put every mocked endpoint back on its fixture response.
 *
 * `vi.clearAllMocks()` clears call history but leaves implementations in place,
 * so a `mockResolvedValue` set for one case stays in force for every case after
 * it - and the failure surfaces in the later test, which looks innocent. This
 * re-establishes the default, so a case that overrides one endpoint cannot
 * decide what the next case sees.
 */
export function resetApiMocks(client: Record<string, unknown>, vi: ViLike): void {
  for (const [groupName, group] of Object.entries(client)) {
    if (!groupName.endsWith('Api') || typeof group !== 'object' || group === null) continue
    for (const [method, value] of Object.entries(group as Record<string, unknown>)) {
      if (typeof value !== 'function') continue
      const key = `${groupName}.${method}`
      if (!(key in RESPONSES)) continue
      vi.mocked(value as (...args: unknown[]) => unknown).mockImplementation(
        async () => RESPONSES[key],
      )
    }
  }
}

/** Only the part of vitest's `vi` this helper needs. */
interface ViLike {
  mocked<T>(fn: T): { mockImplementation(impl: (...args: unknown[]) => unknown): unknown }
}
