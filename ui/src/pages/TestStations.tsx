import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { testStationsApi } from '../api/client'
import { Server, Wifi, WifiOff, Clock, MapPin, Monitor, Radio } from 'lucide-react'

export default function TestStations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['testStations'],
    queryFn: testStationsApi.status,
    refetchInterval: 15000,
  })

  const runners = data?.runners || []
  const onlineCount = runners.filter(r => r.is_online).length

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
            A Test Station is a host where tests execute. Each station registers
            one or more <span className="font-medium text-foreground">Bud runners</span>{' '}
            (the execution agents). Register one with the <code>bud_runner</code> CLI:
          </p>
          <div className="mt-6 p-3 bg-muted rounded-lg inline-block text-left">
            <code className="text-xs text-foreground font-mono block">
              export RUNNER_API_KEY=... # shared secret from the Bud backend
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
            <TestStationCard key={runner.account} runner={runner} />
          ))}
        </div>
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

function TestStationCard({ runner }: { runner: TestStationInfo }) {
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
        </div>

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
