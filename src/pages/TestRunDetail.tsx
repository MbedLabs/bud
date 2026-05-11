import { useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { testRunsApi, resultsApi, TestResult, type TestRunEvent } from '../api/client'
import { formatDateTime } from '../test/date-utils'
import {
  ArrowLeft, CheckCircle, XCircle, Clock, AlertCircle, Activity,
  ChevronDown, ChevronRight, UploadCloud, RefreshCw, Radio, GitBranch,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export default function TestRunDetail() {
  const { id } = useParams<{ id: string }>()
  const runId = parseInt(id || '0')
  const [systemReportOpen, setSystemReportOpen] = useState(false)

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

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['testRunEvents', runId],
    queryFn: () => testRunsApi.getEvents(runId),
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

  const assertionSummary = summarizeAssertions(results || [])
  const totalCount = assertionSummary.total || run.total_tests
  const passedCount = assertionSummary.total > 0 ? assertionSummary.passed : run.passed_tests
  const failedCount = assertionSummary.total > 0 ? assertionSummary.failed : run.failed_tests
  const passRate = totalCount > 0
    ? ((passedCount / totalCount) * 100).toFixed(1)
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
          label="Total Assertions"
          value={totalCount}
          icon={Activity}
          gradient="from-primary/10 to-cyan-500/10"
          iconColor="text-primary"
        />
        <SummaryCard
          label="Passed"
          value={passedCount}
          icon={CheckCircle}
          gradient="from-emerald-500/10 to-emerald-500/5"
          iconColor="text-emerald-600 dark:text-emerald-400"
        />
        <SummaryCard
          label="Failed"
          value={failedCount}
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
          <DetailItem label="Started At" value={formatDateTime(run.started_at)} />
          <DetailItem label="Completed At" value={formatDateTime(run.completed_at)} />
          <DetailItem label="Duration" value={run.duration_seconds ? formatDuration(run.duration_seconds) : '-'} />
          <DetailItem
            label="Test Station"
            value={
              run.runner_account
                ? run.runner_account
                : run.runner_id
                ? `Station #${run.runner_id}`
                : 'Not assigned'
            }
          />
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
          <ResultsTable results={results} />
        )}
      </div>

      {/* System Report */}
      <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
        <button
          type="button"
          onClick={() => setSystemReportOpen(open => !open)}
          className="w-full px-5 py-4 text-left hover:bg-accent/40 transition-colors"
        >
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0">
              <GitBranch className="h-4 w-4 text-primary shrink-0" />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-foreground">System Report</h3>
                <p className="text-xs text-muted-foreground">
                  {eventsLoading
                    ? 'Loading system steps...'
                    : `${events?.length || 0} reported step${events?.length === 1 ? '' : 's'}`}
                </p>
              </div>
            </div>
            {systemReportOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
          </div>
        </button>
        {systemReportOpen && (
          <>
            {eventsLoading ? (
              <div className="p-8 text-center text-muted-foreground border-t border-border">Loading system steps...</div>
            ) : !events || events.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground border-t border-border">No system steps reported yet</div>
            ) : (
              <div className="border-t border-border">
                <RunEventTimeline events={events} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function RunEventTimeline({ events }: { events: TestRunEvent[] }) {
  return (
    <div className="divide-y divide-border">
      {events.map((event) => {
        const Icon = getStageIcon(event.stage)
        return (
          <div key={event.id} className="px-5 py-4">
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${getEventTone(event.status).surface}`}>
                <Icon className={`h-4 w-4 ${getEventTone(event.status).icon}`} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-foreground">{event.title}</p>
                  <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${getEventTone(event.status).badge}`}>
                    {formatEventStatus(event.status)}
                  </span>
                  <span className="text-[11px] text-muted-foreground">{formatDateTime(event.created_at)}</span>
                </div>
                {event.message && (
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{event.message}</p>
                )}
                {event.event_metadata && Object.keys(event.event_metadata).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(event.event_metadata).slice(0, 4).map(([key, value]) => (
                      <span key={key} className="rounded-md border border-border bg-background px-2 py-1 text-[11px] text-muted-foreground">
                        <span className="font-medium text-foreground">{key}</span>: {formatVal(value)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function getStageIcon(stage: string): LucideIcon {
  const icons: Record<string, LucideIcon> = {
    bloom_scope: GitBranch,
    runner: Radio,
    execution: Activity,
    results: UploadCloud,
    bloom_sync: RefreshCw,
  }
  return icons[stage] || Activity
}

function getEventTone(status: string) {
  const tones: Record<string, { surface: string; icon: string; badge: string }> = {
    completed: {
      surface: 'bg-emerald-500/10',
      icon: 'text-emerald-600 dark:text-emerald-400',
      badge: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    },
    running: {
      surface: 'bg-blue-500/10',
      icon: 'text-blue-600 dark:text-blue-400',
      badge: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
    },
    warning: {
      surface: 'bg-amber-500/10',
      icon: 'text-amber-600 dark:text-amber-400',
      badge: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    },
    failed: {
      surface: 'bg-red-500/10',
      icon: 'text-red-600 dark:text-red-400',
      badge: 'bg-red-500/10 text-red-700 dark:text-red-400',
    },
    skipped: {
      surface: 'bg-muted',
      icon: 'text-muted-foreground',
      badge: 'bg-muted text-muted-foreground',
    },
    queued: {
      surface: 'bg-muted',
      icon: 'text-muted-foreground',
      badge: 'bg-muted text-muted-foreground',
    },
  }
  return tones[status] || tones.queued
}

function formatEventStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

interface AssertionShape {
  passed?: boolean
  message?: string
  assertion_type?: string
  expected?: unknown
  actual?: unknown
  result?: unknown
  source_file?: string | null
  source_line?: number | null
  source_function?: string | null
  code_context?: string | null
  traceback?: string | null
  timestamp?: string
  metadata?: Record<string, unknown> | null
}

function ResultsTable({ results }: { results: TestResult[] }) {
  const [expandedCases, setExpandedCases] = useState<Record<string, boolean>>({})
  const testCases = useMemo(() => groupResultsByTestCase(results), [results])

  const toggleCase = (key: string) =>
    setExpandedCases(e => ({ ...e, [key]: !(e[key] ?? true) }))

  return (
    <div className="divide-y divide-border">
      {testCases.map((testCase) => {
        const isOpen = expandedCases[testCase.key] ?? true
        return (
          <section key={testCase.key}>
            <button
              type="button"
              onClick={() => toggleCase(testCase.key)}
              className="w-full px-5 py-3 text-left hover:bg-accent/40 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="mt-0.5 text-muted-foreground">
                    {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </span>
                  <ResultIcon status={testCase.failedAssertions > 0 ? 'failed' : 'passed'} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-foreground">
                      {testCase.name}
                    </span>
                    <span className="mt-0.5 flex min-w-0 flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
                      {testCase.tcId && <span className={`font-medium ${testCase.failedAssertions > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>{testCase.tcId}</span>}
                      {testCase.sourceFile && <span className="truncate">{testCase.sourceFile}</span>}
                      <span>{testCase.assertionCount} check{testCase.assertionCount === 1 ? '' : 's'}</span>
                    </span>
                  </span>
                </div>
                <span className="shrink-0 text-right text-xs">
                  <span className={testCase.failedAssertions > 0 ? 'block text-red-600 dark:text-red-400' : 'block text-emerald-600 dark:text-emerald-400'}>
                    {testCase.passedAssertions} / {testCase.assertionCount} passed
                  </span>
                  {testCase.failedAssertions > 0 && (
                    <span className="block text-red-600 dark:text-red-400">{testCase.failedAssertions} failed</span>
                  )}
                </span>
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-border bg-muted/10 px-5 py-2">
                <ResultDetail assertions={testCase.assertions} />
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}

interface TestCaseGroup {
  key: string
  name: string
  sourceFile: string | null
  tcId: string | null
  methodNames: Set<string>
  methodCount: number
  assertions: AssertionViewModel[]
  assertionCount: number
  passedAssertions: number
  failedAssertions: number
  failedMethods: number
}

function groupResultsByTestCase(results: TestResult[]): TestCaseGroup[] {
  const groups = new Map<string, TestCaseGroup>()
  for (const result of results) {
    const metadata = result.test_metadata || {}
    const sourceFile = stringFromMeta(metadata, 'test_case_file')
    const className = stringFromMeta(metadata, 'test_case_class') || result.test_class
    const name = className || stringFromMeta(metadata, 'test_case_name') || 'UnknownTestCase'
    const key = className ? `${sourceFile || 'unknown'}:${className}` : sourceFile || name
    const assertions = (result.assertions as AssertionShape[] | null) || []

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        name,
        sourceFile,
        tcId: stringFromMeta(metadata, 'tc_id'),
        methodNames: new Set<string>(),
        methodCount: 0,
        assertions: [],
        failedMethods: 0,
        assertionCount: 0,
        passedAssertions: 0,
        failedAssertions: 0,
      })
    }

    const group = groups.get(key)!
    group.methodNames.add(result.test_method)
    group.methodCount = group.methodNames.size
    if (!result.passed) group.failedMethods += 1

    assertions.forEach((assertion) => {
      const passed = assertion.passed !== false
      group.assertions.push({
        ...assertion,
        methodName: result.test_method,
        durationSeconds: result.duration_seconds,
        methodErrorMessage: result.error_message,
      })
      group.assertionCount += 1
      if (passed) group.passedAssertions += 1
      else group.failedAssertions += 1
    })
  }
  return Array.from(groups.values())
}

function stringFromMeta(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function basename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || path
}

function inferAssertionType(assertion: AssertionShape): string {
  const expected = String(assertion.expected ?? '')
  const metadata = assertion.metadata || {}
  if ('tolerance' in metadata || expected.includes('+/-') || expected.includes('±')) return 'AssertInTolerance'
  if ('lower_bound' in metadata || expected.startsWith('[') || expected.startsWith('(') || expected.includes('..')) return 'AssertInRange'
  if (expected.startsWith('[') && expected.endsWith(']')) return 'AssertIn'
  if (expected !== '' && assertion.actual !== undefined) return 'AssertEqual'
  return 'Assert'
}

interface AssertionViewModel extends AssertionShape {
  methodName: string
  durationSeconds: number
  methodErrorMessage: string | null
}

function summarizeAssertions(results: TestResult[]) {
  return results.reduce(
    (summary, result) => {
      const assertions = (result.assertions as AssertionShape[] | null) || []
      assertions.forEach(assertion => {
        summary.total += 1
        if (assertion.passed !== false) summary.passed += 1
        else summary.failed += 1
      })
      return summary
    },
    { total: 0, passed: 0, failed: 0 },
  )
}

function ResultDetail({ assertions }: { assertions: AssertionViewModel[] }) {
  return (
    <div className="space-y-2 pl-10">
      {assertions.length > 0 ? (
        assertions.map((a, i) => <AssertionRow key={i} assertion={a} index={i + 1} />)
      ) : (
        <div className="py-3 text-xs text-muted-foreground">No assertions were reported for this test case.</div>
      )}
    </div>
  )
}

function AssertionRow({ assertion, index }: { assertion: AssertionViewModel; index: number }) {
  const passed = assertion.passed !== false
  const expected = assertion.expected
  const actual = assertion.actual
  const message = assertion.message || '(no message)'
  const assertionType = assertion.assertion_type || inferAssertionType(assertion)
  return (
    <div className={`border-l-2 py-2 pl-3 pr-2 text-xs ${
      passed
        ? 'border-emerald-500/50 bg-emerald-500/[0.02]'
        : 'border-red-500/70 bg-red-500/[0.03]'
    }`}>
      <div className="flex items-start gap-2">
        {passed ? (
          <CheckCircle className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-red-500 mt-0.5 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-mono text-[11px] text-muted-foreground">#{index}</span>
            <span className={`text-[11px] font-semibold ${
              passed
                ? 'text-emerald-700 dark:text-emerald-400'
                : 'text-red-700 dark:text-red-400'
            }`}>
              {assertionType}
            </span>
            <span className="max-w-full truncate text-[11px] text-muted-foreground">{assertion.methodName}</span>
            {assertion.source_file && (
              <span className="text-[11px] text-muted-foreground">
                {basename(assertion.source_file)}{assertion.source_line ? `:${assertion.source_line}` : ''}
              </span>
            )}
          </div>
          {(expected !== undefined || actual !== undefined || message) && (
            <div className="mt-1 grid grid-cols-1 gap-x-3 gap-y-0.5 text-[11px] sm:grid-cols-3">
              <div>
                <span className="text-muted-foreground mr-1.5">Message:</span>
                <span className="text-foreground">{message}</span>
              </div>
              <div>
                <span className="text-muted-foreground mr-1.5">Expected:</span>
                <code className="font-mono text-foreground">{formatVal(expected)}</code>
              </div>
              <div>
                <span className="text-muted-foreground mr-1.5">Actual:</span>
                <code className="font-mono text-foreground">{formatVal(actual)}</code>
              </div>
            </div>
          )}
          {assertion.metadata && Object.keys(assertion.metadata).length > 0 && (
            <div className="mt-1 text-[11px] text-muted-foreground">
              {Object.entries(assertion.metadata).map(([k, v]) => (
                <span key={k} className="mr-3">
                  <span className="opacity-70">{k}:</span>{' '}
                  <code className="font-mono text-foreground">{formatVal(v)}</code>
                </span>
              ))}
            </div>
          )}
          {assertion.traceback && (
            <details className="mt-1.5">
              <summary className="cursor-pointer text-[11px] text-muted-foreground hover:text-foreground">
                trace
              </summary>
              <pre className="mt-1 text-[11px] leading-relaxed text-foreground bg-background border border-border rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-words">
                {assertion.traceback}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}

function formatVal(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') {
    try { return JSON.stringify(v) } catch { return String(v) }
  }
  return String(v)
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
    Pending: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    Running: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
    Completed: 'bg-muted text-muted-foreground',
    Failed: 'bg-muted text-muted-foreground',
    Cancelled: 'bg-muted text-muted-foreground',
  }

  return (
    <span className={`px-3 py-1.5 rounded-md text-xs font-semibold ${config[status] || config.Completed}`}>
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
