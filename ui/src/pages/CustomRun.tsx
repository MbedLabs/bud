import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle,
  ListChecks,
  PlayCircle,
  Search,
  Server,
  XCircle,
} from 'lucide-react'

import {
  catalogApi,
  customRunsApi,
  extractApiErrorMessage,
  testStationsApi,
  type CatalogEntry,
  type CustomRunResult,
} from '../api/client'
import { useDebounced } from '../hooks/useDebounced'
import { formatDateTime } from '../test/date-utils'

/**
 * Build a run from test cases Bud has already seen.
 *
 * Two things about this screen are load-bearing and easy to get wrong:
 *
 * A test case can only be queued where it has already run - Bud never reads a
 * bench's workspace, so that is the only thing it honestly knows. Every row
 * therefore names its bench, and a selection touching two benches becomes two
 * queued runs. That is said before the reader commits, not after.
 *
 * And a queued run is not a started run. The bench polls Bud and picks it up on
 * its own schedule, so the confirmation says "queued", never "running".
 */
export default function CustomRun() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [name, setName] = useState('')
  const [pinned, setPinned] = useState('')
  const [result, setResult] = useState<CustomRunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const debouncedSearch = useDebounced(search, 250)

  const { data: catalog, isLoading } = useQuery({
    queryKey: ['testCatalog', pinned],
    queryFn: () => catalogApi.list(pinned ? { runner_account: pinned } : undefined),
    // Narrowing to a station is a filter, not a new page: blanking the list
    // while the narrowed one arrives loses the reader's place for no reason.
    placeholderData: (previous) => previous,
  })

  const { data: stationsData } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    staleTime: 30_000,
  })
  const stations = useMemo(() => stationsData?.runners ?? [], [stationsData?.runners])

  const entries = useMemo(() => catalog?.entries ?? [], [catalog])

  // The catalogue is one page of everything Bud knows and is not paged, so this
  // filter runs over the whole set rather than a slice of it.
  const visible = useMemo(() => {
    if (!debouncedSearch.trim()) return entries
    const needle = debouncedSearch.toLowerCase()
    return entries.filter((entry) =>
      [entry.test_path, entry.test_class, entry.suite, ...entry.runner_accounts]
        .join(' ')
        .toLowerCase()
        .includes(needle),
    )
  }, [entries, debouncedSearch])

  const bySuite = useMemo(() => {
    const groups = new Map<string, CatalogEntry[]>()
    for (const entry of visible) {
      const group = groups.get(entry.suite) ?? []
      group.push(entry)
      groups.set(entry.suite, group)
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [visible])

  const selectedEntries = useMemo(
    () => entries.filter((entry) => selected.includes(entry.test_path)),
    [entries, selected],
  )

  /**
   * The benches this selection would reach, so the split is visible before the
   * reader commits rather than arriving as a surprise in the response.
   *
   * A case that has run on several benches is not counted as forcing one: the
   * server places those alongside whatever had no choice, and claiming they
   * force a split here would show a warning that never comes true.
   */
  const benchesInvolved = useMemo(() => {
    if (pinned) return [pinned]
    const forced = new Set<string>()
    for (const entry of selectedEntries) {
      if (entry.runner_accounts.length === 1) forced.add(entry.runner_accounts[0])
    }
    return Array.from(forced).sort()
  }, [selectedEntries, pinned])

  const methodTotal = selectedEntries.reduce((sum, entry) => sum + entry.method_count, 0)

  const toggle = (testPath: string) => {
    setResult(null)
    setSelected((current) =>
      current.includes(testPath)
        ? current.filter((path) => path !== testPath)
        : [...current, testPath],
    )
  }

  const queueRun = useMutation({
    mutationFn: () =>
      customRunsApi.create({
        test_paths: selected,
        name: name.trim() || undefined,
        runner_account: pinned || undefined,
      }),
    onSuccess: (data) => {
      setResult(data)
      setError(null)
      setSelected([])
      setName('')
      queryClient.invalidateQueries({ queryKey: ['testRuns'] })
    },
    onError: (failure) => {
      setResult(null)
      setError(extractApiErrorMessage(failure, 'Could not queue the run'))
    },
  })

  return (
    <div className="space-y-5 animate-fade-in">
      <section className="bg-card rounded-lg border border-border shadow-elegant">
        <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-[minmax(220px,1fr)_200px_220px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search test cases, suites, stations..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full rounded-md border border-input bg-background py-1.5 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label htmlFor="custom-run-station" className="sr-only">
              Test Station
            </label>
            <select
              id="custom-run-station"
              value={pinned}
              onChange={(event) => {
                setPinned(event.target.value)
                setSelected([])
                setResult(null)
              }}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            >
              <option value="">Any Test Station</option>
              {stations.map((station) => (
                <option key={station.account} value={station.account}>
                  {station.account}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="custom-run-name" className="sr-only">
              Run name
            </label>
            <input
              id="custom-run-name"
              type="text"
              placeholder="Run name (optional)"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
            />
          </div>
        </div>
      </section>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
          {error}
        </p>
      )}

      {result && <QueuedSummary result={result} />}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        <section className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
          <div className="flex items-center gap-2 border-b border-border px-5 py-4">
            <ListChecks className="h-4 w-4 shrink-0 text-primary" />
            <div>
              <h3 className="text-sm font-semibold text-foreground">Test cases Bud knows</h3>
              <p className="text-xs text-muted-foreground">
                {isLoading
                  ? 'Loading the catalogue...'
                  : `${visible.length} of ${entries.length} test case${entries.length === 1 ? '' : 's'}`}
              </p>
            </div>
          </div>

          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">Loading the catalogue...</div>
          ) : entries.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <p>No test cases yet.</p>
              <p className="mt-1 text-xs">
                A test case appears here once it has run at least once and reported the file it
                came from — Bud does not read a station&rsquo;s workspace.
              </p>
            </div>
          ) : visible.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No test cases match that search
            </div>
          ) : (
            <div className="divide-y divide-border">
              {bySuite.map(([suite, group]) => (
                <div key={suite}>
                  <p className="bg-muted/40 px-5 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {suite}
                  </p>
                  <ul className="divide-y divide-border">
                    {group.map((entry) => (
                      <li key={entry.test_path}>
                        <label className="flex cursor-pointer items-center gap-3 px-5 py-3 hover:bg-accent/40">
                          <input
                            type="checkbox"
                            checked={selected.includes(entry.test_path)}
                            onChange={() => toggle(entry.test_path)}
                            className="h-4 w-4 shrink-0 rounded border-input"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-foreground">
                              {entry.test_class}
                            </span>
                            <span className="block truncate font-mono text-xs text-muted-foreground">
                              {entry.test_path}
                            </span>
                          </span>
                          <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">
                            {entry.method_count} method{entry.method_count === 1 ? '' : 's'}
                          </span>
                          <span className="flex shrink-0 items-center gap-1.5">
                            {entry.last_passed === null ? null : entry.last_passed ? (
                              <CheckCircle
                                className="h-3.5 w-3.5 text-emerald-600"
                                aria-label="Passed when last run"
                              />
                            ) : (
                              <XCircle
                                className="h-3.5 w-3.5 text-red-600"
                                aria-label="Failed when last run"
                              />
                            )}
                            <span className="hidden text-xs text-muted-foreground md:inline">
                              {entry.last_run_at ? formatDateTime(entry.last_run_at) : '—'}
                            </span>
                          </span>
                          <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                            <Server className="h-3.5 w-3.5" aria-hidden="true" />
                            {entry.runner_accounts.join(', ') || 'unassigned'}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="bg-card h-fit rounded-lg border border-border shadow-elegant">
          <div className="border-b border-border px-5 py-4">
            <h3 className="text-sm font-semibold text-foreground">Selection</h3>
            <p className="text-xs text-muted-foreground">
              {selected.length} test case{selected.length === 1 ? '' : 's'}
              {selected.length > 0 && `, ${methodTotal} method${methodTotal === 1 ? '' : 's'}`}
            </p>
          </div>

          <div className="space-y-3 px-5 py-4">
            {selected.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Pick the test cases to run. They can only be queued on a station that has run them
                before.
              </p>
            ) : (
              <>
                <ul className="max-h-48 space-y-1 overflow-y-auto themed-scrollbar">
                  {selectedEntries.map((entry) => (
                    <li key={entry.test_path} className="truncate font-mono text-xs text-foreground">
                      {entry.test_path}
                    </li>
                  ))}
                </ul>

                {benchesInvolved.length > 1 && (
                  <p className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      These test cases live on different stations, so this will queue{' '}
                      {benchesInvolved.length} separate runs — one each for{' '}
                      {benchesInvolved.join(' and ')}.
                    </span>
                  </p>
                )}
              </>
            )}

            <button
              type="button"
              onClick={() => queueRun.mutate()}
              disabled={selected.length === 0 || queueRun.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <PlayCircle className="h-4 w-4" />
              {queueRun.isPending ? 'Queueing…' : 'Queue run'}
            </button>

            <p className="text-xs text-muted-foreground">
              The station picks the run up the next time it checks in, so this queues the work
              rather than starting it.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

/** What was queued, and what could not be — both, always. */
function QueuedSummary({ result }: { result: CustomRunResult }) {
  return (
    <section className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <h3 className="text-sm font-semibold text-foreground">
          {result.runs.length} run{result.runs.length === 1 ? '' : 's'} queued
        </h3>
        <p className="text-xs text-muted-foreground">
          Waiting for the station to check in.
        </p>
      </div>
      <ul className="divide-y divide-border">
        {result.runs.map((run) => (
          <li key={run.id} className="flex items-center gap-3 px-5 py-3">
            <Server className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <Link
                to={`/runs/${run.id}`}
                className="truncate text-sm font-medium text-primary hover:text-primary/80"
              >
                {run.name}
              </Link>
              <p className="text-xs text-muted-foreground">
                {run.runner_account} &middot; {run.selected_tests?.length ?? 0} test case
                {run.selected_tests?.length === 1 ? '' : 's'}
              </p>
            </div>
            <span className="shrink-0 rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
              {run.status}
            </span>
          </li>
        ))}
      </ul>

      {result.unassigned.length > 0 && (
        <div className="border-t border-border px-5 py-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-3.5 w-3.5" />
            Not queued
          </p>
          <ul className="space-y-1">
            {result.unassigned.map((item) => (
              <li key={item.test_path} className="text-xs text-muted-foreground">
                <span className="font-mono text-foreground">{item.test_path}</span> — {item.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
