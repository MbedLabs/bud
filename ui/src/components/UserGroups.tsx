import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Eye, Pencil, Plus, Trash2 } from 'lucide-react'
import {
  extractApiErrorMessage,
  groupsApi,
  policiesApi,
  type Group,
  type Policy,
} from '../api/client'
import ConfirmDialog from './ConfirmDialog'
import { AccessHeader, AccessModal } from './AccessTable'

const inputClass =
  'px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors'

/**
 * Groups: named bundles of policies given to users. Default groups are read-only and can
 * be duplicated; custom policy bundles are edited here.
 */
export default function UserGroups() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Group | 'new' | null>(null)
  const [viewing, setViewing] = useState<Group | null>(null)
  const [sortField, setSortField] = useState<'name' | 'policies'>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deleting, setDeleting] = useState<Group | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const { data: policies } = useQuery({ queryKey: ['policies'], queryFn: policiesApi.list })

  const change = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: (result) => {
      setError(null)
      if (editing === null && result && typeof result === 'object' && 'id' in result) setEditing(result as Group)
      else setEditing(null)
      setDeleting(null)
      queryClient.invalidateQueries({ queryKey: ['groups'] })
      queryClient.invalidateQueries({ queryKey: ['access-users'] })
    },
    onError: (failure) => setError(extractApiErrorMessage(failure, 'Could not change the group')),
  })
  const run = (action: () => Promise<unknown>) => change.mutate(action)

  const policyNames = (group: Group) => group.policies.map((policy) => policy.name).join(', ') || 'None'
  const sorted = [...(groups ?? [])].sort((a, b) => {
    const value = (group: Group) => sortField === 'name' ? group.name : policyNames(group)
    return value(a).localeCompare(value(b)) * (sortDir === 'asc' ? 1 : -1) || a.id - b.id
  })
  const toggleSort = (field: typeof sortField) => {
    setSortDir(field === sortField && sortDir === 'asc' ? 'desc' : 'asc')
    setSortField(field)
  }
  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-foreground">Groups</h2>
        <button onClick={() => setEditing('new')} className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90"><Plus className="h-4 w-4" /> New group</button>
      </div>
      {error && !editing && !deleting && <div role="alert" className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">{error}</div>}
      <div className="border border-border rounded-xl overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-muted/50 text-muted-foreground"><tr>
          {(['name', 'policies'] as const).map((field) => <AccessHeader key={field} field={field} sortField={sortField} sortDir={sortDir} onSort={toggleSort}>{field === 'name' ? 'Name' : 'Policies'}</AccessHeader>)}
          <th className="px-4 py-2" />
        </tr></thead>
        <tbody>{sorted.map((group) => <tr key={group.id} className="border-t border-border">
          <td className="px-4 py-2 text-foreground font-medium">{group.name}{group.is_default && <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-muted text-muted-foreground">Default</span>}</td>
          <td className="px-4 py-2 text-muted-foreground">{policyNames(group)}</td>
          <td className="px-4 py-2"><div className="flex items-center justify-end gap-1">
            <button onClick={() => setViewing(group)} aria-label={`View ${group.name}`} title={`View ${group.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Eye className="h-3.5 w-3.5" /></button>
            {group.is_default ? <button onClick={() => run(() => groupsApi.duplicate(group.id))} disabled={change.isPending} aria-label={`Duplicate ${group.name}`} title={`Duplicate ${group.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Copy className="h-3.5 w-3.5" /></button> : <>
              <button onClick={() => setEditing(group)} aria-label={`Edit ${group.name}`} title={`Edit ${group.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Pencil className="h-3.5 w-3.5" /></button>
              <button onClick={() => setDeleting(group)} aria-label={`Delete ${group.name}`} title={`Delete ${group.name}`} className="p-1 rounded text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
            </>}
          </div></td>
        </tr>)}</tbody>
      </table></div>
      {viewing && <GroupEditor group={viewing} policies={policies ?? []} readOnly isPending={false} error={null} onCancel={() => setViewing(null)} onSave={() => undefined} />}

      {editing && (
        <GroupEditor
          group={editing === 'new' ? null : editing}
          policies={policies ?? []}
          isPending={change.isPending}
          error={error}
          onCancel={() => {
            setEditing(null)
            setError(null)
          }}
          onSave={(data) =>
            run(() =>
              editing === 'new'
                ? groupsApi.create({ ...data, name: data.name ?? '' })
                : groupsApi.update(editing.id, data),
            )
          }
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete group"
          body={`Delete ${deleting.name}? Its members keep their base role and their other groups.`}
          confirmLabel="Delete"
          pendingLabel="Deleting…"
          isPending={change.isPending}
          error={error ?? ''}
          onConfirm={() => run(() => groupsApi.remove(deleting.id))}
          onCancel={() => {
            setDeleting(null)
            setError(null)
          }}
        />
      )}
    </section>
  )
}

function GroupEditor({
  group,
  policies,
  readOnly = false,
  isPending,
  error,
  onCancel,
  onSave,
}: Readonly<{
  group: Group | null
  policies: Policy[]
  readOnly?: boolean
  isPending: boolean
  error: string | null
  onCancel: () => void
  onSave: (data: { name?: string; description?: string | null; policy_ids: number[] }) => void
}>) {
  const [name, setName] = useState(group?.name ?? '')
  const [description, setDescription] = useState(group?.description ?? '')
  const [selected, setSelected] = useState<Set<number>>(new Set(group?.policies.map((policy) => policy.id)))

  const toggle = (id: number) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <AccessModal title={readOnly ? 'View group' : group ? 'Edit group' : 'New group'} onClose={onCancel}>
      {error && <div role="alert" className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">{error}</div>}
      <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!readOnly) onSave({ name: name.trim(), description: description.trim() || null, policy_ids: [...selected] }) }}>
        <label className="block text-sm font-medium text-foreground">Name<input value={name} onChange={(event) => setName(event.target.value)} aria-label="Group name" required readOnly={readOnly} className={`${inputClass} w-full`} /></label>
        <label className="block text-sm font-medium text-foreground">Description<input value={description} onChange={(event) => setDescription(event.target.value)} aria-label="Group description" readOnly={readOnly} className={`${inputClass} w-full`} /></label>
        <fieldset><legend className="text-sm font-medium text-foreground mb-2">Policies</legend>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">{policies.map((policy) => <label key={policy.id} className="flex items-start gap-2 text-sm text-foreground"><input type="checkbox" checked={selected.has(policy.id)} disabled={readOnly} onChange={() => toggle(policy.id)} className="mt-0.5" /><span>{policy.name}{policy.description && <span className="block text-xs text-muted-foreground">{policy.description}</span>}</span></label>)}</div>
        </fieldset>
        {!readOnly && <button type="submit" disabled={!name.trim() || isPending} className="w-full py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50">{isPending ? 'Saving…' : 'Save group'}</button>}
      </form>
    </AccessModal>
  )
}
