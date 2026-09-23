import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2, Users as UsersIcon, X } from 'lucide-react'
import {
  extractApiErrorMessage,
  groupsApi,
  productsApi,
  usersApi,
  type Group,
  type GroupRole,
} from '../api/client'

const inputClass =
  'px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-ring transition-colors'

/**
 * Admin list of user groups. An admin group makes its members administrators; a
 * viewer group limits what its members see to the products it is granted. A user in
 * no group keeps their own role and sees every product.
 */
export default function UserGroups() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [role, setRole] = useState<GroupRole>('viewer')
  const [error, setError] = useState<string | null>(null)

  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: usersApi.list })
  const { data: products } = useQuery({ queryKey: ['products'], queryFn: productsApi.list })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['groups'] })
  const onError = (err: unknown) => setError(extractApiErrorMessage(err, 'The change was not saved.'))
  const change = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError,
  })

  const create = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    change.mutate(async () => {
      await groupsApi.create({ name: name.trim(), role })
      setName('')
    })
  }

  return (
    <section className="mt-10">
      <div className="flex items-center gap-2 mb-1">
        <UsersIcon className="h-4 w-4 text-primary" />
        <h3 className="text-base font-semibold text-foreground">Groups</h3>
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        An admin group makes its members administrators. A viewer group shows its members only the
        products it is granted. Users in no group keep their own role and see every product.
      </p>

      <form onSubmit={create} className="flex flex-wrap items-end gap-2 mb-4">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name"
          aria-label="Group name"
          className={inputClass}
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as GroupRole)}
          aria-label="Group role"
          className={inputClass}
        >
          <option value="viewer">Viewer</option>
          <option value="admin">Admin</option>
        </select>
        <button
          type="submit"
          disabled={!name.trim() || change.isPending}
          className="px-4 py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          New group
        </button>
      </form>
      {error && <p className="text-sm text-destructive mb-3">{error}</p>}

      {groups && groups.length === 0 && (
        <p className="text-sm text-muted-foreground">No groups yet.</p>
      )}
      <div className="space-y-3">
        {groups?.map((group) => (
          <GroupCard
            key={group.id}
            group={group}
            users={users ?? []}
            products={products ?? []}
            run={(action) => change.mutate(action)}
          />
        ))}
      </div>
    </section>
  )
}

function GroupCard({
  group,
  users,
  products,
  run,
}: {
  group: Group
  users: { id: number; full_name: string; email: string }[]
  products: { id: number; name: string }[]
  run: (action: () => Promise<unknown>) => void
}) {
  const memberIds = new Set(group.members.map((m) => m.user_id))
  const grantedIds = new Set(group.grants.map((g) => g.product_id))
  const candidates = users.filter((u) => !memberIds.has(u.id))
  const grantable = products.filter((p) => !grantedIds.has(p.id))

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{group.name}</p>
          {group.description && <p className="text-xs text-muted-foreground">{group.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={group.role}
            onChange={(e) => {
              const next = e.target.value as GroupRole
              run(() => groupsApi.update(group.id, { role: next }))
            }}
            aria-label={`Role of ${group.name}`}
            className={inputClass}
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <button
            onClick={() => {
              if (window.confirm(`Delete the group ${group.name}? Its members keep only their own role.`)) {
                run(() => groupsApi.remove(group.id))
              }
            }}
            aria-label={`Delete ${group.name}`}
            className="p-2 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">Members</p>
          <ul className="space-y-1 mb-2">
            {group.members.length === 0 && <li className="text-sm text-muted-foreground">No members.</li>}
            {group.members.map((m) => (
              <li key={m.user_id} className="flex items-center justify-between text-sm text-foreground">
                <span>
                  {m.full_name} <span className="text-muted-foreground">{m.email}</span>
                </span>
                <button
                  onClick={() => run(() => groupsApi.removeMember(group.id, m.user_id))}
                  aria-label={`Remove ${m.full_name} from ${group.name}`}
                  className="p-1 text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
          <select
            value=""
            onChange={(e) => {
              const userId = Number(e.target.value)
              if (userId) run(() => groupsApi.addMember(group.id, userId))
            }}
            aria-label={`Add a member to ${group.name}`}
            className={`${inputClass} w-full`}
          >
            <option value="">Add a user...</option>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </select>
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">Products</p>
          <ul className="space-y-1 mb-2">
            {group.grants.length === 0 && (
              <li className="text-sm text-muted-foreground">
                {group.role === 'admin' ? 'Admins see every product.' : 'No products: members see none.'}
              </li>
            )}
            {group.grants.map((g) => (
              <li key={g.id} className="flex items-center justify-between text-sm text-foreground">
                <span>{g.product_id === null ? 'All products' : g.product_name}</span>
                <button
                  onClick={() => run(() => groupsApi.removeGrant(group.id, g.id))}
                  aria-label={`Revoke ${g.product_id === null ? 'all products' : g.product_name} from ${group.name}`}
                  className="p-1 text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
          <select
            value=""
            onChange={(e) => {
              const value = e.target.value
              if (!value) return
              run(() => groupsApi.addGrant(group.id, value === 'all' ? null : Number(value)))
            }}
            aria-label={`Grant a product to ${group.name}`}
            className={`${inputClass} w-full`}
          >
            <option value="">Grant a product...</option>
            {!grantedIds.has(null) && <option value="all">All products</option>}
            {grantable.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}
