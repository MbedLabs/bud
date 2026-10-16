import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api, extractApiErrorMessage } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { can } from '../lib/access'

type ReportRequest = {
  id: number
  run_id: number
  run_name: string
  run_status: string | null
  project_prefix: string
  requester_name: string
  requester_email: string
}

export default function ReportRequests({ runId }: Readonly<{ runId?: number }>) {
  const { user } = useAuth()
  const client = useQueryClient()
  const [refusing, setRefusing] = useState<number | null>(null)
  const [reason, setReason] = useState('')
  const requests = useQuery({
    queryKey: ['report-requests', user?.id, runId],
    enabled: can(user, 'bloom_publish.execute'),
    queryFn: async () => (await api.get<ReportRequest[]>('/report-requests', { params: { run_id: runId } })).data,
    refetchInterval: 30000,
  })
  const decide = useMutation({
    mutationFn: ({ row, refuse }: { row: ReportRequest; refuse: boolean }): Promise<unknown> => refuse
      ? api.post(`/report-requests/${row.id}/refuse`, { reason })
      : api.post(`/report-requests/${row.id}/publish`, {}),
    onSuccess: () => {
      setRefusing(null)
      setReason('')
      void client.invalidateQueries({ queryKey: ['report-requests'] })
      void client.invalidateQueries({ queryKey: ['testRunEvents'] })
    },
  })
  if (!can(user, 'bloom_publish.execute')) return null
  if (requests.isError) return <p role="alert" className="text-sm text-destructive">Could not load report requests.</p>
  if (!requests.data?.length) return null
  return (
    <section className="bg-card border border-border rounded-lg overflow-hidden">
      <h3 className="px-5 py-4 border-b border-border font-semibold">Report requests</h3>
      {requests.data.map((row) => (
        <div key={row.id} className="px-5 py-4 border-b last:border-b-0 border-border space-y-3">
          <div className="text-sm">
            <span className="font-medium">{row.requester_name}</span>
            <span className="text-muted-foreground"> ({row.requester_email}) · {row.project_prefix}</span>
            <div><Link className="text-primary hover:text-primary/80" to={`/runs/${row.run_id}`}>{row.run_name}</Link></div>
          </div>
          {refusing === row.id ? (
            <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); decide.mutate({ row, refuse: true }) }}>
              <label className="block text-sm">Reason
                <textarea required maxLength={2000} aria-label="Refusal reason" value={reason} onChange={(event) => setReason(event.target.value)}
                  className="mt-1 block w-full rounded border border-border bg-background px-3 py-2" />
              </label>
              <div className="flex gap-2">
                <button type="submit" disabled={decide.isPending || !reason.trim()} className="px-3 py-2 text-sm rounded bg-primary text-primary-foreground disabled:opacity-50">Refuse request</button>
                <button type="button" disabled={decide.isPending} onClick={() => { setRefusing(null); setReason('') }} className="px-3 py-2 text-sm rounded border border-border">Cancel</button>
              </div>
            </form>
          ) : <div className="flex gap-2">
            <button type="button" disabled={decide.isPending || row.run_status !== 'Completed'} onClick={() => decide.mutate({ row, refuse: false })}
              className="px-3 py-2 text-sm rounded bg-primary text-primary-foreground disabled:opacity-50">Publish report</button>
            <button type="button" disabled={decide.isPending} onClick={() => { decide.reset(); setRefusing(row.id) }}
              className="px-3 py-2 text-sm rounded border border-border hover:bg-accent">Refuse</button>
          </div>}
        </div>
      ))}
      {decide.isError && <p role="alert" className="px-5 py-3 text-sm text-destructive">{extractApiErrorMessage(decide.error, 'Could not complete the request')}</p>}
    </section>
  )
}
