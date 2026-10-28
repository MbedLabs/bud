import ProfilePicture from '../components/ProfilePicture'
import DateField from '../components/DateField'
import SelectField from '../components/SelectField'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { auditApi, testStationsApi, type AuditEvent, type AuditFilters } from '../api/client'
import { formatDateTime } from '../test/date-utils'
import { useDebounced } from '../hooks/useDebounced'

const PAGE_SIZE = 50

const REFUSED = 'refused'

const ACTION_GROUPS: { value: string; label: string }[] = [
  { value: '', label: 'All events' },
  { value: 'api.', label: 'API calls' },
  { value: REFUSED, label: 'Refused attempts' },
  { value: 'auth.', label: 'Authentication' },
  { value: 'user.', label: 'Accounts' },
  { value: 'group.', label: 'Groups' },
  { value: 'station.', label: 'Test stations' },
  { value: 'enrolment_key.', label: 'Enrolment keys' },
  { value: 'integration.', label: 'Bloom integration' },
  { value: 'notification_channel.', label: 'Notifications' },
  { value: 'product.', label: 'Products' },
  { value: 'test_run.', label: 'Test runs' },
  { value: 'artifact.', label: 'Artifacts' },
  { value: 'export.', label: 'Reports' },
]

const ACTOR_TYPES: { value: string; label: string }[] = [
  { value: '', label: 'Anyone' },
  { value: 'user', label: 'Users' },
  { value: 'runner', label: 'Test stations' },
  { value: 'anonymous', label: 'Anonymous' },
  { value: 'service', label: 'Service' },
]

const FIELD_CLASS = 'block mt-1 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground'

/** One value from an event's details, when it is a string or a number. */
function detail(event: AuditEvent, key: string): string | number | undefined {
  const value = event.details?.[key]
  return typeof value === 'string' || typeof value === 'number' ? value : undefined
}

/** The Test Station of a runner event: its name when known, otherwise its id. */
function stationLabel(event: AuditEvent, stationNames: Map<number, string>): string {
  const runnerId = detail(event, 'runner_id')
  if (typeof runnerId !== 'number') return 'Test station'
  return stationNames.get(runnerId) ?? `Station #${runnerId}`
}

/** The Actor cell: the station, the named or numbered user with its client, or the actor type. */
function ActorCell({ event, stationNames }: Readonly<{ event: AuditEvent; stationNames: Map<number, string> }>) {
  if (event.actor_type === 'runner') return <>{stationLabel(event, stationNames)}</>
  const client = detail(event, 'client') === 'cli' ? (
    <span
      title={event.user_agent ?? undefined}
      className="ml-2 px-1.5 py-0.5 rounded border border-border text-xs text-muted-foreground whitespace-nowrap"
    >
      MCP or CLI
    </span>
  ) : null
  if (event.actor_name) {
    return (
      <span className="inline-flex items-center gap-2">
        <ProfilePicture user={{
          id: event.actor_user_id ?? undefined,
          full_name: event.actor_name,
          profile_picture_url: event.actor_profile_picture_url ?? null,
        }} className="w-6 h-6" />
        {event.actor_name}
        {client}
      </span>
    )
  }
  if (event.actor_user_id != null) return <>{`User ${event.actor_user_id}`}{client}</>
  return <>{event.actor_type}</>
}

/** The Event cell: method and route for an API call, otherwise the action. */
function EventCell({ event }: Readonly<{ event: AuditEvent }>) {
  const method = detail(event, 'method')
  const route = detail(event, 'route')
  if (event.action !== 'api.request' || method === undefined) return <>{event.action}</>
  const path = detail(event, 'path')
  return (
    <span title={path === undefined ? undefined : String(path)}>
      <span className="font-semibold">{method}</span> {route ?? path ?? ''}
    </span>
  )
}

/** The text colour of an outcome. */
function outcomeClass(outcome: string): string {
  if (outcome === 'failure') return 'text-red-600'
  if (outcome === 'denied') return 'text-amber-700 dark:text-amber-400'
  return 'text-muted-foreground'
}

/** The Target cell: the HTTP status, the target and what an API call created, or the target. */
function TargetCell({ event }: Readonly<{ event: AuditEvent }>) {
  const target = event.target_type ? `${event.target_type} ${event.target_id ?? ''}`.trim() : ''
  if (event.action !== 'api.request') return <>{target}</>
  const status = detail(event, 'status')
  const createdId = detail(event, 'created_id')
  const createdRun = detail(event, 'created_test_run_id')
  const parts = [
    target,
    createdId === undefined ? '' : `created ${createdId}`,
    createdRun === undefined ? '' : `created run ${createdRun}`,
  ].filter(Boolean)
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      {status !== undefined && (
        <span className={`font-mono text-xs ${event.outcome === 'success' ? 'text-foreground' : outcomeClass(event.outcome)}`}>
          {status}
        </span>
      )}
      {parts.length > 0 && <span>{parts.join(', ')}</span>}
    </span>
  )
}

/** The audit log for users with audit.view: every API request, every refused attempt and every
 * change to accounts, access, configuration and data, newest first, filterable. */
