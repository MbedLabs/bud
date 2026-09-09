import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { AlertTriangle, KeyRound, Plus, Trash2 } from 'lucide-react'
import { testStationsApi } from '../api/client'
import type { RunnerApiKeyCreated } from '../api/client'

/**
 * Administrator management for Test Station enrolment keys.
 *
 * The minted secret is held in component state only, never in localStorage or
 * sessionStorage.
 */
export default function EnrolmentKeys() {
  const queryClient = useQueryClient()

  const [label, setLabel] = useState('')
  const [issued, setIssued] = useState<RunnerApiKeyCreated | null>(null)
  const [keyVisible, setKeyVisible] = useState(false)
  const [copied, setCopied] = useState(false)
  const [actionError, setActionError] = useState('')

  const { data: apiKeys } = useQuery({
    queryKey: ['runnerApiKeys'],
    queryFn: testStationsApi.listApiKeys,
  })

  const createKey = useMutation({
    mutationFn: testStationsApi.createApiKey,
    onSuccess: (created) => {
      setIssued(created)
      setKeyVisible(false)
      setCopied(false)
      setLabel('')
      setActionError('')
      queryClient.invalidateQueries({ queryKey: ['runnerApiKeys'] })
    },
    onError: () => setActionError('Could not create the key.'),
  })

  const revokeKey = useMutation({
    mutationFn: testStationsApi.deleteApiKey,
    onSuccess: () => {
      setActionError('')
      queryClient.invalidateQueries({ queryKey: ['runnerApiKeys'] })
    },
    onError: () => setActionError('Could not revoke the key.'),
  })

  const copyIssued = async () => {
    if (!issued) return
    try {
      await navigator.clipboard.writeText(issued.api_key)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const keys = apiKeys || []

  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant p-5">
      <div className="flex items-center gap-2 mb-1">
        <KeyRound className="h-4 w-4 text-primary" />
        <h3 className="font-semibold text-foreground text-sm">Enrolment keys</h3>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Each key belongs to one Test Station. It pins to the first station that
        registers with it, and from then on only that station can use it.
      </p>

      {actionError && (
        <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {issued && (
        <div className="mb-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <div className="flex items-start gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              <strong>Shown once.</strong> Copy it onto the bench now &mdash; it is not
              stored and cannot be retrieved afterwards.
            </p>
          </div>
          <div className="flex gap-2">
            <input
              readOnly
              type={keyVisible ? 'text' : 'password'}
              value={issued.api_key}
              aria-label="New Test Station API key"
              className="flex-1 min-w-0 px-3 py-2 bg-background border border-input rounded-lg text-sm font-mono text-foreground"
            />
            <button
              type="button"
              onClick={() => setKeyVisible((v) => !v)}
              aria-label={keyVisible ? 'Hide key' : 'Show key'}
              className="px-3 py-2 border border-input rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
            >
              {keyVisible ? 'Hide' : 'Show'}
            </button>
            <button
              type="button"
              onClick={copyIssued}
              className="px-3 py-2 border border-input rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              type="button"
              onClick={() => setIssued(null)}
              className="px-3 py-2 border border-input rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}

      <form
        className="flex gap-2 mb-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (label.trim()) createKey.mutate(label.trim())
        }}
      >
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label, e.g. bench-a"
          aria-label="New key label"
          maxLength={100}
          className="flex-1 min-w-0 px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
        />
        <button
          type="submit"
          disabled={!label.trim() || createKey.isPending}
          className="px-3 py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1.5"
        >
          <Plus className="h-4 w-4" />
          {createKey.isPending ? 'Creating...' : 'New key'}
        </button>
      </form>

      {keys.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No keys yet. A station cannot enrol until one exists.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {keys.map((k) => (
            <li key={k.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="text-sm text-foreground truncate">{k.label}</p>
                <p className="text-xs text-muted-foreground truncate">
                  <span className="font-mono">{k.key_prefix}&hellip;</span>{' '}
                  {k.runner_account ? (
                    <>&middot; {k.runner_account}</>
                  ) : (
                    <span className="italic">
                      &middot; unused &mdash; pins to the first station that registers
                    </span>
                  )}
                </p>
              </div>
              <button
                type="button"
                onClick={() => revokeKey.mutate(k.id)}
                aria-label={`Revoke key ${k.label}`}
                className="p-2 text-muted-foreground hover:text-destructive transition-colors shrink-0"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
