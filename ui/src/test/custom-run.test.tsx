// @vitest-environment jsdom
/**
 * Building a custom run.
 *
 * Two things on this screen have to be true or the feature misleads rather than
 * helps. A test case can only be queued on a station that has already run it,
 * so every row names its station and a selection touching two of them has to
 * say so *before* the reader commits. And queueing is not starting - the station
 * picks the run up when it next checks in - so nothing here may claim a run is
 * under way.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RESPONSES, catalogEntries, resetApiMocks, testRun, user } from './apiFixtures'

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
const CustomRun = (await import('../pages/CustomRun')).default

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CustomRun />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** The checkbox for a test case, found by the row that names it. */
function checkbox(testClass: string): HTMLInputElement {
  const row = screen.getByText(testClass).closest('label') as HTMLElement
  return within(row).getByRole('checkbox') as HTMLInputElement
}

function pick(testClass: string) {
  fireEvent.click(checkbox(testClass))
}

const queueButton = () => screen.getByRole('button', { name: /queue run/i })

beforeEach(() => {
  vi.clearAllMocks()
  resetApiMocks(client as unknown as Record<string, unknown>, vi)
})

afterEach(cleanup)

describe('choosing what to run', () => {
  it('lists what Bud knows, grouped by suite', async () => {
    renderScreen()

    expect(await screen.findByText('VoltageTest')).toBeTruthy()
    expect(screen.getByText('ThermalTest')).toBeTruthy()
    expect(screen.getByText('Nightly')).toBeTruthy()
    expect(screen.getByText('Powertrain')).toBeTruthy()
  })

  it('shows the importable path, not the file the bench reported', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    // An absolute path on the bench means nothing off that machine; this is the
    // form the station's loader actually resolves.
    expect(screen.getByText('BigPack_voltage.VoltageTest')).toBeTruthy()
  })

  it('names the stations each test case has run on', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    // Which station a case can run on is the whole constraint, so it cannot be
    // something the reader has to go and look up. Scoped to each row: the
    // station picker lists the same names.
    const voltage = screen.getByText('VoltageTest').closest('label') as HTMLElement
    const boot = screen.getByText('BootTest').closest('label') as HTMLElement
    expect(within(voltage).getByText('bench-01')).toBeTruthy()
    expect(within(boot).getByText('bench-01, bench-02')).toBeTruthy()
  })

  it('says how many methods a case carries', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    expect(screen.getByText('2 methods')).toBeTruthy()
    expect(screen.getAllByText('1 method').length).toBeGreaterThan(0)
  })

  it('counts the selection in cases and in methods', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    pick('VoltageTest')

    // Two numbers because they answer different questions: how much was picked,
    // and how much will actually execute.
    expect(await screen.findByText(/1 test case, 2 methods/)).toBeTruthy()
  })

  it('searches the catalogue without asking the server again', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    const before = vi.mocked(client.catalogApi.list).mock.calls.length

    fireEvent.change(screen.getByPlaceholderText(/search test cases/i), {
      target: { value: 'thermal' },
    })

    await waitFor(() => expect(screen.queryByText('VoltageTest')).toBeNull())
    expect(screen.getByText('ThermalTest')).toBeTruthy()
    // The catalogue arrives whole and is not paged, so this filter sees all of
    // it - unlike the run list, where searching locally would be a bug.
    expect(vi.mocked(client.catalogApi.list).mock.calls.length).toBe(before)
  })

  it('will not queue nothing', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    expect(queueButton().hasAttribute('disabled')).toBe(true)
  })
})

describe('warning before the selection splits', () => {
  it('says nothing when everything lives on one station', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    pick('VoltageTest')

    expect(screen.queryByText(/separate runs/i)).toBeNull()
  })

  it('does not warn for a case that could run on either station', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    pick('VoltageTest')
    pick('BootTest')

    // Boot runs on both benches, so the server places it alongside Voltage on
    // bench-01. Warning here would show a split that never happens.
    await waitFor(() => expect(screen.getByText(/2 test cases/)).toBeTruthy())
    expect(screen.queryByText(/separate runs/i)).toBeNull()
  })

  it('warns, and names the stations, when the split is real', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    pick('VoltageTest')
    pick('ThermalTest')

    // Voltage has only run on bench-01 and Thermal only on bench-02, so neither
    // can move. The reader is told before committing, not after.
    const warning = await screen.findByText(/2 separate runs/i)
    expect(warning.textContent).toContain('bench-01')
    expect(warning.textContent).toContain('bench-02')
  })
})

