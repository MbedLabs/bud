import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { accessApi, type AccessUser, type UserRole } from '../api/client'
import { ACTION_LABELS, RESOURCE_LABELS } from '../lib/access'
import ProfilePicture from './ProfilePicture'

const ROLE_LABELS: Record<UserRole, string> = { admin: 'Admin', developer: 'Developer', viewer: 'Viewer' }
const ACTION_ORDER = ['Read', 'Write']

/** A person's combined permissions as one Read or Write line per resource. */
function accessLines(person: AccessUser): string[] {
  if (person.role === 'admin') return ['Every permission']
  const rights = new Map<string, Set<string>>()
  for (const permission of person.permissions) {
    const [resource, action] = permission.split('.')
    rights.set(resource, (rights.get(resource) ?? new Set<string>()).add(ACTION_LABELS[action] ?? action))
  }
  const resources = [...Object.keys(RESOURCE_LABELS), ...[...rights.keys()].filter((resource) => !(resource in RESOURCE_LABELS))]
  return resources.filter((resource) => rights.has(resource)).map((resource) => {
    const held = rights.get(resource) ?? new Set<string>()
    const labels = [...ACTION_ORDER.filter((label) => held.has(label)), ...[...held].filter((label) => !ACTION_ORDER.includes(label))]
    return `${RESOURCE_LABELS[resource] ?? resource}: ${labels.join(', ')}`
  })
}

/** One person's base role, every group they hold and their combined access. */
function PersonCard({ person }: Readonly<{ person: AccessUser }>) {
  const lines = accessLines(person)
  return <section aria-label={person.full_name} className="min-w-0 rounded-lg border border-border bg-card p-4">
    <div className="flex items-center gap-3">
      <ProfilePicture user={person} className="w-8 h-8" />
      <div className="min-w-0 flex-1"><h3 className="truncate font-semibold text-foreground">{person.full_name}</h3><p className="truncate text-xs text-muted-foreground">{person.email}</p></div>
      {!person.is_active && <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">Inactive</span>}
    </div>
    <dl className="mt-3 space-y-3 text-sm">
      <div><dt className="text-xs font-medium text-muted-foreground">Base role</dt><dd className="text-foreground">{ROLE_LABELS[person.role] ?? person.role}</dd></div>
      <div><dt className="text-xs font-medium text-muted-foreground">Groups</dt><dd>{person.groups.length === 0 ? <span className="text-muted-foreground">No groups</span> : <ul className="flex flex-wrap gap-1.5">{person.groups.map((group) => <li key={group.id} className="rounded-full border border-border px-2 py-0.5 text-xs text-foreground">{group.name}</li>)}</ul>}</dd></div>
      <div><dt className="text-xs font-medium text-muted-foreground">Combined access</dt><dd>{lines.length === 0 ? <span className="text-muted-foreground">No permissions</span> : <ul className="space-y-0.5 text-foreground">{lines.map((line) => <li key={line}>{line}</li>)}</ul>}</dd></div>
    </dl>
  </section>
}

/** Every person with their base role, groups and combined permissions, for access managers. */
export default function AccessPeople() {
  const users = useQuery({ queryKey: ['access-users'], queryFn: accessApi.users })
  const [search, setSearch] = useState('')
  if (users.isPending) return <p className="text-sm text-muted-foreground">Loading people...</p>
  if (users.isError) return <p role="alert" className="text-sm text-destructive">Could not load people. <button type="button" onClick={() => { void users.refetch() }} className="underline">Retry</button></p>
  const filtered = users.data.filter((person) => `${person.full_name} ${person.email}`.toLowerCase().includes(search.toLowerCase()))
  return <section>
    <h2 className="mb-4 text-xl font-semibold text-foreground">People</h2>
    <input aria-label="Search people" placeholder="Search people..." value={search} onChange={(event) => setSearch(event.target.value)} className="mb-4 w-full rounded-md border border-input bg-background px-3 py-2 text-sm sm:max-w-sm" />
    {filtered.length === 0 ? <p className="text-sm text-muted-foreground">No matching people.</p> : <div className="grid gap-4 sm:grid-cols-2">{filtered.map((person) => <PersonCard key={person.id} person={person} />)}</div>}
  </section>
}
