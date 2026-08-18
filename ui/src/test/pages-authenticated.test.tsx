// @vitest-environment jsdom
/**
 * Every signed-in screen, rendered with real data and driven the way a user
 * drives it.
 *
 * The existing smoke test renders the public screens to a string, so it stops
 * at the first loading state. These mount the real route in jsdom with the API
 * answering in the shapes the backend returns, wait for the page to settle, and
 * assert on what a user would see or on the call the page makes.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { settle } from './settle'

import { RESPONSES, artifact, otherUser, resetApiMocks, testRun, testResult, testStation, user } from './apiFixtures'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const mocked: Record<string, unknown> = { ...actual }
  for (const [groupName, group] of Object.entries(actual)) {
    if (!groupName.endsWith('Api') || typeof group !== 'object' || group === null) continue
    const replacement: Record<string, unknown> = {}
    for (const [method, value] of Object.entries(group)) {
      if (typeof value !== 'function') {
        replacement[method] = value
        continue
      }
      const key = `${groupName}.${method}`
      replacement[method] = vi.fn(async () => {
        if (!(key in RESPONSES)) throw new Error(`no fixture for ${key}`)
        return RESPONSES[key]
      })
    }
    mocked[groupName] = replacement
  }
  mocked.saveBlob = vi.fn()
  return mocked
})

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

const client = await import('../api/client')
const Dashboard = (await import('../pages/Dashboard')).default
const TestRuns = (await import('../pages/TestRuns')).default
const TestRunDetail = (await import('../pages/TestRunDetail')).default
const TestStations = (await import('../pages/TestStations')).default
const Settings = (await import('../pages/Settings')).default
const Users = (await import('../pages/Users')).default

function renderAt(routePath: string, url: string, element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  resetApiMocks(client as unknown as Record<string, unknown>, vi)
  sessionStorage.clear()
  localStorage.clear()
  window.confirm = () => true
  // Settings reports its save with `alert`, which jsdom does not implement.
  window.alert = () => {}
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
})

// Explicit rather than relying on the `globals` setting to register Testing
// Library's own cleanup: without it the previous test's DOM stays mounted and
// every query finds two of everything.
afterEach(cleanup)

/** The arguments of the most recent call to a mocked endpoint. */
function lastCall(fn: unknown): unknown[] {
  const mock = vi.mocked(fn as (...args: unknown[]) => unknown)
  expect(mock.mock.calls.length).toBeGreaterThan(0)
  return mock.mock.calls[mock.mock.calls.length - 1]
}

describe('the dashboard', () => {
  /** The card carrying a given heading, which is where its counters live. */
  function card(title: string): HTMLElement {
    return screen.getByText(title).closest('.bg-card') as HTMLElement
  }

  it('shows the aggregated counters the server returns', async () => {
    renderAt('/', '/', <Dashboard />)

    // The headings render before the counters arrive, so wait for a counter
    // rather than for the card that will hold it. 5 runs at a 60% run pass
    // rate, over 30 tests; the numbers also appear in the outcome donuts now,
    // so each is read off its own card.
    expect(await within(card('Total Test Runs')).findByText('5')).toBeTruthy()
    expect(screen.getAllByText('60%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('30 tests').length).toBeGreaterThan(0)
  })

  it('separates the run pass rate from the test pass rate', async () => {
    renderAt('/', '/', <Dashboard />)

    // A run fails the moment one of its tests does, so the two rates answer
    // different questions and the fixture deliberately disagrees: 60% of runs
    // passed, but 80% of tests did.
    expect(await within(card('Run Pass Rate')).findByText('60%')).toBeTruthy()
    expect(within(card('Test Pass Rate')).getByText('80%')).toBeTruthy()
  })

  it('accounts for the tests that were skipped', async () => {
    renderAt('/', '/', <Dashboard />)

    // Skipped tests are neither passes nor failures, so they are excluded from
    // the rate and have to be reported somewhere or they vanish.
    expect(await screen.findByText(/1 test\(s\) skipped/)).toBeTruthy()
    expect(within(card('Test Outcomes')).getByText('Skipped')).toBeTruthy()
  })

  it('splits both runs and tests by outcome', async () => {
    renderAt('/', '/', <Dashboard />)
    await within(card('Test Outcomes')).findByText('24')

    // Scoped to each donut: the recent-runs list carries status words too.
    const tests = within(card('Test Outcomes'))
    const runs = within(card('Run Outcomes'))
    expect(tests.getByText('Passed')).toBeTruthy()
    expect(tests.getByText('Skipped')).toBeTruthy()
    expect(runs.getByText('Passed')).toBeTruthy()
    expect(runs.getByText('In progress')).toBeTruthy()
  })

  it('re-asks for the counters when the time window changes', async () => {
    renderAt('/', '/', <Dashboard />)
    await screen.findByText('Total Test Runs')

    const windows = screen.getAllByRole('combobox')
    fireEvent.change(windows[0], { target: { value: '7' } })

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.stats) as [{ days?: number }]
      expect(params.days).toBe(7)
    })
  })

  it('downloads a PDF report for the filters on screen', async () => {
    renderAt('/', '/', <Dashboard />)
    await screen.findByText('Total Test Runs')

    fireEvent.click(screen.getByTitle(/download a pdf report/i))

    await waitFor(() => expect(client.reportsApi.testRuns).toHaveBeenCalled())
    await waitFor(() => expect(client.saveBlob).toHaveBeenCalled())
    const [blob, filename] = vi.mocked(client.saveBlob).mock.calls[0]
    expect(blob).toBeInstanceOf(Blob)
    expect(filename).toBe('bud-test-report.pdf')
  })
})

