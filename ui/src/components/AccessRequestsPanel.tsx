import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { accessRequestsApi, extractApiErrorMessage } from '../api/client'

/** Pending access requests, for an administrator to mark granted or refused. */
export default function AccessRequestsPanel() {
  const queryClient = useQueryClient()
  const queryKey = ['access-requests']
  const { data: requests } = useQuery({
    queryKey,
    queryFn: () => accessRequestsApi.list({ status: 'pending' }),
  })
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: 'granted' | 'refused' }) =>
      accessRequestsApi.decide(id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  if (!requests || requests.length === 0) return null

  return (
    <section className="bg-card border border-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-foreground mb-3">Access requests</h3>
      <ul className="divide-y divide-border">
        {requests.map((request) => (
          <li key={request.id} className="py-2 flex items-center justify-between gap-3 text-sm">
            <span className="text-foreground">
              {request.requester_name} ({request.requester_email}) asks for{' '}
              {request.resource_type === 'test-run' ? `test run ${request.resource_ref}` : `product ${request.resource_ref}`}
            </span>
            <span className="flex gap-2">
              <button
                onClick={() => decide.mutate({ id: request.id, decision: 'granted' })}
                className="px-2 py-1 rounded text-xs bg-primary text-white hover:bg-primary/90"
              >
                Mark granted
              </button>
              <button
                onClick={() => decide.mutate({ id: request.id, decision: 'refused' })}
                className="px-2 py-1 rounded text-xs border border-border text-foreground hover:bg-muted"
              >
                Refuse
              </button>
            </span>
          </li>
        ))}
      </ul>
      {decide.isError && (
        <p className="text-sm text-destructive mt-2">{extractApiErrorMessage(decide.error)}</p>
      )}
    </section>
  )
}
