import ProfilePicture from './ProfilePicture'
import SelectField from './SelectField'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { accessRequestsApi, extractApiErrorMessage, groupsApi, type AccessRequestInfo } from '../api/client'

function describe(request: AccessRequestInfo): string {
  if (request.resource_type === 'publish-to-bloom') return `Publish to Bloom (from run ${request.resource_ref})`
  if (request.resource_type === 'test-run') return `test run ${request.resource_ref}`
  return `product ${request.resource_ref}`
}

/**
 * Pending access requests. Granting Publish to Bloom gives the requester the chosen group
 * holding it (Test Operators by default); refusing records the answer.
 */
export default function AccessRequestsPanel() {
  const queryClient = useQueryClient()
  const queryKey = ['access-requests']
  const [chosen, setChosen] = useState<Record<number, number>>({})
  const { data: requests } = useQuery({
    queryKey,
    queryFn: () => accessRequestsApi.list({ status: 'pending' }),
  })
  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const publishing = (groups ?? []).filter((group) => group.permissions.includes('bloom_publish.execute'))
  const fallback = publishing.find((group) => group.system_key === 'test_operators') ?? publishing[0]

  const decide = useMutation({
    mutationFn: ({ id, decision, groupId }: { id: number; decision: 'granted' | 'refused'; groupId?: number }) =>
      accessRequestsApi.decide(id, decision, groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey })
      queryClient.invalidateQueries({ queryKey: ['groups'] })
      queryClient.invalidateQueries({ queryKey: ['access-users'] })
    },
  })

  return (
    <section className="bg-card border border-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-foreground mb-3">Access requests</h3>
      {(!requests || requests.length === 0) && <p className="text-sm text-muted-foreground">No pending requests.</p>}
      <ul className="divide-y divide-border">
        {requests?.map((request) => {
          const isPublish = request.resource_type === 'publish-to-bloom'
          const groupId = chosen[request.id] ?? fallback?.id
          return (
            <li key={request.id} className="py-3 flex flex-wrap items-center justify-between gap-3 text-sm">
              <span className="inline-flex items-center gap-2 text-foreground">
                {request.requester_name && <ProfilePicture user={{
                  full_name: request.requester_name,
                  profile_picture_url: request.requester_profile_picture_url ?? null,
                }} className="w-6 h-6" />}
                <span>{request.requester_name} ({request.requester_email}) asks for {describe(request)}</span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                {isPublish && (
                  <SelectField
                    value={groupId ?? ''}
                    onChange={(event) => setChosen({ ...chosen, [request.id]: Number(event.target.value) })}
                    aria-label={`Group to give ${request.requester_name}`}
                    className="px-2 py-1 bg-background border border-input rounded-md text-xs text-foreground"
                  >
                    {publishing.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </SelectField>
                )}
                <button
                  onClick={() =>
                    decide.mutate({ id: request.id, decision: 'granted', groupId: isPublish ? groupId : undefined })
                  }
                  disabled={isPublish && groupId === undefined}
                  className="px-2 py-1 rounded text-xs bg-primary text-white hover:bg-primary/90 disabled:opacity-50"
                >
                  {isPublish ? 'Grant' : 'Mark granted'}
                </button>
                <button
                  onClick={() => decide.mutate({ id: request.id, decision: 'refused' })}
                  className="px-2 py-1 rounded text-xs border border-border text-foreground hover:bg-muted"
                >
                  Refuse
                </button>
              </span>
            </li>
          )
        })}
      </ul>
      {decide.isError && <p className="text-sm text-destructive mt-2">{extractApiErrorMessage(decide.error)}</p>}
    </section>
  )
}