describe('the run list', () => {
  it('lists the runs the server returns', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    expect(await screen.findByText(testRun.name)).toBeTruthy()
  })

  it('links each run to its detail page', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    const link = (await screen.findByText(testRun.name)).closest('a')
    expect(link?.getAttribute('href')).toContain('/runs/42')
  })

  it('sends the search term to the server rather than filtering the page', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)

    fireEvent.change(screen.getByPlaceholderText(/search test runs/i), {
      target: { value: 'nothing matches' },
    })

    // The page holds twenty of however many runs there are. A search it
    // answered itself would be a search of those twenty, and a run on page
    // three would read as "no such run".
    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ q?: string }]
      expect(params.q).toBe('nothing matches')
    })
  })

  it('asks once for a word, not once per letter', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)
    const before = vi.mocked(client.testRunsApi.list).mock.calls.length
    const search = screen.getByPlaceholderText(/search test runs/i)

    for (const value of ['g', 'ga', 'gat', 'gate', 'gatew', 'gateway']) {
      fireEvent.change(search, { target: { value } })
    }

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ q?: string }]
      expect(params.q).toBe('gateway')
    })
    expect(vi.mocked(client.testRunsApi.list).mock.calls.length - before).toBe(1)
  })

  it('asks the server again when a status is chosen', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)

    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])
    fireEvent.click(await screen.findByRole('button', { name: 'Completed' }))

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ status?: string }]
      expect(params.status).toBe('Completed')
    })
  })

  it('asks the server for the Test Station that was picked', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)

    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])
    fireEvent.click(await screen.findByRole('button', { name: testStation.account }))

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ runner_account?: string }]
      expect(params.runner_account).toBe(testStation.account)
    })
  })

  it('shows whatever the server matched, whichever field it matched on', async () => {
    // The endpoint matches the run name, the test case list and the runner
    // account; which of the three hit is its business. What the page owes is
    // to render the answer rather than second-guess it - a page that filtered
    // again locally would drop a row matched on a field it does not display.
    const other = {
      ...testRun,
      id: 43,
      name: 'Powertrain - Smoke',
      test_case_list: 'BootTests',
      runner_account: 'bench-02',
    }
    vi.mocked(client.testRunsApi.list).mockResolvedValue({ runs: [other], total: 1 })
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(other.name)

    fireEvent.change(screen.getByPlaceholderText(/search test runs/i), {
      target: { value: 'boottests' },
    })

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ q?: string }]
      expect(params.q).toBe('boottests')
    })
    // "BootTests" is the test case list, which is not the row's title.
    expect(screen.getByText(other.name)).toBeTruthy()
  })

  /**
   * A location holds as many benches as the lab has - "Lab A" here is two
   * stations, not one. That is what makes the filter a set membership test
   * rather than a lookup, so the fixture has to have it.
   */
  const labA = { ...testStation, account: 'bench-01', location: 'Lab A' }
  const labAsecond = { ...testStation, account: 'bench-03', location: 'Lab A' }
  const labB = { ...testStation, account: 'bench-02', location: 'Lab B' }
  const runAtA1 = { ...testRun, id: 42, runner_account: 'bench-01' }
  const runAtA2 = { ...testRun, id: 44, name: 'Gateway ECU - Rerun', runner_account: 'bench-03' }
  const runAtB = { ...testRun, id: 43, name: 'Powertrain - Smoke', runner_account: 'bench-02' }

  function renderWithTwoLabs() {
    vi.mocked(client.testStationsApi.status).mockResolvedValue({
      runners: [labA, labAsecond, labB],
    })
    vi.mocked(client.testRunsApi.list).mockResolvedValue({
      runs: [runAtA1, runAtA2, runAtB],
      total: 3,
    })
    return renderAt('/runs', '/runs', <TestRuns />)
  }

  it('asks the server for the whole location, not the benches it can see', async () => {
    renderWithTwoLabs()
    await screen.findByText(runAtA1.name)

    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])
    fireEvent.click(await screen.findByRole('button', { name: 'Lab A' }))

    // Lab A holds two benches, and their runs interleave with everyone else's
    // across pages - so resolving the location to bench accounts in the
    // browser and filtering the current page drops whatever sits on the next
    // one. The location goes to the server, which holds every run.
    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ location?: string }]
      expect(params.location).toBe('Lab A')
    })
    expect(screen.getByText('Location: Lab A')).toBeTruthy()
  })

  it('offers each location once however many benches it holds', async () => {
    renderWithTwoLabs()
    await screen.findByText(runAtA1.name)

    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])

    // Two benches at Lab A, one chip.
    expect(await screen.findAllByRole('button', { name: 'Lab A' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Lab B' })).toHaveLength(1)
  })

  it('shows the location the server answered for, and only that one', async () => {
    renderWithTwoLabs()
    await screen.findByText(runAtB.name)

    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])
    vi.mocked(client.testRunsApi.list).mockResolvedValue({ runs: [runAtB], total: 1 })
    fireEvent.click(await screen.findByRole('button', { name: 'Lab B' }))

    await waitFor(() => expect(screen.queryByText(runAtA1.name)).toBeNull())
    expect(screen.queryByText(runAtA2.name)).toBeNull()
    expect(screen.getByText(runAtB.name)).toBeTruthy()
    const [params] = lastCall(client.testRunsApi.list) as [{ location?: string }]
    expect(params.location).toBe('Lab B')
  })

  it('clears every filter at once', async () => {
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)

    fireEvent.change(screen.getByPlaceholderText(/search test runs/i), {
      target: { value: 'nothing matches' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: /^Filters/ })[0])
    fireEvent.click(await screen.findByRole('button', { name: 'Completed' }))
    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ status?: string; q?: string }]
      expect(params.status).toBe('Completed')
      expect(params.q).toBe('nothing matches')
    })

    fireEvent.click(screen.getByRole('button', { name: /clear/i }))

    expect(await screen.findByText(testRun.name)).toBeTruthy()
    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [
        { status?: string; q?: string; location?: string; runner_account?: string },
      ]
      // Cleared means the parameter is dropped, not sent empty.
      expect(params.status).toBeUndefined()
      expect(params.q).toBeUndefined()
      expect(params.location).toBeUndefined()
      expect(params.runner_account).toBeUndefined()
    })
  })

  it('pages forward and back through the runs', async () => {
    vi.mocked(client.testRunsApi.list).mockResolvedValue({ runs: [testRun], total: 45 })
    renderAt('/runs', '/runs', <TestRuns />)
    await screen.findByText(testRun.name)

    // The first page cannot go back.
    expect((screen.getByTitle('Previous page') as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByTitle('Next page'))

    await waitFor(() => {
      const [params] = lastCall(client.testRunsApi.list) as [{ offset?: number }]
      expect(params.offset).toBeGreaterThan(0)
    })
    await waitFor(() =>
      expect((screen.getByTitle('Previous page') as HTMLButtonElement).disabled).toBe(false),
    )
  })

  it('says so when the run list cannot be loaded', async () => {
    vi.mocked(client.testRunsApi.list).mockRejectedValue(new Error('backend unreachable'))
    renderAt('/runs', '/runs', <TestRuns />)

    await waitFor(() => expect(document.body.textContent).toMatch(/error|failed|unable/i))
    expect(screen.queryByText(testRun.name)).toBeNull()
  })
})

