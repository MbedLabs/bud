import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { extractApiErrorMessage, testStationsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import ConfirmDialog from '../components/ConfirmDialog'
import RowMenu from '../components/RowMenu'
import EnrolmentKeys from '../components/EnrolmentKeys'
import {
  Server, Wifi, WifiOff, Clock, MapPin, Monitor, Radio,
  Trash2, AlertTriangle, Pencil,
} from 'lucide-react'

const STATION_NAME = /^[a-zA-Z0-9_-]{3,50}$/

function isValidStationName(value: string): boolean {
  return STATION_NAME.test(value)
}

export default function TestStations() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const queryClient = useQueryClient()

  const [actionError, setActionError] = useState('')
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [newName, setNewName] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    refetchInterval: 15000,
  })

  // Shares its cache entry with EnrolmentKeys.
  const { data: apiKeys } = useQuery({
    queryKey: ['runnerApiKeys'],
    queryFn: testStationsApi.listApiKeys,
    enabled: isAdmin,
  })

  const removeStation = useMutation({
    mutationFn: testStationsApi.remove,
    onSuccess: () => {
      setActionError('')
      setPendingRemoval(null)
      queryClient.invalidateQueries({ queryKey: ['testStations'] })
      queryClient.invalidateQueries({ queryKey: ['runnerApiKeys'] })
    },
    onError: (error) =>
      setActionError(extractApiErrorMessage(error, 'Could not remove the Test Station')),
  })

  const renameStation = useMutation({
    mutationFn: ({ account, next }: { account: string; next: string }) =>
      testStationsApi.rename(account, next),
    onSuccess: () => {
      setActionError('')
      setRenaming(null)
      setNewName('')
      queryClient.invalidateQueries({ queryKey: ['testStations'] })
      queryClient.invalidateQueries({ queryKey: ['runnerApiKeys'] })
    },
    onError: (error) =>
      setActionError(extractApiErrorMessage(error, 'Could not rename the Test Station')),
  })

  const runners = data?.runners || []
  const onlineCount = runners.filter(r => r.is_online).length
  const keyedAccounts = new Set(
    (apiKeys || []).map(k => k.runner_account).filter((a): a is string => Boolean(a))
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Test Stations</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {onlineCount} of {runners.length} test stations online
          </p>
        </div>
      </div>

      {actionError && !pendingRemoval && !renaming && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {isAdmin && <EnrolmentKeys />}

      {isLoading ? (
        <div className="bg-card rounded-lg border border-border shadow-elegant p-8 text-center text-muted-foreground">
          Loading test stations...
        </div>
      ) : error ? (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6 text-center text-destructive">
          Error loading test stations
        </div>
      ) : runners.length === 0 ? (
        <div className="bg-card rounded-lg border border-border shadow-elegant p-16 text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/10 to-lime-500/10 flex items-center justify-center mx-auto mb-5">
            <Server className="h-10 w-10 text-primary/40" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No Test Stations Registered</h3>
          <p className="text-muted-foreground max-w-md mx-auto text-sm">
            A Test Station is a{' '}
            <span className="font-medium text-foreground">Bud runner</span> — the two
            are the same thing. Each location runs one or more of them, so a single
            machine can host several stations, each with its own account. Register one
            with the <code>bud_runner</code> CLI:
          </p>
          <div className="mt-6 p-3 bg-muted rounded-lg inline-block text-left">
            <code className="text-xs text-foreground font-mono block">
              export RUNNER_API_KEY=... # the key you created above
            </code>
            <code className="text-xs text-foreground font-mono block">
              export BUD_BACKEND_URL=&lt;your Bud backend URL&gt;
            </code>
            <code className="text-xs text-foreground font-mono block">
              bud_runner register --username my-station
            </code>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {runners.map((runner) => (
            <TestStationCard
              key={runner.account}
              runner={runner}
              isAdmin={isAdmin}
              hasKey={keyedAccounts.has(runner.account)}
              onRemove={() => {
                setActionError('')
                setPendingRemoval(runner.account)
              }}
              onRename={() => {
                setActionError('')
                setNewName(runner.account)
                setRenaming(runner.account)
              }}
            />
          ))}
        </div>
      )}
      {renaming && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setRenaming(null)}
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-label="Rename Test Station"
            className="bg-card rounded-lg shadow-elegant p-6 max-w-sm w-full mx-4"
            onClick={(event) => event.stopPropagation()}
            onSubmit={(event) => {
              event.preventDefault()
              if (isValidStationName(newName)) {
                renameStation.mutate({ account: renaming, next: newName })
              }
            }}
          >
            <h3 className="text-lg font-semibold text-foreground mb-2">Rename this Test Station?</h3>
            <p className="text-sm text-muted-foreground mb-4">
              The station keeps its credentials and its runs, and picks the new name up on its
              next heartbeat.
            </p>
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              aria-label="Rename station to"
              maxLength={50}
              autoFocus
              className="w-full mb-4 px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
            />
            {actionError && (
              <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
                {actionError}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setRenaming(null)
                  setActionError('')
                }}
                className="px-4 py-2 border border-input rounded-md text-foreground hover:bg-accent/50 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!isValidStationName(newName) || renameStation.isPending}
                className="px-4 py-2 bg-gradient-button text-white rounded-md hover:opacity-90 disabled:opacity-50 text-sm"
              >
                {renameStation.isPending ? 'Renaming...' : 'Rename'}
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingRemoval && (
        <ConfirmDialog
          title="Remove this Test Station?"
          body={`${pendingRemoval} loses its credentials and cannot upload until it registers again. Its runs are kept.`}
          confirmLabel="Remove"
          pendingLabel="Removing..."
          isPending={removeStation.isPending}
          error={actionError}
          onConfirm={() => removeStation.mutate(pendingRemoval)}
          onCancel={() => {
            setPendingRemoval(null)
            setActionError('')
          }}
        />
      )}
    </div>
  )
}