describe('queueing', () => {
  it('sends the selection', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())

    await waitFor(() =>
      expect(vi.mocked(client.customRunsApi.create).mock.calls[0][0]).toMatchObject({
        test_paths: ['BigPack_voltage.VoltageTest'],
      }),
    )
  })

  it('pins the run to a station when one is chosen', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    fireEvent.change(screen.getByLabelText(/test station/i), { target: { value: 'bench-01' } })
    await waitFor(() =>
      expect(vi.mocked(client.catalogApi.list).mock.calls.slice(-1)[0]?.[0]).toEqual({
        runner_account: 'bench-01',
      }),
    )

    // The narrowed list replaces the old one in place rather than blanking.
    await screen.findByText('VoltageTest')
    pick('VoltageTest')
    fireEvent.click(queueButton())

    await waitFor(() =>
      expect(vi.mocked(client.customRunsApi.create).mock.calls[0][0]).toMatchObject({
        runner_account: 'bench-01',
      }),
    )
  })

  it('carries an optional name', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.change(screen.getByPlaceholderText(/run name/i), {
      target: { value: 'Ad-hoc regression' },
    })
    fireEvent.click(queueButton())

    await waitFor(() =>
      expect(vi.mocked(client.customRunsApi.create).mock.calls[0][0]).toMatchObject({
        name: 'Ad-hoc regression',
      }),
    )
  })

  it('reports the run as queued, not as running', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())

    // The station picks it up on its own schedule. Saying "started" would be a
    // claim Bud cannot make.
    expect(await screen.findByText(/1 run queued/i)).toBeTruthy()
    expect(screen.getByText(/waiting for the station to check in/i)).toBeTruthy()
  })

  it('links each queued run to its page', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())

    const link = (await screen.findByText('Custom run - Nightly')).closest('a')
    expect(link?.getAttribute('href')).toContain('/runs/90')
  })

  it('shows what could not be queued, and why', async () => {
    vi.mocked(client.customRunsApi.create).mockResolvedValue({
      runs: [{ ...testRun, id: 91, status: 'Pending', selected_tests: ['a.B'] }],
      unassigned: [
        { test_path: 'thermal.ThermalTest', reason: 'Has not run on bench-01.' },
      ],
    } as never)
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())

    // A partial success that only reported the successful half would leave the
    // reader believing they queued something they did not.
    expect(await screen.findByText('Not queued')).toBeTruthy()
    expect(screen.getByText(/Has not run on bench-01/)).toBeTruthy()
  })

  it('clears the selection once it is queued', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())
    await screen.findByText(/1 run queued/i)

    // Otherwise the next click queues the same tests a second time.
    expect(checkbox('VoltageTest').checked).toBe(false)
    expect(queueButton().hasAttribute('disabled')).toBe(true)
  })

  it('says why a refusal happened rather than doing nothing', async () => {
    vi.mocked(client.customRunsApi.create).mockRejectedValue(
      Object.assign(new Error('Request failed'), {
        isAxiosError: true,
        response: { data: { detail: 'None of the selected test cases can be run' } },
      }),
    )
    renderScreen()
    await screen.findByText('VoltageTest')
    pick('VoltageTest')

    fireEvent.click(queueButton())

    expect(await screen.findByText(/None of the selected test cases can be run/)).toBeTruthy()
  })
})

describe('an empty catalogue', () => {
  it('explains why it is empty instead of looking broken', async () => {
    vi.mocked(client.catalogApi.list).mockResolvedValue({ entries: [], total: 0 } as never)
    renderScreen()

    // "No test cases" with no reason reads as a bug. The reason is that Bud
    // learns test cases from runs, and has not seen one yet.
    expect(await screen.findByText(/no test cases yet/i)).toBeTruthy()
    expect(screen.getByText(/does not read a station/i)).toBeTruthy()
  })

  it('still lists a catalogue that a search empties, differently', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    fireEvent.change(screen.getByPlaceholderText(/search test cases/i), {
      target: { value: 'no-such-test' },
    })

    expect(await screen.findByText(/no test cases match that search/i)).toBeTruthy()
    expect(screen.queryByText(/no test cases yet/i)).toBeNull()
  })
})

describe('the catalogue rows', () => {
  it('marks how each case last finished', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    // Picking a case that has been failing is a decision the reader should be
    // able to make from this screen.
    const voltage = screen.getByText('VoltageTest').closest('label') as HTMLElement
    const boot = screen.getByText('BootTest').closest('label') as HTMLElement
    expect(within(voltage).getByLabelText(/passed when last run/i)).toBeTruthy()
    expect(within(boot).getByLabelText(/failed when last run/i)).toBeTruthy()
  })

  it('agrees with the fixture on how many cases there are', async () => {
    renderScreen()
    await screen.findByText('VoltageTest')

    expect(
      screen.getByText(new RegExp(`${catalogEntries.length} of ${catalogEntries.length} test case`)),
    ).toBeTruthy()
  })
})