describe('a run in detail', () => {
  it('groups results by test class, the level the run counters use', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)

    expect(await screen.findByText(testRun.name)).toBeTruthy()
    // Two methods of one class: one passed, one failed.
    expect(screen.getAllByText(testResult.test_class).length).toBeGreaterThan(0)
    expect(screen.getByText('1 / 2 passed')).toBeTruthy()
    expect(screen.getAllByText('1 failed').length).toBeGreaterThan(0)
  })

  it('asks for the run named in the URL', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)
    expect(lastCall(client.testRunsApi.get)[0]).toBe(42)
    expect(lastCall(client.resultsApi.list)[0]).toBe(42)
  })

  it('shows the run header counters the backend aggregated', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    // 3 tests, 2 passed, 1 failed, and the run's own status.
    expect(screen.getAllByText('3').length).toBeGreaterThan(0)
    expect(screen.getAllByText(testRun.status).length).toBeGreaterThan(0)
    expect(screen.getAllByText(testRun.runner_account as string).length).toBeGreaterThan(0)
  })

  it('downloads a PDF for this run alone', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    fireEvent.click(screen.getByTitle(/download this run as a pdf/i))

    await waitFor(() => expect(client.reportsApi.testRun).toHaveBeenCalledWith(42))
    await waitFor(() => expect(client.saveBlob).toHaveBeenCalled())
    expect(vi.mocked(client.saveBlob).mock.calls[0][1]).toBe('bud-run-42.pdf')
  })

  it('says why the report could not be generated', async () => {
    vi.mocked(client.reportsApi.testRun).mockRejectedValueOnce(
      Object.assign(new Error('Request failed'), {
        isAxiosError: true,
        response: { data: { detail: 'This run has no results to report on' } },
      }),
    )
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    fireEvent.click(screen.getByTitle(/download this run as a pdf/i))

    expect(await screen.findByText(/no results to report on/i)).toBeTruthy()
    expect(client.saveBlob).not.toHaveBeenCalled()
    // The button comes back rather than staying stuck on "Preparing…".
    await waitFor(() =>
      expect((screen.getByTitle(/download this run as a pdf/i) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    )
  })

  it('hides passing test cases when the results are filtered to failures', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)
    // Both methods belong to one class, and that class contains a failure.
    expect(screen.getAllByText(testResult.test_class).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /^Filters/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Passed' }))

    // Nothing here passed outright, so filtering to passes empties the table.
    await waitFor(() => expect(screen.queryByText(testResult.test_class)).toBeNull())
  })

  it('clears the outcome filters again', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    fireEvent.click(screen.getByRole('button', { name: /^Filters/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Passed' }))
    await waitFor(() => expect(screen.queryByText(testResult.test_class)).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: /clear/i }))

    expect(await screen.findByText(testResult.test_class)).toBeTruthy()
  })

  it('opens the system report to show the events of the run', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)
    expect(screen.getByText('1 reported step')).toBeTruthy()
    expect(screen.queryByText('Results uploaded')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /system report/i }))

    expect(await screen.findByText('Results uploaded')).toBeTruthy()
  })

  it('lists what the run left behind', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    // An artifact used to be reachable only by someone who already knew its
    // integer id: it could be uploaded and downloaded, but never enumerated.
    expect(await screen.findByText(artifact.original_filename)).toBeTruthy()
    expect(lastCall(client.testRunsApi.getArtifacts)[0]).toBe(42)
  })

  it('says how large each artifact is, in units a reader uses', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(artifact.original_filename)

    // 4,718,592 bytes. Printing the byte count would be honest and useless.
    expect(screen.getByText(/4\.5 MB/)).toBeTruthy()
  })

  it('names the test case an artifact belongs to', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(artifact.original_filename)

    expect(screen.getByText(new RegExp(artifact.test_case))).toBeTruthy()
  })

  it('downloads through the API client, not a bare link', async () => {
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(artifact.original_filename)

    fireEvent.click(screen.getByRole('button', { name: /download/i }))

    // The endpoint is authenticated. An <a href> would arrive without a token
    // and redirect the reader to the login screen.
    await waitFor(() =>
      expect(lastCall(client.artifactsApi.download)[0]).toBe(artifact.id),
    )
    await waitFor(() => expect(vi.mocked(client.saveBlob)).toHaveBeenCalled())
  })

  it('says so when a download fails rather than doing nothing', async () => {
    vi.mocked(client.artifactsApi.download).mockRejectedValue(new Error('File not found on disk'))
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(artifact.original_filename)

    fireEvent.click(screen.getByRole('button', { name: /download/i }))

    // The retention sweep can remove the file while the page still lists it,
    // so a failed download is an ordinary outcome and has to be visible.
    expect(await screen.findByText(/File not found on disk/)).toBeTruthy()
  })

  it('says a run has no artifacts rather than showing an empty panel', async () => {
    vi.mocked(client.testRunsApi.getArtifacts).mockResolvedValue([])
    renderAt('/runs/:id', '/runs/42', <TestRunDetail />)
    await screen.findByText(testRun.name)

    expect(await screen.findByText(/no artifacts uploaded for this run/i)).toBeTruthy()
  })
})