interface TestStationInfo {
  account: string
  is_online: boolean
  is_active?: boolean
  location?: string | null
  last_heartbeat?: string | null
  socket_port?: number
  current_run?: {
    id: number
    name: string
  }
}

function TestStationCard({
  runner,
  isAdmin,
  hasKey,
  onRemove,
  onRename,
}: {
  runner: TestStationInfo
  isAdmin: boolean
  hasKey: boolean
  onRemove: () => void
  onRename: () => void
}) {
  return (
    <Link
      to={`/runs?station=${encodeURIComponent(runner.account)}`}
      className={`block bg-card rounded-lg border shadow-elegant overflow-hidden transition-all duration-300 hover:shadow-glow group cursor-pointer ${
        runner.is_online
          ? 'border-primary/20 hover:border-primary/40'
          : 'border-border opacity-70'
      }`}
    >
      {/* Top accent bar */}
      <div className={`h-1 ${
        runner.is_online
          ? 'bg-gradient-to-r from-primary via-bud-forest to-bud-orange'
          : 'bg-muted'
      }`} />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              runner.is_online
                ? 'bg-primary/10 group-hover:bg-primary/20 transition-colors'
                : 'bg-muted'
            }`}>
              <Server className={`h-5 w-5 ${
                runner.is_online ? 'text-primary' : 'text-muted-foreground'
              }`} />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-foreground text-sm truncate">{runner.account}</h3>
              <div className="flex items-center mt-1 gap-1.5">
                {runner.is_online ? (
                  <>
                    <Radio className="h-3 w-3 text-emerald-500 animate-pulse" />
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Online</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3 w-3 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">Offline</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {isAdmin && (
            <RowMenu
              label={`Actions for ${runner.account}`}
              actions={[
                { label: 'Rename', icon: Pencil, onSelect: onRename },
                { label: 'Remove', icon: Trash2, onSelect: onRemove, destructive: true },
              ]}
            />
          )}
        </div>

        {isAdmin && !hasKey && (
          <div className="mb-4 flex items-start gap-2 p-2.5 rounded-md bg-amber-500/10 border border-amber-500/30">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-700 dark:text-amber-400">
              No enrolment key. Create one above and re-register this station.
            </p>
          </div>
        )}

        {/* Details */}
        <div className="space-y-2.5">
          {runner.location && (
            <div className="flex items-center text-xs text-muted-foreground min-w-0">
              <MapPin className="h-3.5 w-3.5 mr-2 text-muted-foreground/50 shrink-0" />
              <span className="truncate">{runner.location}</span>
            </div>
          )}

          {runner.last_heartbeat && (
            <div className="flex items-center text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5 mr-2 text-muted-foreground/50" />
              Last seen: {formatLastSeen(runner.last_heartbeat)}
            </div>
          )}

          {runner.current_run && (
            <div className="flex items-center text-xs min-w-0">
              <Monitor className="h-3.5 w-3.5 mr-2 text-amber-700 dark:text-amber-300 shrink-0" />
              <span className="text-amber-800 dark:text-amber-300 font-medium truncate">
                Running: {runner.current_run.name}
              </span>
            </div>
          )}
        </div>

        {/* Status Badge */}
        {runner.is_online && !runner.current_run && (
          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex items-center justify-center py-2 bg-emerald-500/10 rounded-md">
              <Wifi className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 mr-1.5" />
              <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Ready for Tests</span>
            </div>
          </div>
        )}

        {runner.is_online && runner.current_run && (
          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex items-center justify-center py-2 bg-amber-500/10 rounded-md">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-amber-500 rounded-full mr-2 animate-pulse" />
                <span className="text-xs text-amber-800 dark:text-amber-300 font-medium">Busy</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Link>
  )
}

function formatLastSeen(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} hours ago`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} days ago`

  return date.toLocaleDateString()
}
