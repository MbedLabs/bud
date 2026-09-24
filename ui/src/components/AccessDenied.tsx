import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldAlert } from 'lucide-react'
import {
  accessRequestsApi,
  extractApiErrorMessage,
  type AccessRequestInfo,
  type AccessResourceType,
} from '../api/client'

interface AccessDeniedProps {
  resourceType: AccessResourceType
  resourceRef: string
}

function formatDate(value: string): string {
  return value.replace('T', ' ').slice(0, 16) + ' UTC'
}

/**
 * The page shown when a resource is refused (403) or not visible (404): it names the
 * resource only by what the address already says, and lets the user ask the
 * administrators for access once per day.
 */
export default function AccessDenied({ resourceType, resourceRef }: AccessDeniedProps) {
  const queryClient = useQueryClient()
  const params = { resource_type: resourceType, resource_ref: resourceRef }
  const queryKey = ['access-request', resourceType, resourceRef]
  const { data: existing } = useQuery({ queryKey, queryFn: () => accessRequestsApi.mine(params) })
  const create = useMutation({
    mutationFn: () => accessRequestsApi.create(params),
    onSuccess: (created) => queryClient.setQueryData<AccessRequestInfo | null>(queryKey, created),
  })
  const request = create.data ?? existing ?? null
  const label = resourceType === 'test-run' ? `Test run ${resourceRef}` : `Product ${resourceRef}`

  return (
    <div className="max-w-lg mx-auto mt-16 bg-card border border-border rounded-xl p-8 text-center">
      <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-destructive/10 flex items-center justify-center">
        <ShieldAlert className="h-6 w-6 text-destructive" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">You don&apos;t have access to this resource</h2>
      <p className="text-sm text-muted-foreground mt-2">{label}</p>
      {request === null && (
        <button
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className="mt-6 inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          Request access
        </button>
      )}
      {request?.status === 'pending' && (
        <p className="text-sm text-foreground mt-6">
          {request.already_requested && !create.data
            ? `A request is already pending since ${formatDate(request.created_at)}.`
            : `Access requested on ${formatDate(request.created_at)}.`}
        </p>
      )}
      {request?.status === 'pending' && create.data?.mail_sent === false && (
        <p className="text-sm text-destructive mt-2">
          Your request is recorded, but the email to the administrators could not be sent. Tell an administrator directly.
        </p>
      )}
      {request?.status === 'granted' && (
        <p className="text-sm text-foreground mt-6">
          An administrator granted this request. Reload the page once your access is in place.
        </p>
      )}
      {request?.status === 'refused' && (
        <p className="text-sm text-foreground mt-6">
          An administrator refused this request on {formatDate(request.decided_at ?? request.created_at)}.
        </p>
      )}
      {create.isError && (
        <p className="text-sm text-destructive mt-2">{extractApiErrorMessage(create.error)}</p>
      )}
    </div>
  )
}
