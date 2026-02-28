import { useQuery } from '@tanstack/react-query'
import { runnersApi } from '../api/client'
import { Server, Wifi, WifiOff, Clock, MapPin, Monitor } from 'lucide-react'

export default function Runners() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['runners'],
    queryFn: runnersApi.status,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const runners = data?.runners || []
  const onlineCount = runners.filter(r => r.is_online).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Test Runners</h2>
          <p className="text-gray-500">
            {onlineCount} of {runners.length} runners online
          </p>
        </div>
      </div>

      {/* Runner List */}
      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          Loading runners...
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center text-red-600">
          Error loading runners
        </div>
      ) : runners.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <Server className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Runners Registered</h3>
          <p className="text-gray-500 max-w-md mx-auto">
            Runners are test execution agents that connect to run your test cases.
            Use the bud_runner CLI to register a runner.
          </p>
          <div className="mt-6 p-4 bg-gray-50 rounded-lg inline-block text-left">
            <code className="text-sm text-gray-700">
              bud_runner register --account my-runner --location "Lab 1"
            </code>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {runners.map((runner) => (
            <RunnerCard key={runner.account} runner={runner} />
          ))}
        </div>
      )}
    </div>
  )
}

interface RunnerInfo {
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

function RunnerCard({ runner }: { runner: RunnerInfo }) {
  return (
    <div className={`bg-white rounded-lg shadow-md overflow-hidden border-l-4 ${
      runner.is_online ? 'border-green-500' : 'border-gray-300'
    }`}>
      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center">
            <div className={`p-2 rounded-lg ${
              runner.is_online ? 'bg-green-100' : 'bg-gray-100'
            }`}>
              <Server className={`h-6 w-6 ${
                runner.is_online ? 'text-green-600' : 'text-gray-400'
              }`} />
            </div>
            <div className="ml-3">
              <h3 className="font-semibold text-gray-900">{runner.account}</h3>
              <div className="flex items-center mt-1">
                {runner.is_online ? (
                  <>
                    <Wifi className="h-4 w-4 text-green-500 mr-1" />
                    <span className="text-sm text-green-600">Online</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="h-4 w-4 text-gray-400 mr-1" />
                    <span className="text-sm text-gray-500">Offline</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="space-y-3">
          {runner.location && (
            <div className="flex items-center text-sm text-gray-600">
              <MapPin className="h-4 w-4 mr-2 text-gray-400" />
              {runner.location}
            </div>
          )}
          
          {runner.last_heartbeat && (
            <div className="flex items-center text-sm text-gray-600">
              <Clock className="h-4 w-4 mr-2 text-gray-400" />
              Last seen: {formatLastSeen(runner.last_heartbeat)}
            </div>
          )}

          {runner.current_run && (
            <div className="flex items-center text-sm">
              <Monitor className="h-4 w-4 mr-2 text-blue-500" />
              <span className="text-blue-600">
                Running: {runner.current_run.name}
              </span>
            </div>
          )}
        </div>

        {/* Status Bar */}
        {runner.is_online && !runner.current_run && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-center justify-center py-2 bg-green-50 rounded-lg">
              <span className="text-sm text-green-700 font-medium">Ready for Tests</span>
            </div>
          </div>
        )}

        {runner.is_online && runner.current_run && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-center justify-center py-2 bg-blue-50 rounded-lg">
              <div className="animate-pulse flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                <span className="text-sm text-blue-700 font-medium">Executing Tests</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
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
