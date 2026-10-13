import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { accessApi, extractApiErrorMessage, groupsApi, type AccessUser, type Group, type GroupMember } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { can } from '../lib/access'
import ProfilePicture from './ProfilePicture'

/** The people assigned to each Bud policy group. */
export default function AccessUsers() {
  const { user, refreshUser } = useAuth()
  const users = useQuery({ queryKey: ['access-users'], queryFn: accessApi.users })
  const groups = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  if (users.isPending || groups.isPending) return <p className="text-sm text-muted-foreground">Loading assignments...</p>
  if (users.isError || groups.isError) return <p role="alert" className="text-sm text-destructive">Could not load assignments. <button type="button" onClick={() => { void users.refetch(); void groups.refetch() }} className="underline">Retry</button></p>
  return <section>
    <h2 className="text-xl font-semibold text-foreground mb-4">Assignments</h2>
    <div className="grid gap-4 sm:grid-cols-2">
      {groups.data.map((group) => <GroupRoster key={group.id} group={group} people={users.data} onChange={refreshUser} canAssign={(group.system_key !== 'app_administration' || user?.role === 'admin') && group.permissions.every((permission) => can(user, permission))} />)}
    </div>
  </section>
}

/** A member's picture with its group-removal action on hover. */
function MemberIdentity({ member, group, disabled, canRemove, onRemove }: { member: GroupMember; group: Group; disabled: boolean; canRemove: boolean; onRemove: () => void }) {
  const label = `Remove ${member.full_name} from ${group.name}`
  return <span className="inline-flex min-w-0 items-center gap-2 align-middle">
    <span className="group/image relative inline-flex shrink-0">
      <ProfilePicture user={{ ...member, id: member.user_id }} className="w-6 h-6" />
      {canRemove && <button type="button" aria-label={label} title={label} disabled={disabled} onClick={onRemove} className="absolute -right-1 -top-1 z-10 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-card text-red-500 opacity-0 transition-opacity group-hover/image:opacity-100 group-focus-within/image:opacity-100 [@media(hover:none)]:opacity-100 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-wait disabled:opacity-50"><X className="h-3 w-3" aria-hidden="true" /></button>}
    </span><span className="truncate">{member.full_name}</span>
  </span>
}

/** A policy group's roster and unified checked people selection. */
function GroupRoster({ group, people, canAssign, onChange }: { group: Group; people: AccessUser[]; canAssign: boolean; onChange: () => Promise<void> }) {
  const queryClient = useQueryClient()
  const [choosing, setChoosing] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const assignedIds = group.members.map((member) => member.user_id)
  const candidates = new Map(people.map((person) => [person.id, person]))
  for (const member of group.members) if (!candidates.has(member.user_id)) candidates.set(member.user_id, { ...member, id: member.user_id, is_active: false, groups: [], permissions: [] })
  const eligible = [...candidates.values()].filter((person) => assignedIds.includes(person.id) || person.is_active && (!group.permissions.includes('stations.manage') || person.role === 'admin' || person.role === 'developer')).sort((a, b) => a.full_name.localeCompare(b.full_name))
  const filtered = eligible.filter((person) => `${person.full_name} ${person.email}`.toLowerCase().includes(search.toLowerCase()))
  const addedIds = selected.filter((id) => !assignedIds.includes(id))
  const removedIds = assignedIds.filter((id) => !selected.includes(id))
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['access-users'] })
    void queryClient.invalidateQueries({ queryKey: ['groups'] })
    void onChange()
  }
  const save = useMutation({
    mutationFn: async () => {
      for (const id of addedIds) await groupsApi.addMember(group.id, id)
      for (const id of removedIds) await groupsApi.removeMember(group.id, id)
    },
    onSuccess: () => { refresh(); setChoosing(false); setSelected([]); setSearch(''); setError('') },
    onError: (failure) => { refresh(); setError(extractApiErrorMessage(failure, 'Could not save selection')) },
  })
  const remove = useMutation({
    mutationFn: (id: number) => groupsApi.removeMember(group.id, id),
    onSuccess: () => { refresh(); setError('') },
    onError: (failure) => setError(extractApiErrorMessage(failure, 'Could not remove assignment')),
  })
  const busy = save.isPending || remove.isPending
  return <section aria-label={group.name} className="min-w-0 rounded-lg border border-border bg-card p-4">
    <div className="flex items-center justify-between gap-2"><h3 className="font-semibold text-foreground">{group.name}</h3>
      {canAssign && <button type="button" disabled={busy} onClick={() => { setSelected(choosing ? [] : assignedIds); setSearch(''); setChoosing((value) => !value); setError('') }} className="rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-accent disabled:opacity-50">{choosing ? 'Cancel selection' : 'Choose people'}</button>}
    </div>
    {!choosing && (group.members.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">No people assigned.</p> : <ul className="mt-3 space-y-2">{group.members.map((member) => <li key={member.user_id} className="min-w-0"><p className="text-sm text-foreground"><MemberIdentity member={member} group={group} canRemove={canAssign} disabled={busy} onRemove={() => remove.mutate(member.user_id)} /></p><p className="truncate text-xs text-muted-foreground">{member.email}</p></li>)}</ul>)}
    {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
    {choosing && <fieldset disabled={busy} className="mt-4 min-w-0 space-y-3">
      <legend className="text-sm font-medium">Select people</legend>
      <input aria-label={`Search people for ${group.name}`} placeholder="Search people..." value={search} onChange={(event) => setSearch(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
      <div className="max-h-56 space-y-2 overflow-y-auto">{filtered.map((person) => <label key={person.id} className="flex items-start gap-2 text-sm"><input type="checkbox" aria-label={`Select ${person.full_name}`} checked={selected.includes(person.id)} onChange={() => setSelected((values) => values.includes(person.id) ? values.filter((id) => id !== person.id) : [...values, person.id])} className="mt-1" /><span className="min-w-0"><span className="inline-flex min-w-0 items-center gap-2"><ProfilePicture user={person} className="w-6 h-6" /><span className="truncate">{person.full_name}</span></span><span className="block truncate text-xs text-muted-foreground">{person.email}</span></span></label>)}{filtered.length === 0 && <p className="text-sm text-muted-foreground">{search ? 'No matching people.' : 'No people available.'}</p>}</div>
      <button type="button" disabled={busy || addedIds.length + removedIds.length === 0} onClick={() => save.mutate()} className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">{save.isPending ? 'Saving...' : 'Save selection'}</button>
    </fieldset>}
  </section>
}
