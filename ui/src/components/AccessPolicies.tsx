import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Eye, Pencil, Plus, Trash2 } from 'lucide-react'
import {
  extractApiErrorMessage,
  policiesApi,
  type CatalogueResource,
  type PermissionMatrix,
  type Policy,
} from '../api/client'
import { ACTION_LABELS, RESOURCE_LABELS } from '../lib/access'
import ConfirmDialog from './ConfirmDialog'
import { AccessHeader, AccessModal } from './AccessTable'

const inputClass =
  'px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors'

/**
 * Policies: person-agnostic permission sets that groups bundle. Each shows the rights it
 * covers. Defaults are read-only; an Admin duplicates one to customise it.
 */
export default function AccessPolicies({ canEdit }: Readonly<{ canEdit: boolean }>) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Policy | 'new' | null>(null)
  const [viewing, setViewing] = useState<Policy | null>(null)
  const [sortField, setSortField] = useState<'name' | 'permissions'>('name')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [deleting, setDeleting] = useState<Policy | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data: policies } = useQuery({ queryKey: ['policies'], queryFn: policiesApi.list })
  const { data: catalogue } = useQuery({ queryKey: ['policy-catalogue'], queryFn: policiesApi.catalogue })

  const change = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: (result) => {
      setError(null)
      if (editing === null && result && typeof result === 'object' && 'id' in result) setEditing(result as Policy)
      else setEditing(null)
      setDeleting(null)
      void queryClient.invalidateQueries({ queryKey: ['policies'] })
      void queryClient.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (failure) => setError(extractApiErrorMessage(failure, 'Could not change the policy')),
  })
  const run = (action: () => Promise<unknown>) => change.mutate(action)

  const summaries = (policy: Policy) => {
    const entries = Object.entries(policy.permissions).map(([resource, actions]) => {
      const labels = [...new Set(actions.map((action) => ACTION_LABELS[action] ?? action))]
      return { resource, rights: (labels.includes('Write') ? labels.filter((label) => label !== 'Read') : labels).join(', ') }
    })
    if (entries.length === 0) return ['None']
    if (new Set(entries.map((entry) => entry.rights)).size === 1) return [entries[0].rights]
    return entries.map((entry) => `${RESOURCE_LABELS[entry.resource] ?? entry.resource}: ${entry.rights}`)
  }
  const sorted = [...(policies ?? [])].sort((a, b) => {
    const value = (policy: Policy) => sortField === 'name' ? policy.name : summaries(policy).join(', ')
    return value(a).localeCompare(value(b)) * (sortDir === 'asc' ? 1 : -1) || a.id - b.id
  })
  const toggleSort = (field: typeof sortField) => {
    setSortDir(field === sortField && sortDir === 'asc' ? 'desc' : 'asc')
    setSortField(field)
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <div><h2 className="text-xl font-semibold text-foreground">Policies</h2></div>
        {canEdit && <button onClick={() => setEditing('new')} className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90"><Plus className="h-4 w-4" /> New policy</button>}
      </div>
      {error && !editing && !deleting && <div role="alert" className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">{error}</div>}
      <div className="border border-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground"><tr>
            {(['name', 'permissions'] as const).map((field) => <AccessHeader key={field} field={field} sortField={sortField} sortDir={sortDir} onSort={toggleSort}>{field.charAt(0).toUpperCase() + field.slice(1)}</AccessHeader>)}
            <th className="px-4 py-2" />
          </tr></thead>
          <tbody>{sorted.map((policy) => <tr key={policy.id} className="border-t border-border">
            <td className="px-4 py-2 text-foreground font-medium">{policy.name}{policy.is_default && <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-muted text-muted-foreground">Default</span>}</td>
            <td className="px-4 py-2 text-muted-foreground">{summaries(policy).map((summary) => <div key={summary}>{summary}</div>)}</td>
            <td className="px-4 py-2"><div className="flex items-center justify-end gap-1">
              <button onClick={() => setViewing(policy)} aria-label={`View ${policy.name}`} title={`View ${policy.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Eye className="h-3.5 w-3.5" /></button>
              {canEdit && (policy.is_default ? <button onClick={() => run(() => policiesApi.duplicate(policy.id))} disabled={change.isPending} aria-label={`Duplicate ${policy.name}`} title={`Duplicate ${policy.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Copy className="h-3.5 w-3.5" /></button> : <>
                <button onClick={() => setEditing(policy)} aria-label={`Edit ${policy.name}`} title={`Edit ${policy.name}`} className="p-1 rounded text-muted-foreground hover:text-foreground"><Pencil className="h-3.5 w-3.5" /></button>
                <button onClick={() => setDeleting(policy)} aria-label={`Delete ${policy.name}`} title={`Delete ${policy.name}`} className="p-1 rounded text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
              </>)}
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>
      {viewing && <PolicyEditor policy={viewing} catalogue={catalogue ?? []} readOnly isPending={false} error={null} onCancel={() => setViewing(null)} onSave={() => undefined} />}

      {editing && (
        <PolicyEditor
          policy={editing === 'new' ? null : editing}
          catalogue={catalogue ?? []}
          isPending={change.isPending}
          error={error}
          onCancel={() => {
            setEditing(null)
            setError(null)
          }}
          onSave={(data) =>
            run(() =>
              editing === 'new'
                ? policiesApi.create({ ...data, name: data.name ?? '' })
                : policiesApi.update(editing.id, data),
            )
          }
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete policy"
          body={`Delete ${deleting.name}? A policy that a group uses cannot be deleted.`}
          confirmLabel="Delete"
          pendingLabel="Deleting…"
          isPending={change.isPending}
          error={error ?? ''}
          onConfirm={() => run(() => policiesApi.remove(deleting.id))}
          onCancel={() => {
            setDeleting(null)
            setError(null)
          }}
        />
      )}
    </section>
  )
}

function PolicyEditor({
  policy,
  catalogue,
  readOnly = false,
  isPending,
  error,
  onCancel,
  onSave,
}: Readonly<{
  policy: Policy | null
  catalogue: CatalogueResource[]
  readOnly?: boolean
  isPending: boolean
  error: string | null
  onCancel: () => void
  onSave: (data: { name?: string; description?: string | null; permissions: PermissionMatrix }) => void
}>) {
  const [name, setName] = useState(policy?.name ?? '')
  const [description, setDescription] = useState(policy?.description ?? '')
  const [matrix, setMatrix] = useState<PermissionMatrix>(policy?.permissions ?? {})

  const toggle = (resource: string, action: string) =>
    setMatrix((current) => {
      const actions = new Set(current[resource] ?? [])
      if (actions.has(action)) actions.delete(action)
      else actions.add(action)
      return { ...current, [resource]: [...actions] }
    })

  return (
    <AccessModal title={readOnly ? 'View policy' : policy ? 'Edit policy' : 'New policy'} onClose={onCancel}>
      {error && <div role="alert" className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">{error}</div>}
      <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!readOnly) onSave({ name: name.trim(), description: description.trim() || null, permissions: matrix }) }}>
        <label className="block text-sm font-medium text-foreground">Name<input value={name} onChange={(event) => setName(event.target.value)} aria-label="Policy name" required readOnly={readOnly} className={`${inputClass} w-full`} /></label>
        <label className="block text-sm font-medium text-foreground">Description<input value={description} onChange={(event) => setDescription(event.target.value)} aria-label="Policy description" readOnly={readOnly} className={`${inputClass} w-full`} /></label>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="text-muted-foreground"><th className="text-left font-medium pr-3">Resource</th><th className="font-medium px-2">Read</th><th className="font-medium px-2">Write</th></tr></thead>
          <tbody>{catalogue.map((row) => <tr key={row.resource} className="border-t border-border">
            <th className="text-left font-normal py-2 pr-3 whitespace-nowrap">{RESOURCE_LABELS[row.resource] ?? row.resource}</th>
            {(['Read', 'Write'] as const).map((label) => {
              const action = row.actions.find((value) => ACTION_LABELS[value] === label)
              return <td key={label} className="text-center px-2"><input type="checkbox" aria-label={`${label} ${RESOURCE_LABELS[row.resource] ?? row.resource}`} checked={!!action && (matrix[row.resource]?.includes(action) ?? false)} disabled={readOnly || !action} onChange={() => { if (action) toggle(row.resource, action) }} /></td>
            })}
          </tr>)}</tbody>
        </table></div>
        {!readOnly && <button type="submit" disabled={!name.trim() || isPending} className="w-full py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50">{isPending ? 'Saving…' : 'Save policy'}</button>}
      </form>
    </AccessModal>
  )
}
