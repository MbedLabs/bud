import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { testRunsApi, runnersApi } from '../api/client'
import { CheckCircle, XCircle, PlayCircle, Server } from 'lucide-react'

export default function Dashboard() {
  const { data: testRunsData, isLoading: runsLoading } = useQuery({
    queryKey: ['testRuns', { limit: 5 }],
    queryFn: () => testRunsApi.list({ limit: 5 }),
  })

  const { data: runnersData, isLoading: runnersLoading } = useQuery({
    queryKey: ['runners'],
    queryFn: runnersApi.status,
  })

  const runs = testRunsData?.runs || []
  const runners = runnersData?.runners || []

  // Calculate stats
  const totalRuns = testRunsData?.total || 0
  const passedRuns = runs.filter(r => r.status === 'Completed' && r.failed_tests === 0).length
  const failedRuns = runs.filter(r => r.status === 'Failed' || r.failed_tests > 0).length
  const onlineRunners = runners.filter(r => r.is_online).length

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard
          title="Total Test Runs"
          value={totalRuns}
          icon={PlayCircle}
          color="bg-blue-500"
        />
        <StatCard
          title="Passed"
          value={passedRuns}
          icon={CheckCircle}
          color="bg-green-500"
        />
        <StatCard
          title="Failed"
          value={failedRuns}
          icon={XCircle}
          color="bg-red-500"
        />
        <StatCard
          title="Online Runners"
          value={`${onlineRunners}/${runners.length}`}
          icon={Server}
          color="bg-purple-500"
        />
      </div>

      {/* Recent Test Runs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-semibold">Recent Test Runs</h3>
          <Link to="/runs" className="text-sm text-primary-600 hover:text-primary-700">
            View all →
          </Link>
        </div>
        
        {runsLoading ? (
          <div className="p-6 text-center text-gray-500">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="p-6 text-center text-gray-500">No test runs yet</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {runs.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="block px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{run.name}</p>
                    <p className="text-sm text-gray-500">{run.test_case_list}</p>
                  </div>
                  <div className="flex items-center space-x-4">
                    <StatusBadge status={run.status} />
                    <div className="text-sm text-gray-500">
                      {run.passed_tests}/{run.total_tests} passed
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Runners Status */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-semibold">Runner Status</h3>
          <Link to="/runners" className="text-sm text-primary-600 hover:text-primary-700">
            Manage →
          </Link>
        </div>
        
        {runnersLoading ? (
          <div className="p-6 text-center text-gray-500">Loading...</div>
        ) : runners.length === 0 ? (
          <div className="p-6 text-center text-gray-500">No runners registered</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {runners.map((runner) => (
              <div key={runner.account} className="px-6 py-4 flex items-center justify-between">
                <div className="flex items-center">
                  <div className={`w-3 h-3 rounded-full mr-3 ${
                    runner.is_online ? 'bg-green-500' : 'bg-gray-400'
                  }`} />
                  <div>
                    <p className="font-medium text-gray-900">{runner.account}</p>
                    <p className="text-sm text-gray-500">{runner.location || 'Unknown location'}</p>
                  </div>
                </div>
                <span className={`text-sm ${runner.is_online ? 'text-green-600' : 'text-gray-500'}`}>
                  {runner.is_online ? 'Online' : 'Offline'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ title, value, icon: Icon, color }: {
  title: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  color: string
}) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center">
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div className="ml-4">
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    Pending: 'bg-gray-100 text-gray-800',
    Running: 'bg-blue-100 text-blue-800',
    Completed: 'bg-green-100 text-green-800',
    Failed: 'bg-red-100 text-red-800',
    Cancelled: 'bg-yellow-100 text-yellow-800',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || colors.Pending}`}>
      {status}
    </span>
  )
}
