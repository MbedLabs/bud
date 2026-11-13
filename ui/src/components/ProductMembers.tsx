import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import {
  accessApi, extractApiErrorMessage, groupsApi, productsApi,
  type AccessUser, type Group, type ProductMember,
} from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { can } from '../lib/access'
import { givesProductAccess } from '../lib/accessScope'
import ProfilePicture from './ProfilePicture'

/** The people holding each group on one product, as Bloom's project members. */
export default function ProductMembers({ productId }: Readonly<{ productId: number }>) {
  const { user } = useAuth()
  const users = useQuery({ queryKey: ['access-users'], queryFn: accessApi.users })
  const groups = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const members = useQuery({ queryKey: ['product-members', productId], queryFn: () => productsApi.members(productId) })
  const queries = [users, groups, members]
  if (queries.some((query) => query.isPending)) return <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">Loading product members...</div>
  if (queries.some((query) => query.isError)) return <div role="alert" className="rounded-lg border border-border bg-card p-6 text-sm text-destructive">Could not load product members. <button type="button" onClick={() => queries.forEach((query) => void query.refetch())} className="underline">Retry</button></div>
  const rosterGroups = (groups.data ?? []).filter(givesProductAccess)
  return <section className="rounded-lg border border-border bg-card p-6 shadow-elegant">
    <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">Product members</h3>
    <p className="mt-1 mb-5 text-sm text-muted-foreground">Choose the people who receive each group of policies in this product. These groups are available in every product; people are assigned separately in each one.</p>
    <div className="grid gap-4 sm:grid-cols-2">
      {rosterGroups.map((group) => <ProductGroupRoster key={`${productId}-${group.id}`} productId={productId} group={group} members={members.data ?? []} people={users.data ?? []} canAssign={(group.system_key !== 'app_administration' || user?.role === 'admin') && group.permissions.every((permission) => can(user, permission))} />)}
    </div>
  </section>
}

/** One group's people on the product, with the selection that sets them. */
function ProductGroupRoster({ productId, group, members, people, canAssign }: Readonly<{
  productId: number; group: Group; members: ProductMember[]; people: AccessUser[]; canAssign: boolean
}>) {
  const queryClient = useQueryClient()
  const [choosing, setChoosing] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const assigned = members.filter((member) => member.group_id === group.id)
  const assignedIds = assigned.map((member) => member.user_id)
  const eligible = people
    .filter((person) => assignedIds.includes(person.id) || (person.is_active && person.role !== 'admin' && (!group.permissions.includes('stations.manage') || person.role === 'developer')))
    .sort((a, b) => a.full_name.localeCompare(b.full_name))
  const filtered = eligible.filter((person) => `${person.full_name} ${person.email}`.toLowerCase().includes(search.toLowerCase()))
  const changed = selected.length !== assignedIds.length || selected.some((id) => !assignedIds.includes(id))
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['product-members', productId] })
    void queryClient.invalidateQueries({ queryKey: ['access-users'] })
  }
  const save = useMutation({
    mutationFn: (userIds: number[]) => productsApi.setGroupMembers(productId, group.id, userIds),
    onSuccess: () => { refresh(); setChoosing(false); setSelected([]); setSearch(''); setError('') },
    onError: (failure) => { refresh(); setError(extractApiErrorMessage(failure, 'Could not save selection')) },
  })
  const busy = save.isPending
  return <section aria-label={group.name} className="min-w-0 rounded-lg border border-border bg-background/40 p-4">
    <div className="flex items-center justify-between gap-2"><h4 className="font-semibold text-foreground">{group.name}</h4>
      {canAssign && <button type="button" disabled={busy} onClick={() => { setSelected(choosing ? [] : assignedIds); setSearch(''); setChoosing((value) => !value); setError('') }} className="rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-accent disabled:opacity-50">{choosing ? 'Cancel selection' : 'Select members'}</button>}
    </div>
    {!choosing && (assigned.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">No people assigned.</p> : <ul className="mt-3 space-y-2">
      {assigned.map((member) => <li key={member.user_id} className="flex min-w-0 items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="inline-flex max-w-full items-center gap-2 text-sm text-foreground"><ProfilePicture user={{ ...member, id: member.user_id }} className="w-6 h-6" /><span className="truncate">{member.full_name}</span></p>
          <p className="truncate text-xs text-muted-foreground">{member.email}</p>
        </div>
        {canAssign && <button type="button" aria-label={`Remove ${member.full_name} from ${group.name}`} title={`Remove ${member.full_name} from ${group.name}`} disabled={busy} onClick={() => save.mutate(assignedIds.filter((id) => id !== member.user_id))} className="rounded-md p-1 text-muted-foreground hover:bg-red-500/10 hover:text-red-500 disabled:opacity-50"><X className="h-3.5 w-3.5" /></button>}
      </li>)}
    </ul>)}
    {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
    {choosing && <fieldset disabled={busy} className="mt-4 min-w-0 space-y-3">
      <legend className="text-sm font-medium">Select members</legend>
      <input aria-label={`Search people for ${group.name}`} placeholder="Search people..." value={search} onChange={(event) => setSearch(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
      <p className="text-xs text-muted-foreground">People can receive several groups in this product. Assignments in other products stay separate.</p>
      <div className="max-h-56 space-y-2 overflow-y-auto">
        {filtered.map((person) => <label key={person.id} className="flex items-start gap-2 text-sm"><input type="checkbox" aria-label={`Select ${person.full_name}`} checked={selected.includes(person.id)} onChange={() => setSelected((values) => values.includes(person.id) ? values.filter((id) => id !== person.id) : [...values, person.id])} className="mt-1" /><span className="min-w-0"><span className="inline-flex min-w-0 items-center gap-2"><ProfilePicture user={person} className="w-6 h-6" /><span className="truncate">{person.full_name}</span></span><span className="block truncate text-xs text-muted-foreground">{person.email}</span></span></label>)}
        {filtered.length === 0 && <p className="text-sm text-muted-foreground">{search ? 'No matching people.' : 'No people available.'}</p>}
      </div>
      <button type="button" disabled={busy || !changed} onClick={() => save.mutate(selected)} className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">{busy ? 'Saving...' : 'Save selection'}</button>
    </fieldset>}
  </section>
}