describe('the Test Stations screen', () => {
  it('lists each station and whether it is online', async () => {
    renderAt('/test-stations', '/test-stations', <TestStations />)

    expect(await screen.findByText(testStation.account)).toBeTruthy()
    expect(screen.getAllByText(/online/i).length).toBeGreaterThan(0)
  })
})

describe('settings', () => {
  it('shows the configured Bloom URL', async () => {
    renderAt('/settings', '/settings', <Settings />)
    expect(await screen.findByDisplayValue('https://bloom.example.com')).toBeTruthy()
  })

  it('clears the Bloom credential after confirming', async () => {
    renderAt('/settings', '/settings', <Settings />)
    await screen.findByDisplayValue('https://bloom.example.com')

    fireEvent.click(screen.getByRole('button', { name: /clear credential/i }))

    await waitFor(() =>
      expect(lastCall(client.settingsApi.updateALM)[0]).toMatchObject({
        clear_bloom_token: true,
      }),
    )
  })

  it('keeps the Bloom credential when clearing is declined', async () => {
    window.confirm = () => false
    renderAt('/settings', '/settings', <Settings />)
    await screen.findByDisplayValue('https://bloom.example.com')

    fireEvent.click(screen.getByRole('button', { name: /clear credential/i }))

    // Losing the credential silently would stop every result sync from Bud.
    await settle()
    expect(client.settingsApi.updateALM).not.toHaveBeenCalled()
  })

  it('saves a new Bloom URL', async () => {
    renderAt('/settings', '/settings', <Settings />)
    const field = await screen.findByDisplayValue('https://bloom.example.com')

    fireEvent.change(field, { target: { value: 'https://plm.example.com' } })
    fireEvent.click(screen.getAllByRole('button', { name: /save/i })[0])

    await waitFor(() => {
      const [payload] = lastCall(client.settingsApi.updateALM) as [{ bloom_url: string }]
      expect(payload.bloom_url).toBe('https://plm.example.com')
    })
  })
})

