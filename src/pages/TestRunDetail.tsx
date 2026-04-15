import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { testRunsApi, resultsApi, TestResult } from '../api/client'
import { ArrowLeft, CheckCircle, XCircle, Clock, AlertCircle, Download, Activity } from 'lucide-react'

export default function TestRunDetail() {
  const { id } = useParams<{ id: string }>()
  const runId = parseInt(id || '0')

  const { data: run, isLoading: runLoading, error: runError } = useQuery({
    queryKey: ['testRun', runId],
    queryFn: () => testRunsApi.get(runId),
    enabled: !!runId,
  })

  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['testResults', runId],
    queryFn: () => resultsApi.list(runId),
    enabled: !!runId,
  })

  if (runLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  if (runError || !run) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-8 text-center">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground">Test Run Not Found</h3>
        <p className="text-muted-foreground mt-2">The requested test run could not be found.</p>
        <Link to="/runs" className="mt-4 inline-block text-primary hover:text-primary/80">
          &larr; Back to Test Runs
        </Link>
      </div>
    )
  }

  const passRate = run.total_tests > 0
    ? ((run.passed_tests / run.total_tests) * 100).toFixed(1)
    : '0'

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/runs" className="p-2 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h2 className="text-xl font-bold text-foreground">{run.name}</h2>
            <p className="text-sm text-muted-foreground">{run.test_case_list}</p>
          </div>
        </div>
        <StatusBadge status={run.status} />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Total Tests"
          value={run.total_tests}
          icon={Activity}
          gradient="from-primary/10 to-cyan-500/10"
          iconColor="text-primary"
        />
        <SummaryCard
          label="Passed"
          value={run.passed_tests}
          icon={CheckCircle}
          gradient="from-emerald-500/10 to-emerald-500/5"
          iconColor="text-emerald-600 dark:text-emerald-400"
        />
        <SummaryCard
          label="Failed"
          value={run.failed_tests}
          icon={XCircle}
          gradient="from-red-500/10 to-red-500/5"
          iconColor="text-red-600 dark:text-red-400"
        />
        <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Pass Rate</p>
            <span className={`text-lg font-bold ${
              parseFloat(passRate) >= 80 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'
            }`}>{passRate}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                parseFloat(passRate) >= 80
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  : 'bg-gradient-to-r from-amber-500 to-amber-400'
              }`}
              style={{ width: `${passRate}%` }}
            />
          </div>
        </div>
      </div>

      {/* Run Details */}
      <div className="bg-card rounded-lg border border-border shadow-elegant p-5">
        <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          Run Details
        </h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <DetailItem label="Started At" value={run.started_at ? new Date(run.started_at).toLocaleString() : '-'} />
          <DetailItem label="Completed At" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : '-'} />
          <DetailItem label="Duration" value={run.duration_seconds ? formatDuration(run.duration_seconds) : '-'} />
          <DetailItem label="Test Station" value={run.runner_id ? `Station #${run.runner_id}` : 'Not assigned'} />
        </dl>
      </div>

      {/* Test Results */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Test Results</h3>
        </div>

        {resultsLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading results...</div>
        ) : !results || results.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No test results yet</div>
        ) : (
          <table className="min-w-full divide-y divide-border">
            <thead>
              <tr className="bg-muted/50">
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Test Case
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Message
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Artifacts
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {results.map((result: TestResult) => (
                <tr key={result.id} className={`hover:bg-accent/50 transition-colors ${
                  !result.passed ? 'bg-red-500/[0.02]' : ''
                }`}>
                  <td className="px-5 py-3 whitespace-nowrap">
                    <ResultIcon status={result.passed ? 'passed' : 'failed'} />
                  </td>
                  <td className="px-5 py-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">{result.test_method}</p>
                      <p className="text-xs text-muted-foreground">{result.test_class}</p>
                    </div>
                  </td>
                  <td className="px-5 py-3 whitespace-nowrap text-xs text-muted-foreground">
                    {result.duration_seconds ? formatDuration(result.duration_seconds) : '-'}
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground max-w-md truncate">
                    {result.error_message || '-'}
                  </td>
                  <td className="px-5 py-3 whitespace-nowrap">
                    {result.artifacts && result.artifacts.length > 0 ? (
                      <div className="flex items-center gap-2">
                        {result.artifacts.map((artifact: string, i: number) => (
                          <a
                            key={i}
                            href={artifact}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:text-primary/80 transition-colors"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                        ))}
                      </div>
                    ) : (
                      <span className="text-muted-foreground/40">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-foreground mt-1">{value}</dd>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, string> = {
    Pending: 'bg-muted text-muted-foreground',
    Running: 'bg-primary/10 text-primary',
    Completed: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    Failed: 'bg-red-500/10 text-red-700 dark:text-red-400',
    Cancelled: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  }

  return (
    <span className={`px-3 py-1.5 rounded-md text-xs font-semibold ${config[status] || config.Pending}`}>
      {status}
    </span>
  )
}

function SummaryCard({ label, value, icon: Icon, gradient, iconColor }: {
  label: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  gradient: string
  iconColor: string
}) {
  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
        </div>
        <div className={`p-2.5 rounded-lg bg-gradient-to-br ${gradient}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
    </div>
  )
}

function ResultIcon({ status }: { status: string }) {
  switch (status) {
    case 'passed':
      return <CheckCircle className="h-4 w-4 text-emerald-500" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'skipped':
      return <AlertCircle className="h-4 w-4 text-amber-500" />
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) return `${minutes}m ${secs.toFixed(0)}s`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}h ${mins}m`
}
