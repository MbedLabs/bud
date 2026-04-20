import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { testRunsApi, testStationsApi, type TestRun } from '../api/client'
import { formatDateTime } from '../test/date-utils'

const EMPTY_TEST_RUNS: TestRun[] = []
import { Search, Filter, ChevronLeft, ChevronRight, PlayCircle, Server } from 'lucide-react'

export default function TestRuns() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  // Bud runner *account* (matches Runner.account). We filter by account name
  // rather than runner_id because the stations endpoint returns accounts and
  // TestRun has a runner_id FK — we map id↔account via the stations list.
  const [stationFilter, setStationFilter] = useState<string>('')
  const limit = 20

  const { data, isLoading, error } = useQuery({
    queryKey: ['testRuns', { page, limit, status: statusFilter, station: stationFilter }],
    queryFn: () =>
      testRunsApi.list({
        offset: (page - 1) * limit,
        limit,
        status: statusFilter || undefined,
        runner_account: stationFilter || undefined,
      }),
  })

  const { data: stationsData } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    staleTime: 30_000,
  })
  const stations = stationsData?.runners || []

  const runs = data?.runs ?? EMPTY_TEST_RUNS
  const total = data?.total || 0
  const totalPages = Math.ceil(total / limit)

  // Search is kept client-side because the backend list endpoint doesn't
  // expose a ?q= parameter yet. Status + station are already server-side.
  const filteredRuns = useMemo(() => {
    if (!search) return runs
    const q = search.toLowerCase()
    return runs.filter(run =>
      run.name.toLowerCase().includes(q) ||
      run.test_case_list.toLowerCase().includes(q) ||
      (run.runner_account && run.runner_account.toLowerCase().includes(q))
    )
  }, [runs, search])

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Filters */}
      <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search test runs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
              className="bg-background border border-input rounded-md px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
            >
              <option value="">All Status</option>
              <option value="Pending">Pending</option>
              <option value="Running">Running</option>
              <option value="Completed">Completed</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-muted-foreground" />
            <select
              value={stationFilter}
              onChange={(e) => { setStationFilter(e.target.value); setPage(1) }}
              className="bg-background border border-input rounded-md px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors"
              title="Filter by Test Station (Bud runner account)"
            >
              <option value="">All Test Stations</option>
              {stations.map(s => (
                <option key={s.account} value={s.account}>{s.account}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

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
            <p className="text-sm text-muted-foreground">No test runs found</p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-border">
            <thead>
              <tr className="bg-muted/50">
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Name
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Test List
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
                  Started
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
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-muted-foreground">
                    {run.test_case_list}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs">
                    <span className="text-emerald-600 dark:text-emerald-400">{run.passed_tests} passed</span>
                    {run.failed_tests > 0 && (
                      <span className="text-red-600 dark:text-red-400 ml-1.5">{run.failed_tests} failed</span>
                    )}
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
                </tr>
              ))}
            </tbody>
          </table>
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
    Pending: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    Running: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
    Completed: 'bg-muted text-muted-foreground',
    Cancelled: 'bg-muted text-muted-foreground',
  }

  return (
    <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${config[status] || config.Completed}`}>
      {status}
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
