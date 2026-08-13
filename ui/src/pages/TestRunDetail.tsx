import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useParams, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import {
  artifactsApi,
  extractApiErrorMessage,
  reportsApi,
  resultsApi,
  saveBlob,
  testRunsApi,
  TestResult,
  type Artifact,
  type TestRunEvent,
} from '../api/client'
import { summarizeAssertions, summarizeTestCases } from '../lib/testRunAssertions'
import {
  EMPTY_OUTCOME_FILTERS,
  filterAssertionsForDisplay,
  hasActiveOutcomeFilters,
  shouldShowTestCase,
  toggleOutcomeFilter,
  type OutcomeFilters,
} from '../lib/testRunResultFilters'
import { formatDateTime } from '../test/date-utils'
import {
  ArrowLeft, CheckCircle, XCircle, Clock, AlertCircle, Activity,
  ChevronDown, ChevronRight, UploadCloud, RefreshCw, Radio, GitBranch,
  Filter, X, FileDown, Paperclip, FileText, Download,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export default function TestRunDetail() {
  const { id } = useParams<{ id: string }>()
  const runId = parseInt(id || '0')
  const [reportError, setReportError] = useState<string | null>(null)
  const [reportPending, setReportPending] = useState(false)
  const [systemReportOpen, setSystemReportOpen] = useState(false)
  const [resultsFiltersOpen, setResultsFiltersOpen] = useState(false)
  const [outcomeFilters, setOutcomeFilters] = useState<OutcomeFilters>(EMPTY_OUTCOME_FILTERS)

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

  const { data: artifacts, isLoading: artifactsLoading } = useQuery({
    queryKey: ['testRunArtifacts', runId],
    queryFn: () => testRunsApi.getArtifacts(runId),
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

  // Test cases and assertions are counted separately: a single test case normally
  // carries several assertions, so the two totals are not interchangeable.
  const assertionSummary = summarizeAssertions(results || [])
  const testSummary = summarizeTestCases(run, results || [])
  const passRate = testSummary.total > 0
    ? ((testSummary.passed / testSummary.total) * 100).toFixed(1)
    : '0'
  const assertionPassRate = assertionSummary.total > 0
    ? ((assertionSummary.passed / assertionSummary.total) * 100).toFixed(1)
    : null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 min-w-0">
          <Link to="/runs" className="p-2 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-foreground truncate">{run.name}</h2>
            <p className="text-sm text-muted-foreground truncate">{run.test_case_list}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={async () => {
              setReportError(null)
              setReportPending(true)
              try {
                const { blob, filename } = await reportsApi.testRun(runId)
                saveBlob(blob, filename)
              } catch (error) {
                setReportError(extractApiErrorMessage(error, 'Could not generate the report'))
              } finally {
                setReportPending(false)
              }
            }}
            disabled={reportPending}
            title="Download this run as a PDF report"
            className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileDown className="h-4 w-4" />
            {reportPending ? 'Preparing…' : 'PDF report'}
          </button>
          <StatusBadge status={run.status} />
        </div>
      </div>

      {reportError && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
          {reportError}
        </p>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Total"
          tests={testSummary.total}
          assertions={assertionSummary.total}
          icon={Activity}
          gradient="from-primary/10 to-lime-500/10"
          iconColor="text-primary"
        />
        <SummaryCard
          label="Passed"
          tests={testSummary.passed}
          assertions={assertionSummary.passed}
          icon={CheckCircle}
          gradient="from-emerald-500/10 to-emerald-500/5"
          iconColor="text-emerald-600 dark:text-emerald-400"
        />
        <SummaryCard
          label="Failed"
          tests={testSummary.failed}
          assertions={assertionSummary.failed}
          icon={XCircle}
          gradient="from-red-500/10 to-red-500/5"
          iconColor="text-red-600 dark:text-red-400"
        />
        <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Pass Rate</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {assertionPassRate !== null ? `${assertionPassRate}% of assertions` : 'No assertions recorded'}
              </p>
            </div>
            <span className={`text-lg font-bold ${
              parseFloat(passRate) >= 80 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'
            }`}>{passRate}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                parseFloat(passRate) >= 80
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
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
        <div className="flex flex-col gap-3 border-b border-border p-4 md:flex-row md:items-center md:justify-between">
          <h3 className="text-sm font-semibold text-foreground">Test Results</h3>
          {results && results.length > 0 && (
            <button
              type="button"
              onClick={() => setResultsFiltersOpen((open) => !open)}
              className={`inline-flex items-center justify-center gap-2 rounded-md border px-2.5 py-1.5 text-sm font-medium transition-colors ${
                resultsFiltersOpen || hasActiveOutcomeFilters(outcomeFilters)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-input bg-background text-foreground hover:bg-accent'
              }`}
              aria-expanded={resultsFiltersOpen}
              aria-controls="testrun-results-filter-panel"
            >
              <Filter className="h-4 w-4" />
              Filters
              {hasActiveOutcomeFilters(outcomeFilters) && (
                <span className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                  On
                </span>
              )}
            </button>
          )}
        </div>

        {resultsFiltersOpen && results && results.length > 0 && (
          <div id="testrun-results-filter-panel" className="space-y-3 border-b border-border p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Filter className="h-4 w-4 text-primary" />
              Outcome
            </div>
            <div className="flex flex-wrap gap-2">
              {(
                [
                  { key: 'passed' as const, label: 'Passed' },
                  { key: 'failed' as const, label: 'Failed' },
                  { key: 'failedOnly' as const, label: 'Failed only' },
                ] as const
              ).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setOutcomeFilters((current) => toggleOutcomeFilter(current, key))}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    outcomeFilters[key]
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Failed shows failing test cases with every assertion. Failed only keeps failing cases but hides
              passing assertions inside them.
            </p>
            {hasActiveOutcomeFilters(outcomeFilters) && (
              <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2">
                {outcomeFilters.passed && <OutcomeFilterChip label="Passed" />}
                {outcomeFilters.failed && <OutcomeFilterChip label="Failed" />}
                {outcomeFilters.failedOnly && <OutcomeFilterChip label="Failed only" />}
                <button
                  type="button"
                  onClick={() => setOutcomeFilters(EMPTY_OUTCOME_FILTERS)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                  Clear all
                </button>
              </div>
            )}
          </div>
        )}

        {resultsLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading results...</div>
        ) : !results || results.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No test results yet</div>
        ) : (
          <ResultsTable results={results} outcomeFilters={outcomeFilters} />
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

      <RunArtifacts artifacts={artifacts} isLoading={artifactsLoading} />

      <PublishToBloom runId={runId} hasReport={(artifacts || []).some(isReport)} />
    </div>
  )
}

/**
 * What the run left behind: screenshots, plots, traces, packet captures.
 *
 * These could be uploaded and fetched by id, but nothing listed them, so an
 * artifact attached to a run was only reachable by someone who already knew its
 * integer id. Downloads go through the API client rather than a bare link,
 * because the endpoint is authenticated and a plain href arrives without a
 * token.
 */
function RunArtifacts({ artifacts, isLoading }: { artifacts?: Artifact[]; isLoading: boolean }) {
  const [downloading, setDownloading] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const download = async (artifact: Artifact) => {
    setError(null)
    setDownloading(artifact.id)
    try {
      const { blob, filename } = await artifactsApi.download(artifact.id, artifact.original_filename)
      saveBlob(blob, filename)
    } catch (failure) {
      // A retention sweep can remove the file while the page still lists it, so
      // a failed download is a normal outcome and has to say so.
      setError(extractApiErrorMessage(failure, 'Could not download the artifact'))
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Paperclip className="h-4 w-4 text-primary shrink-0" />
          <div>
            <h3 className="text-sm font-semibold text-foreground">Artifacts</h3>
            <p className="text-xs text-muted-foreground">
              {isLoading
                ? 'Loading artifacts...'
                : `${artifacts?.length || 0} file${artifacts?.length === 1 ? '' : 's'} uploaded for this run`}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <p className="border-b border-border px-5 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      )}

      {isLoading ? (
        <div className="p-8 text-center text-muted-foreground">Loading artifacts...</div>
      ) : !artifacts || artifacts.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground">
          No artifacts uploaded for this run
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {artifacts.map((artifact) => (
            <li key={artifact.id} className="flex items-center gap-3 px-5 py-3">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {artifact.original_filename}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(artifact.size_bytes)}
                  {artifact.test_case ? ` \u00b7 ${artifact.test_case}` : ''}
                  {` \u00b7 ${formatDateTime(artifact.created_at)}`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => download(artifact)}
                disabled={downloading === artifact.id}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5" />
                {downloading === artifact.id ? 'Downloading...' : 'Download'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** A byte count as a reader would say it. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`
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
      surface: 'bg-amber-500/10',
      icon: 'text-amber-700 dark:text-amber-300',
      badge: 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
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

function ResultsTable({
  results,
  outcomeFilters,
}: {
  results: TestResult[]
  outcomeFilters: OutcomeFilters
}) {
  const [expandedCases, setExpandedCases] = useState<Record<string, boolean>>({})
  const testCases = useMemo(() => groupResultsByTestCase(results), [results])
  const visibleTestCases = useMemo(
    () => testCases.filter((testCase) => shouldShowTestCase(testCase.failedAssertions, outcomeFilters)),
    [testCases, outcomeFilters],
  )

  const toggleCase = (key: string) =>
    setExpandedCases(e => ({ ...e, [key]: !(e[key] ?? false) }))

  if (visibleTestCases.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        No test cases match the current outcome filters.
      </div>
    )
  }

  return (
    <div className="divide-y divide-border">
      {visibleTestCases.map((testCase) => {
        const visibleAssertions = filterAssertionsForDisplay(
          testCase.assertions,
          testCase.failedAssertions,
          outcomeFilters,
        )
        const isOpen = expandedCases[testCase.key] ?? false
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
                <ResultDetail assertions={visibleAssertions} />
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
                <code className="font-mono text-foreground break-all">{formatVal(expected)}</code>
              </div>
              <div>
                <span className="text-muted-foreground mr-1.5">Actual:</span>
                <code className="font-mono text-foreground break-all">{formatVal(actual)}</code>
              </div>
            </div>
          )}
          {assertion.metadata && Object.keys(assertion.metadata).length > 0 && (
            <div className="mt-1 text-[11px] text-muted-foreground">
              {Object.entries(assertion.metadata).map(([k, v]) => (
                <span key={k} className="mr-3">
                  <span className="opacity-70">{k}:</span>{' '}
                  <code className="font-mono text-foreground break-all">{formatVal(v)}</code>
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
      <dd className="text-sm text-foreground mt-1 break-words">{value}</dd>
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
    <span className={`px-3 py-1.5 rounded-md text-xs font-semibold ${config[status] || config.Pending}`}>
      {status}
    </span>
  )
}

/** Reports the test-case count and the assertion count side by side, because a run
 *  summarised by only one of the two is ambiguous. */
function SummaryCard({ label, tests, assertions, icon: Icon, gradient, iconColor }: {
  label: string
  tests: number
  assertions: number
  icon: React.ComponentType<{ className?: string }>
  gradient: string
  iconColor: string
}) {
  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant p-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-foreground leading-none">{tests}</span>
            <span className="text-[11px] font-medium text-muted-foreground">
              {tests === 1 ? 'test' : 'tests'}
            </span>
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-sm font-semibold text-muted-foreground leading-none">{assertions}</span>
            <span className="text-[11px] font-medium text-muted-foreground">
              {assertions === 1 ? 'assertion' : 'assertions'}
            </span>
          </div>
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

function OutcomeFilterChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-foreground">
      {label}
    </span>
  )
}


/** A report is what Bloom keeps; logs and screenshots stay here. */
function isReport(artifact: Artifact): boolean {
  const name = artifact.original_filename.toLowerCase()
  return name.endsWith('.pdf') || name.endsWith('.xml')
}

/**
 * Sending this run's report to Bloom, when someone asks for it.
 *
 * Not automatic: a suite that runs nightly would put a Report document into the
 * PLM every night, and a project holding a year of them is harder to read than
 * one holding none.
 */
function PublishToBloom({ runId, hasReport }: { runId: number; hasReport: boolean }) {
  const [prefix, setPrefix] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const publish = useMutation({
    mutationFn: () => testRunsApi.publishToBloom(runId, prefix.trim().toUpperCase()),
    onSuccess: (data) => {
      setError(null)
      setResult(
        `${data.doc_id ?? 'Report'} ${data.created ? 'created' : 'updated'} with ` +
          `${data.published_files.length} file${data.published_files.length === 1 ? '' : 's'}.`,
      )
    },
    onError: (failure) => {
      setResult(null)
      setError(extractApiErrorMessage(failure, 'Could not publish to Bloom'))
    },
  })

  return (
    <div className="bg-card rounded-lg shadow-elegant overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">Publish to Bloom</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          {hasReport
            ? 'Files this run produced become a Report document in the chosen project.'
            : 'This run has no report to publish yet.'}
        </p>
      </div>
      <div className="p-5 flex flex-wrap items-center gap-3">
        <input
          value={prefix}
          onChange={(event) => setPrefix(event.target.value)}
          placeholder="Project prefix, e.g. VCU"
          aria-label="Bloom project prefix"
          className="px-3 py-2 bg-background border border-input rounded-md text-sm w-56"
        />
        <button
          onClick={() => publish.mutate()}
          disabled={!hasReport || !prefix.trim() || publish.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {publish.isPending ? 'Publishing...' : 'Publish report'}
        </button>
        {result && <span className="text-sm text-green-600 dark:text-green-400">{result}</span>}
        {error && <span className="text-sm text-red-500">{error}</span>}
      </div>
    </div>
  )
}
