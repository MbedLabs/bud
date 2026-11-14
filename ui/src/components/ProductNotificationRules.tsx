import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Loader2, Plus, Trash2 } from 'lucide-react'
import {
  extractApiErrorMessage,
  productsApi,
  type NotificationRunFilter,
  type ProductNotificationRule,
} from '../api/client'
import { FILTER_OPTIONS, formatLabel } from '../lib/notifications'
import Select from './Select'

const labelClass = 'block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5'

/** Whether a failed request was refused for missing products management on the product. */
function isForbidden(error: unknown): boolean {
  return (error as { response?: { status?: number } } | null)?.response?.status === 403
}

/** A product's notification rules: the channels its finished runs are posted to, with their filters. */
export default function ProductNotificationRules({ productId }: Readonly<{ productId: number }>) {
  const queryClient = useQueryClient()
  const [channelId, setChannelId] = useState('')
  const [runFilter, setRunFilter] = useState<NotificationRunFilter>('all')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const rulesKey = ['productNotificationRules', productId]

  const rules = useQuery({
    queryKey: rulesKey,
    queryFn: () => productsApi.notificationRules(productId),
    retry: false,
  })
  const channels = useQuery({
    queryKey: ['productNotificationChannels', productId],
    queryFn: () => productsApi.notificationChannels(productId),
    enabled: rules.isSuccess,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: rulesKey })
  const fail = (fallback: string) => (error: unknown) =>
    setMessage({ ok: false, text: extractApiErrorMessage(error, fallback) })

  const create = useMutation({
    mutationFn: () =>
      productsApi.createNotificationRule(productId, { channel_id: Number(channelId), run_filter: runFilter }),
    onSuccess: (rule) => {
      setChannelId('')
      setRunFilter('all')
      setMessage({ ok: true, text: `Runs are posted to ${rule.channel_name}.` })
      void refresh()
    },
    onError: fail('Could not add the rule'),
  })
  const update = useMutation({
    mutationFn: ({ rule, filter }: { rule: ProductNotificationRule; filter: NotificationRunFilter }) =>
      productsApi.updateNotificationRule(productId, rule.id, { run_filter: filter }),
    onSuccess: refresh,
    onError: fail('Could not change the rule'),
  })
  const remove = useMutation({
    mutationFn: (rule: ProductNotificationRule) => productsApi.deleteNotificationRule(productId, rule.id),
    onSuccess: refresh,
    onError: fail('Could not remove the rule'),
  })

  if (rules.isError && isForbidden(rules.error)) {
    return (
      <p className="text-sm text-muted-foreground">
        Product management on this product is required to see and change where its runs are posted.
      </p>
    )
  }

  const used = new Set((rules.data ?? []).map((rule) => rule.channel_id))
  const choices = (channels.data ?? [])
    .filter((channel) => !used.has(channel.id))
    .map((channel) => ({ value: String(channel.id), label: `${channel.name} (${formatLabel(channel.format)})` }))
  const noChoice = channels.isSuccess
    ? 'Every channel already has a rule on this product, or no channel exists in Settings.'
    : 'Loading channels...'

  return (
    <section aria-labelledby="product-notifications" className="bg-card rounded-lg border border-border shadow-elegant">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2 bg-muted/30 rounded-t-lg">
        <Bell className="h-4 w-4 text-primary" />
        <h3 id="product-notifications" className="text-sm font-semibold text-foreground">Notifications</h3>
      </div>
      <div className="p-5 space-y-4">
        <p className="text-xs text-muted-foreground">
          Finished runs of this product are posted to these channels, in addition to the channels set for all products in Settings.
        </p>
        {message && (
          <output className={`block text-xs ${message.ok ? 'text-emerald-600' : 'text-destructive'}`}>{message.text}</output>
        )}
        {rules.isLoading && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
          </div>
        )}
        {rules.isError && !isForbidden(rules.error) && (
          <p role="alert" className="text-sm text-destructive">Could not load the notification rules.</p>
        )}
        {rules.isSuccess && (
          <ul className="divide-y divide-border border border-border rounded-md">
            {rules.data.map((rule) => (
              <li key={rule.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground break-words">{rule.channel_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatLabel(rule.channel_format)}
                    {rule.channel_enabled ? '' : ' · Channel disabled'}
                  </p>
                </div>
                <Select
                  label={`Post to ${rule.channel_name}`}
                  value={rule.run_filter}
                  onChange={(filter) => update.mutate({ rule, filter })}
                  options={FILTER_OPTIONS}
                  wrapperClassName="w-full sm:w-64"
                />
                <button
                  type="button"
                  onClick={() => remove.mutate(rule)}
                  aria-label={`Remove the rule for ${rule.channel_name}`}
                  title={`Remove the rule for ${rule.channel_name}`}
                  className="p-1 rounded text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
            {rules.data.length === 0 && (
              <li className="px-3 py-3 text-xs text-muted-foreground">No rules: only the channels for all products receive this product's runs.</li>
            )}
          </ul>
        )}
        {rules.isSuccess && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (channelId) create.mutate()
            }}
            className="grid gap-3 sm:grid-cols-2"
          >
            <div>
              {choices.length > 0 ? (
                <>
                  <label htmlFor="rule-channel" className={labelClass}>Channel</label>
                  <Select
                    id="rule-channel"
                    label="Channel"
                    value={channelId}
                    onChange={setChannelId}
                    options={[{ value: '', label: 'Choose a channel', disabled: true }, ...choices]}
                  />
                </>
              ) : (
                <>
                  <p className={labelClass}>Channel</p>
                  <p className="text-xs text-muted-foreground py-2">{noChoice}</p>
                </>
              )}
            </div>
            <div>
              <label htmlFor="rule-filter" className={labelClass}>Post</label>
              <Select id="rule-filter" label="Post" value={runFilter} onChange={setRunFilter} options={FILTER_OPTIONS} />
            </div>
            <div className="sm:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={!channelId || create.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Add rule
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  )
}
