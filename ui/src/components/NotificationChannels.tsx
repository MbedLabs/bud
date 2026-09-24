import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Loader2, Send, Trash2 } from 'lucide-react'
import {
  extractApiErrorMessage,
  notificationsApi,
  type NotificationChannel,
  type NotificationFormat,
  type NotificationRunFilter,
} from '../api/client'

const FORMATS: { value: NotificationFormat; label: string }[] = [
  { value: 'teams', label: 'Microsoft Teams (Workflows or connector, read from the URL)' },
  { value: 'slack', label: 'Slack' },
  { value: 'discord', label: 'Discord' },
  { value: 'json', label: 'JSON (n8n, scripts, any endpoint)' },
]

const FILTERS: { value: NotificationRunFilter; label: string }[] = [
  { value: 'all', label: 'All finished runs' },
  { value: 'failures', label: 'Failures only' },
  { value: 'first_failure', label: 'First failure after a green run' },
]

const inputClass =
  'w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors'
const labelClass = 'block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5'

/** Admin list of the channels a finished run is posted to, with add, test and delete. */
export default function NotificationChannels() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [format, setFormat] = useState<NotificationFormat>('teams')
  const [url, setUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [runFilter, setRunFilter] = useState<NotificationRunFilter>('all')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const { data: channels, isLoading } = useQuery({
    queryKey: ['notificationChannels'],
    queryFn: notificationsApi.listChannels,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['notificationChannels'] })

  const create = useMutation({
    mutationFn: () =>
      notificationsApi.createChannel({
        name: name.trim(),
        format,
        url: url.trim(),
        secret: secret || undefined,
        run_filter: runFilter,
      }),
    onSuccess: () => {
      setName('')
      setUrl('')
      setSecret('')
      setMessage({ ok: true, text: 'Channel added.' })
      refresh()
    },
    onError: (error) => setMessage({ ok: false, text: extractApiErrorMessage(error, 'Could not add the channel') }),
  })

  const update = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      notificationsApi.updateChannel(id, { enabled }),
    onSuccess: refresh,
    onError: (error) => setMessage({ ok: false, text: extractApiErrorMessage(error, 'Could not update the channel') }),
  })

  const remove = useMutation({
    mutationFn: (id: number) => notificationsApi.deleteChannel(id),
    onSuccess: refresh,
    onError: (error) => setMessage({ ok: false, text: extractApiErrorMessage(error, 'Could not delete the channel') }),
  })

  const test = useMutation({
    mutationFn: (channel: NotificationChannel) => notificationsApi.testChannel(channel.id),
    onSuccess: (result, channel) =>
      setMessage(
        result.delivered
          ? { ok: true, text: `Test message delivered to ${channel.name}.` }
          : {
              ok: false,
              text: `${channel.name} did not accept the test message after ${result.attempts} attempt(s)${result.error ? `: ${result.error}` : ''}.`,
            },
      ),
    onError: (error) => setMessage({ ok: false, text: extractApiErrorMessage(error, 'Could not send the test message') }),
  })

  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30">
        <Bell className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Run notifications</h3>
      </div>
      <div className="p-5 space-y-4">
        <p className="text-xs text-muted-foreground">
          When a run finishes, Bud posts its result and a link to the run to these channels. Create an
          incoming webhook in Teams, Slack or Discord, or use any endpoint that accepts JSON. The URL
          and secret are stored encrypted and never shown again.
        </p>

        {message && (
          <p className={`text-xs ${message.ok ? 'text-emerald-600' : 'text-destructive'}`} role="status">
            {message.text}
          </p>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
          </div>
        ) : (
          <ul className="divide-y divide-border border border-border rounded-md">
            {(channels ?? []).map((channel) => (
              <li key={channel.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground">{channel.name}</p>
                  <p className="text-[11px] text-muted-foreground font-mono truncate">
                    {channel.format} · {FILTERS.find((f) => f.value === channel.run_filter)?.label ?? channel.run_filter} ·{' '}
                    {channel.url_prefix}
                  </p>
                </div>
                <label className="flex items-center gap-1 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={channel.enabled}
                    onChange={(e) => update.mutate({ id: channel.id, enabled: e.target.checked })}
                    aria-label={`Enable ${channel.name}`}
                  />
                  Enabled
                </label>
                <button
                  type="button"
                  onClick={() => test.mutate(channel)}
                  disabled={test.isPending}
                  title={`Send a test message to ${channel.name}`}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-foreground hover:bg-muted disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" /> Test
                </button>
                <button
                  type="button"
                  onClick={() => remove.mutate(channel.id)}
                  title={`Delete ${channel.name}`}
                  className="p-1 rounded text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
            {channels?.length === 0 && (
              <li className="px-3 py-3 text-xs text-muted-foreground">No channels yet.</li>
            )}
          </ul>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate()
          }}
          className="grid gap-3 sm:grid-cols-2"
        >
          <div>
            <label htmlFor="channel-name" className={labelClass}>Name</label>
            <input id="channel-name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="qa-results" className={inputClass} />
          </div>
          <div>
            <label htmlFor="channel-format" className={labelClass}>Format</label>
            <select id="channel-format" value={format} onChange={(e) => setFormat(e.target.value as NotificationFormat)} className={inputClass}>
              {FORMATS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="channel-url" className={labelClass}>Webhook URL</label>
            <input id="channel-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} required placeholder="https://..." className={`${inputClass} font-mono`} />
          </div>
          <div>
            <label htmlFor="channel-secret" className={labelClass}>Signing secret (optional)</label>
            <input id="channel-secret" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="HMAC secret for X-Bud-Signature" className={`${inputClass} font-mono`} />
          </div>
          <div>
            <label htmlFor="channel-filter" className={labelClass}>Post</label>
            <select id="channel-filter" value={runFilter} onChange={(e) => setRunFilter(e.target.value as NotificationRunFilter)} className={inputClass}>
              {FILTERS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <button
              type="submit"
              disabled={create.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
              Add channel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
