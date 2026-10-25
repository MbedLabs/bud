import { useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import AccessPeople from '../components/AccessPeople'
import AccessPolicies from '../components/AccessPolicies'
import AccessRequestsPanel from '../components/AccessRequestsPanel'
import AccessUsers from '../components/AccessUsers'
import UserGroups from '../components/UserGroups'
import { accessRequestsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { canManageAccess } from '../lib/access'

const TABS = [
  { key: 'assignments', label: 'Assignments' },
  { key: 'people', label: 'People' },
  { key: 'groups', label: 'Groups' },
  { key: 'policies', label: 'Policies' },
  { key: 'requests', label: 'Requests' },
] as const

type TabKey = (typeof TABS)[number]['key']

/**
 * Group assignments, each person's access, groups, policies and access requests for access managers.
 */
export default function AccessPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const allowed = canManageAccess(user)
  const { data: pending } = useQuery({
    queryKey: ['access-requests'],
    queryFn: () => accessRequestsApi.list({ status: 'pending' }),
    enabled: allowed,
  })

  if (!allowed) {
    return <div className="p-6 text-muted-foreground">Access management is required.</div>
  }

  const requested = params.get('tab')
  const tab: TabKey = TABS.some((t) => t.key === requested) ? (requested as TabKey) : 'assignments'
  const isAdmin = user?.role === 'admin'

  return (
    <div className="animate-fade-in space-y-6">
      <h1 className="sr-only">Access</h1>
      <div role="tablist" aria-label="Access" className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setParams({ tab: t.key })}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
            {t.key === 'requests' && pending && pending.length > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-bud-orange text-white text-[10px] font-semibold">
                {pending.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === 'assignments' && <AccessUsers />}
      {tab === 'people' && <AccessPeople />}
      {tab === 'groups' && <UserGroups />}
      {tab === 'policies' && <AccessPolicies canEdit={isAdmin} />}
      {tab === 'requests' && <AccessRequestsPanel />}
    </div>
  )
}
