import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { auditApi, type AuditFilters } from '../api/client'

const PAGE_SIZE = 50

const ACTION_GROUPS: { value: string; label: string }[] = [
  { value: '', label: 'All events' },
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

/** The admin audit log: security-relevant events, newest first, filterable. */
export default function AuditPage() {
  const [action, setAction] = useState('')
  const [outcome, setOutcome] = useState('')
  const [since, setSince] = useState('')
  const [until, setUntil] = useState('')
  const [page, setPage] = useState(0)

  const filters: AuditFilters = {
    action: action || undefined,
    outcome: outcome || undefined,
    since: since || undefined,
    until: until || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }
  const { data, isLoading } = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => auditApi.list(filters),
  })
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  const resetPage = () => setPage(0)

  return (
    <div className="p-6 space-y-4">
      <p className="text-sm text-muted-foreground">
        Events cannot be changed or deleted here.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-muted-foreground">
          Events
          <select
            aria-label="Events"
            value={action}
            onChange={(e) => { setAction(e.target.value); resetPage() }}
            className="block mt-1 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground"
          >
            {ACTION_GROUPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </label>
        <label className="text-sm text-muted-foreground">
          Outcome
          <select
            aria-label="Outcome"
            value={outcome}
            onChange={(e) => { setOutcome(e.target.value); resetPage() }}
            className="block mt-1 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground"
          >
            <option value="">Any</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="ignored">Ignored</option>
          </select>
        </label>
        <label className="text-sm text-muted-foreground">
          From
          <input
            aria-label="From"
            type="date"
            value={since}
            onChange={(e) => { setSince(e.target.value); resetPage() }}
            className="block mt-1 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground"
          />
        </label>
        <label className="text-sm text-muted-foreground">
          Until
          <input
            aria-label="Until"
            type="date"
            value={until}
            onChange={(e) => { setUntil(e.target.value); resetPage() }}
            className="block mt-1 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground"
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
            {(data?.items ?? []).map((event) => (
              <tr key={event.id} className="border-t border-border align-top">
                <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">
                  {event.occurred_at.replace('T', ' ').slice(0, 19)}
                </td>
                <td className="px-4 py-2 text-foreground">
                  {event.actor_name ?? (event.actor_user_id != null ? `User ${event.actor_user_id}` : event.actor_type)}
                </td>
                <td className="px-4 py-2 text-foreground font-mono text-xs">{event.action}</td>
                <td className="px-4 py-2 text-muted-foreground">
                  {event.target_type ? `${event.target_type} ${event.target_id ?? ''}`.trim() : ''}
                </td>
                <td className={`px-4 py-2 ${event.outcome === 'failure' ? 'text-red-600' : 'text-muted-foreground'}`}>
                  {event.outcome}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{event.ip ?? ''}</td>
                <td className="px-4 py-2 text-muted-foreground font-mono text-xs">{event.request_id ?? ''}</td>
              </tr>
            ))}
            {!isLoading && (data?.items.length ?? 0) === 0 && (
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
