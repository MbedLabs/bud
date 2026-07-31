import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { testRunsApi, testStationsApi, type TestRunStatsFilters } from '../api/client'
import { formatDateTime } from '../test/date-utils'
import { CheckCircle, XCircle, PlayCircle, Server, TrendingUp, Activity, Filter, X } from 'lucide-react'

const DEFAULT_DAYS = 30

const TIME_RANGES: { label: string; days?: number }[] = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Last year', days: 365 },
  { label: 'All time', days: undefined },
]

export default function Dashboard() {
  const [days, setDays] = useState<number | undefined>(DEFAULT_DAYS)
  const [station, setStation] = useState('')
  const [suite, setSuite] = useState('')

  const filters: TestRunStatsFilters = {
    ...(days !== undefined && { days }),
    ...(station && { runner_account: station }),
    ...(suite && { suite }),
  }
  const filtersAreDefault = days === DEFAULT_DAYS && !station && !suite

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['testRunStats', filters],
    queryFn: () => testRunsApi.stats(filters),
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['testRunFilterOptions', days],
    queryFn: () => testRunsApi.filterOptions(days !== undefined ? { days } : undefined),
  })

  const { data: testRunsData, isLoading: runsLoading } = useQuery({
    queryKey: ['testRuns', { limit: 5, station, suite }],
    queryFn: () =>
      testRunsApi.list({
        limit: 5,
        ...(station && { runner_account: station }),
        ...(suite && { suite }),
      }),
  })

  const { data: runnersData, isLoading: runnersLoading } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
  })

  const runs = testRunsData?.runs || []
  const runners = runnersData?.runners || []
  const onlineRunners = runners.filter(r => r.is_online).length

  // Every counter below is aggregated server-side across the whole filtered set,
  // so it no longer depends on how many runs the listing happens to load.
  const totalRuns = stats?.total_runs ?? 0
  const passedRuns = stats?.passed_runs ?? 0
  const failedRuns = stats?.failed_runs ?? 0
  const passRate = stats?.run_pass_rate ?? 0

  const stationOptions = filterOptions?.runner_accounts ?? []
  const suiteOptions = filterOptions?.suites ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Filters */}
      <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 md:flex-1">
            <FilterSelect
              label="Time range"
              value={days === undefined ? 'all' : String(days)}
              onChange={(value) => setDays(value === 'all' ? undefined : Number(value))}
              options={TIME_RANGES.map(range => ({
                value: range.days === undefined ? 'all' : String(range.days),
                label: range.label,
              }))}
            />
            <FilterSelect
              label="Test Station"
              value={station}
              onChange={setStation}
              placeholder="All stations"
              options={stationOptions.map(account => ({ value: account, label: account }))}
            />
            <FilterSelect
              label="Suite"
              value={suite}
              onChange={setSuite}
              placeholder="All suites"
              options={suiteOptions.map(name => ({ value: name, label: name }))}
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <button
              type="button"
              onClick={() => {
                setDays(DEFAULT_DAYS)
                setStation('')
                setSuite('')
              }}
              disabled={filtersAreDefault}
              className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5" />
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Test Runs"
          value={statsLoading ? '—' : totalRuns}
          icon={PlayCircle}
          gradient="from-primary to-bud-orange"
          subtitle={stats ? `${stats.total_tests} tests` : undefined}
        />
        <StatCard
          title="Passed"
          value={statsLoading ? '—' : passedRuns}
          icon={CheckCircle}
          gradient="from-emerald-500 to-emerald-700"
          subtitle={stats ? `${stats.passed_tests} tests passed` : undefined}
        />
        <StatCard
          title="Failed"
          value={statsLoading ? '—' : failedRuns}
          icon={XCircle}
          gradient="from-red-500 to-red-700"
          subtitle={stats ? `${stats.failed_tests} tests failed` : undefined}
        />
        <StatCard
          title="Test Stations Online"
          value={`${onlineRunners}/${runners.length}`}
          icon={Server}
          gradient="from-bud-forest to-bud-orange"
          subtitle={onlineRunners === runners.length && runners.length > 0 ? 'All stations online' : undefined}
          subtitleTone={onlineRunners === runners.length && runners.length > 0 ? 'positive' : 'muted'}
        />
      </div>

      {/* Pass Rate Bar */}
      <div className="bg-card rounded-lg border border-border shadow-elegant p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <div>
              <span className="text-sm font-medium text-foreground">Overall Pass Rate</span>
              <p className="text-xs text-muted-foreground">
                {stats && stats.in_progress_runs > 0
                  ? `${stats.in_progress_runs} run(s) still in progress are excluded`
                  : 'Share of decided runs that passed'}
              </p>
            </div>
          </div>
          <span className={`text-2xl font-bold ${
            passRate >= 80 ? 'text-emerald-600 dark:text-emerald-400' : passRate >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
          }`}>{passRate}%</span>
        </div>
        <div className="h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-smooth ${
              passRate >= 80 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' : passRate >= 50 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-red-500 to-red-400'
            }`}
            style={{ width: `${passRate}%` }}
          />
        </div>
      </div>

      {/* Recent Test Runs */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex justify-between items-center">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            Recent Test Runs
          </h3>
          <Link to="/runs" className="text-xs font-medium text-primary hover:text-primary/80 transition-colors">
            View all &rarr;
          </Link>
        </div>

        {runsLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No test runs yet</div>
        ) : (
          <div className="divide-y divide-border">
            {runs.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="block px-5 py-3.5 hover:bg-accent/50 transition-colors duration-150 group"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-foreground group-hover:text-primary transition-colors truncate">{run.name}</p>
                    <div className="flex items-center gap-2 mt-0.5 min-w-0">
                      <p className="text-xs text-muted-foreground truncate">{run.test_case_list}</p>
                      <span className="text-[10px] text-muted-foreground/40">•</span>
                      <p className="text-[10px] text-muted-foreground font-mono">{formatDateTime(run.started_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                    <StatusBadge status={run.status} />
                    <div className="text-xs text-muted-foreground">
                      {run.passed_tests}/{run.total_tests} passed
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Test Station Status */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex justify-between items-center">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Server className="h-4 w-4 text-primary" />
            Test Station Status
          </h3>
          <Link to="/test-stations" className="text-xs font-medium text-primary hover:text-primary/80 transition-colors">
            Manage &rarr;
          </Link>
        </div>

        {runnersLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : runners.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No test stations registered</div>
        ) : (
          <div className="divide-y divide-border">
            {runners.map((runner) => (
              <Link
                key={runner.account}
                to={`/runs?station=${encodeURIComponent(runner.account)}`}
                className="px-5 py-3.5 flex items-center justify-between hover:bg-accent/50 transition-colors duration-150"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                    runner.is_online ? 'bg-emerald-500 animate-pulse' : 'bg-muted-foreground/30'
                  }`} />
                  <div className="min-w-0">
                    <p className="font-medium text-foreground text-sm truncate">{runner.account}</p>
                    <p className="text-xs text-muted-foreground truncate">{runner.location || 'Unknown location'}</p>
                  </div>
                </div>
                <span className={`text-xs font-medium ${runner.is_online ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
                  {runner.is_online ? 'Online' : 'Offline'}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Labelled dropdown used by the dashboard filter bar. An empty value means "no
 *  filter", which is why the placeholder option carries an empty string. */
function FilterSelect({ label, value, onChange, options, placeholder }: {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground transition-colors hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  )
}

function StatCard({ title, value, icon: Icon, gradient, subtitle, subtitleTone = 'muted' }: {
  title: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  gradient: string
  subtitle?: string
  subtitleTone?: 'muted' | 'positive'
}) {
  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant hover:shadow-glow transition-shadow duration-300 p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="text-3xl font-bold text-foreground mt-2">{value}</p>
          {subtitle && (
            <p className={`text-xs mt-1 ${
              subtitleTone === 'positive'
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-muted-foreground'
            }`}>{subtitle}</p>
          )}
        </div>
        <div className={`p-2.5 rounded-lg bg-gradient-to-br ${gradient}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
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