describe('users', () => {
  it('lists the accounts', async () => {
    renderAt('/users', '/users', <Users />)
    expect(await screen.findByText(user.full_name)).toBeTruthy()
  })

  it('sends an invitation', async () => {
    renderAt('/users', '/users', <Users />)
    await screen.findByText(user.full_name)

    fireEvent.click(screen.getByRole('button', { name: /invite/i }))
    const dialog = await screen.findByRole('button', { name: /send invite/i })
    fireEvent.change(screen.getByTitle('Full name'), { target: { value: 'Grace Hopper' } })
    fireEvent.change(screen.getByTitle('Email address'), {
      target: { value: 'grace@example.com' },
    })
    fireEvent.click(dialog)

    await waitFor(() => {
      const [payload] = lastCall(client.usersApi.invite) as [
        { email: string; full_name: string },
      ]
      expect(payload).toMatchObject({ email: 'grace@example.com', full_name: 'Grace Hopper' })
    })
  })

  it('deletes another account after confirming', async () => {
    renderAt('/users', '/users', <Users />)
    const row = (await screen.findByText(otherUser.full_name)).closest('tr')
    expect(row).toBeTruthy()

    fireEvent.click(within(row as HTMLElement).getByTitle('Delete user'))

    // react-query hands the mutation a context object alongside the id.
    await waitFor(() => expect(client.usersApi.delete).toHaveBeenCalled())
    expect(vi.mocked(client.usersApi.delete).mock.calls[0][0]).toBe(otherUser.id)
  })

  it('does nothing when the deletion is declined', async () => {
    window.confirm = () => false
    renderAt('/users', '/users', <Users />)
    const row = (await screen.findByText(otherUser.full_name)).closest('tr')

    fireEvent.click(within(row as HTMLElement).getByTitle('Delete user'))

    // The mutation is not called synchronously, so a bare assertion here would
    // pass whether the confirmation was honoured or not.
    await settle()
    expect(client.usersApi.delete).not.toHaveBeenCalled()
  })

  it('does not offer to delete the account you are signed in as', async () => {
    renderAt('/users', '/users', <Users />)
    const ownRow = (await screen.findByText(user.full_name)).closest('tr')
    expect(within(ownRow as HTMLElement).queryByTitle('Delete user')).toBeNull()
  })

  it('shows the invitation link the server hands back', async () => {
    vi.mocked(client.usersApi.invite).mockResolvedValueOnce({
      message: 'Invitation sent',
      user: otherUser,
      invite_link: 'https://bud.example.com/accept-invite#token=abc',
    } as Awaited<ReturnType<typeof client.usersApi.invite>>)
    renderAt('/users', '/users', <Users />)
    await screen.findByText(user.full_name)

    fireEvent.click(screen.getByRole('button', { name: /invite/i }))
    fireEvent.change(await screen.findByTitle('Full name'), { target: { value: 'Grace Hopper' } })
    fireEvent.change(screen.getByTitle('Email address'), {
      target: { value: 'grace@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send invite/i }))

    const field = (await screen.findByTitle(
      'Generated invitation link',
    )) as HTMLInputElement
    // The token belongs in the fragment, so it stays out of server logs.
    expect(field.value).toContain('#token=')
    expect(field.readOnly).toBe(true)
  })

  it('reports why an invitation was refused', async () => {
    vi.mocked(client.usersApi.invite).mockRejectedValueOnce(
      Object.assign(new Error('Request failed'), {
        isAxiosError: true,
        response: { data: { detail: 'Email is already registered' } },
      }),
    )
    renderAt('/users', '/users', <Users />)
    await screen.findByText(user.full_name)

    fireEvent.click(screen.getByRole('button', { name: /invite/i }))
    fireEvent.change(await screen.findByTitle('Full name'), { target: { value: 'Grace Hopper' } })
    fireEvent.change(screen.getByTitle('Email address'), {
      target: { value: 'ada@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send invite/i }))

    expect(await screen.findByText(/already registered/i)).toBeTruthy()
  })

  it('deactivates an account without deleting it', async () => {
    renderAt('/users', '/users', <Users />)
    const row = (await screen.findByText(otherUser.full_name)).closest('tr')

    fireEvent.click(within(row as HTMLElement).getByTitle('Deactivate'))

    await waitFor(() => expect(client.usersApi.update).toHaveBeenCalled())
    const [id, data] = vi.mocked(client.usersApi.update).mock.calls[0]
    expect(id).toBe(otherUser.id)
    expect(data).toEqual({ is_active: false })
    expect(client.usersApi.delete).not.toHaveBeenCalled()
  })

  it('starts an administrator-driven email change through the confirmed flow', async () => {
    renderAt('/users', '/users', <Users />)
    const row = (await screen.findByText(otherUser.full_name)).closest('tr')

    fireEvent.click(within(row as HTMLElement).getByTitle('Change email'))
    fireEvent.change(await screen.findByLabelText('New email'), {
      target: { value: 'grace.hopper@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send confirmation email/i }))

    await waitFor(() => expect(client.usersApi.startEmailChange).toHaveBeenCalled())
    const [id, email] = vi.mocked(client.usersApi.startEmailChange).mock.calls[0]
    expect(id).toBe(otherUser.id)
    expect(email).toBe('grace.hopper@example.com')
  })
})
