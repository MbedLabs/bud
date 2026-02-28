import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { testRunsApi, resultsApi, TestResult } from '../api/client'
import { ArrowLeft, CheckCircle, XCircle, Clock, AlertCircle, Download } from 'lucide-react'

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
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (runError || !run) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-red-900">Test Run Not Found</h3>
        <p className="text-red-700 mt-2">The requested test run could not be found.</p>
        <Link to="/runs" className="mt-4 inline-block text-primary-600 hover:text-primary-700">
          ← Back to Test Runs
        </Link>
      </div>
    )
  }

  const passRate = run.total_tests > 0 
    ? ((run.passed_tests / run.total_tests) * 100).toFixed(1) 
    : '0'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/runs" className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </Link>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{run.name}</h2>
            <p className="text-gray-500">{run.test_case_list}</p>
          </div>
        </div>
        <StatusBadge status={run.status} large />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Total Tests"
          value={run.total_tests}
          icon={Clock}
          color="text-gray-600"
        />
        <SummaryCard
          label="Passed"
          value={run.passed_tests}
          icon={CheckCircle}
          color="text-green-600"
        />
        <SummaryCard
          label="Failed"
          value={run.failed_tests}
          icon={XCircle}
          color="text-red-600"
        />
        <SummaryCard
          label="Pass Rate"
          value={`${passRate}%`}
          icon={CheckCircle}
          color={parseFloat(passRate) >= 80 ? 'text-green-600' : 'text-yellow-600'}
        />
      </div>

      {/* Run Details */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Run Details</h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-gray-500">Started At</dt>
            <dd className="text-gray-900">
              {run.started_at ? new Date(run.started_at).toLocaleString() : '-'}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Completed At</dt>
            <dd className="text-gray-900">
              {run.completed_at ? new Date(run.completed_at).toLocaleString() : '-'}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Duration</dt>
            <dd className="text-gray-900">
              {run.duration_seconds ? formatDuration(run.duration_seconds) : '-'}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Runner</dt>
            <dd className="text-gray-900">{run.runner_id || 'Not assigned'}</dd>
          </div>
        </dl>
      </div>

      {/* Test Results */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">Test Results</h3>
        </div>

        {resultsLoading ? (
          <div className="p-6 text-center text-gray-500">Loading results...</div>
        ) : !results || results.length === 0 ? (
          <div className="p-6 text-center text-gray-500">No test results yet</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Test Case
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Message
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Artifacts
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {results.map((result: TestResult) => (
                <tr key={result.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <ResultIcon status={result.passed ? 'passed' : 'failed'} />
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-gray-900">{result.test_method}</p>
                      <p className="text-sm text-gray-500">{result.test_class}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {result.duration_seconds ? formatDuration(result.duration_seconds) : '-'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-md truncate">
                    {result.error_message || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {result.artifacts && result.artifacts.length > 0 ? (
                      <div className="flex items-center space-x-2">
                        {result.artifacts.map((artifact: string, i: number) => (
                          <a
                            key={i}
                            href={artifact}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary-600 hover:text-primary-700"
                          >
                            <Download className="h-4 w-4" />
                          </a>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-400">-</span>
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

function StatusBadge({ status, large = false }: { status: string; large?: boolean }) {
  const colors: Record<string, string> = {
    Pending: 'bg-gray-100 text-gray-800',
    Running: 'bg-blue-100 text-blue-800',
    Completed: 'bg-green-100 text-green-800',
    Failed: 'bg-red-100 text-red-800',
    Cancelled: 'bg-yellow-100 text-yellow-800',
  }

  const sizeClasses = large ? 'px-4 py-2 text-sm' : 'px-2 py-1 text-xs'

  return (
    <span className={`rounded-full font-medium ${sizeClasses} ${colors[status] || colors.Pending}`}>
      {status}
    </span>
  )
}

function SummaryCard({ label, value, icon: Icon, color }: {
  label: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  color: string
}) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <Icon className={`h-8 w-8 ${color}`} />
      </div>
    </div>
  )
}

function ResultIcon({ status }: { status: string }) {
  switch (status) {
    case 'PASSED':
      return <CheckCircle className="h-5 w-5 text-green-500" />
    case 'FAILED':
      return <XCircle className="h-5 w-5 text-red-500" />
    case 'SKIPPED':
      return <AlertCircle className="h-5 w-5 text-yellow-500" />
    default:
      return <Clock className="h-5 w-5 text-gray-400" />
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
