import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { testRunsApi, testStationsApi, type TestRun } from '../api/client'
import { formatDateTime } from '../test/date-utils'
import { Search, Filter, ChevronLeft, ChevronRight, PlayCircle, Server, X } from 'lucide-react'

const EMPTY_TEST_RUNS: TestRun[] = []

const STATUS_OPTIONS = ['Pending', 'Running', 'Completed', 'Cancelled'] as const

export default function TestRuns() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [stationFilter, setStationFilter] = useState<string>(searchParams.get('station') || '')
  const [locationFilter, setLocationFilter] = useState<string>(searchParams.get('location') || '')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const limit = 20

  const hasActiveFilters = Boolean(statusFilter || stationFilter || locationFilter || search)

  const { data, isLoading, error } = useQuery({
    queryKey: ['testRuns', { page, limit, status: statusFilter, station: stationFilter }],
    queryFn: () =>
      testRunsApi.list({
        offset: (page - 1) * limit,
        limit,
        latest_per_suite: true,
        status: statusFilter || undefined,
        runner_account: stationFilter || undefined,
      }),
  })

  const { data: stationsData } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    staleTime: 30_000,
  })
  const stations = useMemo(() => stationsData?.runners ?? [], [stationsData?.runners])
  const locationOptions = useMemo(() => {
    const locations = new Set<string>()
    for (const station of stations) {
      if (station.location) {
        locations.add(station.location)
      }
    }
    return Array.from(locations).sort((a, b) => a.localeCompare(b))
  }, [stations])

  const runs = data?.runs ?? EMPTY_TEST_RUNS
  const total = data?.total || 0
  const totalPages = Math.ceil(total / limit)

  const filteredRuns = useMemo(() => {
    let result = runs
    if (locationFilter) {
      const accountsAtLocation = new Set(
        stations
          .filter((station) => station.location === locationFilter)
          .map((station) => station.account)
      )
      result = result.filter((run) => run.runner_account && accountsAtLocation.has(run.runner_account))
    }
    if (!search) return result
    const q = search.toLowerCase()
    return result.filter(run =>
      run.name.toLowerCase().includes(q) ||
      run.test_case_list.toLowerCase().includes(q) ||
      (run.runner_account && run.runner_account.toLowerCase().includes(q))
    )
  }, [runs, search, locationFilter, stations])

  const clearFilters = () => {
    setSearch('')
    setStatusFilter('')
    setStationFilter('')
    setLocationFilter('')
    setPage(1)
    setSearchParams(prev => {
      prev.delete('station')
      prev.delete('location')
      return prev
    }, { replace: true })
  }

  const setStation = (v: string) => {
    setStationFilter(v)
    setPage(1)
    setSearchParams(prev => {
      if (v) prev.set('station', v)
      else prev.delete('station')
      return prev
    }, { replace: true })
  }

  const setLocation = (v: string) => {
    setLocationFilter(v)
    setPage(1)
    setSearchParams(prev => {
      if (v) prev.set('location', v)
      else prev.delete('location')
      return prev
    }, { replace: true })
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <section className="bg-card rounded-lg border border-border shadow-elegant">
        <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search test runs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
            />
          </div>
          <button
            type="button"
            onClick={() => setFiltersOpen((o) => !o)}
            className={`inline-flex items-center justify-center gap-2 rounded-md border px-2.5 py-1.5 text-sm font-medium transition-colors ${
              filtersOpen || hasActiveFilters
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-input bg-background text-foreground hover:bg-accent'
            }`}
            aria-expanded={filtersOpen}
            aria-controls="testruns-filter-panel"
          >
            <Filter className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">On</span>
            )}
          </button>
        </div>

        {filtersOpen && (
          <div id="testruns-filter-panel" className="space-y-3 border-t border-border p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Filter className="h-4 w-4 text-primary" />
              Filters
            </div>

            <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase text-muted-foreground">Status</div>
                <div className="flex flex-wrap gap-2">
                  {STATUS_OPTIONS.map((status) => (
                    <button
                      key={status}
                      onClick={() => { setStatusFilter(statusFilter === status ? '' : status); setPage(1) }}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        statusFilter === status
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border bg-background text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-xs font-medium uppercase text-muted-foreground">Test Station</div>
                <div className="flex flex-wrap gap-2">
                  {stations.map((station) => (
                    <button
                      key={station.account}
                      type="button"
                      onClick={() => setStation(stationFilter === station.account ? '' : station.account)}
                      className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        stationFilter === station.account
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border bg-background text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {station.account}
                    </button>
                  ))}
                </div>
              </div>
              {locationOptions.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase text-muted-foreground">Location</div>
                  <div className="flex flex-wrap gap-2">
                    {locationOptions.map((location) => (
                      <button
                        key={location}
                        type="button"
                        onClick={() => setLocation(locationFilter === location ? '' : location)}
                        className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                          locationFilter === location
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border bg-background text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {location}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2">
              {search && <FilterChip label={`Search: ${search}`} />}
              {statusFilter && <FilterChip label={`Status: ${statusFilter}`} />}
              {stationFilter && <FilterChip label={`Station: ${stationFilter}`} />}
              {locationFilter && <FilterChip label={`Location: ${locationFilter}`} />}
              {hasActiveFilters && (
                <button onClick={clearFilters} className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
                  <X className="h-3.5 w-3.5" />
                  Clear all
                </button>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Table */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : error ? (
          <div className="p-8 text-center text-destructive">Error loading test runs</div>
        ) : filteredRuns.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
              <PlayCircle className="h-8 w-8 text-muted-foreground/50" />
            </div>
            <p className="text-sm text-muted-foreground">
              {hasActiveFilters ? 'No test runs match the current filters' : 'No test runs found'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead>
              <tr className="bg-muted/50">
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Name
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Results
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Test Station
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Started At
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Completed At
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredRuns.map((run) => (
                <tr key={run.id} className="hover:bg-accent/50 transition-colors group">
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <Link
                      to={`/runs/${run.id}`}
                      className="text-sm font-medium text-foreground group-hover:text-primary transition-colors"
                    >
                      {run.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs">
                    <span className="text-emerald-600 dark:text-emerald-400">{run.passed_tests} passed</span>
                    <span className="text-red-600 dark:text-red-400 ml-1.5">{run.failed_tests} failed</span>
                    {run.skipped_tests > 0 && (
                      <span className="text-muted-foreground ml-1.5">{run.skipped_tests} skipped</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-muted-foreground">
                    {run.runner_account ? (
                      <span className="inline-flex items-center gap-1.5">
                        <Server className="h-3 w-3 text-muted-foreground/60" />
                        {run.runner_account}
                      </span>
                    ) : (
                      <span className="text-muted-foreground/40">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-muted-foreground">
                    {run.duration_seconds ? formatDuration(run.duration_seconds) : '-'}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-muted-foreground">
                    {formatDateTime(run.started_at)}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-muted-foreground">
                    {run.completed_at ? formatDateTime(run.completed_at) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-3.5 border-t border-border flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total} runs
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md border border-border text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-3 text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-md border border-border text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, string> = {
    Pending: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
    Running: 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
    Completed: 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
    Failed: 'bg-red-500/10 text-red-700 dark:text-red-400',
    Cancelled: 'bg-muted text-muted-foreground',
  }

  return (
    <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${config[status] || config.Pending}`}>
      {status}
    </span>
  )
}

function FilterChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs text-primary">
      {label}
    </span>
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) return `${minutes}m ${secs.toFixed(0)}s`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}h ${mins}m`
}