export default function AuditPage() {
  const [group, setGroup] = useState('')
  const [outcome, setOutcome] = useState('')
  const [actorType, setActorType] = useState('')
  const [address, setAddress] = useState('')
  const [requestId, setRequestId] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [page, setPage] = useState(0)
  const debouncedAddress = useDebounced(address.trim(), 250)
  const debouncedRequestId = useDebounced(requestId.trim(), 250)
  const refused = group === REFUSED

  const filters: AuditFilters = {
    action: refused ? undefined : group || undefined,
    outcome: refused ? 'denied' : outcome || undefined,
    actor_type: actorType || undefined,
    ip: debouncedAddress || undefined,
    request_id: debouncedRequestId || undefined,
    since: since || undefined,
    until: until || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }
  const { data, isLoading } = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => auditApi.list(filters),
  })
  const items = useMemo(() => data?.items ?? [], [data?.items])
  const showsStations = items.some((event) => event.actor_type === 'runner' && typeof event.details?.runner_id === 'number')
  const { data: stationsData } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    staleTime: 30_000,
    enabled: showsStations,
  })
  const stationNames = useMemo(
    () => new Map((stationsData?.runners ?? []).map((station) => [station.id, station.account])),
    [stationsData?.runners],
  )
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  const resetPage = () => setPage(0)

  return (
    <div className="p-6 space-y-4">
      <p className="text-sm text-muted-foreground">
        Every API request and every refused attempt is recorded. Events cannot be changed or deleted here.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-muted-foreground">
          Events
          <SelectField
            aria-label="Events"
            value={group}
            onChange={(e) => { setGroup(e.target.value); resetPage() }}
            className={FIELD_CLASS}
          >
            {ACTION_GROUPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
          </SelectField>
        </label>
        <label className="text-sm text-muted-foreground">
          Outcome
          <SelectField
            aria-label="Outcome"
            value={refused ? 'denied' : outcome}
            disabled={refused}
            onChange={(e) => { setOutcome(e.target.value); resetPage() }}
            className={FIELD_CLASS}
          >
            <option value="">Any</option>
            <option value="success">Success</option>
            <option value="denied">Denied</option>
            <option value="failure">Failure</option>
            <option value="ignored">Ignored</option>
          </SelectField>
        </label>
        <label className="text-sm text-muted-foreground">
          Actor
          <SelectField
            aria-label="Actor"
            value={actorType}
            onChange={(e) => { setActorType(e.target.value); resetPage() }}
            className={FIELD_CLASS}
          >
            {ACTOR_TYPES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </SelectField>
        </label>
        <label className="text-sm text-muted-foreground">
          Address
          <input
            type="text"
            value={address}
            onChange={(e) => { setAddress(e.target.value); resetPage() }}
            placeholder="Client address"
            spellCheck={false}
            className={`${FIELD_CLASS} w-40 text-sm placeholder:text-muted-foreground`}
          />
        </label>
        <label className="text-sm text-muted-foreground">
          Request id
          <input
            type="text"
            value={requestId}
            onChange={(e) => { setRequestId(e.target.value); resetPage() }}
            spellCheck={false}
            className={`${FIELD_CLASS} w-40 text-sm font-mono placeholder:text-muted-foreground`}
          />
        </label>
        <label className="text-sm text-muted-foreground">
          From
          <DateField
            label="From"
            value={since}
            onChange={(next) => { setSince(next); resetPage() }}
            className={FIELD_CLASS}
          />
        </label>
        <label className="text-sm text-muted-foreground">
          Until
          <DateField
            label="Until"
            value={until}
            onChange={(next) => { setUntil(next); resetPage() }}
            className={FIELD_CLASS}
          />
        </label>
      </div>
      <div className="border border-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th className="text-left font-medium px-4 py-2">Time (UTC)</th>
              <th className="text-left font-medium px-4 py-2">Actor</th>
              <th className="text-left font-medium px-4 py-2">Event</th>
              <th className="text-left font-medium px-4 py-2">Target</th>
              <th className="text-left font-medium px-4 py-2">Outcome</th>
              <th className="text-left font-medium px-4 py-2">Address</th>
              <th className="text-left font-medium px-4 py-2">Request</th>
            </tr>
          </thead>
          <tbody>
            {items.map((event) => (
              <tr key={event.id} className="border-t border-border align-top">
                <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">
                  {formatDateTime(event.occurred_at)}
                </td>
                <td className="px-4 py-2 text-foreground">
                  <ActorCell event={event} stationNames={stationNames} />
                </td>
                <td className="px-4 py-2 text-foreground font-mono text-xs">
                  <EventCell event={event} />
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  <TargetCell event={event} />
                </td>
                <td className={`px-4 py-2 ${outcomeClass(event.outcome)}`}>
                  {event.outcome}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{event.ip ?? ''}</td>
                <td className="px-4 py-2 text-muted-foreground font-mono text-xs">{event.request_id ?? ''}</td>
              </tr>
            ))}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">No events match these filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{total} events</span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 border border-border rounded-lg disabled:opacity-50"
          >
            Newer
          </button>
          <button
            onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
            disabled={page >= lastPage}
            className="px-3 py-1.5 border border-border rounded-lg disabled:opacity-50"
          >
            Older
          </button>
        </div>
      </div>
    </div>
  )
}
