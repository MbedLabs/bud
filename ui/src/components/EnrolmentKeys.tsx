import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { AlertTriangle, KeyRound, Plus, Trash2 } from 'lucide-react'
import { extractApiErrorMessage, testStationsApi } from '../api/client'
import type { RunnerApiKey, RunnerApiKeyCreated } from '../api/client'
import ConfirmDialog from './ConfirmDialog'
import RowMenu from './RowMenu'

/**
 * Administrator management for Test Station enrolment keys.
 *
 * The minted secret is held in component state only, never in localStorage or
 * sessionStorage.
 */
const STATION_NAME = /^[a-zA-Z0-9_-]{3,50}$/

function isValidStationName(value: string): boolean {
  return STATION_NAME.test(value)
}

export default function EnrolmentKeys() {
  const queryClient = useQueryClient()

  const [label, setLabel] = useState('')
  const [issued, setIssued] = useState<RunnerApiKeyCreated | null>(null)
  const [keyVisible, setKeyVisible] = useState(false)
  const [copied, setCopied] = useState(false)
  const [actionError, setActionError] = useState('')
  const [pendingRevoke, setPendingRevoke] = useState<RunnerApiKey | null>(null)

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
    onError: (error) => setActionError(extractApiErrorMessage(error, 'Could not create the key')),
  })

  const revokeKey = useMutation({
    mutationFn: testStationsApi.deleteApiKey,
    onSuccess: () => {
      setActionError('')
      setPendingRevoke(null)
      queryClient.invalidateQueries({ queryKey: ['runnerApiKeys'] })
      queryClient.invalidateQueries({ queryKey: ['testStations'] })
    },
    onError: (error) => setActionError(extractApiErrorMessage(error, 'Could not revoke the key')),
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
        The name you give a key is the name its Test Station takes, whatever the
        bench registers as. A key pins to the first station that uses it, and
        from then on only that station can.
      </p>

      {actionError && !pendingRevoke && (
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
          if (isValidStationName(label.trim())) createKey.mutate(label.trim())
        }}
      >
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Station name, e.g. bench-a"
          aria-label="New station name"
          maxLength={50}
          className="flex-1 min-w-0 px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
        />
        <button
          type="submit"
          disabled={!isValidStationName(label.trim()) || createKey.isPending}
          aria-label="Add station"
          title="Add station"
          className="px-3 py-2 bg-gradient-button text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
        >
          <Plus className="h-4 w-4" />
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
              <RowMenu
                label={`Actions for ${k.label}`}
                actions={[
                  {
                    label: 'Revoke',
                    icon: Trash2,
                    destructive: true,
                    onSelect: () => {
                      setActionError('')
                      setPendingRevoke(k)
                    },
                  },
                ]}
              />
            </li>
          ))}
        </ul>
      )}

      {pendingRevoke && (
        <ConfirmDialog
          title="Revoke this enrolment key?"
          body={
            pendingRevoke.runner_account
              ? `${pendingRevoke.label} enrolled ${pendingRevoke.runner_account}. Revoking it does not remove the station, but the station cannot register again without a new key.`
              : `${pendingRevoke.label} has not been used yet. Revoking it cannot be undone.`
          }
          confirmLabel="Revoke"
          pendingLabel="Revoking..."
          isPending={revokeKey.isPending}
          error={actionError}
          onConfirm={() => revokeKey.mutate(pendingRevoke.id)}
          onCancel={() => {
            setPendingRevoke(null)
            setActionError('')
          }}
        />
      )}
    </div>
  )
}
