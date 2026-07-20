import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Eye, Shield, Trash2, UserPlus, X } from 'lucide-react'
import { extractApiErrorMessage, InviteUserResponse, usersApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const ROLE_CONFIG = {
  admin: { label: 'Admin', color: 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400', icon: Shield },
  viewer: { label: 'Viewer', color: 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400', icon: Eye },
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [pendingDeleteUserId, setPendingDeleteUserId] = useState<number | null>(null)

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })

  const inviteMutation = useMutation({
    mutationFn: usersApi.invite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof usersApi.update>[1] }) =>
      usersApi.update(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: usersApi.delete,
    onMutate: async (id: number) => {
      setDeleteError(null)
      setPendingDeleteUserId(id)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
    onError: (error: unknown) => {
      setDeleteError(extractApiErrorMessage(error, 'Failed to delete user'))
    },
    onSettled: () => {
      setPendingDeleteUserId(null)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Invite and manage Bud users</p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
        >
          <UserPlus className="h-4 w-4" />
          Invite User
        </button>
      </div>

      {deleteError && (
        <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          {deleteError}
        </div>
      )}

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">User</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Role</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Created</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => {
              const roleConf = ROLE_CONFIG[u.role as keyof typeof ROLE_CONFIG] || ROLE_CONFIG.viewer
              const isSelf = u.id === currentUser?.id
              return (
                <tr key={u.id} className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-bud-orange flex items-center justify-center text-white text-xs font-bold">
                        {u.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">{u.full_name}</p>
                        <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${roleConf.color}`}>
                      <roleConf.icon className="h-3 w-3" />
                      {roleConf.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                        u.is_active
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                          : 'bg-gray-100 text-gray-500 dark:bg-gray-900/20 dark:text-gray-400'
                      }`}
                    >
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {!isSelf && currentUser?.role === 'admin' && (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => updateMutation.mutate({ id: u.id, data: { is_active: !u.is_active } })}
                          className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                          title={u.is_active ? 'Deactivate' : 'Activate'}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (pendingDeleteUserId !== u.id && confirm('Delete this user?')) {
                              deleteMutation.mutate(u.id)
                            }
                          }}
                          disabled={pendingDeleteUserId === u.id}
                          className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                          title="Delete user"
                        >
                          {pendingDeleteUserId === u.id ? (
                            <span className="inline-block h-3.5 w-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        </div>
      </div>

      {showInviteModal && (
        <InviteUserModal
          onClose={() => {
            setShowInviteModal(false)
            inviteMutation.reset()
          }}
          onSubmit={(data) => inviteMutation.mutateAsync(data)}
          isLoading={inviteMutation.isPending}
          error={inviteMutation.error ? extractApiErrorMessage(inviteMutation.error, 'Failed to send invitation') : null}
        />
      )}
    </div>
  )
}

function InviteUserModal({
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  onClose: () => void
  onSubmit: (data: { email: string; full_name: string; role?: 'admin' | 'viewer' }) => Promise<InviteUserResponse>
  isLoading: boolean
  error: string | null
}) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<'admin' | 'viewer'>('viewer')
  const [inviteLink, setInviteLink] = useState<string | null>(null)
  const [invitedEmail, setInvitedEmail] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setCopied(false)
    try {
      const response = await onSubmit({ email, full_name: fullName, role })
      setInviteLink(response.invite_link ?? null)
      setInvitedEmail(response.user.email)
    } catch {
      // Error is rendered by parent mutation state.
    }
  }

  const handleCopyLink = async () => {
    if (!inviteLink) {
      return
    }

    try {
      await navigator.clipboard.writeText(inviteLink)
      setCopied(true)
    } catch {
      window.prompt('Copy invite link:', inviteLink)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-xl shadow-elegant p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Invite User</h2>
          <button onClick={onClose} title="Close invite modal" className="p-1 rounded text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}
        {inviteLink && (
          <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-sm">
            <p className="text-green-700 dark:text-green-400 font-medium">Invitation sent to {invitedEmail}</p>
            <div className="mt-2 flex gap-2">
              <input
                value={inviteLink}
                readOnly
                title="Generated invitation link"
                aria-label="Generated invitation link"
                placeholder="Generated invitation link"
                className="flex-1 min-w-0 px-2 py-1 bg-background border border-input rounded text-xs text-foreground"
              />
              <button
                type="button"
                onClick={handleCopyLink}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-primary text-white text-xs font-medium hover:bg-primary/90"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy Link'}
              </button>
            </div>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Full Name</label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              title="Full name"
              placeholder="Jane Doe"
              className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              title="Email address"
              placeholder="name@company.com"
              className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'admin' | 'viewer')}
              title="Role"
              className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground"
            >
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 bg-gradient-button text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
          >
            {isLoading ? 'Sending Invite...' : 'Send Invite'}
          </button>
        </form>
      </div>
    </div>
  )
}
