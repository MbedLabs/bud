import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { testRunsApi, testStationsApi } from '../api/client'
import { formatDateTime } from '../test/date-utils'
import { CheckCircle, XCircle, PlayCircle, Server, TrendingUp, Activity } from 'lucide-react'

export default function Dashboard() {
  const { data: testRunsData, isLoading: runsLoading } = useQuery({
    queryKey: ['testRuns', { limit: 5 }],
    queryFn: () => testRunsApi.list({ limit: 5 }),
  })

  const { data: runnersData, isLoading: runnersLoading } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
  })

  const runs = testRunsData?.runs || []
  const runners = runnersData?.runners || []

  const totalRuns = testRunsData?.total || 0
  const passedRuns = runs.filter(r => r.status === 'Completed' && r.failed_tests === 0).length
  const failedRuns = runs.filter(r => r.status === 'Failed' || r.failed_tests > 0).length
  const onlineRunners = runners.filter(r => r.is_online).length

  const passRate = totalRuns > 0
    ? Math.round((passedRuns / Math.max(totalRuns, 1)) * 100)
    : 0

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Test Runs"
          value={totalRuns}
          icon={PlayCircle}
          gradient="from-primary to-teal-700"
        />
        <StatCard
          title="Passed"
          value={passedRuns}
          icon={CheckCircle}
          gradient="from-emerald-500 to-emerald-700"
        />
        <StatCard
          title="Failed"
          value={failedRuns}
          icon={XCircle}
          gradient="from-red-500 to-red-700"
        />
        <StatCard
          title="Test Stations Online"
          value={`${onlineRunners}/${runners.length}`}
          icon={Server}
          gradient="from-cyan-500 to-teal-700"
          subtitle={onlineRunners === runners.length && runners.length > 0 ? 'All stations online' : undefined}
        />
      </div>

      {/* Pass Rate Bar */}
      <div className="bg-card rounded-lg border border-border shadow-elegant p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Overall Pass Rate</span>
          </div>
          <span className={`text-2xl font-bold ${
            passRate >= 80 ? 'text-emerald-600 dark:text-emerald-400' : passRate >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
          }`}>{passRate}%</span>
        </div>
        <div className="h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-smooth ${
              passRate >= 80 ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : passRate >= 50 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-red-500 to-red-400'
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

function StatCard({ title, value, icon: Icon, gradient, subtitle }: {
  title: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  gradient: string
  subtitle?: string
}) {
  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant hover:shadow-glow transition-shadow duration-300 p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="text-3xl font-bold text-foreground mt-2">{value}</p>
          {subtitle && <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">{subtitle}</p>}
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
    Running: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
    Completed: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-400',
    Failed: 'bg-red-500/10 text-red-700 dark:text-red-400',
    Cancelled: 'bg-muted text-muted-foreground',
  }

  return (
    <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${config[status] || config.Pending}`}>
      {status}
    </span>
  )
}
